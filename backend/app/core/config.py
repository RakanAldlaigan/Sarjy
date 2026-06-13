from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""


settings = Settings()
