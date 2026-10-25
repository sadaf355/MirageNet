from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "MirageNet API"
    app_env: str = "development"
    database_url: str = "sqlite:///./miragenet.db"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://localhost:3000"
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

settings = Settings()
