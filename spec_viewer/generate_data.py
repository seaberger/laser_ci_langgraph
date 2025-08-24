#!/usr/bin/env python3
"""
Generate JavaScript data file from the SQLite database for the spec viewer.
Run this script to update the data displayed in the HTML viewer.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

def extract_database_data():
    """Extract product and spec data from the database."""
    
    # Database path
    db_path = Path(__file__).parent.parent / "data" / "laser-ci.sqlite"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query to get all products with their normalized specs AND raw specs
    query = """
    SELECT 
        p.id,
        p.name as product_name,
        m.name as vendor_name,
        ns.wavelength_nm,
        ns.output_power_mw_nominal,
        ns.output_power_mw_min,
        ns.rms_noise_pct,
        ns.power_stability_pct,
        ns.linewidth_mhz,
        ns.linewidth_nm,
        ns.m2,
        ns.beam_diameter_mm,
        ns.beam_divergence_mrad,
        ns.polarization,
        ns.modulation_analog_hz,
        ns.modulation_digital_hz,
        ns.ttl_shutter,
        ns.fiber_output,
        ns.fiber_na,
        ns.fiber_mfd_um,
        ns.warmup_time_min,
        ns.interfaces,
        ns.dimensions_mm,
        ns.vendor_fields,
        rd.raw_specs as raw_specs_json
    FROM products p
    JOIN manufacturers m ON p.manufacturer_id = m.id
    LEFT JOIN normalized_specs ns ON p.id = ns.product_id
    LEFT JOIN (
        SELECT product_id, raw_specs, 
               ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY fetched_at DESC) as rn
        FROM raw_documents
        WHERE raw_specs IS NOT NULL
    ) rd ON p.id = rd.product_id AND rd.rn = 1
    ORDER BY m.name, p.name
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    products = []
    for row in rows:
        product = {
            "id": row["id"],
            "name": row["product_name"],
            "vendor": row["vendor_name"],
            "specs": {}
        }
        
        # Add all spec fields
        spec_fields = [
            "wavelength_nm",
            "output_power_mw_nominal", 
            "output_power_mw_min",
            "rms_noise_pct",
            "power_stability_pct",
            "linewidth_mhz",
            "linewidth_nm",
            "m2",
            "beam_diameter_mm",
            "beam_divergence_mrad",
            "polarization",
            "modulation_analog_hz",
            "modulation_digital_hz",
            "ttl_shutter",
            "fiber_output",
            "fiber_na",
            "fiber_mfd_um",
            "warmup_time_min"
        ]
        
        for field in spec_fields:
            value = row[field]
            # Convert SQLite boolean (0/1) to JavaScript boolean
            if field in ["ttl_shutter", "fiber_output"]:
                if value is not None:
                    value = bool(value)
            product["specs"][field] = value
        
        # Handle JSON fields
        if row["interfaces"]:
            try:
                product["specs"]["interfaces"] = json.loads(row["interfaces"])
            except:
                product["specs"]["interfaces"] = None
        else:
            product["specs"]["interfaces"] = None
            
        if row["dimensions_mm"]:
            try:
                product["specs"]["dimensions_mm"] = json.loads(row["dimensions_mm"])
            except:
                product["specs"]["dimensions_mm"] = None
        else:
            product["specs"]["dimensions_mm"] = None
        
        # Parse vendor_fields JSON if present
        if row["vendor_fields"]:
            try:
                product["specs"]["vendor_fields"] = json.loads(row["vendor_fields"])
            except:
                product["specs"]["vendor_fields"] = None
        else:
            product["specs"]["vendor_fields"] = None
        
        # Add raw specs
        if row["raw_specs_json"]:
            try:
                product["raw_specs"] = json.loads(row["raw_specs_json"])
            except:
                product["raw_specs"] = {}
        else:
            product["raw_specs"] = {}
            
        products.append(product)
    
    conn.close()
    
    # Get last update time from raw_documents
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(fetched_at) as last_update FROM raw_documents")
    last_update = cursor.fetchone()[0]
    conn.close()
    
    if last_update:
        # Parse and format the date
        try:
            dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            last_updated = dt.strftime("%Y-%m-%d")
        except:
            last_updated = datetime.now().strftime("%Y-%m-%d")
    else:
        last_updated = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "products": products,
        "lastUpdated": last_updated
    }

def generate_javascript_file(data):
    """Generate the JavaScript data file."""
    
    if not data:
        print("No data to generate")
        return
    
    # Create the JavaScript content
    js_content = f"""// Auto-generated data from database
// Last generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

const LASER_DATA = {json.dumps(data, indent=2, ensure_ascii=False)};

// Make data available globally
window.LASER_DATA = LASER_DATA;
"""
    
    # Write to file
    output_path = Path(__file__).parent / "js" / "data.js"
    output_path.write_text(js_content, encoding='utf-8')
    
    print(f"Generated {output_path}")
    print(f"  - {len(data['products'])} products")
    print(f"  - Last updated: {data['lastUpdated']}")
    
    # Show vendor breakdown
    vendors = {}
    for product in data['products']:
        vendor = product['vendor']
        vendors[vendor] = vendors.get(vendor, 0) + 1
    
    print("\nVendor breakdown:")
    for vendor, count in sorted(vendors.items()):
        print(f"  - {vendor}: {count} products")

def main():
    """Main function."""
    print("Extracting data from database...")
    data = extract_database_data()
    
    if data:
        print(f"\nFound {len(data['products'])} products")
        generate_javascript_file(data)
        print("\nData generation complete!")
        print("\nTo view the spec viewer:")
        print("  1. Open spec_viewer/index.html in a web browser")
        print("  2. Or run: python -m http.server 8000 in the spec_viewer directory")
        print("     then navigate to http://localhost:8000")
    else:
        print("Failed to extract data from database")

if __name__ == "__main__":
    main()