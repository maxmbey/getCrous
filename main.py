import argparse
import logging
import time
import json
import os
import random
import tempfile
import uuid
import shutil
import sys
from typing import List, Set

import telepot
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.authenticator import Authenticator, AuthenticationError
from src.parser import Parser
from src.models import UserConf, Notification, SearchResults
from src.notification_builder import NotificationBuilder
from src.settings import Settings
from src.telegram_notifier import TelegramNotifier

# --- Logging config ---
logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
    level=logging.INFO,
)
logger = logging.getLogger("accommodation_notifier")

# --- JSON stockage pour éviter les doublons ---
SEEN_FILE = "seen_ids.json"


def load_seen_ids(reset: bool = False) -> Set[int]:
    """Charge les IDs déjà vus, avec option pour reset"""
    if reset and os.path.exists(SEEN_FILE):
        logger.info("🗑️ Suppression du fichier seen_ids.json (reset demandé)")
        os.remove(SEEN_FILE)
        return set()
    
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            seen_ids = set(data.get("seen_ids", []))
            logger.info(f"📂 {len(seen_ids)} logements déjà vus chargés")
            return seen_ids
    
    logger.info("📂 Aucun fichier d'historique trouvé, démarrage propre")
    return set()

def save_seen_ids(seen_ids: Set[int]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen_ids": list(seen_ids)}, f, ensure_ascii=False, indent=2)

# --- Config utilisateurs ---
def load_users_conf() -> List[UserConf]:
    settings = Settings()
    
    users = [
        UserConf(
            conf_title="Moi",
            telegram_id=settings.MY_TELEGRAM_ID,
            search_url=settings.RESIDENCES_URL,
            ignored_ids=[2755],
        )
    ]
    
    # Liste des IDs Telegram optionnels (jusqu'à 10)
    optional_ids = [
        ('TELEGRAM_ID_2', 'Utilisateur 2'),
        ('TELEGRAM_ID_3', 'Utilisateur 3'),
        ('TELEGRAM_ID_4', 'Utilisateur 4'),
        ('TELEGRAM_ID_5', 'Utilisateur 5'),
        ('TELEGRAM_ID_6', 'Utilisateur 6'),
        ('TELEGRAM_ID_7', 'Utilisateur 7'),
        ('TELEGRAM_ID_8', 'Utilisateur 8'),
        ('TELEGRAM_ID_9', 'Utilisateur 9'),
        ('TELEGRAM_ID_10', 'Utilisateur 10'),
        ('TELEGRAM_ID_11', 'Utilisateur 11'),
    ]
    
    # Ajouter chaque utilisateur s'il est défini
    for field_name, title in optional_ids:
        telegram_id = getattr(settings, field_name, None)
        if telegram_id:
            users.append(UserConf(
                conf_title=title,
                telegram_id=telegram_id,
                search_url=settings.RESIDENCES_URL,
                ignored_ids=[],  # Peut avoir ses propres IDs ignorés
            ))
    
    logger.info(f"📱 {len(users)} utilisateur(s) configuré(s)")
    return users

# --- Selenium driver ---
def create_driver(headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        logger.info("Running in headless mode")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
    else:
        logger.info("Running in non-headless mode")

    # Créer un répertoire temporaire unique pour le profil Chrome
    temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    logger.info(f"Utilisation du profil Chrome temporaire : {temp_dir}")

    # Randomiser l'User-Agent pour éviter la détection
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")

    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--disable-default-apps")
    
    # Ajouter des options anti-détection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Masquer les traces de webdriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Stocker le chemin du profil temporaire pour le nettoyage
        driver._temp_profile_dir = temp_dir
        
        return driver
        
    except Exception as e:
        # Nettoyer le répertoire temporaire en cas d'erreur
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Répertoire temporaire nettoyé : {temp_dir}")
        except:
            pass
        raise e

def cleanup_driver(driver: webdriver.Chrome) -> None:
    """Ferme proprement le driver et nettoie le profil temporaire"""
    try:
        temp_dir = getattr(driver, '_temp_profile_dir', None)
        driver.quit()
        
        # Nettoyer le répertoire temporaire
        if temp_dir and os.path.exists(temp_dir):
            time.sleep(1)  # Attendre un peu pour que Chrome libère les fichiers
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Répertoire temporaire nettoyé : {temp_dir}")
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage du driver : {e}")

def random_sleep(base_delay: float, variance_percent: float = 0.3) -> None:
    """Sleep avec une variation aléatoire pour simuler un comportement humain"""
    variance = base_delay * variance_percent
    actual_delay = base_delay + random.uniform(-variance, variance)
    time.sleep(max(0.5, actual_delay))  # Minimum 0.5 seconde

# --- NOUVELLE LOGIQUE OPTIMISÉE CORRIGÉE VRAIMENT ---
def process_users_optimized(driver, parser_obj, notification_builder, notifier, user_confs, seen_ids, id_to_name):
    """
    Version optimisée qui fait UN SEUL appel par URL unique, mais envoie les notifications à TOUS les utilisateurs.
    """
    # 1️⃣ Grouper les utilisateurs par URL de recherche
    urls_to_users = {}
    for conf in user_confs:
        url = str(conf.search_url)
        if url not in urls_to_users:
            urls_to_users[url] = []
        urls_to_users[url].append(conf)
    
    logger.info(f"🔗 {len(urls_to_users)} URL(s) unique(s) à traiter pour {len(user_confs)} utilisateur(s)")
    
    # 2️⃣ Traiter chaque URL UNE SEULE FOIS
    for search_url, users_for_this_url in urls_to_users.items():
        logger.info(f"🔍 Traitement de: {search_url}")
        logger.info(f"👥 Utilisateurs concernés: {[u.conf_title for u in users_for_this_url]}")
        
        try:
            # UN SEUL APPEL de scraping complet par URL
            search_results = parser_obj.get_accommodations(search_url)
            current_ids = {acc.id for acc in search_results.accommodations if acc.id}
            
            logger.info(f"📊 Trouvé {len(current_ids)} logements sur cette URL")
            
            # 3️⃣ Identifier les VRAIMENT nouveaux logements GLOBALEMENT
            new_accommodations = []
            for acc in search_results.accommodations:
                if acc.id and acc.id not in seen_ids:
                    new_accommodations.append(acc)
            
            logger.info(f"🆕 {len(new_accommodations)} logement(s) VRAIMENT nouveaux détectés")
            
            # Vérifier les logements disparus GLOBALEMENT
            removed_ids = seen_ids - current_ids
            if removed_ids:
                logger.info(f"📉 {len(removed_ids)} logement(s) disparu(s): {removed_ids}")
            
            # 4️⃣ Traiter chaque utilisateur pour cette URL
            for user_conf in users_for_this_url:
                logger.info(f"👤 Traitement pour: {user_conf.conf_title}")
                
                # CAS 1: Aucun logement disponible
                if not search_results.accommodations:
                    logger.info(f"❌ Aucun logement disponible pour {user_conf.conf_title}")
                    notifier.send_notifications(user_conf.telegram_id, [
                        Notification(message="❌ Aucun logement disponible actuellement.")
                    ])
                
                # CAS 2: Il y a des nouveaux logements
                elif new_accommodations:
                    # Filtrer selon les IDs ignorés de cet utilisateur
                    user_new_accommodations = [
                        acc for acc in new_accommodations 
                        if acc.id not in user_conf.ignored_ids
                    ]
                    
                    if user_new_accommodations:
                        logger.info(f"✅ {len(user_new_accommodations)} nouveau(x) logement(s) à notifier pour {user_conf.conf_title}")
                        
                        for acc in user_new_accommodations:
                            logger.info(f"📤 Envoi notification pour logement ID {acc.id} à {user_conf.conf_title}")
                            notifications = notification_builder.search_results_notification(
                                SearchResults(
                                    search_url=search_url,
                                    count=1,
                                    accommodations=[acc]
                                )
                            )
                            
                            for notif in notifications:
                                notifier.send_notifications(user_conf.telegram_id, [notif])
                                random_sleep(1.5, 0.5)
                    else:
                        logger.info(f"🚫 Tous les nouveaux logements sont ignorés pour {user_conf.conf_title}")
                        
                # CAS 3: Pas de nouveaux logements
                else:
                    logger.info(f"✋ Aucun nouveau logement pour {user_conf.conf_title}")
                
                # 5️⃣ Notifier les logements disparus
                if removed_ids:
                    logger.info(f"📉 Notification de {len(removed_ids)} logement(s) disparu(s) pour {user_conf.conf_title}")
                    for removed_id in removed_ids:
                        removed_title = id_to_name.get(removed_id)
                        msg = f"⚠️ Le logement n'est plus disponible : {removed_title or 'ID ' + str(removed_id)}"
                        notifier.send_notifications(user_conf.telegram_id, [Notification(message=msg)])
                        random_sleep(1, 0.3)
                
                # Petit délai entre utilisateurs
                random_sleep(1, 0.3)
            
            # 6️⃣ Marquer les nouveaux logements comme vus APRÈS avoir notifié TOUS les utilisateurs
            if new_accommodations:
                logger.info(f"💾 Marquage de {len(new_accommodations)} nouveau(x) logement(s) comme vus")
                for acc in new_accommodations:
                    seen_ids.add(acc.id)
                    id_to_name[acc.id] = acc.title
                    logger.info(f"✅ Logement {acc.id} ({acc.title}) ajouté aux IDs vus")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de {search_url}: {e}")
            # Notifier tous les utilisateurs de cette URL de l'erreur
            for user_conf in users_for_this_url:
                try:
                    error_notif = Notification(message=f"⚠️ Erreur lors de la vérification: {str(e)[:100]}...")
                    notifier.send_notifications(user_conf.telegram_id, [error_notif])
                except:
                    logger.error(f"Impossible de notifier l'erreur à {user_conf.conf_title}")
        
        # Délai entre URLs différentes
        random_sleep(3, 0.4)
    
    # 7️⃣ Nettoyer les IDs disparus (une seule fois à la fin)
    all_current_ids = set()
    for search_url in urls_to_users.keys():
        try:
            # Récupération légère des IDs actuels
            current_ids = set(parser_obj.get_accommodation_ids(search_url))
            all_current_ids.update(current_ids)
        except Exception as e:
            logger.warning(f"Impossible de vérifier les IDs pour {search_url}: {e}")
    
    # Supprimer les IDs qui n'existent plus nulle part
    removed_ids = seen_ids - all_current_ids
    if removed_ids:
        logger.info(f"🧹 Nettoyage: suppression de {len(removed_ids)} ID(s) disparus définitivement")
        for removed_id in removed_ids:
            seen_ids.remove(removed_id)
            id_to_name.pop(removed_id, None)
            logger.info(f"🗑️ ID {removed_id} supprimé de la mémoire")

# --- Boucle principale ---
def main_loop(reset_data: bool = False):
    settings = Settings()
    bot = telepot.Bot(token=settings.TELEGRAM_BOT_TOKEN)
    bot.getMe()  # test token valide

    user_confs = load_users_conf()
    seen_ids = load_seen_ids(reset=reset_data)
    # Dictionnaire pour associer ID -> Nom
    id_to_name = {}

    loop_count = 0

    while True:
        driver = None  # Initialiser à None
        try:
            loop_count += 1
            logger.info(f"🔄 Début du cycle {loop_count}")
            
            # Délai aléatoire au début pour varier le timing
            initial_delay = random.uniform(2, 8)
            logger.info(f"⏱️ Délai initial aléatoire: {initial_delay:.1f}s")
            time.sleep(initial_delay)
            
            driver = create_driver(headless=True)
            
            # GESTION DE L'ERREUR D'AUTHENTIFICATION CRITIQUE
            try:
                Authenticator(settings.MSE_EMAIL, settings.MSE_PASSWORD).authenticate_driver(driver)
            except AuthenticationError as e:
                logger.error(f"🚨 Erreur d'authentification critique: {e}")
                if driver is not None:
                    try:
                        cleanup_driver(driver)
                    except Exception as cleanup_error:
                        logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
                # Arrêter complètement le programme
                sys.exit(1)
            
            # Petit délai aléatoire après l'authentification
            random_sleep(5, 0.5)  # Augmenté de 3 à 5
            
            parser_obj = Parser(driver)
            notification_builder = NotificationBuilder()
            notifier = TelegramNotifier(bot)

            # 🚀 NOUVELLE LOGIQUE OPTIMISÉE CORRIGÉE
            process_users_optimized(driver, parser_obj, notification_builder, notifier, user_confs, seen_ids, id_to_name)

            save_seen_ids(seen_ids)
            cleanup_driver(driver)  # Utiliser la nouvelle fonction
            driver = None  # Réinitialiser pour éviter le double nettoyage
            
            # Petit délai après fermeture du driver
            random_sleep(2, 0.3)
            
        except AuthenticationError:
            # Cette exception est déjà gérée plus haut avec sys.exit(1)
            # Ne devrait pas arriver ici, mais au cas où
            if driver is not None:
                try:
                    cleanup_driver(driver)
                except Exception as cleanup_error:
                    logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
            sys.exit(1)
            
        except Exception as e:
            logger.error(f"Erreur pendant le scraping : {e}")
            
            # S'assurer que le driver est fermé même en cas d'erreur
            if driver is not None:
                try:
                    cleanup_driver(driver)
                except Exception as cleanup_error:
                    logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
            
            # Délai plus long en cas d'erreur pour éviter de spam
            error_delay = random.uniform(30, 60)
            logger.info(f"⚠️ Attente de {error_delay:.1f}s après erreur")
            time.sleep(error_delay)

        # Calcul du délai principal avec randomisation
        base_delay = settings.FREQUENCE_VERIF
        # Variance de ±15% (±4.5 min si FREQUENCE_VERIF = 30 min)
        variance = base_delay * 0.15
        actual_delay = base_delay + random.uniform(-variance, variance)
        
        # S'assurer qu'on ne descend pas en dessous de 20 minutes
        actual_delay = max(1200, actual_delay)  # 1200s = 20min
        
        logger.info(f"⏰ Attente de {actual_delay / 60:.1f} minutes avant le prochain check...")
        logger.info(f"📊 Prochaine vérification vers {time.strftime('%H:%M:%S', time.localtime(time.time() + actual_delay))}")
        
        time.sleep(actual_delay)

# --- Entry point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the accommodation notifier")
    parser.add_argument("--loop", action="store_true", help="Run the script in loop mode (every 30min)")
    parser.add_argument("--no-headless", action="store_true", help="Run Chrome in non-headless mode")
    parser.add_argument("--reset", action="store_true", help="Reset seen IDs (clear history)")
    args = parser.parse_args()

    settings = Settings()

    if args.loop:
        main_loop(reset_data=args.reset)
    else:
        driver = None  # Initialiser à None
        try:
            # Délai aléatoire initial même en mode one-shot
            initial_delay = random.uniform(1, 4)
            logger.info(f"⏱️ Délai initial aléatoire: {initial_delay:.1f}s")
            time.sleep(initial_delay)
            
            driver = create_driver(headless=not args.no_headless)
            
            # GESTION DE L'ERREUR D'AUTHENTIFICATION CRITIQUE
            try:
                Authenticator(settings.MSE_EMAIL, settings.MSE_PASSWORD).authenticate_driver(driver)
            except AuthenticationError as e:
                logger.error(f"🚨 Erreur d'authentification critique: {e}")
                if driver is not None:
                    try:
                        cleanup_driver(driver)
                    except Exception as cleanup_error:
                        logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
                # Arrêter complètement le programme
                sys.exit(1)
            
            random_sleep(5, 0.4)  # Augmenté de 2 à 5
            
            parser_obj = Parser(driver)
            notification_builder = NotificationBuilder()
            notifier = TelegramNotifier(telepot.Bot(token=settings.TELEGRAM_BOT_TOKEN))

            user_confs = load_users_conf()
            seen_ids = load_seen_ids(reset=args.reset)
            id_to_name = {}

            # 🚀 NOUVELLE LOGIQUE OPTIMISÉE CORRIGÉE (mode one-shot)
            process_users_optimized(driver, parser_obj, notification_builder, notifier, user_confs, seen_ids, id_to_name)

            save_seen_ids(seen_ids)
            cleanup_driver(driver)  # Utiliser la nouvelle fonction
            
        except AuthenticationError as e:
            logger.error(f"🚨 Erreur d'authentification critique: {e}")
            if driver is not None:
                try:
                    cleanup_driver(driver)
                except Exception as cleanup_error:
                    logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
            # Arrêter complètement le programme
            sys.exit(1)
            
        except Exception as e:
            logger.error(f"Erreur pendant l'exécution : {e}")
            
            # S'assurer que le driver est fermé même en cas d'erreur
            if driver is not None:
                try:
                    cleanup_driver(driver)
                except Exception as cleanup_error:
                    logger.warning(f"Erreur lors du nettoyage du driver : {cleanup_error}")
            
            raise e