from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any, List, Tuple
import requests, pdfplumber, io
from bs4 import BeautifulSoup
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from pathlib import Path
import tempfile


class Target(dict): ...


class BaseScraper(ABC):
    def __init__(self, targets: list[dict]):
        self._targets = targets

    @abstractmethod
    def vendor(self) -> str: ...

    def iter_targets(self) -> Iterable[Target]:
        for t in self._targets:
            pid = t["product_id"]
            if t.get("product_url"):
                yield {"product_id": pid, "url": t["product_url"], "kind": "html"}
            for ds in t.get("datasheets", []):
                yield {"product_id": pid, "url": ds, "kind": "pdf"}

    def fetch(self, url: str) -> tuple[int, str, str]:
        r = requests.get(url, timeout=30)
        ctype = (
            "pdf"
            if url.lower().endswith(".pdf")
            or "application/pdf" in r.headers.get("content-type", "")
            else "html"
        )
        text = ""
        if ctype == "html":
            text = r.text
        else:
            # Use pdfplumber as fallback for simple text extraction
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages)
        return r.status_code, ctype, text

    def extract_table_kv_pairs(self, html_text: str) -> dict:
        """Extract key-value pairs from HTML tables"""
        soup = BeautifulSoup(html_text, "html.parser")
        kv = {}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    k = cells[0].get_text(" ", strip=True)
                    v = cells[1].get_text(" ", strip=True)
                    if k and v:
                        kv[k] = v
        return kv
    
    def extract_all_html_specs(self, html_text: str) -> dict:
        """Extract specs from multiple HTML sources: tables, lists, definition lists"""
        soup = BeautifulSoup(html_text, "html.parser")
        kv = {}
        
        # 1. Extract from tables
        kv.update(self.extract_table_kv_pairs(html_text))
        
        # 2. Extract from bullet points with colons
        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)
            if ":" in text:
                k, v = text.split(":", 1)
                kv[k.strip()] = v.strip()
        
        # 3. Extract from definition lists (dl/dt/dd)
        for dl in soup.find_all("dl"):
            terms = dl.find_all("dt")
            defs = dl.find_all("dd")
            for term, definition in zip(terms, defs):
                k = term.get_text(" ", strip=True)
                v = definition.get_text(" ", strip=True)
                if k and v:
                    kv[k] = v
        
        # 4. Extract from divs with specific patterns (e.g., spec-name/spec-value classes)
        for div in soup.find_all("div", class_=["spec", "specification", "product-spec"]):
            # Look for label/value pairs
            label = div.find(class_=["spec-label", "spec-name", "label"])
            value = div.find(class_=["spec-value", "spec-data", "value"])
            if label and value:
                k = label.get_text(" ", strip=True)
                v = value.get_text(" ", strip=True)
                if k and v:
                    kv[k] = v
        
        return kv
    
    def extract_pdf_specs_with_docling(self, pdf_content: bytes) -> Tuple[str, dict]:
        """Extract text and structured data from PDF using Docling"""
        try:
            # Save PDF to temporary file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_path = Path(tmp_file.name)
            
            # Initialize Docling converter
            converter = DocumentConverter()
            
            # Convert PDF
            result = converter.convert(tmp_path)
            
            # Extract text
            full_text = result.document.export_to_markdown()
            
            # Extract tables as key-value pairs
            kv = {}
            if hasattr(result.document, 'tables') and result.document.tables:
                for table in result.document.tables:
                    # Process each table to extract key-value pairs
                    if hasattr(table, 'data') and len(table.data) > 0:
                        # If table has headers in first row
                        if len(table.data[0]) >= 2:
                            for row in table.data[1:]:  # Skip header row
                                if len(row) >= 2:
                                    k = str(row[0]).strip()
                                    v = str(row[1]).strip()
                                    if k and v:
                                        kv[k] = v
                        
                        # Also try treating first column as keys
                        for row in table.data:
                            if len(row) >= 2:
                                k = str(row[0]).strip()
                                v = str(row[1]).strip()
                                if k and v and not k.lower() in ['parameter', 'specification', 'spec', 'feature']:
                                    kv[k] = v
            
            # Clean up temp file
            tmp_path.unlink()
            
            return full_text, kv
            
        except Exception as e:
            print(f"Docling extraction failed: {e}, falling back to pdfplumber")
            # Fallback to pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
                text = "\n".join(pages)
            return text, {}
