import logging
from time import sleep
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import HttpUrl
from selenium.webdriver.chrome.webdriver import WebDriver

from src.models import Accommodation, SearchResults

logger = logging.getLogger(__name__)


class Parser:
    """Class to parse the CROUS website and get the available accommodations"""

    def __init__(self, authenticated_driver: WebDriver):
        self.driver = authenticated_driver

    def get_accommodation_ids(self, search_url: HttpUrl) -> List[int]:
        """NOUVEAU: Récupère rapidement juste les IDs des logements disponibles (parsing léger)"""
        self.driver.get(str(search_url))
        sleep(2)

        current_url = self.driver.current_url
        logger.info(f"Getting accommodation IDs from: {current_url}")

        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # Trouver la liste principale des logements
        main_list = soup.find("ul", class_="fr-grid-row fr-grid-row--gutters svelte-11sc5my")
        if not main_list:
            logger.warning("Liste principale des logements non trouvée")
            return []
            
        # Trouver tous les éléments <li> des logements
        accommodation_items = main_list.find_all("li", class_=lambda x: x and "fr-col-12" in x)
        logger.info(f"Trouvé {len(accommodation_items)} éléments de logement")
        
        accommodation_ids = []
        
        for item in accommodation_items:
            # Récupérer juste l'ID à partir de l'URL
            title_tag = item.find("h3", class_="fr-card__title")
            if title_tag:
                link_tag = title_tag.find("a")
                if link_tag and link_tag.get("href"):
                    url = link_tag["href"]
                    try:
                        accommodation_id = int(url.split("/")[-1])
                        accommodation_ids.append(accommodation_id)
                    except (ValueError, IndexError):
                        logger.warning(f"Impossible d'extraire l'ID depuis l'URL: {url}")
        
        logger.info(f"IDs récupérés: {accommodation_ids}")
        return accommodation_ids

    def get_accommodations(self, search_url: HttpUrl) -> SearchResults:
        """Returns the accommodations found on the CROUS website for the given search URL"""
        self.driver.get(str(search_url))
        sleep(2)

        current_url = self.driver.current_url
        logger.info(f"Getting accommodations from the current page: {current_url}")

        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        num_accommodations = self._get_accommodations_count(soup)
        logger.info(f"Found {num_accommodations} accommodations")

        return SearchResults(
            search_url=current_url,
            count=num_accommodations,
            accommodations=self._parse_accommodations(soup),
        )

    def _get_accommodations_count(self, soup: BeautifulSoup) -> Optional[int]:
        results_heading = soup.find("h2", class_="SearchResults-desktop fr-h4 svelte-11sc5my")
        if not results_heading:
            return None
        number_or_aucun = results_heading.text.split()[0]
        if number_or_aucun == "Aucun":
            return 0
        try:
            return int(number_or_aucun)
        except ValueError:
            return None

    def _parse_accommodations(self, soup: BeautifulSoup) -> List[Accommodation]:
        # Trouver la liste principale des logements
        main_list = soup.find("ul", class_="fr-grid-row fr-grid-row--gutters svelte-11sc5my")
        if not main_list:
            logger.warning("Liste principale des logements non trouvée")
            return []
            
        # Trouver tous les éléments <li> des logements
        accommodation_items = main_list.find_all("li", class_=lambda x: x and "fr-col-12" in x)
        logger.info(f"Trouvé {len(accommodation_items)} éléments de logement")
        
        accommodations: List[Accommodation] = []
        
        for i, item in enumerate(accommodation_items):
            logger.info(f"Parsing logement {i+1}/{len(accommodation_items)}")
            acc = self._parse_accommodation_card(item)
            if acc:
                # NOUVEAU: Récupérer toutes les photos de l'annonce
                acc = self._get_accommodation_details(acc)
                accommodations.append(acc)
        return accommodations

    def _parse_accommodation_card(self, accommodation_item: BeautifulSoup) -> Optional[Accommodation]:
        # Nom et URL
        title_tag = accommodation_item.find("h3", class_="fr-card__title")
        if not title_tag:
            logger.warning("Titre non trouvé pour un logement")
            return None
        title = title_tag.text.strip()
        link_tag = title_tag.find("a")
        url = link_tag["href"] if link_tag else None
        accommodation_id = int(url.split("/")[-1]) if url else None

        # Image principale
        img_tag = accommodation_item.find("img", class_="fr-responsive-img")
        image_url = img_tag["src"] if img_tag else None

        # Adresse
        address_tag = accommodation_item.find("p", class_="fr-card__desc")
        address = address_tag.text.strip() if address_tag else None

        # Détails
        details = accommodation_item.find_all("p", class_="fr-card__detail")
        overview_details = []
        for d in details:
            text = d.get_text(separator=" ").strip()
            overview_details.append(text)

        # Prix
        price_tag = accommodation_item.find("p", class_="fr-badge")
        try:
            price = float(price_tag.text.strip().replace("€", "").replace(",", ".")) if price_tag else None
        except Exception:
            price = price_tag.text.strip() if price_tag else None

        # Construire l'URL complète si relative
        detail_url = None
        if url:
            if url.startswith("http"):
                detail_url = url
            else:
                detail_url = f"https://trouverunlogement.lescrous.fr{url}"

        logger.info(f"Logement parsé: {title} (ID: {accommodation_id})")

        return Accommodation(
            id=accommodation_id,
            title=title,
            image_url=image_url,
            detail_url=detail_url,
            price=price,
            overview_details="\n".join([address] + overview_details) if address else "\n".join(overview_details)
        )

    def _get_accommodation_details(self, acc: Accommodation) -> Accommodation:
        """NOUVEAU: Navigue vers la page détaillée pour récupérer toutes les photos"""
        if not acc.detail_url:
            logger.warning(f"Pas d'URL détaillée pour {acc.title}")
            return acc

        try:
            logger.info(f"Récupération des photos pour: {acc.title}")
            
            # Sauvegarder l'URL actuelle
            current_url = self.driver.current_url
            
            # Naviguer vers la page détaillée
            self.driver.get(str(acc.detail_url))
            sleep(3)  # Attendre un peu plus pour le chargement
            
            # Parser les images dans la galerie
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # Trouver la section slider avec les photos
            slider_section = soup.find("section", class_="Slider svelte-i1xb97")
            
            image_urls = []
            if slider_section:
                logger.info("Section slider trouvée")
                # Trouver la liste des slides
                slides_list = slider_section.find("ul", class_="Slider-slides scrollbar-hidden svelte-i1xb97")
                if slides_list:
                    logger.info("Liste des slides trouvée")
                    # Trouver tous les éléments <li> contenant des photos
                    photo_items = slides_list.find_all("li")
                    logger.info(f"Trouvé {len(photo_items)} éléments photo")
                    
                    for item in photo_items:
                        # Chercher l'image dans chaque item
                        img_tag = item.find("img", class_="fr-responsive-img fr-ratio-16x9 svelte-y6vkg0")
                        if img_tag and img_tag.get("src"):
                            image_urls.append(img_tag["src"])
                else:
                    logger.warning("Liste des slides non trouvée")
            else:
                logger.warning("Section slider non trouvée")
            
            # Si pas de slider, essayer de trouver des images autrement
            if not image_urls:
                logger.info("Fallback: recherche d'images alternatives")
                # Fallback: chercher toutes les images qui semblent être des photos de logement
                all_images = soup.find_all("img")
                for img in all_images:
                    src = img.get("src", "")
                    if src and "preview" in src and "Résidence" in src:
                        image_urls.append(src)
            
            # Nettoyer et convertir en URLs absolues
            clean_urls = []
            for url in image_urls:
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = "https://trouverunlogement.lescrous.fr" + url
                elif not url.startswith("http"):
                    continue
                clean_urls.append(url)
            
            # Supprimer les doublons tout en gardant l'ordre
            seen = set()
            unique_urls = []
            for url in clean_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            acc.all_images = unique_urls[:10]  # Limiter à 10 photos max
            logger.info(f"Trouvé {len(acc.all_images)} photos pour {acc.title}")
            
            # Retourner à la page de résultats
            self.driver.get(current_url)
            sleep(2)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des photos pour {acc.title}: {e}")
            
        return acc