from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_tracker"

    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    MAX_RESUME_MB: int = 5

    CORS_ORIGINS: str = "*"
    DEV_MODE: bool = True

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
