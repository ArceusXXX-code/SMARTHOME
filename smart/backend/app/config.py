from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Ростелеком"
    DATABASE_URL: str = "sqlite:///./smart_home.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
