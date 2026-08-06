from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    METADATA_DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    TOKENALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    GOOGLE_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        extra="ignore",
    )


settings = Settings()

DATABASE_URL = settings.DATABASE_URL
METADATA_DATABASE_URL = settings.METADATA_DATABASE_URL
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
TOKENALGORITHM = settings.TOKENALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
GOOGLE_API_KEY = settings.GOOGLE_API_KEY