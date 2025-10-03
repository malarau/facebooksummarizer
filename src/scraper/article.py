from goose3 import Goose
from src.config.config import Config

class ArticleScraper:
    """Extracts content from article URLs."""
    def __init__(self):
        self.goose = Goose()
        self.goose.config.http_timeout = Config.HTTP_TIMEOUT

    def scrape_article(self, url: str) -> str:
        """Extract content from an article URL."""
        try:
            article = self.goose.extract(url=url)
            return article.cleaned_text
        except Exception as e:
            return f"Failed to scrape article: {str(e)}"