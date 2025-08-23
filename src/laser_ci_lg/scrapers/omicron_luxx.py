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
                status, ctype, text = self.fetch(tgt["url"])
                raw_specs = None
                if ctype == "html":
                    raw_specs = self.extract_table_kv_pairs(text)
                    if not raw_specs:
                        raw_specs = None
                s.add(
                    RawDocument(
                        product_id=tgt["product_id"],
                        url=tgt["url"],
                        http_status=status,
                        content_type="pdf_text" if ctype == "pdf" else "html",
                        text=text[:2_000_000],
                        raw_specs=raw_specs,
                    )
                )
            s.commit()
        finally:
            s.close()