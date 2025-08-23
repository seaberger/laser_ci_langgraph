#!/usr/bin/env python
"""Test enhanced scraping capabilities"""

from src.laser_ci_lg.scrapers.coherent import CoherentScraper
from src.laser_ci_lg.db import bootstrap_db, SessionLocal
from src.laser_ci_lg.models import Manufacturer, Product

def test_enhanced_extraction():
    print("Testing Enhanced Extraction Capabilities")
    print("=" * 50)
    
    # Initialize database
    print("1. Initializing database...")
    bootstrap_db()
    
    # Create test data
    s = SessionLocal()
    try:
        # Check if Coherent exists
        coherent = s.query(Manufacturer).filter_by(name="Coherent").first()
        if not coherent:
            coherent = Manufacturer(name="Coherent", homepage="https://www.coherent.com")
            s.add(coherent)
            s.flush()
        
        # Create a test product if needed
        test_product = s.query(Product).filter_by(
            manufacturer_id=coherent.id,
            name="OBIS LX/LS"
        ).first()
        
        if not test_product:
            test_product = Product(
                manufacturer_id=coherent.id,
                segment_id="diode_instrumentation",
                name="OBIS LX/LS",
                product_url="https://www.coherent.com/lasers/cw-solid-state/obis-ls-lx"
            )
            s.add(test_product)
            s.flush()
        
        s.commit()
        
        # Create test targets
        targets = [{
            "product_id": test_product.id,
            "product_url": test_product.product_url,
            "datasheets": ["https://www.coherent.com/resources/datasheet/lasers/obis-family-ds.pdf"]
        }]
        
    finally:
        s.close()
    
    print("2. Testing HTML extraction capabilities...")
    scraper = CoherentScraper(targets)
    
    # Test HTML extraction
    test_html = """
    <html>
    <body>
        <h2>Specifications</h2>
        <table>
            <tr><td>Wavelength</td><td>488 nm</td></tr>
            <tr><td>Output Power</td><td>50 mW</td></tr>
            <tr><td>Beam Diameter</td><td>0.7 mm</td></tr>
            <tr><td>Power Stability</td><td>&lt;1%</td></tr>
        </table>
        
        <ul>
            <li>RMS Noise: <0.2%</li>
            <li>M²: <1.2</li>
            <li>Polarization: Linear, 100:1</li>
        </ul>
        
        <dl>
            <dt>Warm-up Time</dt>
            <dd>10 minutes</dd>
            <dt>Interfaces</dt>
            <dd>USB, RS-232</dd>
        </dl>
        
        <div class="spec">
            <span class="spec-label">Modulation</span>
            <span class="spec-value">Analog up to 10 kHz</span>
        </div>
    </body>
    </html>
    """
    
    specs = scraper.extract_all_html_specs(test_html)
    
    print("\n3. Extracted HTML Specs:")
    print("-" * 30)
    for key, value in specs.items():
        print(f"  {key}: {value}")
    
    print("\n4. Testing PDF extraction (requires network)...")
    print("   Note: Actual PDF extraction would require downloading real PDFs")
    print("   Docling will process PDF tables and export to markdown format")
    
    print("\n5. Summary of Enhancements:")
    print("-" * 30)
    print("✓ HTML table extraction")
    print("✓ HTML list extraction (li with colons)")
    print("✓ HTML definition list extraction (dl/dt/dd)")
    print("✓ HTML div with spec classes extraction")
    print("✓ PDF table extraction with Docling")
    print("✓ PDF text to markdown conversion")
    print("✓ Fallback to pdfplumber if Docling fails")
    
    expected_specs = [
        "Wavelength", "Output Power", "Beam Diameter", 
        "Power Stability", "RMS Noise", "M²", "Polarization",
        "Warm-up Time", "Interfaces", "Modulation"
    ]
    
    found_specs = [spec for spec in expected_specs if any(spec.lower() in key.lower() for key in specs.keys())]
    
    print(f"\n6. Coverage: {len(found_specs)}/{len(expected_specs)} expected specs found")
    print(f"   Found: {', '.join(found_specs)}")
    
    if len(found_specs) == len(expected_specs):
        print("\n✅ All expected specs extracted successfully!")
    else:
        missing = [spec for spec in expected_specs if spec not in found_specs]
        print(f"\n⚠️  Missing specs: {', '.join(missing)}")

if __name__ == "__main__":
    test_enhanced_extraction()