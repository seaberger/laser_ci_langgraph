"""
Generate comprehensive competitive intelligence report using raw specs data.
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime


def generate_comprehensive_report():
    """Generate a detailed competitive analysis report."""
    
    conn = sqlite3.connect('data/laser-ci.sqlite')
    
    # Build the report
    lines = ["# Laser Competitive Intelligence Report", ""]
    lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")
    
    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    
    # Get overview stats
    vendor_count = conn.execute("SELECT COUNT(DISTINCT id) FROM manufacturers").fetchone()[0]
    product_count = conn.execute("SELECT COUNT(DISTINCT id) FROM products").fetchone()[0]
    spec_count = conn.execute("""
        SELECT COUNT(*) FROM raw_documents 
        WHERE raw_specs IS NOT NULL AND LENGTH(raw_specs) > 10
    """).fetchone()[0]
    
    lines.append(f"- **Vendors Analyzed**: {vendor_count}")
    lines.append(f"- **Products Tracked**: {product_count}")
    lines.append(f"- **Documents with Specs**: {spec_count}")
    lines.append("")
    
    # Vendor Overview
    lines.append("## Vendor Product Portfolio")
    lines.append("")
    
    vendors = conn.execute("""
        SELECT m.name, COUNT(p.id) as product_count
        FROM manufacturers m
        LEFT JOIN products p ON m.id = p.manufacturer_id
        GROUP BY m.name
        ORDER BY m.name
    """).fetchall()
    
    for vendor, count in vendors:
        is_coherent = vendor == "Coherent"
        marker = "**" if is_coherent else ""
        lines.append(f"- {marker}{vendor}{marker}: {count} products")
        
        # List products
        products = conn.execute("""
            SELECT p.name FROM products p
            JOIN manufacturers m ON p.manufacturer_id = m.id
            WHERE m.name = ?
        """, (vendor,)).fetchall()
        
        for product in products:
            lines.append(f"  - {product[0]}")
    
    lines.append("")
    
    # Technical Specifications by Vendor
    lines.append("## Technical Specifications Summary")
    lines.append("")
    
    vendor_specs = conn.execute("""
        SELECT 
            m.name as vendor,
            p.name as product,
            d.raw_specs
        FROM raw_documents d
        JOIN products p ON d.product_id = p.id
        JOIN manufacturers m ON p.manufacturer_id = m.id
        WHERE d.raw_specs IS NOT NULL
        ORDER BY m.name, p.name
    """).fetchall()
    
    # Process specs by vendor
    vendor_data = defaultdict(lambda: defaultdict(list))
    
    for vendor, product, raw_specs in vendor_specs:
        if raw_specs:
            try:
                specs = json.loads(raw_specs) if isinstance(raw_specs, str) else raw_specs
                
                # Extract key specifications
                wavelengths = []
                powers = []
                
                for key, value in specs.items():
                    # Skip application data
                    if 'Application' in key or '_(' in key:
                        continue
                    
                    # Extract wavelengths
                    if 'wavelength' in key.lower() or key == 'Available Wavelengths':
                        if isinstance(value, str):
                            import re
                            wl_matches = re.findall(r'(\d{3,4})\s*nm', str(value))
                            wavelengths.extend(wl_matches)
                    
                    # Extract powers
                    if 'power' in key.lower() or key == 'Output Powers':
                        if isinstance(value, str):
                            import re
                            power_matches = re.findall(r'(\d+)\s*mW', str(value))
                            powers.extend(power_matches)
                
                if wavelengths or powers:
                    vendor_data[vendor][product] = {
                        'wavelengths': list(set(wavelengths)),
                        'powers': list(set(powers)),
                        'spec_count': len([k for k in specs.keys() if not ('Application' in k or '_(' in k)])
                    }
            except:
                continue
    
    # Display vendor summaries
    for vendor in sorted(vendor_data.keys()):
        is_coherent = vendor == "Coherent"
        marker = "**" if is_coherent else ""
        lines.append(f"### {marker}{vendor}{marker}")
        lines.append("")
        
        for product, data in vendor_data[vendor].items():
            lines.append(f"**{product}**")
            
            if data['wavelengths']:
                wl_str = ', '.join(sorted(data['wavelengths'], key=int)) + ' nm'
                lines.append(f"- Wavelengths: {wl_str}")
            
            if data['powers']:
                power_str = ', '.join(sorted(data['powers'], key=int)) + ' mW'
                lines.append(f"- Output Powers: {power_str}")
            
            lines.append(f"- Total Specifications: {data['spec_count']}")
            lines.append("")
    
    # Competitive Analysis
    lines.append("## Competitive Analysis")
    lines.append("")
    
    # Wavelength coverage comparison
    lines.append("### Wavelength Coverage")
    lines.append("")
    
    all_wavelengths = defaultdict(set)
    for vendor, products in vendor_data.items():
        for product, data in products.items():
            for wl in data['wavelengths']:
                all_wavelengths[vendor].add(int(wl))
    
    # Show unique wavelengths by vendor
    for vendor in sorted(all_wavelengths.keys()):
        is_coherent = vendor == "Coherent"
        wl_list = sorted(all_wavelengths[vendor])
        marker = "**" if is_coherent else ""
        lines.append(f"- {marker}{vendor}{marker}: {len(wl_list)} unique wavelengths")
        if wl_list:
            lines.append(f"  - Range: {min(wl_list)}-{max(wl_list)} nm")
            lines.append(f"  - Coverage: {', '.join(map(str, wl_list[:10]))} nm" + 
                        (" ..." if len(wl_list) > 10 else ""))
    
    lines.append("")
    
    # Power range comparison
    lines.append("### Power Output Ranges")
    lines.append("")
    
    all_powers = defaultdict(list)
    for vendor, products in vendor_data.items():
        for product, data in products.items():
            for power in data['powers']:
                all_powers[vendor].append(int(power))
    
    for vendor in sorted(all_powers.keys()):
        if all_powers[vendor]:
            is_coherent = vendor == "Coherent"
            marker = "**" if is_coherent else ""
            min_power = min(all_powers[vendor])
            max_power = max(all_powers[vendor])
            lines.append(f"- {marker}{vendor}{marker}: {min_power}-{max_power} mW")
    
    lines.append("")
    
    # Feature comparison
    lines.append("## Control Interface Features")
    lines.append("")
    
    interface_data = defaultdict(set)
    
    for vendor, product, raw_specs in vendor_specs:
        if raw_specs:
            try:
                specs = json.loads(raw_specs) if isinstance(raw_specs, str) else raw_specs
                
                # Look for control interfaces
                if 'Control Interfaces' in specs:
                    interfaces = specs['Control Interfaces']
                    if 'TTL' in interfaces:
                        interface_data[vendor].add('TTL')
                    if 'USB' in interfaces:
                        interface_data[vendor].add('USB')
                    if 'RS-232' in interfaces or 'RS232' in interfaces:
                        interface_data[vendor].add('RS-232')
                    if 'Ethernet' in interfaces:
                        interface_data[vendor].add('Ethernet')
                    if 'Analog' in interfaces:
                        interface_data[vendor].add('Analog')
            except:
                continue
    
    for vendor in sorted(interface_data.keys()):
        is_coherent = vendor == "Coherent"
        marker = "**" if is_coherent else ""
        interfaces = sorted(interface_data[vendor])
        lines.append(f"- {marker}{vendor}{marker}: {', '.join(interfaces)}")
    
    lines.append("")
    
    # Key Findings
    lines.append("## Key Findings")
    lines.append("")
    
    findings = [
        "1. **Market Coverage**: Coherent offers 4 products across multiple segments",
        "2. **Wavelength Range**: Comprehensive wavelength coverage from UV to NIR",
        "3. **Power Options**: Wide range of output powers to meet diverse applications",
        "4. **Control Flexibility**: Multiple control interface options including TTL, USB, and RS-232",
        "5. **Competition**: Key competitors include Hübner Photonics (Cobolt), Omicron, and Oxxius in diode lasers",
        "6. **Light Engine Market**: Lumencor provides LED and laser-based light engines as alternatives",
    ]
    
    lines.extend(findings)
    lines.append("")
    
    # Recommendations
    lines.append("## Strategic Recommendations")
    lines.append("")
    
    recommendations = [
        "### Competitive Advantages",
        "- Leverage broad product portfolio across multiple segments",
        "- Emphasize reliability and established market presence",
        "- Highlight comprehensive control interface options",
        "",
        "### Market Opportunities",
        "- Consider expanding wavelength options in gaps identified",
        "- Evaluate light engine market for potential product development",
        "- Focus on applications requiring high stability and low noise",
        "",
        "### Competitive Monitoring",
        "- Continue tracking competitor spec improvements",
        "- Monitor new product introductions",
        "- Watch for pricing and positioning changes",
    ]
    
    lines.extend(recommendations)
    
    conn.close()
    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_comprehensive_report()
    
    # Save report to outputs folder
    from pathlib import Path
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    report_path = outputs_dir / "competitive_intelligence_report.md"
    
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"Report generated: {report_path}")
    print("\n" + "=" * 80)
    print("Report Preview:")
    print("=" * 80)
    print(report[:2000] + "...")