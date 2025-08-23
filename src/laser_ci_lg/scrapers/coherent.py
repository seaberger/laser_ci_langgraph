from .base import BaseScraper
from ..db import SessionLocal
from ..models import RawDocument
import requests


class CoherentScraper(BaseScraper):
    def vendor(self) -> str:
        return "Coherent"

    def run(self):
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Fetch the content
                r = requests.get(tgt["url"], timeout=30)
                status = r.status_code
                
                # Determine content type
                is_pdf = (
                    tgt["url"].lower().endswith(".pdf") or
                    "application/pdf" in r.headers.get("content-type", "")
                )
                
                if is_pdf:
                    # Use Docling for PDF extraction
                    text, raw_specs = self.extract_pdf_specs_with_docling(r.content)
                    content_type = "pdf_text"
                    
                    # If no specs extracted from tables, try parsing the text
                    if not raw_specs:
                        # Extract specs from markdown text
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
                else:
                    # Use enhanced HTML extraction
                    text = r.text
                    raw_specs = self.extract_all_html_specs(text)
                    content_type = "html"
                
                # Store the document with extracted specs
                s.add(
                    RawDocument(
                        product_id=tgt["product_id"],
                        url=tgt["url"],
                        http_status=status,
                        content_type=content_type,
                        text=text[:2_000_000],
                        raw_specs=raw_specs if raw_specs else None,
                    )
                )
            s.commit()
        finally:
            s.close()
