from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql://admin:password@localhost:5432/consent_db"
    mongo_url: str = "mongodb://admin:password@localhost:27017/consent_db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:3002"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
