from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql://admin:password@localhost:5432/consent_db"
    redis_url: str = "redis://localhost:6379/0"

    salesforce_webhook_secret: str = ""
    hubspot_webhook_secret: str = ""
    outreach_webhook_secret: str = ""
    highspot_webhook_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
