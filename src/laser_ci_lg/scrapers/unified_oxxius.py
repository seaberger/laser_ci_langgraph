"""
Unified Oxxius scraper with smart discovery support.
"""

from .unified_base import UnifiedBaseScraper


class UnifiedOxxiusScraper(UnifiedBaseScraper):
    """Unified scraper for Oxxius with smart discovery."""
    
    def vendor(self) -> str:
        return "Oxxius"
    
    def __init__(self, config_path: str = "config/target_products.yml", force_refresh: bool = False):
        """Initialize with smart config by default."""
        super().__init__(config_path, force_refresh)