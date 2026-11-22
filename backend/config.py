import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "ObraExacta API & Telegram Bot"
    API_V1_PREFIX: str = "/api"
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_POLLING_TIMEOUT: int = 10

    # Gemini Model
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = "obraexacta"

    # Financial defaults (Tasa oficial BCV verificada en tiempo real)
    TASA_BCV_DEFAULT: float = 918.77
    MARGEN_META_DEFAULT: float = 30.0
    PENSION_LAW_PERCENTAGE: float = 9.0  # 9% Ley de Protección de Pensiones sobre Mano de Obra

    # Frontend host for deep links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
