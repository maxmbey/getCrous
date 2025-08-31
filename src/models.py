from typing import List, Optional
from pydantic import Field, HttpUrl, BaseModel


class Accommodation(BaseModel):
    id: int | None
    title: str | None
    price: float | str | None
    overview_details: str | None = None
    image_url: HttpUrl | None = None  # Photo principale (miniature)
    all_images: List[HttpUrl] = Field(default_factory=list)  # NOUVEAU: toutes les photos
    detail_url: HttpUrl | None = None  # NOUVEAU: URL vers l'annonce complète


class SearchResults(BaseModel):
    search_url: HttpUrl
    count: Optional[int]
    accommodations: List[Accommodation]


class Notification(BaseModel):
    message: str
    photo_url: Optional[HttpUrl] = None  # Ancienne méthode (compatibilité)
    photo_urls: List[HttpUrl] = Field(default_factory=list)  # NOUVEAU: pour carrousel


class UserConf(BaseModel):
    conf_title: Optional[str]
    telegram_id: str
    search_url: HttpUrl
    ignored_ids: List[int] = Field(default_factory=list)