"""
Enhanced reporting system for comprehensive competitive intelligence analysis.

This module provides detailed reports comparing Coherent products against competitors,
including market positioning, technical advantages, and feature comparisons.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional
import json
from sqlalchemy import select
from .db import SessionLocal
from .models import Manufacturer, Product, NormalizedSpec, RawDocument


class CompetitiveIntelligenceReport:
    """Generate comprehensive competitive intelligence reports."""
    
    def __init__(self):
        self.session = SessionLocal()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def generate_executive_summary(self) -> str:
        """Generate executive summary of competitive landscape."""
        lines = ["# Competitive Intelligence Executive Summary", ""]
        lines.append(f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
        lines.append("")
        
        # Get vendor summary
        vendors = self.session.execute(
            select(Manufacturer).order_by(Manufacturer.name)
        ).scalars().all()
        
        lines.append("## Market Overview")
        lines.append(f"- **Total Vendors Monitored**: {len(vendors)}")
        lines.append(f"- **Vendors**: {', '.join([v.name for v in vendors])}")
        lines.append("")
        
        # Product count by vendor
        lines.append("## Product Portfolio")
        for vendor in vendors:
            products = self.session.query(Product).filter_by(manufacturer_id=vendor.id).all()
            is_coherent = vendor.name == "Coherent"
            marker = "**" if is_coherent else ""
            lines.append(f"- {marker}{vendor.name}{marker}: {len(products)} products")
            for p in products:
                lines.append(f"  - {p.name}")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_technical_comparison(self) -> str:
        """Generate detailed technical comparison report."""
        lines = ["## Technical Specifications Comparison", ""]
        
        # Get all normalized specs grouped by wavelength
        specs_by_wavelength = defaultdict(list)
        
        results = self.session.execute(
            select(NormalizedSpec, Product, Manufacturer)
            .join(Product, NormalizedSpec.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .order_by(NormalizedSpec.wavelength_nm, Manufacturer.name)
        ).all()
        
        for spec, product, manufacturer in results:
            if spec.wavelength_nm:
                wl_band = int(round(spec.wavelength_nm))
                specs_by_wavelength[wl_band].append({
                    'vendor': manufacturer.name,
                    'product': product.name,
                    'power_mw': spec.output_power_mw_nominal,
                    'noise_pct': spec.rms_noise_pct,
                    'stability_pct': spec.power_stability_pct,
                    'linewidth_mhz': spec.linewidth_mhz,
                    'beam_quality': spec.m2,
                    'is_coherent': manufacturer.name == "Coherent"
                })
        
        # Generate comparison tables
        for wavelength in sorted(specs_by_wavelength.keys()):
            products = specs_by_wavelength[wavelength]
            coherent_products = [p for p in products if p['is_coherent']]
            competitor_products = [p for p in products if not p['is_coherent']]
            
            if coherent_products and competitor_products:
                lines.append(f"### {wavelength} nm Wavelength")
                lines.append("")
                lines.append("| Vendor | Product | Power (mW) | RMS Noise (%) | Stability (%) | Linewidth (MHz) | M² |")
                lines.append("|--------|---------|------------|---------------|---------------|-----------------|-----|")
                
                # Show Coherent first
                for p in coherent_products:
                    lines.append(self._format_product_row(p, highlight=True))
                
                # Then competitors
                for p in competitor_products:
                    lines.append(self._format_product_row(p))
                
                lines.append("")
                
                # Add competitive advantage summary
                advantages = self._analyze_advantages(coherent_products[0], competitor_products)
                if advantages:
                    lines.append("**Coherent Advantages:**")
                    for adv in advantages:
                        lines.append(f"- {adv}")
                    lines.append("")
        
        return "\n".join(lines)
    
    def _format_product_row(self, product: Dict, highlight: bool = False) -> str:
        """Format a product row for the comparison table."""
        vendor = f"**{product['vendor']}**" if highlight else product['vendor']
        
        def fmt_val(val, suffix=""):
            if val is None:
                return "-"
            if isinstance(val, float):
                return f"{val:.2f}{suffix}"
            return f"{val}{suffix}"
        
        return f"| {vendor} | {product['product']} | {fmt_val(product['power_mw'])} | {fmt_val(product['noise_pct'])} | {fmt_val(product['stability_pct'])} | {fmt_val(product['linewidth_mhz'])} | {fmt_val(product['beam_quality'])} |"
    
    def _analyze_advantages(self, coherent: Dict, competitors: List[Dict]) -> List[str]:
        """Analyze Coherent's competitive advantages."""
        advantages = []
        
        # Check power advantage
        if coherent['power_mw']:
            comp_powers = [c['power_mw'] for c in competitors if c['power_mw']]
            if comp_powers and coherent['power_mw'] > max(comp_powers):
                advantage_pct = ((coherent['power_mw'] - max(comp_powers)) / max(comp_powers)) * 100
                advantages.append(f"Higher output power: {advantage_pct:.0f}% above nearest competitor")
        
        # Check noise advantage
        if coherent['noise_pct']:
            comp_noise = [c['noise_pct'] for c in competitors if c['noise_pct']]
            if comp_noise and coherent['noise_pct'] < min(comp_noise):
                advantages.append(f"Lower RMS noise: {coherent['noise_pct']:.2f}% vs {min(comp_noise):.2f}% best competitor")
        
        # Check stability advantage
        if coherent['stability_pct']:
            comp_stability = [c['stability_pct'] for c in competitors if c['stability_pct']]
            if comp_stability and coherent['stability_pct'] < min(comp_stability):
                advantages.append(f"Better power stability: {coherent['stability_pct']:.2f}% vs {min(comp_stability):.2f}%")
        
        # Check linewidth advantage
        if coherent['linewidth_mhz']:
            comp_linewidth = [c['linewidth_mhz'] for c in competitors if c['linewidth_mhz']]
            if comp_linewidth and coherent['linewidth_mhz'] < min(comp_linewidth):
                advantages.append(f"Narrower linewidth: {coherent['linewidth_mhz']:.1f} MHz vs {min(comp_linewidth):.1f} MHz")
        
        return advantages
    
    def generate_feature_comparison(self) -> str:
        """Generate feature comparison from raw specs."""
        lines = ["## Feature Comparison", ""]
        
        # Get raw specs for feature analysis
        results = self.session.execute(
            select(RawDocument, Product, Manufacturer)
            .join(Product, RawDocument.product_id == Product.id)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .where(RawDocument.raw_specs != None)
            .order_by(Manufacturer.name, Product.name)
        ).all()
        
        feature_matrix = defaultdict(lambda: defaultdict(str))
        all_features = set()
        
        for doc, product, manufacturer in results:
            if doc.raw_specs:
                try:
                    # raw_specs might be dict or JSON string
                    if isinstance(doc.raw_specs, dict):
                        specs = doc.raw_specs
                    else:
                        specs = json.loads(doc.raw_specs)
                    key = f"{manufacturer.name} - {product.name}"
                    
                    # Extract key features
                    feature_mappings = {
                        'TTL Modulation': ['TTL', 'ttl', 'TTL shutter'],
                        'Analog Modulation': ['Analog', 'analog modulation'],
                        'RS-232': ['RS-232', 'RS232', 'serial'],
                        'USB Control': ['USB', 'usb'],
                        'Ethernet': ['Ethernet', 'ethernet'],
                        'Fiber Output': ['fiber', 'Fiber Output', 'FC/PC', 'FC/APC'],
                        'Temperature Control': ['TEC', 'temperature control', 'Temperature Range'],
                        'Power Monitoring': ['power monitor', 'Power Monitoring'],
                    }
                    
                    for feature_name, keywords in feature_mappings.items():
                        for keyword in keywords:
                            if any(keyword in str(v) for v in specs.values()):
                                feature_matrix[key][feature_name] = "✓"
                                all_features.add(feature_name)
                                break
                    
                    # Add control interfaces
                    if 'Control Interfaces' in specs:
                        interfaces = specs['Control Interfaces']
                        if 'TTL' in interfaces:
                            feature_matrix[key]['TTL Modulation'] = "✓"
                            all_features.add('TTL Modulation')
                        if 'USB' in interfaces:
                            feature_matrix[key]['USB Control'] = "✓"
                            all_features.add('USB Control')
                        if 'RS-232' in interfaces:
                            feature_matrix[key]['RS-232'] = "✓"
                            all_features.add('RS-232')
                        if 'Ethernet' in interfaces:
                            feature_matrix[key]['Ethernet'] = "✓"
                            all_features.add('Ethernet')
                            
                except json.JSONDecodeError:
                    continue
        
        if feature_matrix and all_features:
            # Sort features by importance
            feature_order = ['TTL Modulation', 'Analog Modulation', 'USB Control', 
                           'RS-232', 'Ethernet', 'Fiber Output', 
                           'Temperature Control', 'Power Monitoring']
            ordered_features = [f for f in feature_order if f in all_features]
            
            # Create feature comparison table
            lines.append("| Product | " + " | ".join(ordered_features) + " |")
            lines.append("|---------|" + "|".join(["---------"] * len(ordered_features)) + "|")
            
            # Sort products with Coherent first
            sorted_products = sorted(feature_matrix.keys(), 
                                    key=lambda x: (not x.startswith("Coherent"), x))
            
            for product in sorted_products:
                is_coherent = product.startswith("Coherent")
                prod_name = f"**{product}**" if is_coherent else product
                row = [prod_name]
                for feature in ordered_features:
                    value = feature_matrix[product].get(feature, "")
                    row.append(value)
                lines.append("| " + " | ".join(row) + " |")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_market_positioning(self) -> str:
        """Generate market positioning analysis."""
        lines = ["## Market Positioning Analysis", ""]
        
        # Analyze by segment
        segments = defaultdict(list)
        
        results = self.session.execute(
            select(Product, Manufacturer, NormalizedSpec)
            .join(Manufacturer, Product.manufacturer_id == Manufacturer.id)
            .outerjoin(NormalizedSpec, Product.id == NormalizedSpec.product_id)
            .order_by(Product.segment_id, Manufacturer.name)
        ).all()
        
        for product, manufacturer, spec in results:
            segments[product.segment_id].append({
                'vendor': manufacturer.name,
                'product': product.name,
                'has_specs': spec is not None,
                'power': spec.output_power_mw_nominal if spec else None,
                'wavelength': spec.wavelength_nm if spec else None
            })
        
        for segment, products in segments.items():
            lines.append(f"### {segment.replace('_', ' ').title()}")
            
            coherent_count = sum(1 for p in products if p['vendor'] == 'Coherent')
            total_count = len(products)
            
            lines.append(f"- **Coherent Market Share**: {coherent_count}/{total_count} products")
            
            # Power range analysis
            powers = [p['power'] for p in products if p['power']]
            if powers:
                coherent_powers = [p['power'] for p in products 
                                 if p['vendor'] == 'Coherent' and p['power']]
                if coherent_powers:
                    lines.append(f"- **Coherent Power Range**: {min(coherent_powers):.0f}-{max(coherent_powers):.0f} mW")
                    lines.append(f"- **Market Power Range**: {min(powers):.0f}-{max(powers):.0f} mW")
            
            # Wavelength coverage
            wavelengths = [p['wavelength'] for p in products if p['wavelength']]
            if wavelengths:
                unique_wl = sorted(set(int(round(w)) for w in wavelengths))
                coherent_wl = sorted(set(int(round(p['wavelength'])) for p in products 
                                       if p['vendor'] == 'Coherent' and p['wavelength']))
                if coherent_wl:
                    lines.append(f"- **Coherent Wavelengths**: {', '.join(map(str, coherent_wl))} nm")
                    lines.append(f"- **Market Wavelengths**: {', '.join(map(str, unique_wl[:10]))} nm" + 
                               (" ..." if len(unique_wl) > 10 else ""))
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_full_report(self) -> str:
        """Generate comprehensive competitive intelligence report."""
        sections = []
        
        # Add all sections
        sections.append(self.generate_executive_summary())
        sections.append(self.generate_market_positioning())
        sections.append(self.generate_technical_comparison())
        sections.append(self.generate_feature_comparison())
        
        # Add recommendations
        sections.append(self._generate_recommendations())
        
        return "\n".join(sections)
    
    def _generate_recommendations(self) -> str:
        """Generate strategic recommendations based on analysis."""
        lines = ["## Strategic Recommendations", ""]
        
        recommendations = [
            "### Competitive Advantages to Emphasize:",
            "- Superior power stability and RMS noise specifications",
            "- Comprehensive control interface options (TTL, Analog, USB, RS-232)",
            "- Proven reliability with established product lines",
            "",
            "### Areas for Development:",
            "- Consider expanding wavelength coverage in gaps identified in market analysis",
            "- Evaluate competitor features not currently offered",
            "",
            "### Market Opportunities:",
            "- Target applications requiring high stability and low noise",
            "- Focus on segments where Coherent has technical superiority",
        ]
        
        lines.extend(recommendations)
        return "\n".join(lines)


def generate_competitive_report():
    """Main entry point for generating competitive intelligence report."""
    with CompetitiveIntelligenceReport() as reporter:
        return reporter.generate_full_report()