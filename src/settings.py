# pydantic-settings class

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MSE_LOGIN_URL: str = "https://www.messervices.etudiant.gouv.fr/envole/oauth2/login"

    MSE_EMAIL: str = Field(default=...)
    MSE_PASSWORD: str = Field(default=...)

    TELEGRAM_BOT_TOKEN: str = Field(default=...)
    MY_TELEGRAM_ID: str = Field(default=...)
    
    # IDs Telegram optionnels (jusqu'à 10 utilisateurs supplémentaires)
    TELEGRAM_ID_2: Optional[str] = Field(default=None)
    TELEGRAM_ID_3: Optional[str] = Field(default=None)
    TELEGRAM_ID_4: Optional[str] = Field(default=None)
    TELEGRAM_ID_5: Optional[str] = Field(default=None)
    TELEGRAM_ID_6: Optional[str] = Field(default=None)
    TELEGRAM_ID_7: Optional[str] = Field(default=None)
    TELEGRAM_ID_8: Optional[str] = Field(default=None)
    TELEGRAM_ID_9: Optional[str] = Field(default=None)
    TELEGRAM_ID_10: Optional[str] = Field(default=None)
    TELEGRAM_ID_11: Optional[str] = Field(default=None)

    RESIDENCES_URL: str = Field(default=...)
    RESIDENCES_VILLE: str = Field(default=...)

    FREQUENCE_VERIF: int = Field(...)