import logging
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, UnexpectedAlertPresentException
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
        sleep(self.delay)

        # Step 1.5: Vérifier et forcer la langue française
        self._ensure_french_language(driver)

        # Step 2: Click on "Connexion"
        logger.info("Clicking Connexion link")
        connexion_link = driver.find_element(By.LINK_TEXT, "Connexion")
        driver.execute_script("arguments[0].click();", connexion_link)
        sleep(self.delay)

        # Step 2.5: Choose Messervices (logo)
        logger.info("Choosing Messervices login")
        mse_connect_button = driver.find_element(By.CLASS_NAME, "logo-mse-connect-fr")
        driver.execute_script("arguments[0].click();", mse_connect_button)
        sleep(self.delay)

        # Step 3: Input credentials and submit
        logger.info("Inputting credentials")
        username_input = driver.find_element(By.ID, "login_login")
        password_input = driver.find_element(By.ID, "login_password")

        username_input.send_keys(self.email)
        password_input.send_keys(self.password)

        logger.info("Submitting the form")
        password_input.send_keys(Keys.RETURN)

        sleep(self.delay)

        # Step 4: Validate the rules
        self._validate_rules(driver)

        # Step 5: Force update the auth status
        driver.get("https://trouverunlogement.lescrous.fr/mse/discovery/connect")

        # Done
        logger.info("Successfully authenticated to the CROUS website")

    def _ensure_french_language(self, driver: WebDriver) -> None:
        """Vérifie que la page est en français et force le changement si nécessaire."""
        wait = WebDriverWait(driver, 10)
        
        try:
            logger.info("Vérification de la langue de la page...")
            
            # Chercher le dropdown de langue
            language_dropdown = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.dropdown[title*='Choix de la langue'], li.dropdown[title*='Language choice']"))
            )
            
            # Vérifier l'image du drapeau actuel
            current_flag = driver.find_element(By.CSS_SELECTOR, "li.dropdown img.language-flag")
            flag_src = current_flag.get_attribute("src")
            
            if "fr.png" in flag_src:
                logger.info("✅ La page est déjà en français")
                return
            
            logger.info("🌐 La page n'est pas en français, changement vers le français...")
            
            # Cliquer sur le dropdown pour l'ouvrir
            dropdown_toggle = language_dropdown.find_element(By.CSS_SELECTOR, "a.dropdown-toggle")
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            sleep(1)
            
            # Chercher et cliquer sur le lien français
            french_link = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/langue/fr'], a[title*='Française'], a[aria-label*='Française']"))
            )
            
            logger.info("Changement vers la langue française...")
            driver.execute_script("arguments[0].click();", french_link)
            sleep(3)  # Attendre le rechargement de la page
            
            logger.info("✅ Langue changée vers le français")
            
        except TimeoutException:
            logger.warning("⚠️ Dropdown de langue non trouvé, suppose que la page est déjà en français")
        except NoSuchElementException as e:
            logger.warning(f"⚠️ Élément de langue non trouvé: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur lors du changement de langue: {e}")
            # Continuer quand même, ne pas faire échouer l'authentification

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
        
        # Gérer les éventuelles alertes de vérification
        self._handle_verification_alert(driver)

        # Étapes de navigation post-login avec attentes améliorées
        try:
            logger.info("Recherche de l'image 'En résidence'...")
            # Gérer les alertes avant de chercher l'élément
            self._handle_verification_alert(driver)
            
            residence_img = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "img[alt*='En résidence']"))
            )
            driver.execute_script("arguments[0].click();", residence_img)
            sleep(self.delay)
            logger.info("Image 'En résidence' trouvée et cliquée")
        except UnexpectedAlertPresentException:
            logger.warning("Alerte de vérification détectée, gestion de l'alerte...")
            self._handle_verification_alert(driver)
            # Réessayer après avoir géré l'alerte
            try:
                residence_img = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "img[alt*='En résidence']"))
                )
                driver.execute_script("arguments[0].click();", residence_img)
                sleep(self.delay)
                logger.info("Image 'En résidence' trouvée et cliquée (après gestion alerte)")
            except TimeoutException:
                logger.warning("Image 'En résidence' non trouvée après gestion de l'alerte")
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
                
                # Gérer les alertes éventuelles dans la nouvelle fenêtre
                self._handle_verification_alert(driver)
        except Exception as e:
            logger.warning(f"Erreur lors du changement de fenêtre: {e}")

    def _handle_verification_alert(self, driver: WebDriver) -> None:
        """Gère les alertes de vérification qui peuvent apparaître."""
        try:
            # Vérifier s'il y a une alerte présente
            alert = driver.switch_to.alert
            alert_text = alert.text
            
            if "Vérification en cours" in alert_text or "veuillez patienter" in alert_text.lower():
                logger.info(f"🔄 Alerte de vérification détectée: '{alert_text}'")
                
                # Accepter l'alerte pour la fermer
                alert.accept()
                logger.info("✅ Alerte de vérification acceptée")
                
                # Attendre plus longtemps pour que la vérification se termine
                sleep(15)
                logger.info("⏳ Attente supplémentaire de 15s pour la vérification...")
                
                # Vérifier s'il y a d'autres alertes en cascade
                self._handle_verification_alert(driver)
                
            else:
                # Autre type d'alerte, l'accepter quand même
                logger.warning(f"⚠️ Alerte inattendue détectée: '{alert_text}'")
                alert.accept()
                sleep(3)
                
        except Exception:
            # Pas d'alerte présente, c'est normal
            pass