"""
Enhanced Lumencor scraper with custom extraction logic.

This scraper handles Lumencor's Nuxt/Vue SPA structure by:
1. Using browser automation to render JavaScript content
2. Waiting for specific elements to load
3. Extracting specifications from dynamically loaded content
4. Parsing model configurations and laser line specifications
"""

from .base import BaseScraper
from ..db import SessionLocal
from typing import Dict, Any, List, Tuple
import re
import json
import time


class LumencorEnhancedScraper(BaseScraper):
    """Enhanced scraper for Lumencor with custom extraction."""
    
    def vendor(self) -> str:
        """Return vendor name."""
        return "Lumencor"
    
    def extract_lumencor_specs(self, html: str, url: str) -> Dict[str, Any]:
        """
        Custom extraction for Lumencor's unique page structure.
        
        Lumencor specifications are often embedded in:
        1. Product configuration tables
        2. Model variant descriptions
        3. JavaScript-rendered content
        """
        specs = {}
        
        # Determine product family from URL and content
        # Check URL first for most accurate detection
        url_lower = url.lower()
        html_upper = html.upper()
        
        # Priority order: URL path > page title > content
        if 'sola' in url_lower:
            specs['Product Family'] = 'SOLA Light Engine'
            specs['Type'] = 'White Light LED'
        elif 'spectra-x' in url_lower or 'spectra_x' in url_lower:
            specs['Product Family'] = 'SPECTRA X Light Engine'
            specs['Type'] = 'Multi-Wavelength LED Light Source'
        elif 'spectra' in url_lower and 'spectra-x' not in url_lower:
            specs['Product Family'] = 'SPECTRA Light Engine'
            specs['Type'] = 'LED Light Source'
        elif 'aura' in url_lower:
            specs['Product Family'] = 'AURA Light Engine'
            specs['Type'] = 'LED Light Source'
        elif 'ziva' in url_lower:
            specs['Product Family'] = 'ZIVA Light Engine'
            specs['Type'] = 'Laser Light Source'
        elif 'celesta' in url_lower or 'CELESTA' in html_upper:
            specs['Product Family'] = 'CELESTA Light Engine'
            specs['Type'] = 'Solid-State Laser Light Source'
        elif 'retra' in url_lower:
            specs['Product Family'] = 'RETRA Light Engine'
            specs['Type'] = 'LED Light Source'
        elif 'magma' in url_lower:
            specs['Product Family'] = 'MAGMA Light Engine'
            specs['Type'] = 'LED Light Source'
        
        # If still no match, try to extract from page title
        if 'Product Family' not in specs:
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
                for product in ['CELESTA', 'SOLA', 'SPECTRA X', 'SPECTRA', 'AURA', 'ZIVA', 'RETRA', 'MAGMA']:
                    if product in title.upper():
                        specs['Product Family'] = f'{product} Light Engine'
                        if 'CELESTA' in product or 'ZIVA' in product:
                            specs['Type'] = 'Solid-State Laser Light Source'
                        else:
                            specs['Type'] = 'LED Light Source'
                        break
        
        # Extract wavelengths and powers based on product type
        # SOLA is white light (broadband), others have discrete wavelengths
        if specs.get('Product Family') == 'SOLA Light Engine':
            # SOLA has broadband white light output
            specs['Spectral Range'] = '380-680 nm'
            specs['Output Type'] = 'Broadband White Light'
            
            # Look for power specification
            power_match = re.search(r'(\d+(?:\.\d+)?)\s*W\s*(?:output|power)', html, re.IGNORECASE)
            if not power_match:
                power_match = re.search(r'(\d+)\s*mW\s*(?:output|power)', html, re.IGNORECASE)
            if power_match:
                specs['Output Power'] = power_match.group(1) + (' W' if 'W' in power_match.group(0) else ' mW')
        else:
            # Extract discrete wavelengths and powers
            # Pattern 1: "XXX nm / YYY mW" or "XXX nm, YYY mW"
            wavelength_power_pairs = re.findall(
                r'(\d{3,4})\s*nm\s*[,/]\s*(\d+)\s*mW',
                html, re.IGNORECASE
            )
            
            if wavelength_power_pairs:
                wavelengths = []
                powers = []
                for wl, power in wavelength_power_pairs:
                    wavelengths.append(f"{wl} nm")
                    powers.append(f"{power} mW")
                    specs[f'Wavelength {wl}nm Power'] = f"{power} mW"
                
                if wavelengths:
                    specs['Available Wavelengths'] = ', '.join(sorted(set(wavelengths)))
                if powers:
                    specs['Output Powers'] = ', '.join(sorted(set(powers), key=lambda x: int(x.split()[0])))
        
        # Pattern 2: Look for wavelength lists
        wavelength_lists = re.findall(
            r'(\d{3,4}(?:\s*[,/]\s*\d{3,4})+)\s*nm',
            html, re.IGNORECASE
        )
        
        for wl_list in wavelength_lists:
            wavelengths = re.findall(r'\d{3,4}', wl_list)
            if len(wavelengths) > 1:
                specs['Laser Lines'] = ', '.join([f"{wl} nm" for wl in wavelengths])
                specs['Number of Channels'] = str(len(wavelengths))
                break
        
        # Extract individual wavelengths if no pairs found
        if 'Available Wavelengths' not in specs:
            individual_wavelengths = set(re.findall(r'(\d{3,4})\s*nm', html))
            # Filter reasonable laser wavelengths (350-1100 nm range)
            valid_wavelengths = [
                wl for wl in individual_wavelengths 
                if 350 <= int(wl) <= 1100
            ]
            if valid_wavelengths:
                specs['Available Wavelengths'] = ', '.join([f"{wl} nm" for wl in sorted(valid_wavelengths)])
        
        # Extract power values if not found in pairs
        if 'Output Powers' not in specs:
            individual_powers = set(re.findall(r'(\d+)\s*mW', html))
            # Filter reasonable power values (1-5000 mW range)
            valid_powers = [
                p for p in individual_powers 
                if 1 <= int(p) <= 5000
            ]
            if valid_powers:
                specs['Output Powers'] = ', '.join([f"{p} mW" for p in sorted(valid_powers, key=int)])
        
        # Extract technical specifications from common patterns
        tech_patterns = {
            'Stability': r'stability[:\s]+([<>≤≥]?\s*\d+(?:\.\d+)?\s*%)',
            'Noise': r'noise[:\s]+([<>≤≥]?\s*\d+(?:\.\d+)?\s*%)',
            'Bandwidth': r'bandwidth[:\s]+(\d+(?:\.\d+)?\s*nm)',
            'Beam Diameter': r'beam\s+diameter[:\s]+(\d+(?:\.\d+)?\s*mm)',
            'Divergence': r'divergence[:\s]+(\d+(?:\.\d+)?\s*mrad)',
            'Lifetime': r'lifetime[:\s]+([>,≥]?\s*\d+(?:,\d{3})*\s*hours?)',
            'Warm-up Time': r'warm[\s-]?up[:\s]+(\d+(?:\.\d+)?\s*(?:min|minutes?))',
        }
        
        for spec_name, pattern in tech_patterns.items():
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                specs[spec_name] = match.group(1).strip()
        
        # Look for control interfaces
        if any(term in html.lower() for term in ['ttl', 'analog', 'rs-232', 'usb', 'ethernet']):
            interfaces = []
            if 'ttl' in html.lower():
                interfaces.append('TTL')
            if 'analog' in html.lower():
                interfaces.append('Analog')
            if 'rs-232' in html.lower() or 'rs232' in html.lower():
                interfaces.append('RS-232')
            if 'usb' in html.lower():
                interfaces.append('USB')
            if 'ethernet' in html.lower():
                interfaces.append('Ethernet')
            
            if interfaces:
                specs['Control Interfaces'] = ', '.join(interfaces)
        
        # Extract from NUXT data if present
        nuxt_match = re.search(r'window\.__NUXT__=(.*?);</script>', html, re.DOTALL)
        if nuxt_match:
            try:
                # The NUXT data might contain structured product info
                nuxt_str = nuxt_match.group(1)
                
                # Look for specific product data patterns
                if 'technicalSpecs' in nuxt_str:
                    # Try to extract technical specs section
                    tech_section = re.search(r'technicalSpecs["\']?\s*:\s*["\']?([^"\'};]+)', nuxt_str)
                    if tech_section:
                        specs['Technical Data Available'] = 'Yes'
                
                # Extract model numbers
                model_patterns = re.findall(r'CELESTA[\s-]?(\w+)', nuxt_str, re.IGNORECASE)
                if model_patterns:
                    models = list(set(model_patterns))
                    if models:
                        specs['Model Variants'] = ', '.join(models[:5])
            except:
                pass
        
        return specs
    
    def fetch_with_enhanced_browser(self, url: str) -> Tuple[int, str, str, str, str, Dict]:
        """
        Enhanced browser fetching specifically for Lumencor.
        Waits for dynamic content and interacts with the page as needed.
        """
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()
                
                try:
                    print(f"  → Enhanced browser fetching: {url}")
                    
                    # Navigate to the page
                    response = page.goto(url, wait_until="networkidle", timeout=60000)
                    
                    # Wait for Vue/Nuxt to render
                    page.wait_for_timeout(5000)
                    
                    # Try to find and click on specifications tab if present
                    try:
                        spec_buttons = page.locator('button:has-text("Specification"), button:has-text("Technical"), button:has-text("Specs"), a:has-text("Specification"), a:has-text("Technical")')
                        if spec_buttons.count() > 0:
                            spec_buttons.first.click()
                            page.wait_for_timeout(2000)
                    except:
                        pass
                    
                    # Try to expand any collapsed sections
                    try:
                        expanders = page.locator('[aria-expanded="false"], .collapsed, .accordion-button')
                        for i in range(min(expanders.count(), 5)):
                            try:
                                expanders.nth(i).click()
                                page.wait_for_timeout(500)
                            except:
                                pass
                    except:
                        pass
                    
                    # Scroll to load lazy content
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                    
                    # Get the fully rendered HTML
                    html_content = page.content()
                    
                    # Check if it's a PDF URL that actually delivered a PDF
                    if url.lower().endswith('.pdf'):
                        if html_content.startswith('%PDF'):
                            # It's a real PDF
                            content = html_content.encode()
                            cache_path = self.get_pdf_cache_path(url)
                            cache_path.write_bytes(content)
                            content_hash = self.calculate_content_hash(content)
                            text, raw_specs = self.extract_pdf_specs_with_docling(content)
                            return response.status, "pdf_text", text, content_hash, str(cache_path), raw_specs
                    
                    # Process as HTML with custom extraction
                    content_hash = self.calculate_content_hash(html_content.encode())
                    
                    # Use custom extraction for Lumencor
                    raw_specs = self.extract_lumencor_specs(html_content, url)
                    
                    # Also try standard extraction and merge (but don't overwrite custom fields)
                    standard_specs = self.extract_all_html_specs(html_content)
                    if standard_specs:
                        # Only add specs that don't exist in custom extraction
                        for key, value in standard_specs.items():
                            if key not in raw_specs:
                                raw_specs[key] = value
                    
                    return response.status, "html", html_content, content_hash, None, raw_specs
                    
                finally:
                    browser.close()
                    
        except Exception as e:
            print(f"  → Enhanced browser error: {e}")
            # Fall back to standard browser fetch
            return self.fetch_with_browser(url)
    
    def run(self):
        """Run the enhanced Lumencor scraper."""
        s = SessionLocal()
        try:
            for tgt in self.iter_targets():
                # Use enhanced browser fetching for Lumencor
                status, content_type, text, content_hash, file_path, raw_specs = self.fetch_with_enhanced_browser(tgt["url"])
                
                # Store using base class method
                self.store_document(s, tgt, status, content_type, text, 
                                  content_hash, file_path, raw_specs)
            s.commit()
        finally:
            s.close()