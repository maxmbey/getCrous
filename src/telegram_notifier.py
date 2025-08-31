import logging
import time
from typing import List
from telepot import Bot  # type: ignore
from telepot.exception import TooManyRequestsError
from src.models import Notification

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends notifications to a Telegram user, one per accommodation."""

    def __init__(self, bot: Bot, delay_between_messages: float = 1.0):
        self.bot = bot
        self.delay_between_messages = delay_between_messages

    def send_notifications(self, telegram_id: str, notifications: List[Notification]) -> None:
        """Send each notification separately, with photo carousel if available."""
        for i, notif in enumerate(notifications):
            # Ajouter un délai entre les messages (sauf pour le premier)
            if i > 0:
                time.sleep(self.delay_between_messages)
                
            self._send_single_notification(telegram_id, notif)

    def _send_single_notification(self, telegram_id: str, notification: Notification) -> None:
        """Envoie une notification unique avec gestion du rate limit"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if notification.photo_urls and len(notification.photo_urls) > 1:
                    # NOUVEAU: Envoyer un carrousel (MediaGroup) pour plusieurs photos
                    logger.info(f"Envoi d'un carrousel de {len(notification.photo_urls)} photos")
                    self._send_media_group(telegram_id, notification)
                elif notification.photo_urls and len(notification.photo_urls) == 1:
                    # Une seule photo
                    logger.info("Envoi d'une photo unique")
                    self.bot.sendPhoto(
                        chat_id=telegram_id,
                        photo=str(notification.photo_urls[0]),
                        caption=notification.message,
                        parse_mode="HTML"
                    )
                elif getattr(notification, "photo_url", None):
                    # Ancienne méthode (compatibilité)
                    logger.info("Envoi d'une photo (méthode legacy)")
                    self.bot.sendPhoto(
                        chat_id=telegram_id,
                        photo=str(notification.photo_url),
                        caption=notification.message,
                        parse_mode="HTML"
                    )
                else:
                    # Pas de photo
                    logger.info("Envoi d'un message texte uniquement")
                    self.bot.sendMessage(
                        chat_id=telegram_id,
                        text=notification.message,
                        parse_mode="HTML"
                    )
                
                # Si on arrive ici, l'envoi a réussi
                break
                
            except TooManyRequestsError as e:
                retry_after = getattr(e, 'retry_after', 30)
                logger.warning(f"Rate limit atteint. Attente de {retry_after} secondes (tentative {attempt + 1}/{max_retries})")
                
                if attempt < max_retries - 1:  # Pas de sleep à la dernière tentative
                    time.sleep(retry_after)
                else:
                    logger.error(f"Échec d'envoi après {max_retries} tentatives: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi (tentative {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(2)  # Attente courte pour autres erreurs
                else:
                    logger.error(f"Échec d'envoi définitif après {max_retries} tentatives")
                    raise

    def _send_media_group(self, telegram_id: str, notification: Notification) -> None:
        """NOUVEAU: Envoie un carrousel de photos via MediaGroup"""
        try:
            # Préparer les médias pour le carrousel
            media = []
            
            for i, photo_url in enumerate(notification.photo_urls[:10]):  # Max 10 photos
                media_item = {
                    'type': 'photo',
                    'media': str(photo_url)
                }
                
                # Ajouter la caption seulement à la première photo
                if i == 0:
                    media_item['caption'] = notification.message
                    media_item['parse_mode'] = 'HTML'
                
                media.append(media_item)
            
            logger.info(f"Envoi du carrousel avec {len(media)} photos")
            
            # Envoyer le carrousel
            self.bot.sendMediaGroup(
                chat_id=telegram_id,
                media=media
            )
            
            logger.info("Carrousel envoyé avec succès")
            
        except TooManyRequestsError:
            # Re-raise pour être gérée par _send_single_notification
            raise
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du carrousel: {e}")
            # Fallback: envoyer la première photo avec caption
            if notification.photo_urls:
                logger.info("Fallback: envoi de la première photo uniquement")
                try:
                    self.bot.sendPhoto(
                        chat_id=telegram_id,
                        photo=str(notification.photo_urls[0]),
                        caption=notification.message,
                        parse_mode="HTML"
                    )
                except Exception as fallback_error:
                    logger.error(f"Erreur fallback: {fallback_error}")
                    # Si même le fallback échoue, envoyer juste le texte
                    self.bot.sendMessage(
                        chat_id=telegram_id,
                        text=notification.message,
                        parse_mode="HTML"
                    )