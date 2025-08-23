from datetime import datetime, timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import Manufacturer, Product, NormalizedSpec


def monthly_report(days: int = 35) -> str:
    s = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        latest, prev = {}, {}
        ns_rows = (
            s.execute(
                select(NormalizedSpec).order_by(
                    NormalizedSpec.product_id, NormalizedSpec.snapshot_ts.desc()
                )
            )
            .scalars()
            .all()
        )
        for ns in ns_rows:
            if ns.product_id not in latest:
                latest[ns.product_id] = ns
            elif ns.snapshot_ts < latest[ns.product_id].snapshot_ts:
                prev.setdefault(ns.product_id, ns)

        prows = s.execute(
            select(Product, Manufacturer).join(
                Manufacturer, Product.manufacturer_id == Manufacturer.id
            )
        ).all()
        vendor_first_seen = {}
        for p, m in prows:
            vendor_first_seen.setdefault(m.name, p.created_at)
            vendor_first_seen[m.name] = min(vendor_first_seen[m.name], p.created_at)
        new_entrants = sorted([v for v, ts in vendor_first_seen.items() if ts >= since])

        lines = ["# Monthly Laser CI Report", ""]
        if new_entrants:
            lines.append("## New Entrants")
            for v in new_entrants:
                lines.append(f"- {v}")
            lines.append("")

        lines.append("## Significant Spec Changes")
        for pid, ns in latest.items():
            pv = prev.get(pid)
            if not pv:
                continue

            def big_change(a, b, th):
                if a is None or b is None or b == 0:
                    return False
                return abs(a - b) / abs(b) >= th

            changes = []
            if big_change(ns.output_power_mw_nominal, pv.output_power_mw_nominal, 0.10):
                changes.append(
                    f"Power {pv.output_power_mw_nominal}→{ns.output_power_mw_nominal} mW"
                )
            if big_change(ns.rms_noise_pct, pv.rms_noise_pct, 0.25):
                changes.append(f"RMS noise {pv.rms_noise_pct}→{ns.rms_noise_pct} %")
            if big_change(ns.power_stability_pct, pv.power_stability_pct, 0.25):
                changes.append(
                    f"Stability {pv.power_stability_pct}→{ns.power_stability_pct} %"
                )
            if big_change(ns.modulation_digital_hz, pv.modulation_digital_hz, 1.0):
                changes.append(
                    f"Digital mod BW {pv.modulation_digital_hz}→{ns.modulation_digital_hz} Hz"
                )
            if changes:
                p = s.get(Product, pid)
                lines.append(f"- **{p.name}** ({p.segment_id}) — " + "; ".join(changes))
        return "\n".join(lines) + "\n"
    finally:
        s.close()
