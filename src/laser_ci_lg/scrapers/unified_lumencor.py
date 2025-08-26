"""
Unified Lumencor scraper with smart discovery support.
Handles JavaScript-heavy site with browser automation.
"""

from .unified_base import UnifiedBaseScraper


class UnifiedLumencorScraper(UnifiedBaseScraper):
    """Unified scraper for Lumencor with smart discovery."""
    
    def vendor(self) -> str:
        return "Lumencor"
    
    def __init__(self, config_path: str = "config/target_products.yml", force_refresh: bool = False):
        """Initialize with smart config by default."""
        super().__init__(config_path, force_refresh)