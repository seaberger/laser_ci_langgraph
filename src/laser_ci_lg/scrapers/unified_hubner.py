"""
Unified Hübner Photonics (Cobolt) scraper with smart discovery support.
"""

from .unified_base import UnifiedBaseScraper


class UnifiedHubnerScraper(UnifiedBaseScraper):
    """Unified scraper for Hübner Photonics with smart discovery."""
    
    def vendor(self) -> str:
        return "Hübner Photonics (Cobolt)"
    
    def __init__(self, config_path: str = "config/target_products.yml", force_refresh: bool = False):
        """Initialize with smart config by default."""
        super().__init__(config_path, force_refresh)