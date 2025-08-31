from typing import List
from html import escape
from src.models import Accommodation, Notification, SearchResults


class NotificationBuilder:
    """Builds notifications from search results, one notification per accommodation."""

    def __init__(self, notify_when_no_results: bool = False):
        self.notify_when_no_results = notify_when_no_results

    def search_results_notification(self, search_results: SearchResults) -> List[Notification]:
        """Returns a list of Notification objects, one per accommodation with all photos."""
        accommodations = search_results.accommodations
        notifications: List[Notification] = []

        if not accommodations and not self.notify_when_no_results:
            notifications.append(Notification(message="❌ Aucun logement trouvé."))
            return notifications

        for acc in accommodations:
            price_str = f"{acc.price}€" if isinstance(acc.price, float) else acc.price
            overview = acc.overview_details or ""
            
            # Construire message HTML avec emojis
            message_parts = [
                f"🏠 <b>{escape(acc.title or '')}</b>",
                f"📍 {escape(overview)}",
                f"💶 Prix: {price_str}",
            ]
            
            if acc.all_images:
                message_parts.append(f"📸 {len(acc.all_images)} photos disponibles")
            
            message = "\n".join(message_parts)

            # NOUVEAU: Utiliser toutes les photos pour le carrousel
            photo_urls = acc.all_images if acc.all_images else []
            
            notifications.append(Notification(
                message=message, 
                photo_urls=photo_urls
            ))

        return notifications