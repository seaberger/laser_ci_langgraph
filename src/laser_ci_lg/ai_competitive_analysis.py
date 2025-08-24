"""
AI-powered competitive intelligence analysis using OpenAI GPT.

This module sends competitive data to OpenAI for deep analysis,
generating strategic insights and recommendations.
"""

import json
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class AICompetitiveAnalyzer:
    """Generate AI-powered competitive analysis using OpenAI."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Use o3-pro for maximum reasoning performance
        # Available models: o3-pro, o3-2025-04-16, o3-mini, gpt-4o, gpt-4.1
        self.model = os.getenv("OPENAI_MODEL", "o3-pro")
        
        # Check model and provide info
        if self.model == "o3-pro":
            print("Using o3-pro (maximum reasoning performance, 20% fewer errors than o1)")
        elif self.model == "o3-2025-04-16" or self.model == "openai/o3-2025-04-16":
            print("Using o3 (advanced reasoning model)")
        elif self.model == "o3-mini":
            print("Using o3-mini (cost-efficient reasoning model)")
        elif "gpt-4.1" in self.model:
            print(f"Using {self.model} (latest GPT-4.1 series)")
        elif self.model == "gpt-4o":
            print("Using GPT-4o (optimized for speed)")
        else:
            print(f"Using model: {self.model}")
        
        self.conn = sqlite3.connect('data/laser-ci.sqlite')
    
    def gather_competitive_data(self) -> Dict[str, Any]:
        """Gather all competitive intelligence data for analysis."""
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'vendors': {},
            'market_overview': {},
            'raw_capabilities': {}
        }
        
        # Get vendor and product data
        vendors = self.conn.execute("""
            SELECT m.name, m.homepage, COUNT(p.id) as product_count
            FROM manufacturers m
            LEFT JOIN products p ON m.id = p.manufacturer_id
            GROUP BY m.name
            ORDER BY m.name
        """).fetchall()
        
        for vendor_name, homepage, product_count in vendors:
            data['vendors'][vendor_name] = {
                'homepage': homepage,
                'product_count': product_count,
                'products': [],
                'specifications': {},
                'capabilities': {}
            }
            
            # Get products and specs for this vendor
            products = self.conn.execute("""
                SELECT 
                    p.name as product,
                    p.segment_id,
                    d.url,
                    d.content_type,
                    d.raw_specs
                FROM products p
                LEFT JOIN raw_documents d ON p.id = d.product_id
                JOIN manufacturers m ON p.manufacturer_id = m.id
                WHERE m.name = ?
            """, (vendor_name,)).fetchall()
            
            for product, segment, url, content_type, raw_specs in products:
                product_data = {
                    'name': product,
                    'segment': segment,
                    'wavelengths': [],
                    'powers': [],
                    'features': [],
                    'control_interfaces': [],
                    'spec_count': 0
                }
                
                if raw_specs:
                    try:
                        specs = json.loads(raw_specs) if isinstance(raw_specs, str) else raw_specs
                        
                        # Extract key information
                        for key, value in specs.items():
                            # Skip application data
                            if 'Application' in key or '_(' in key:
                                continue
                            
                            # Wavelengths
                            if 'wavelength' in key.lower() or key == 'Available Wavelengths':
                                if isinstance(value, str):
                                    import re
                                    wl_matches = re.findall(r'(\d{3,4})\s*nm', str(value))
                                    product_data['wavelengths'].extend([int(w) for w in wl_matches])
                            
                            # Powers
                            if 'power' in key.lower() or key == 'Output Powers':
                                if isinstance(value, str):
                                    import re
                                    power_matches = re.findall(r'(\d+)\s*mW', str(value))
                                    product_data['powers'].extend([int(p) for p in power_matches])
                            
                            # Control interfaces
                            if key == 'Control Interfaces':
                                interfaces = value.split(', ') if isinstance(value, str) else []
                                product_data['control_interfaces'] = interfaces
                            
                            # Count non-application specs
                            product_data['spec_count'] += 1
                        
                        # Deduplicate
                        product_data['wavelengths'] = sorted(list(set(product_data['wavelengths'])))
                        product_data['powers'] = sorted(list(set(product_data['powers'])))
                        
                    except Exception as e:
                        print(f"Error processing specs for {vendor_name} - {product}: {e}")
                
                # Add to vendor data
                if product not in [p['name'] for p in data['vendors'][vendor_name]['products']]:
                    data['vendors'][vendor_name]['products'].append(product_data)
        
        # Calculate market overview
        data['market_overview'] = {
            'total_vendors': len(data['vendors']),
            'total_products': sum(v['product_count'] for v in data['vendors'].values()),
            'vendor_names': list(data['vendors'].keys()),
            'coherent_product_count': data['vendors'].get('Coherent', {}).get('product_count', 0)
        }
        
        return data
    
    def generate_ai_analysis(self, data: Dict[str, Any]) -> str:
        """Send data to OpenAI for comprehensive analysis."""
        
        # Prepare the prompt
        prompt = f"""
You are a competitive intelligence analyst specializing in the laser and photonics industry. 
Analyze the following competitive data and generate a comprehensive strategic report for Coherent Corporation.

COMPETITIVE DATA:
{json.dumps(data, indent=2)}

Generate a detailed competitive intelligence report with the following sections:

1. EXECUTIVE SUMMARY
   - Key findings and immediate action items
   - Coherent's current market position
   - Critical competitive threats and opportunities

2. MARKET LANDSCAPE ANALYSIS
   - Market segmentation and size
   - Vendor positioning and specialization
   - Technology trends and gaps

3. COMPETITIVE POSITIONING
   - Coherent's strengths vs. competitors
   - Wavelength coverage comparison
   - Power output capabilities
   - Product portfolio gaps

4. TECHNICAL DIFFERENTIATION
   - Feature comparison matrix
   - Control interface capabilities
   - Unique selling propositions by vendor
   - Technology leadership areas

5. COMPETITIVE THREATS
   - Direct competitive overlaps
   - Emerging threats from each competitor
   - Market share risks

6. STRATEGIC OPPORTUNITIES
   - Unserved wavelength ranges
   - Power output gaps in the market
   - Feature differentiation opportunities
   - Potential partnership or acquisition targets

7. STRATEGIC RECOMMENDATIONS
   - Short-term actions (0-6 months)
   - Medium-term initiatives (6-18 months)
   - Long-term strategic positioning
   - R&D investment priorities

8. COMPETITIVE INTELLIGENCE INSIGHTS
   - Notable patterns in competitor offerings
   - Pricing strategy implications
   - Customer segment targeting recommendations

Format the report in Markdown with clear headers, bullet points, and emphasis where appropriate.
Focus on actionable insights rather than just data presentation.
Highlight Coherent's position using **bold** text.
"""
        
        # Call OpenAI with latest API patterns
        try:
            # Use structured output for better analysis if available
            messages = [
                {
                    "role": "system", 
                    "content": "You are an expert competitive intelligence analyst in the laser and photonics industry, providing strategic insights for executive decision-making. Focus on actionable recommendations and competitive advantages."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Configure for o3 reasoning models
            completion_params = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": 8000,  # o3 uses max_completion_tokens
            }
            
            # Add o3 specific parameters for reasoning models
            if self.model in ["o3-pro", "o3-2025-04-16", "openai/o3-2025-04-16", "o3-mini"]:
                # o3 reasoning models support reasoning_effort parameter
                if self.model == "o3-pro":
                    completion_params["reasoning_effort"] = "high"  # Maximum for o3-pro
                    print(f"Using o3-pro with high reasoning effort for deep analysis...")
                elif self.model == "o3-mini":
                    completion_params["reasoning_effort"] = "medium"  # Options: low, medium, high
                    print(f"Using o3-mini with medium reasoning effort...")
                else:
                    completion_params["reasoning_effort"] = "high"  # High for full o3
                    print(f"Using o3 with high reasoning effort...")
            else:
                # Standard models use temperature
                completion_params["temperature"] = 0.7
                completion_params["max_tokens"] = completion_params.pop("max_completion_tokens")
            
            response = self.client.chat.completions.create(**completion_params)
            
            # Handle response based on model type
            if hasattr(response.choices[0].message, 'content'):
                return response.choices[0].message.content
            else:
                # Handle potential new response format
                return str(response.choices[0].message)
            
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return self._generate_fallback_report(data)
    
    def _generate_fallback_report(self, data: Dict[str, Any]) -> str:
        """Generate a basic report if OpenAI fails."""
        
        lines = ["# Competitive Intelligence Report", ""]
        lines.append("*Note: AI analysis unavailable, showing basic data summary*")
        lines.append("")
        
        lines.append("## Market Overview")
        lines.append(f"- Total Vendors: {data['market_overview']['total_vendors']}")
        lines.append(f"- Total Products: {data['market_overview']['total_products']}")
        lines.append(f"- Coherent Products: {data['market_overview']['coherent_product_count']}")
        lines.append("")
        
        lines.append("## Vendor Summary")
        for vendor, vdata in data['vendors'].items():
            is_coherent = vendor == "Coherent"
            marker = "**" if is_coherent else ""
            lines.append(f"- {marker}{vendor}{marker}: {vdata['product_count']} products")
        
        return "\n".join(lines)
    
    def generate_report(self) -> str:
        """Main method to generate the AI-powered competitive report."""
        
        print("Gathering competitive intelligence data...")
        data = self.gather_competitive_data()
        
        print(f"Analyzing data for {len(data['vendors'])} vendors...")
        print("Sending to OpenAI for strategic analysis...")
        
        report = self.generate_ai_analysis(data)
        
        # Add metadata
        model_display = {
            "o3-pro": "o3-pro (Maximum Reasoning Performance)",
            "o3-2025-04-16": "o3 (Advanced Reasoning)",
            "openai/o3-2025-04-16": "o3 (Advanced Reasoning)",
            "o3-mini": "o3-mini (Efficient Reasoning)",
            "gpt-4.1": "GPT-4.1 (Latest)",
            "gpt-4.1-mini": "GPT-4.1 Mini",
            "gpt-4o": "GPT-4o (Optimized)"
        }.get(self.model, self.model)
        
        header = f"""# AI-Powered Competitive Intelligence Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*
*Analysis Model: {model_display}*
*Powered by OpenAI o3 Reasoning Models (August 2025)*

---

"""
        
        return header + report
    
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()


def generate_ai_competitive_report():
    """Generate AI-powered competitive intelligence report."""
    
    analyzer = AICompetitiveAnalyzer()
    report = analyzer.generate_report()
    
    # Save report to outputs folder
    from pathlib import Path
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    report_path = outputs_dir / "competitive_intelligence_report.md"
    
    with open(report_path, "w") as f:
        f.write(report)
    
    print("\n" + "=" * 80)
    print("AI Competitive Intelligence Report Generated!")
    print("=" * 80)
    print(f"Report saved to: {report_path}")
    print(f"Report length: {len(report)} characters")
    
    # Show preview
    print("\nReport Preview:")
    print("-" * 80)
    preview_lines = report.split('\n')[:30]
    print('\n'.join(preview_lines))
    if len(report.split('\n')) > 30:
        print("\n... [Full report saved to file]")
    
    return report


if __name__ == "__main__":
    generate_ai_competitive_report()