import logging
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from time import sleep

from src.settings import Settings

settings = Settings()

logger = logging.getLogger(__name__)


class Authenticator:
    """Class that handles the authentication to the CROUS website and returns a WebDriver object that is authenticated."""

    def __init__(self, email: str, password: str, delay: int = 2):
        self.email = email
        self.password = password
        self.delay = delay

    def authenticate_driver(self, driver: WebDriver) -> None:
        """Authenticates the given WebDriver object to the CROUS website."""

        logger.info("Authenticating to the CROUS website...")

        sleep(self.delay)

        # Step 1: Go to the login page
        logger.info(f"Going to the login page: {settings.MSE_LOGIN_URL}")
        driver.get(settings.MSE_LOGIN_URL)
        sleep(self.delay * 2)  # Augmenter le délai initial

        # Debug: Afficher le titre de la page et une partie du contenu
        logger.info(f"Page title: {driver.title}")
        logger.info(f"Current URL: {driver.current_url}")
        
        # Vérifier si on est déjà redirigé
        if "trouverunlogement" in driver.current_url:
            logger.info("Déjà connecté ou redirigé vers le site de logement")
            return

        # Step 2: Try multiple selectors for "Connexion"
        logger.info("Looking for Connexion link")
        wait = WebDriverWait(driver, 15)
        
        connexion_selectors = [
            (By.LINK_TEXT, "Connexion"),
            (By.PARTIAL_LINK_TEXT, "Connexion"),
            (By.XPATH, "//a[contains(text(), 'Connexion')]"),
            (By.XPATH, "//a[contains(@href, 'login') or contains(@href, 'connexion')]"),
            (By.CSS_SELECTOR, "a[href*='login']"),
            (By.CSS_SELECTOR, ".btn-connexion"),
            (By.ID, "connexion"),
            (By.CLASS_NAME, "connexion")
        ]
        
        connexion_element = None
        for by, selector in connexion_selectors:
            try:
                logger.info(f"Trying selector: {by} = '{selector}'")
                connexion_element = wait.until(EC.element_to_be_clickable((by, selector)))
                logger.info(f"Found connexion element with: {by} = '{selector}'")
                break
            except TimeoutException:
                logger.debug(f"Selector failed: {by} = '{selector}'")
                continue
        
        if not connexion_element:
            # Debug: Sauvegarder le HTML pour inspection
            html_content = driver.page_source
            logger.error("No connexion element found. Saving page source for debug...")
            with open("/tmp/debug_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.error("Page source saved to /tmp/debug_page.html")
            
            # Chercher tous les liens disponibles
            all_links = driver.find_elements(By.TAG_NAME, "a")
            logger.error("Available links on page:")
            for i, link in enumerate(all_links[:10]):  # Limiter à 10 liens
                try:
                    text = link.text.strip()
                    href = link.get_attribute("href")
                    if text or href:
                        logger.error(f"Link {i}: text='{text}', href='{href}'")
                except Exception as e:
                    logger.error(f"Error reading link {i}: {e}")
            
            raise Exception("Could not find connexion link with any selector")

        # Click on connexion
        logger.info("Clicking Connexion link")
        driver.execute_script("arguments[0].click();", connexion_element)
        sleep(self.delay)

        # Step 2.5: Choose Messervices (logo) with multiple selectors
        logger.info("Choosing Messervices login")
        
        mse_selectors = [
            (By.CLASS_NAME, "logo-mse-connect-fr"),
            (By.CSS_SELECTOR, ".logo-mse-connect-fr"),
            (By.XPATH, "//img[contains(@class, 'logo-mse')]"),
            (By.XPATH, "//button[contains(@class, 'mse') or contains(@title, 'messervices')]"),
            (By.CSS_SELECTOR, "img[src*='messervices']"),
        ]
        
        mse_element = None
        for by, selector in mse_selectors:
            try:
                logger.info(f"Trying MSE selector: {by} = '{selector}'")
                mse_element = wait.until(EC.element_to_be_clickable((by, selector)))
                logger.info(f"Found MSE element with: {by} = '{selector}'")
                break
            except TimeoutException:
                logger.debug(f"MSE selector failed: {by} = '{selector}'")
                continue
        
        if not mse_element:
            logger.error("Could not find MSE connect button")
            # Debug: chercher tous les éléments avec 'mse' dans le nom
            mse_elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'mse') or contains(text(), 'messervices')]")
            logger.error(f"Found {len(mse_elements)} elements containing 'mse':")
            for elem in mse_elements:
                try:
                    logger.error(f"MSE element: tag={elem.tag_name}, class={elem.get_attribute('class')}, text={elem.text}")
                except:
                    pass
            raise Exception("Could not find MSE connect button")
        
        driver.execute_script("arguments[0].click();", mse_element)
        sleep(self.delay)

        # Step 3: Input credentials and submit
        logger.info("Inputting credentials")
        
        # Attendre que les champs soient disponibles
        try:
            username_input = wait.until(EC.presence_of_element_located((By.ID, "login_login")))
            password_input = wait.until(EC.presence_of_element_located((By.ID, "login_password")))
        except TimeoutException:
            logger.error("Could not find login form fields")
            # Debug: chercher des champs de formulaire
            inputs = driver.find_elements(By.TAG_NAME, "input")
            logger.error(f"Found {len(inputs)} input fields:")
            for i, inp in enumerate(inputs):
                try:
                    input_type = inp.get_attribute("type")
                    input_name = inp.get_attribute("name")
                    input_id = inp.get_attribute("id")
                    logger.error(f"Input {i}: type={input_type}, name={input_name}, id={input_id}")
                except:
                    pass
            raise Exception("Could not find login form fields")

        username_input.clear()
        username_input.send_keys(self.email)
        password_input.clear()
        password_input.send_keys(self.password)

        logger.info("Submitting the form")
        password_input.send_keys(Keys.RETURN)

        sleep(self.delay)

        # Step 4: Validate the rules
        self._validate_rules(driver)

        # Step 5: Force update the auth status
        try:
            driver.get("https://trouverunlogement.lescrous.fr/mse/discovery/connect")
            sleep(3)
        except Exception as e:
            logger.warning(f"Could not navigate to discovery connect: {e}")

        # Done
        logger.info("Successfully authenticated to the CROUS website")

    def _validate_rules(self, driver: WebDriver) -> None:
        """Handle captcha and final login submit with improved waiting."""
        logger.info("Handling captcha and submitting login")

        wait = WebDriverWait(driver, 15)
        
        # Step 1: Gérer le captcha avec attente
        try:
            logger.info("Recherche de la checkbox captcha...")
            # Attendre que la checkbox soit présente et cliquable
            checkbox = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id*='login[altcha]_checkbox']"))
            )
            driver.execute_script("arguments[0].click();", checkbox)
            logger.info(f"Captcha checkbox trouvée et cliquée avec ID: {checkbox.get_attribute('id')}")
            
            # Attendre plus longtemps que le captcha se valide
            logger.info("Attente de la validation du captcha...")
            sleep(10)  # Délai plus long pour la validation du captcha
            
        except TimeoutException:
            logger.warning("Captcha checkbox non trouvée dans les 15 secondes")
            # Essayer l'ancienne méthode en fallback
            try:
                checkbox = driver.find_element(By.ID, "login[altcha]_checkbox")
                driver.execute_script("arguments[0].click();", checkbox)
                sleep(10)
                logger.info("Captcha checkbox trouvée avec ID fixe (fallback)")
            except NoSuchElementException:
                logger.warning("Aucune checkbox captcha trouvée, peut-être déjà validée")

        # Step 2: Soumettre le formulaire de login
        try:
            logger.info("Recherche du bouton de soumission...")
            submit_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), \"S'identifier\")]"))
            )
            driver.execute_script("arguments[0].click();", submit_button)
            logger.info("Formulaire de login soumis")
            
            # Attendre que la page se charge après soumission
            sleep(13)  # Délai plus long après soumission
            
        except TimeoutException:
            logger.warning("Bouton de soumission non trouvé (peut-être déjà connecté)")

        # Attendre que la redirection se fasse complètement
        logger.info("Attente de la redirection complète...")
        sleep(8)

        # Étapes de navigation post-login avec attentes améliorées
        try:
            logger.info("Recherche de l'image 'En résidence'...")
            residence_img = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "img[alt*='En résidence']"))
            )
            driver.execute_script("arguments[0].click();", residence_img)
            sleep(self.delay)
            logger.info("Image 'En résidence' trouvée et cliquée")
        except TimeoutException:
            logger.warning("Image 'En résidence' non trouvée dans les 15 secondes")
            # Continuer quand même, peut-être que nous sommes déjà sur la bonne page

        # Gérer les fenêtres/onglets
        self._switch_to_latest_window(driver)

        # Sélectionner l'année prochaine
        try:
            logger.info("Recherche du bouton radio année prochaine...")
            next_year_radio = wait.until(
                EC.element_to_be_clickable((By.ID, "PeriodField-nextSchoolYear"))
            )
            driver.execute_script("arguments[0].click();", next_year_radio)
            sleep(self.delay)
            logger.info("Année prochaine sélectionnée")
        except TimeoutException:
            logger.warning("Radio bouton année prochaine non trouvé dans les 15 secondes")

        # Remplir le champ ville
        try:
            logger.info("Recherche du champ ville...")
            city_input = wait.until(
                EC.element_to_be_clickable((By.ID, "PlaceAutocompletearia-autocomplete-1-input"))
            )
            city_input.clear()
            city_input.send_keys(settings.RESIDENCES_VILLE)
            sleep(8)  # Attendre que l'autocomplétion se charge
            logger.info(f"Ville '{settings.RESIDENCES_VILLE}' saisie")
        except TimeoutException:
            logger.warning("Champ ville non trouvé dans les 15 secondes")

        # Sélectionner la première option
        try:
            logger.info("Recherche de la première option ville...")
            first_option = wait.until(
                EC.element_to_be_clickable((By.ID, "PlaceAutocompletearia-autocomplete-1-option--0"))
            )
            driver.execute_script("arguments[0].click();", first_option)
            sleep(self.delay)
            logger.info("Première option ville sélectionnée")
        except TimeoutException:
            logger.warning("Première option ville non trouvée dans les 15 secondes")

        # Lancer la recherche
        try:
            logger.info("Recherche du bouton 'Lancer une recherche'...")
            search_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.fr-btn.svelte-w11odb"))
            )
            driver.execute_script("arguments[0].click();", search_button)
            sleep(self.delay)
            logger.info("Bouton 'Lancer une recherche' cliqué")
        except TimeoutException:
            logger.warning("Bouton 'Lancer une recherche' non trouvé dans les 15 secondes")

        # Gérer les fenêtres/onglets à nouveau
        self._switch_to_latest_window(driver)

        # Passer à la recherche de logements
        try:
            logger.info("Recherche du bouton 'Passer à la recherche de logements'...")
            submit_search = wait.until(
                EC.element_to_be_clickable((By.NAME, "searchSubmit"))
            )
            driver.execute_script("arguments[0].click();", submit_search)
            sleep(self.delay)
            logger.info("Bouton 'Passer à la recherche de logements' cliqué")
        except TimeoutException:
            logger.warning("Bouton 'Passer à la recherche de logements' non trouvé dans les 15 secondes")

        # Gérer les fenêtres/onglets une dernière fois
        self._switch_to_latest_window(driver)

        # Remplir le champ ville final
        try:
            logger.info("Recherche du champ ville final...")
            final_city_input = wait.until(
                EC.element_to_be_clickable((By.ID, "PlaceAutocompletearia-autocomplete-1-input"))
            )
            final_city_input.clear()
            final_city_input.send_keys(settings.RESIDENCES_VILLE)
            sleep(8)  # Attendre l'autocomplétion
            logger.info(f"Ville finale '{settings.RESIDENCES_VILLE}' saisie")
        except TimeoutException:
            logger.warning("Champ ville final non trouvé dans les 15 secondes")

        # Sélectionner la première option finale
        try:
            logger.info("Recherche de la première option ville finale...")
            final_first_option = wait.until(
                EC.element_to_be_clickable((By.ID, "PlaceAutocompletearia-autocomplete-1-option--0"))
            )
            driver.execute_script("arguments[0].click();", final_first_option)
            sleep(self.delay)
            logger.info("Première option ville finale sélectionnée")
        except TimeoutException:
            logger.warning("Première option ville finale non trouvée dans les 15 secondes")
        
        logger.info("Navigation post-login terminée, prêt pour le scraping")

    def _switch_to_latest_window(self, driver: WebDriver) -> None:
        """Switch to the latest opened window/tab."""
        try:
            windows = driver.window_handles
            if len(windows) > 1:
                driver.switch_to.window(windows[-1])
                logger.info(f"Basculé vers la fenêtre {len(windows)}")
                sleep(7)  # Attendre que la nouvelle fenêtre se charge
        except Exception as e:
            logger.warning(f"Erreur lors du changement de fenêtre: {e}")