from .base import BaseScraper
from ..db import SessionLocal
from ..models import RawDocument


class CoherentScraper(BaseScraper):
    def vendor(self) -> str:
        return "Coherent"

    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Use enhanced fetch with caching
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_cache(tgt["url"])
                
                # For PDFs without extracted specs, try parsing markdown text
                if content_type == "pdf_text" and not raw_specs:
                    lines = text.split('\n')
                    raw_specs = {}
                    for line in lines:
                        if ':' in line and len(line) < 200:  # Likely a spec line
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                k = parts[0].strip().replace('*', '').replace('#', '')
                                v = parts[1].strip()
                                if k and v:
                                    raw_specs[k] = v
                
                # Use the base class method for proper duplicate handling
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()
