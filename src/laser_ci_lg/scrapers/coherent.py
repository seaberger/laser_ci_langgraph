from .base import BaseScraper
from ..db import SessionLocal
from ..models import RawDocument
from bs4 import BeautifulSoup


class CoherentScraper(BaseScraper):
    def vendor(self) -> str:
        return "Coherent"

    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                status, ctype, text = self.fetch(tgt["url"])
                raw_specs = None
                if ctype == "html":
                    soup = BeautifulSoup(text, "html.parser")
                    bullets = [
                        li.get_text(" ", strip=True) for li in soup.find_all("li")
                    ]
                    raw_specs = {}
                    for b in bullets:
                        if ":" in b:
                            k, v = b.split(":", 1)
                            raw_specs[k.strip()] = v.strip()
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
