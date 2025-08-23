from .base import BaseScraper
from ..db import SessionLocal
from ..models import RawDocument


class OmicronLuxxScraper(BaseScraper):
    def vendor(self) -> str:
        return "Omicron"

    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Use enhanced fetch with caching
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                
                # Use the base class method for proper duplicate handling
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()