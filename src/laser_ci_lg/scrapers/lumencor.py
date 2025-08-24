"""
Scraper for Lumencor light engines and laser systems.

Products include:
- CELESTA light engines (laser-based)
- SOLA light engines (white light)
- SPECTRA/SPECTRA X light engines (multi-wavelength)
- AURA light engines
"""

from .lumencor_enhanced import LumencorEnhancedScraper


# Use the enhanced scraper with custom extraction
class LumencorScraper(LumencorEnhancedScraper):
    """Scraper for Lumencor light engines with custom extraction."""
    pass