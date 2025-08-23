from .base import BaseScraper
from ..db import SessionLocal
from ..models import RawDocument


class OxxiusLbxScraper(BaseScraper):
    def vendor(self) -> str:
        return "Oxxius"

    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Use enhanced fetch with caching
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                
                # Check if document with same hash already exists
                existing = s.query(RawDocument).filter_by(
                    url=tgt["url"],
                    content_hash=content_hash
                ).first()
                
                if existing:
                    print(f"  → Document unchanged, skipping database insert")
                    continue
                
                s.add(
                    RawDocument(
                        product_id=tgt["product_id"],
                        url=tgt["url"],
                        http_status=status,
                        content_type=content_type,
                        text=text[:2_000_000],
                        raw_specs=raw_specs if raw_specs else None,
                        content_hash=content_hash,
                        file_path=file_path,
                    )
                )
            s.commit()
        finally:
            s.close()