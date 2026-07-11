from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenRouter (Architect, Security, Efficiency agents)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Sarvam AI (Compliance Agent — Indian regulatory context)
    SARVAM_API_KEY: str = ""
    SARVAM_BASE_URL: str = "https://api.sarvam.ai/v1"
    SARVAM_MODEL: str = "sarvam-m"

    # Neo4j AuraDB
    NEO4J_URI: str = "neo4j+s://a125825f.databases.neo4j.io"
    NEO4J_USERNAME: str = "a125825f"
    NEO4J_PASSWORD: str = ""

    # SQLite (local dev)
    DATABASE_URL: str = "sqlite+aiosqlite:///./morpheus.db"

    # App
    APP_NAME: str = "MORPHEUS"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
