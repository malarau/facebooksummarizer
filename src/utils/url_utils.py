import re
from typing import Optional

class URLUtils:
    """Utilities for extracting URLs and post IDs."""
    def extract_url(self, text: str) -> Optional[str]:
        """Extract the first URL from text (with or without www)."""
        # Soporta: https://..., http://..., www..., dominio.tld/...
        url_pattern = r'(https?://\S+|www\.\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?)'
        match = re.search(url_pattern, text)
        return match.group(0) if match else None

    def extract_post_id(self, post_link: str) -> Optional[str]:
        """Extract post ID from a Facebook post URL."""
        url_pattern = r'\/posts\/(pfbid\w+)'
        match = re.search(url_pattern, post_link)
        return match.group(1) if match else None