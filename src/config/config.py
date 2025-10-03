from pathlib import Path
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Config:
    """Configuration class for environment variables."""
    FB_EMAIL: str = os.getenv("FB_EMAIL")
    FB_PASSWORD: str = os.getenv("FB_PASSWORD")
    FB_PAGES: List[str] = os.getenv("FB_PAGES", "").split(",")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
    SOURCE_URL: str = "https://www.facebook.com/"
    COOKIE_DIR: Path = Path(__file__).parent.parent.parent / "database" / "cookies"
    DB_PATH: Path = Path(__file__).parent.parent.parent / "database" / "data.db"
    TIMEOUT: int = 10
    HTTP_TIMEOUT: int = 10
    MAX_SCROLLS: int = 5
    POST_LIMIT: int = 10

    @staticmethod
    def validate():
        """Validate required environment variables."""
        required = ["FB_EMAIL", "FB_PASSWORD", "FB_PAGES", "OPENROUTER_API_KEY"]
        missing = [key for key in required if not getattr(Config, key, None)]
        if missing:
            raise ValueError(f"Missing environment variables: {missing}")