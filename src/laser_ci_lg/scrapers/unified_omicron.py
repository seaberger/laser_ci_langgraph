"""
Unified Omicron scraper with smart discovery support.
"""

from .unified_base import UnifiedBaseScraper


class UnifiedOmicronScraper(UnifiedBaseScraper):
    """Unified scraper for Omicron with smart discovery."""
    
    def vendor(self) -> str:
        return "Omicron"
    
    def __init__(self, config_path: str = "config/target_products.yml", force_refresh: bool = False):
        """Initialize with smart config by default."""
        super().__init__(config_path, force_refresh)