from collections import defaultdict
from sqlalchemy import select
from .db import SessionLocal
from .models import NormalizedSpec, Product, Manufacturer


def benchmark_vs_coherent(segment_id: str = "diode_instrumentation"):
    s = SessionLocal()
    try:
        rows = s.execute(
            select(NormalizedSpec, Product, Manufacturer)
            .join(Product, NormalizedSpec.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .where(Product.segment_id == segment_id)
            .order_by(NormalizedSpec.snapshot_ts.desc())
        ).all()

        latest = {}
        for ns, p, m in rows:
            if p.id not in latest:
                latest[p.id] = (ns, p, m)

        def band_nm(w):
            return None if w is None else int(round(w))

        def pclass(mw):
            if mw is None:
                return "unknown"
            if mw < 50:
                return "<50 mW"
            if mw < 150:
                return "50–150 mW"
            if mw < 500:
                return "150–500 mW"
            return ">=500 mW"

        buckets = defaultdict(list)
        for ns, p, m in latest.values():
            buckets[
                (band_nm(ns.wavelength_nm), pclass(ns.output_power_mw_nominal))
            ].append((ns, p, m))

        rows_out = []
        for (wl, pc), items in sorted(buckets.items()):
            coh = [t for t in items if t[2].name.startswith("Coherent")]
            comp = [t for t in items if not t[2].name.startswith("Coherent")]
            if not coh or not comp:
                continue
            base = coh[0][0]
            for ns, p, m in comp:
                rows_out.append(
                    {
                        "wl_nm": wl,
                        "power_class": pc,
                        "vendor": m.name,
                        "model": p.name,
                        "Δnoise_pct": None
                        if (ns.rms_noise_pct is None or base.rms_noise_pct is None)
                        else ns.rms_noise_pct - base.rms_noise_pct,
                        "Δstability_pct": None
                        if (
                            ns.power_stability_pct is None
                            or base.power_stability_pct is None
                        )
                        else ns.power_stability_pct - base.power_stability_pct,
                        "Δlinewidth_MHz": None
                        if (ns.linewidth_mhz is None or base.linewidth_mhz is None)
                        else ns.linewidth_mhz - base.linewidth_mhz,
                    }
                )
        return rows_out
    finally:
        s.close()
