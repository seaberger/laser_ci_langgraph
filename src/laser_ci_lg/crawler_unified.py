"""
Unified crawler that supports both smart discovery and static configurations.
"""

from ruamel.yaml import YAML
from .db import SessionLocal, bootstrap_db
from .models import Manufacturer, Product

# Import unified scrapers
from .scrapers.unified_coherent import UnifiedCoherentScraper
from .scrapers.unified_lumencor import UnifiedLumencorScraper
from .scrapers.unified_hubner import UnifiedHubnerScraper
from .scrapers.unified_omicron import UnifiedOmicronScraper
from .scrapers.unified_oxxius import UnifiedOxxiusScraper


def seed_from_unified_config(config_path: str = "config/target_products.yml"):
    """
    Seed database with manufacturers from unified config.
    Products will be created dynamically during scraping.
    """
    yaml = YAML(typ="safe")
    with open(config_path) as f:
        cfg = yaml.load(f)
    
    s = SessionLocal()
    try:
        for vendor in cfg["vendors"]:
            # Create manufacturer if doesn't exist
            m = s.query(Manufacturer).filter_by(name=vendor["name"]).one_or_none()
            if not m:
                m = Manufacturer(
                    name=vendor["name"],
                    homepage=vendor.get("homepage")
                )
                s.add(m)
                print(f"  ✓ Added manufacturer: {vendor['name']}")
        
        s.commit()
    finally:
        s.close()


def run_unified_scrapers(
    config_path: str = "config/target_products.yml",
    force_refresh: bool = False,
    vendor_filter: str = None,
    use_smart: bool = None
):
    """
    Run unified scrapers with smart discovery support.
    
    Args:
        config_path: Path to configuration file
        force_refresh: Force refresh all content (ignore SHA-256 cache)
        vendor_filter: Optional filter to run specific vendor
        use_smart: Override discovery mode (None = use config setting)
    """
    yaml = YAML(typ="safe")
    with open(config_path) as f:
        cfg = yaml.load(f)
    
    # Mapping of vendor names to scraper classes
    scraper_map = {
        "Coherent": UnifiedCoherentScraper,
        "Lumencor": UnifiedLumencorScraper,
        "Hübner Photonics (Cobolt)": UnifiedHubnerScraper,
        "Omicron": UnifiedOmicronScraper,
        "Oxxius": UnifiedOxxiusScraper,
    }
    
    # Alternative names for CLI convenience
    alias_map = {
        "coherent": "Coherent",
        "lumencor": "Lumencor",
        "hubner": "Hübner Photonics (Cobolt)",
        "cobolt": "Hübner Photonics (Cobolt)",
        "omicron": "Omicron",
        "oxxius": "Oxxius",
    }
    
    # Process vendor filter
    if vendor_filter:
        vendor_filter = alias_map.get(vendor_filter.lower(), vendor_filter)
    
    scrapers_run = 0
    
    for vendor_cfg in cfg["vendors"]:
        vendor_name = vendor_cfg["name"]
        
        # Skip if filter doesn't match
        if vendor_filter and vendor_name != vendor_filter:
            continue
        
        # Get scraper class
        scraper_class = scraper_map.get(vendor_name)
        if not scraper_class:
            print(f"  ⚠ No scraper implementation for: {vendor_name}")
            continue
        
        # Override discovery mode if requested
        if use_smart is not None:
            vendor_cfg["discovery_mode"] = "smart" if use_smart else "static"
        
        print(f"\nRunning {vendor_name} scraper...")
        print(f"  Config: {config_path}")
        print(f"  Force refresh: {force_refresh}")
        print(f"  Discovery mode: {vendor_cfg.get('discovery_mode', 'static')}")
        
        try:
            # Create and run scraper
            scraper = scraper_class(config_path=config_path, force_refresh=force_refresh)
            scraper.run()
            scrapers_run += 1
        except Exception as e:
            print(f"  ✗ Error running {vendor_name} scraper: {e}")
    
    if scrapers_run == 0 and vendor_filter:
        print(f"\nNo scrapers matched filter: '{vendor_filter}'")
        print("\nAvailable vendors:")
        for vendor in cfg["vendors"]:
            print(f"  - {vendor['name']}")
    
    return scrapers_run


def run_unified_pipeline(
    config_path: str = "config/smart_competitors.yml",
    force_refresh: bool = False,
    vendor_filter: str = None,
    use_smart: bool = True
):
    """
    Run complete unified pipeline with smart discovery.
    
    This is the main entry point that combines:
    1. Database bootstrap
    2. Manufacturer seeding
    3. Smart discovery or static scraping
    4. SHA-256 deduplication
    """
    print("Unified Pipeline with Smart Discovery")
    print("="*60)
    
    # Bootstrap database
    print("\n1. Setting up database...")
    bootstrap_db()
    
    # Seed manufacturers
    print("\n2. Seeding manufacturers...")
    seed_from_unified_config(config_path)
    
    # Run scrapers
    print("\n3. Running scrapers...")
    scrapers_run = run_unified_scrapers(
        config_path=config_path,
        force_refresh=force_refresh,
        vendor_filter=vendor_filter,
        use_smart=use_smart
    )
    
    print(f"\n✓ Pipeline complete: {scrapers_run} scrapers run")
    return scrapers_run