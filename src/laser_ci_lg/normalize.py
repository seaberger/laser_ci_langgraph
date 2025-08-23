from sqlalchemy import select
from .db import SessionLocal
from .models import RawDocument, NormalizedSpec
from .specs import canonical_key, parse_value_to_unit, CANONICAL_SPEC_KEYS
from .llm import llm_normalize


def simple_kv_from_text(text: str) -> dict:
    kv = {}
    for line in text.splitlines():
        if ":" in line and len(line) < 120:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return kv


def normalize_all(use_llm: bool = True, model: str | None = None) -> int:
    """Return count of inserted NormalizedSpec rows."""
    s = SessionLocal()
    inserted = 0
    try:
        raw_docs = (
            s.execute(
                select(RawDocument).order_by(
                    RawDocument.product_id, RawDocument.fetched_at.desc()
                )
            )
            .scalars()
            .all()
        )
        # group by product_id
        by_pid = {}
        for d in raw_docs:
            by_pid.setdefault(d.product_id, []).append(d)

        for pid, docs in by_pid.items():
            merged_raw, blobs = {}, []
            for d in docs:
                if d.raw_specs:
                    merged_raw.update(d.raw_specs)
                blobs.append(d.text)
            if not merged_raw:
                for d in docs:
                    merged_raw.update(simple_kv_from_text(d.text))

            canonical = {k: None for k in CANONICAL_SPEC_KEYS}
            extras = {}
            for k, v in merged_raw.items():
                ck = canonical_key(k)
                if ck:
                    canonical[ck] = parse_value_to_unit(ck, str(v))
                else:
                    extras[k] = v
            canonical["vendor_fields"] = extras or None

            if use_llm and sum(v is not None for v in canonical.values()) < 4:
                try:
                    llm = llm_normalize(merged_raw, "\n".join(blobs[:2]), model=model)
                    for k in set(CANONICAL_SPEC_KEYS) | {"vendor_fields"}:
                        if llm.get(k) is not None:
                            canonical[k] = llm.get(k)
                except Exception as e:
                    # fail open; keep heuristic result
                    pass

            ns = NormalizedSpec(product_id=pid, source_raw_id=docs[0].id, **canonical)
            s.add(ns)
            inserted += 1
        s.commit()
        return inserted
    finally:
        s.close()
