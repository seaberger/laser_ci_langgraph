from ruamel.yaml import YAML
from .db import SessionLocal, bootstrap_db
from .models import Manufacturer, Product
from .scrapers.coherent import CoherentScraper
from .scrapers.hubner_cobolt import CoboltScraper
from .scrapers.omicron_luxx import OmicronLuxxScraper
from .scrapers.oxxius_lbx import OxxiusLbxScraper
from .scrapers.lumencor import LumencorScraper


def seed_from_config(path="config/competitors.yml"):
    yaml = YAML(typ="safe")
    with open(path) as f:
        cfg = yaml.load(f)
    s = SessionLocal()
    try:
        for v in cfg["vendors"]:
            m = s.query(Manufacturer).filter_by(name=v["name"]).one_or_none()
            if not m:
                m = Manufacturer(name=v["name"], homepage=v.get("homepage"))
                s.add(m)
                s.flush()
            for seg in v["segments"]:
                for p in seg["products"]:
                    exists = (
                        s.query(Product)
                        .filter_by(
                            manufacturer_id=m.id, segment_id=seg["id"], name=p["name"]
                        )
                        .one_or_none()
                    )
                    if not exists:
                        s.add(
                            Product(
                                manufacturer_id=m.id,
                                segment_id=seg["id"],
                                name=p["name"],
                                product_url=p.get("product_url"),
                            )
                        )
        s.commit()
    finally:
        s.close()


def run_scrapers_from_config(path="config/competitors.yml", force_refresh=False, scraper_filter=None):
    yaml = YAML(typ="safe")
    with open(path) as f:
        cfg = yaml.load(f)
    s = SessionLocal()
    try:
        pid_map = {
            (p.manufacturer_id, p.segment_id, p.name): p.id
            for p in s.query(Product).all()
        }
    finally:
        s.close()

    def make_targets(vendor_name, seg):
        # rebuild Product ids per vendor/segment/name
        s2 = SessionLocal()
        try:
            from sqlalchemy import select
            from .models import Manufacturer, Product

            man = s2.query(Manufacturer).filter_by(name=vendor_name).one()
            targets = []
            for p in seg["products"]:
                pid = (
                    s2.query(Product)
                    .filter_by(
                        manufacturer_id=man.id, segment_id=seg["id"], name=p["name"]
                    )
                    .one()
                    .id
                )
                targets.append(
                    {
                        "product_id": pid,
                        "product_url": p.get("product_url"),
                        "datasheets": p.get("datasheets", []),
                    }
                )
            return targets
        finally:
            s2.close()

    def should_run_scraper(vendor_name: str, scraper_filter: str) -> bool:
        """Check if a scraper should run based on the filter"""
        if not scraper_filter:
            return True
        
        # Normalize names for comparison
        vendor_lower = vendor_name.lower()
        filter_lower = scraper_filter.lower().replace('.py', '')
        
        # Check various matching patterns
        if filter_lower in vendor_lower:
            return True
        
        # Check specific mappings
        mappings = {
            'coherent': ['coherent'],
            'hubner': ['hübner', 'hubner', 'cobolt'],
            'cobolt': ['hübner', 'hubner', 'cobolt'],
            'omicron': ['omicron'],
            'oxxius': ['oxxius'],
            'lumencor': ['lumencor'],
            'luxx': ['omicron'],
            'lbx': ['oxxius'],
            'celesta': ['lumencor'],
            'spectra': ['lumencor'],
            'sola': ['lumencor'],
        }
        
        for key, values in mappings.items():
            if filter_lower == key:
                return any(v in vendor_lower for v in values)
        
        return False
    
    scrapers = []
    for v in cfg["vendors"]:
        # Check if this vendor should be processed
        if scraper_filter and not should_run_scraper(v["name"], scraper_filter):
            continue
            
        for seg in v["segments"]:
            t = make_targets(v["name"], seg)
            if v["name"].startswith("Coherent"):
                scrapers.append(CoherentScraper(t, force_refresh=force_refresh))
            elif "Hübner" in v["name"] or "Cobolt" in v["name"]:
                scrapers.append(CoboltScraper(t, force_refresh=force_refresh))
            elif v["name"] == "Omicron":
                scrapers.append(OmicronLuxxScraper(t, force_refresh=force_refresh))
            elif v["name"] == "Oxxius":
                scrapers.append(OxxiusLbxScraper(t, force_refresh=force_refresh))
            elif v["name"] == "Lumencor":
                scrapers.append(LumencorScraper(t, force_refresh=force_refresh))
    
    if not scrapers and scraper_filter:
        print(f"No scrapers matched filter: '{scraper_filter}'")
        print("\nAvailable scrapers:")
        print("  - coherent")
        print("  - hubner (or cobolt)")
        print("  - omicron (or luxx)")
        print("  - oxxius (or lbx)")
        print("  - lumencor (or celesta, spectra, sola)")
        return
    
    for sc in scrapers:
        print(f"\nRunning {sc.vendor()} scraper...")
        sc.run()
