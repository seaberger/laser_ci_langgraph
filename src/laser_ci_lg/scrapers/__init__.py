"""
Laser manufacturer web scrapers
"""

from .base import BaseScraper
from .coherent import CoherentScraper
from .hubner_cobolt import CoboltScraper
from .omicron_luxx import OmicronLuxxScraper
from .oxxius_lbx import OxxiusLbxScraper

__all__ = [
    "BaseScraper",
    "CoherentScraper",
    "CoboltScraper",
    "OmicronLuxxScraper",
    "OxxiusLbxScraper",
]