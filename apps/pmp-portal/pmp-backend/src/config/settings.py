"""Application settings loaded from environment."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql://admin:password@localhost:5432/consent_db"
    mongo_url: str = "mongodb://admin:password@localhost:27017/consent_db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = ["http://localhost:3001"]

    # Magic link
    magic_link_expire_minutes: int = 15
    pmp_frontend_url: str = "http://localhost:3001"

    # SMTP (leave smtp_host empty in development -> link is printed to console)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "privacy@yourcompany.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
