from ruamel.yaml import YAML
from .db import get_engine, SessionLocal
from .models import Base, Manufacturer, Product
from .scrapers.coherent import CoherentScraper
from .scrapers.hubner_cobolt import CoboltScraper
from .scrapers.omicron_luxx import OmicronLuxXScraper
from .scrapers.oxxius_lbx import OxxiusLBXScraper


def bootstrap_db():
    Base.metadata.create_all(get_engine())


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


def run_scrapers_from_config(path="config/competitors.yml"):
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

    scrapers = []
    for v in cfg["vendors"]:
        for seg in v["segments"]:
            t = make_targets(v["name"], seg)
            if v["name"].startswith("Coherent"):
                scrapers.append(CoherentScraper(t))
            elif "Hübner" in v["name"] or "Cobolt" in v["name"]:
                scrapers.append(CoboltScraper(t))
            elif v["name"] == "Omicron":
                scrapers.append(OmicronLuxXScraper(t))
            elif v["name"] == "Oxxius":
                scrapers.append(OxxiusLBXScraper(t))
    for sc in scrapers:
        sc.run()
