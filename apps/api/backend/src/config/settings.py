from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql://admin:password@localhost:5432/consent_db"
    redis_url: str = "redis://localhost:6379/0"

    salesforce_webhook_secret: str = ""
    hubspot_webhook_secret: str = ""
    outreach_webhook_secret: str = ""
    highspot_webhook_secret: str = ""

    # ES256 private key (PEM) for signing consent receipts. Required in
    # production — see receipt_service for why an ephemeral key is unsafe there.
    receipt_private_key: str = ""

    # Collector limits
    collector_rate_per_minute: int = 120
    collector_max_body_bytes: int = 4096

    # Site-wide ceiling, a backstop for when per-client limiting cannot help
    # (distributed sources with genuinely different addresses).
    collector_rate_per_site_per_minute: int = 6000

    # Number of proxies in front of this service that rewrite X-Forwarded-For.
    # 0 means we are directly exposed and the header is ignored entirely.
    # Behind an ALB set 1; behind CloudFront -> ALB set 2. Setting this higher
    # than the real chain length lets callers spoof their own address, so it
    # must match the deployed topology rather than be set defensively high.
    collector_trusted_proxy_hops: int = 0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
