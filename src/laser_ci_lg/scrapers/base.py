from abc import ABC, abstractmethod
from typing import Iterable
import requests, pdfplumber, io
from bs4 import BeautifulSoup


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
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages)
        return r.status_code, ctype, text

    def extract_table_kv_pairs(self, html_text: str) -> dict:
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
