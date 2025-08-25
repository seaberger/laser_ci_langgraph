"""
Advanced extraction utilities for superior spec extraction from HTML and PDF documents.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from bs4 import BeautifulSoup
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import PdfFormatOption
from pathlib import Path
import tempfile


class SpecPattern:
    """Regex patterns for extracting technical specifications with units."""
    
    # Wavelength patterns: 405±5 nm, 488 nm, 561-570 nm, 632 to 643 nm
    WAVELENGTH = re.compile(
        r'(\d+(?:\.\d+)?)\s*(?:±\s*\d+(?:\.\d+)?)?\s*'
        r'(?:(?:to|-)\s*\d+(?:\.\d+)?)?\s*'
        r'(nm|μm|um|micron)',
        re.IGNORECASE
    )
    
    # Power patterns: 50-100 mW, >50 mW, ≤100 W, 100 mW (typical)
    POWER = re.compile(
        r'([<>≤≥]?\s*\d+(?:\.\d+)?)\s*'
        r'(?:(?:to|-)\s*\d+(?:\.\d+)?)?\s*'
        r'(mW|W|kW|MW)\b',
        re.IGNORECASE
    )
    
    # Ratio patterns: >50:1, 100:1, ≥75:1 (typical)
    RATIO = re.compile(
        r'([<>≤≥]?\s*\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)'
    )
    
    # M² (beam quality) patterns: M²≤1.3, M2<1.1, M² ≤1.3
    BEAM_QUALITY = re.compile(
        r'M[²2]\s*([<>≤≥]?\s*\d+(?:\.\d+)?)',
        re.IGNORECASE
    )
    
    # Temperature patterns: 10-45°C, -20 to +60°C, 25±3°C
    TEMPERATURE = re.compile(
        r'(-?\d+(?:\.\d+)?)\s*'
        r'(?:(?:to|–|-)\s*\+?(-?\d+(?:\.\d+)?))?\s*'
        r'(?:±\s*\d+(?:\.\d+)?)?\s*'
        r'°?C\b',
        re.IGNORECASE
    )
    
    # Percentage patterns: <0.25%, ≤2%, <1% RMS
    PERCENTAGE = re.compile(
        r'([<>≤≥]?\s*\d+(?:\.\d+)?)\s*%'
    )
    
    # Dimension patterns: 155 x 180 x 52.2 mm, 10.2 mm, Ø35.6 mm
    DIMENSION = re.compile(
        r'(?:Ø\s*)?(\d+(?:\.\d+)?)\s*'
        r'(?:x\s*\d+(?:\.\d+)?)*\s*'
        r'(mm|cm|m|in|inch|ft)\b',
        re.IGNORECASE
    )
    
    # Frequency/Bandwidth: 50 kHz, 20 Hz to 20 MHz
    FREQUENCY = re.compile(
        r'(\d+(?:\.\d+)?)\s*'
        r'(?:(?:to|-)\s*\d+(?:\.\d+)?)?\s*'
        r'(Hz|kHz|MHz|GHz)\b',
        re.IGNORECASE
    )
    
    # Voltage/Current: 12±2 V, 5V, 100 mA
    ELECTRICAL = re.compile(
        r'(\d+(?:\.\d+)?)\s*'
        r'(?:±\s*\d+(?:\.\d+)?)?\s*'
        r'(V|mV|kV|A|mA|μA|uA)\b',
        re.IGNORECASE
    )
    
    # Time patterns: <5 minutes, 8 hours, 2500 hours
    TIME = re.compile(
        r'([<>≤≥]?\s*\d+(?:\.\d+)?)\s*'
        r'(minutes?|hours?|seconds?|ms|μs|us|ns)\b',
        re.IGNORECASE
    )


class AdvancedHTMLExtractor:
    """Enhanced HTML table extraction with pandas and complex structure handling."""
    
    def __init__(self):
        self.spec_keywords = [
            'specification', 'parameter', 'characteristic', 'performance',
            'optical', 'electrical', 'mechanical', 'environmental',
            'wavelength', 'power', 'beam', 'noise', 'stability'
        ]
    
    def extract_all_specs(self, html_text: str) -> Dict[str, Any]:
        """Extract specs from HTML using multiple methods."""
        specs = {}
        
        # Try pandas first for structured tables
        specs.update(self._extract_with_pandas(html_text))
        
        # Fallback to BeautifulSoup for complex cases
        specs.update(self._extract_with_beautifulsoup(html_text))
        
        # Extract from unstructured text
        specs.update(self._extract_from_text(html_text))
        
        return specs
    
    def _extract_with_pandas(self, html_text: str) -> Dict[str, Any]:
        """Use pandas to extract tables with automatic handling of complex structures."""
        specs = {}
        
        try:
            # Read all tables from HTML
            from io import StringIO
            tables = pd.read_html(StringIO(html_text), header=[0, 1], index_col=0)
            
            for table in tables:
                # Check if this looks like a spec table
                if self._is_spec_table(table):
                    # Extract specs from DataFrame
                    specs.update(self._dataframe_to_specs(table))
        except Exception as e:
            # Pandas couldn't parse, continue with other methods
            pass
        
        return specs
    
    def _extract_with_beautifulsoup(self, html_text: str) -> Dict[str, Any]:
        """Enhanced BeautifulSoup extraction handling all columns and complex structures."""
        soup = BeautifulSoup(html_text, 'html.parser')
        specs = {}
        
        for table in soup.find_all('table'):
            # Extract all headers (including multi-level)
            headers = self._extract_headers(table)
            
            # Extract all rows with proper column mapping
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell is usually the spec name
                    spec_name = cells[0].get_text(' ', strip=True)
                    
                    # Check for concatenated product table (Omicron issue)
                    # If the value contains multiple product models, split them
                    if any(pattern in spec_name for pattern in ['Wavelength', 'Power', 'Model']):
                        # This might be a header or concatenated table
                        all_text = ' '.join([cell.get_text(' ', strip=True) for cell in cells])
                        extracted = self._extract_from_concatenated_table(all_text)
                        if extracted:
                            specs.update(extracted)
                            continue
                    
                    # Extract values from ALL columns
                    if len(headers) > 0:
                        # Map to headers
                        for i, cell in enumerate(cells[1:], 1):
                            if i < len(headers):
                                key = f"{spec_name}_{headers[i]}" if headers[i] else spec_name
                                value = cell.get_text(' ', strip=True)
                                if value and value not in ['', '-', 'N/A']:
                                    specs[key] = self._parse_value(value)
                    else:
                        # No headers, just extract all values
                        values = [cell.get_text(' ', strip=True) for cell in cells[1:]]
                        values = [v for v in values if v and v not in ['', '-', 'N/A']]
                        if values:
                            # Check if this looks like a concatenated product list
                            if len(values) == 1 and len(values[0]) > 500:
                                # Likely concatenated data, try to extract
                                extracted = self._extract_from_concatenated_table(values[0])
                                if extracted:
                                    specs.update(extracted)
                                else:
                                    specs[spec_name] = self._parse_value(values[0])
                            elif len(values) == 1:
                                specs[spec_name] = self._parse_value(values[0])
                            else:
                                specs[spec_name] = [self._parse_value(v) for v in values]
        
        return specs
    
    def _extract_headers(self, table) -> List[str]:
        """Extract headers from table, handling multi-level headers."""
        headers = []
        
        # Look for thead
        thead = table.find('thead')
        if thead:
            header_rows = thead.find_all('tr')
            if header_rows:
                # Get the last header row (most specific)
                header_cells = header_rows[-1].find_all(['th', 'td'])
                headers = [cell.get_text(' ', strip=True) for cell in header_cells]
        
        # If no thead, check first row
        if not headers:
            first_row = table.find('tr')
            if first_row:
                header_cells = first_row.find_all('th')
                if header_cells:
                    headers = [cell.get_text(' ', strip=True) for cell in header_cells]
        
        return headers
    
    def _extract_from_text(self, html_text: str) -> Dict[str, Any]:
        """Extract specs from unstructured text using regex patterns."""
        soup = BeautifulSoup(html_text, 'html.parser')
        text = soup.get_text(' ', strip=True)
        specs = {}
        
        # Extract wavelengths
        wavelengths = SpecPattern.WAVELENGTH.findall(text)
        if wavelengths:
            specs['wavelengths_nm'] = [f"{val}{unit}" for val, unit in wavelengths]
        
        # Extract power values
        powers = SpecPattern.POWER.findall(text)
        if powers:
            specs['power_values'] = [f"{val}{unit}" for val, unit in powers]
        
        # Extract M² values
        m2_matches = SpecPattern.BEAM_QUALITY.findall(text)
        if m2_matches:
            specs['beam_quality_m2'] = m2_matches[0] if m2_matches else None
        
        # Extract ratios (polarization, extinction, etc.)
        ratios = SpecPattern.RATIO.findall(text)
        if ratios:
            specs['ratios'] = [f"{v1}:{v2}" for v1, v2 in ratios]
        
        return specs
    
    def _extract_from_concatenated_table(self, text: str) -> Dict[str, Any]:
        """Extract specs from concatenated product table text (Omicron/LuxX issue)."""
        specs = {}
        
        # Pattern for LuxX/LBX products: "LuxX® 375-20 375nm / 20mW"
        # or "LBX-405 405nm / 60mW"
        product_pattern = re.compile(
            r'((?:LuxX|LBX|Luxx)[®+]?\s*[\d-]+)\s+'  # Product model
            r'(\d+)\s*nm\s*/\s*(\d+)\s*mW',           # Wavelength / Power
            re.IGNORECASE
        )
        
        matches = product_pattern.findall(text)
        for model, wavelength, power in matches:
            # Clean model name
            model_clean = model.replace('®', '').replace('\xa0', ' ').strip()
            specs[f"{model_clean}_wavelength"] = f"{wavelength}nm"
            specs[f"{model_clean}_power"] = f"{power}mW"
        
        # Also extract as lists for aggregate analysis
        if matches:
            specs['product_models'] = [m[0].replace('®', '').strip() for m in matches]
            specs['wavelengths'] = [f"{m[1]}nm" for m in matches]
            specs['power_levels'] = [f"{m[2]}mW" for m in matches]
        
        return specs
    
    def _parse_value(self, value: str) -> Any:
        """Parse a value string, preserving technical formats."""
        if not value:
            return value
        
        # Don't split ratios
        if ':' in value and re.match(r'\d+\s*:\s*\d+', value):
            return value
        
        # Preserve inequalities
        if any(char in value for char in ['<', '>', '≤', '≥']):
            return value
        
        # Preserve ranges
        if any(sep in value for sep in [' to ', '-', '–', '±']):
            return value
        
        return value
    
    def _is_spec_table(self, df: pd.DataFrame) -> bool:
        """Check if a DataFrame looks like a specification table."""
        # Check column names
        text = str(df.columns).lower() + str(df.index).lower()
        return any(keyword in text for keyword in self.spec_keywords)
    
    def _dataframe_to_specs(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Convert a pandas DataFrame to a specs dictionary with clean keys."""
        specs = {}
        
        # Check if this is a product comparison table (multiple products as columns)
        # vs a single product spec table (spec names in first column)
        first_col_values = df.iloc[:, 0] if len(df.columns) > 0 else []
        
        # If columns look like product names, treat as comparison table
        if len(df.columns) > 1 and all(isinstance(col, str) for col in df.columns):
            # Each column is a product, rows are specs
            for col in df.columns:
                if col and not col.startswith('Unnamed'):
                    product_key = str(col).strip()
                    for index, row in df.iterrows():
                        spec_name = str(index).strip()
                        value = row[col]
                        if pd.notna(value):
                            # Clean the spec name
                            clean_spec = self._clean_spec_name(spec_name)
                            # Create key with product suffix
                            key = f"{clean_spec}_{product_key}"
                            specs[key] = str(value)
        else:
            # Standard extraction - append column to row
            for index, row in df.iterrows():
                spec_name = str(index)
                for col in df.columns:
                    value = row[col]
                    if pd.notna(value):
                        # Clean the spec name
                        clean_spec = self._clean_spec_name(spec_name)
                        # Only append column if it's meaningful
                        if col and not str(col).startswith('Unnamed'):
                            key = f"{clean_spec}_{col}"
                        else:
                            key = clean_spec
                        specs[key] = str(value)
        
        return specs
    
    def _clean_spec_name(self, spec_name: str) -> str:
        """Clean a spec name to make it more normalizable."""
        import re
        
        # Remove footnote numbers (e.g., "Wavelength 1" -> "Wavelength")
        cleaned = re.sub(r'\s+\d+\s*$', '', spec_name)
        
        # Remove units in parentheses at the end
        # "Output Power (mW)" -> "Output Power"
        cleaned = re.sub(r'\s*\([^)]+\)\s*$', '', cleaned)
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned


class AdvancedPDFExtractor:
    """Enhanced PDF extraction with Docling configured for maximum accuracy."""
    
    def __init__(self):
        # Configure Docling for maximum table extraction accuracy
        self.pipeline_options = PdfPipelineOptions(
            do_table_structure=True,
            do_ocr=False,  # OCR not needed for digital PDFs
        )
        self.pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                )
            }
        )
    
    def extract_specs(self, pdf_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract text and structured specs from PDF."""
        specs = {}
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)
        
        try:
            # Convert with Docling
            result = self.converter.convert(tmp_path)
            
            # Get full text
            full_text = result.document.export_to_markdown()
            
            # Extract from tables
            if hasattr(result.document, 'tables') and result.document.tables:
                for table in result.document.tables:
                    specs.update(self._process_docling_table(table))
            
            # Extract from text using patterns
            specs.update(self._extract_from_pdf_text(full_text))
            
        finally:
            # Clean up
            tmp_path.unlink()
        
        return full_text, specs
    
    def _process_docling_table(self, table) -> Dict[str, Any]:
        """Process a Docling table object to extract all specs."""
        specs = {}
        
        try:
            # Try multiple methods to extract table data
            
            # Method 1: Try to get as DataFrame
            if hasattr(table, 'to_dataframe'):
                try:
                    df = table.to_dataframe()
                    specs.update(self._dataframe_to_specs(df))
                    if specs:  # If we got data, return it
                        return specs
                except:
                    pass
            
            # Method 2: Try to get table data directly
            if hasattr(table, 'data'):
                # Process raw table data
                table_data = table.data
                if hasattr(table_data, '__len__') and len(table_data) > 0:
                    # Detect if first row is headers
                    headers = []
                    data_start = 0
                    
                    # Try to detect Oxxius-style table headers
                    # Headers might be: Emission wavelength | Linewidth | Power stability | Output power | Beam waist | M² | Polarization | Digital mod | Analog mod
                    oxxius_headers = [
                        'wavelength', 'linewidth', 'power_stability', 'output_power',
                        'beam_diameter', 'beam_quality', 'polarization', 'digital_mod', 'analog_mod'
                    ]
                    
                    if len(table_data[0]) > 1:
                        # Check if first row looks like headers
                        first_row = [str(cell).lower() for cell in table_data[0]]
                        first_row_text = ' '.join(first_row)
                        
                        # Check for known header patterns
                        if any(keyword in first_row_text for keyword in 
                               ['wavelength', 'power', 'linewidth', 'beam', 'modulation', 
                                'model', 'cellx', '405', '488', '561', '637']):
                            headers = table_data[0]
                            data_start = 1
                        # Special case: Oxxius tables might have headers in a specific pattern
                        elif 'emission' in first_row_text or 'fwhm' in first_row_text:
                            headers = oxxius_headers[:len(table_data[0])]
                            data_start = 1
                    
                    # Process each row
                    for row in table_data[data_start:]:
                        if len(row) >= 2:
                            spec_name = str(row[0]).strip()
                            
                            # Skip header-like rows
                            if spec_name.lower() in ['parameter', 'specification', 'spec', 'feature', '']:
                                continue
                            
                            # Check for Oxxius model pattern (LBX-XXX, LCX-XXX, LPX-XXX)
                            is_oxxius_model = bool(re.match(r'^L[BCPX]X-\d+', spec_name))
                            
                            # Process all columns
                            if len(headers) > 1:
                                # Map values to headers with validation
                                for i, value in enumerate(row[1:], 1):
                                    if i < len(headers):
                                        header = str(headers[i]).strip()
                                        
                                        # For Oxxius tables, use predefined header mapping
                                        if is_oxxius_model and i <= len(oxxius_headers):
                                            header = oxxius_headers[i-1]
                                        
                                        key = f"{spec_name}_{header}" if header else spec_name
                                        value_str = str(value).strip()
                                        if value_str and value_str not in ['', '-', 'N/A', 'None']:
                                            specs[key] = self._parse_technical_value(value_str)
                            else:
                                # No headers, store all values
                                values = [str(v).strip() for v in row[1:] 
                                         if str(v).strip() not in ['', '-', 'N/A', 'None']]
                                if values:
                                    if len(values) == 1:
                                        specs[spec_name] = self._parse_technical_value(values[0])
                                    else:
                                        specs[spec_name] = [self._parse_technical_value(v) for v in values]
            
            # Method 3: Try to extract from table's text representation
            if hasattr(table, 'text') or hasattr(table, '__str__'):
                table_text = str(table.text if hasattr(table, 'text') else table)
                # Parse markdown table format
                lines = table_text.split('\n')
                for line in lines:
                    if '|' in line and not line.startswith('|---'):
                        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                        if len(cells) >= 2:
                            key = cells[0]
                            values = cells[1:]
                            if key and not key.lower() in ['parameter', 'specification', '']:
                                if len(values) == 1:
                                    specs[key] = self._parse_technical_value(values[0])
                                else:
                                    specs[key] = [self._parse_technical_value(v) for v in values]
                                    
        except Exception as e:
            # Continue even if table processing fails
            pass
        
        return specs
    
    def _parse_markdown_table(self, table_text: str) -> Dict[str, Any]:
        """Parse a markdown table from Docling output."""
        specs = {}
        lines = table_text.strip().split('\n')
        
        if len(lines) < 3:  # Need at least header, separator, and one data row
            return specs
        
        # Parse header row - split by | and filter out empty
        header_line = lines[0]
        # Split preserving empty cells between pipes
        header_parts = header_line.split('|')
        headers = []
        for part in header_parts:
            # Keep track of position including empty cells
            headers.append(part.strip())
        
        # Remove first and last if empty (from leading/trailing |)
        if headers and headers[0] == '':
            headers = headers[1:]
        if headers and headers[-1] == '':
            headers = headers[:-1]
        
        # Clean headers - remove multi-word descriptions
        clean_headers = []
        for h in headers:
            h_lower = h.lower()
            if not h or h == '':  # First column is usually model/empty
                clean_headers.append('model')
            elif 'emission' in h_lower and 'wavelength' in h_lower:
                clean_headers.append('wavelength')
            elif 'linewidth' in h_lower:
                clean_headers.append('linewidth')
            elif 'power' in h_lower and 'stability' in h_lower:
                clean_headers.append('power_stability')
            elif 'output' in h_lower and 'power' in h_lower:
                clean_headers.append('output_power')
            elif 'beam' in h_lower and ('waist' in h_lower or 'diameter' in h_lower):
                clean_headers.append('beam_diameter')
            elif 'beam' in h_lower and 'quality' in h_lower:
                clean_headers.append('beam_quality')
            elif 'm²' in h_lower or 'm2' in h_lower:
                clean_headers.append('beam_quality')
            elif 'polarization' in h_lower:
                clean_headers.append('polarization')
            elif 'digital' in h_lower:
                clean_headers.append('digital_modulation')
            elif 'analog' in h_lower:
                clean_headers.append('analog_modulation')
            else:
                clean_headers.append(h.replace(' ', '_').lower())
        
        # Skip separator line (line 1)
        # Process data rows
        for line in lines[2:]:
            if not line.strip() or '---' in line:
                continue
            
            # Split preserving empty cells
            parts = line.split('|')
            values = []
            for part in parts:
                values.append(part.strip())
            
            # Remove first and last if empty
            if values and values[0] == '':
                values = values[1:]
            if values and values[-1] == '':
                values = values[:-1]
            
            if len(values) >= 2:
                model = values[0]
                # Check for laser model pattern
                if re.match(r'^L[BCPX]X-\d+', model):
                    # Match values to headers by position
                    for i in range(1, min(len(values), len(clean_headers))):
                        val = values[i]
                        header = clean_headers[i]
                        if val and val not in ['', '-', 'N/A'] and header != 'model':
                            key = f"{model}_{header}"
                            specs[key] = self._parse_technical_value(val)
        
        return specs
    
    def _extract_from_pdf_text(self, text: str) -> Dict[str, Any]:
        """Extract specs from PDF text using advanced patterns."""
        specs = {}
        
        # First try to extract markdown tables
        if '|' in text and '---|' in text:
            # Find all markdown tables
            lines = text.split('\n')
            table_start = None
            for i, line in enumerate(lines):
                if '|' in line:
                    if table_start is None:
                        table_start = i
                elif table_start is not None:
                    # End of table, process it
                    table_text = '\n'.join(lines[table_start:i])
                    if '---|' in table_text:  # Valid markdown table
                        table_specs = self._parse_markdown_table(table_text)
                        specs.update(table_specs)
                    table_start = None
            
            # Process last table if exists
            if table_start is not None:
                table_text = '\n'.join(lines[table_start:])
                if '---|' in table_text:
                    table_specs = self._parse_markdown_table(table_text)
                    specs.update(table_specs)
        
        lines = text.split('\n')
        
        # Parse markdown tables
        in_table = False
        table_headers = []
        
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                in_table = False
                table_headers = []
                continue
            
            # Detect markdown table
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|')]
                cells = [c for c in cells if c]  # Remove empty cells
                
                # Check if this is a separator line
                if any('---' in cell for cell in cells):
                    in_table = True
                    # Previous line should be headers
                    if i > 0 and '|' in lines[i-1]:
                        header_cells = [h.strip() for h in lines[i-1].split('|')]
                        table_headers = [h for h in header_cells if h]
                    continue
                
                # Process table row
                if in_table and len(cells) >= 2:
                    spec_name = cells[0]
                    if spec_name and not spec_name.lower() in ['specifications', 'parameter', '']:
                        # Clean the spec name
                        clean_spec = self._clean_spec_name(spec_name)
                        if len(table_headers) > 1 and len(cells) == len(table_headers):
                            # Map to headers
                            for j in range(1, len(cells)):
                                if j < len(table_headers):
                                    key = f"{clean_spec}_{table_headers[j]}"
                                    value = cells[j]
                                    if value and value not in ['-', 'N/A', '']:
                                        specs[key] = self._parse_technical_value(value)
                        else:
                            # No headers or mismatch, just extract values
                            values = cells[1:]
                            values = [v for v in values if v and v not in ['-', 'N/A', '']]
                            if values:
                                if len(values) == 1:
                                    specs[clean_spec] = self._parse_technical_value(values[0])
                                else:
                                    specs[clean_spec] = [self._parse_technical_value(v) for v in values]
            
            # Look for spec patterns with colons (but don't split ratios)
            elif ':' in line:
                # Check if it's a ratio (e.g., "50:1")
                if re.search(r'\d+\s*:\s*\d+', line):
                    # It's a ratio, try to extract the spec name and value
                    # Pattern: "Polarization Ratio: >50:1"
                    match = re.match(r'^([^:]+?):\s*([<>≤≥]?\s*\d+\s*:\s*\d+.*)$', line)
                    if match:
                        key = match.group(1).strip().replace('*', '').replace('#', '')
                        value = match.group(2).strip()
                        if key and value and len(key) < 100:
                            specs[key] = value
                else:
                    # Regular key:value pattern
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('#', '')
                        value = parts[1].strip()
                        if key and value and len(key) < 100:  # Reasonable key length
                            specs[key] = self._parse_technical_value(value)
        
        # Extract using regex patterns on full text
        pattern_specs = self._extract_pattern_specs(text)
        specs.update(pattern_specs)
        
        return specs
    
    def _extract_pattern_specs(self, text: str) -> Dict[str, Any]:
        """Extract specs using regex patterns."""
        specs = {}
        
        # M² (beam quality)
        m2_matches = re.findall(r'M[²2]\s*(?:\(.*?\))?\s*([<>≤≥]?\s*\d+(?:\.\d+)?)', text)
        if m2_matches:
            specs['beam_quality_m2'] = m2_matches[0] if len(m2_matches) == 1 else m2_matches
        
        # Wavelength with context
        wavelength_matches = re.findall(
            r'(?:Wavelength|λ).*?(\d+(?:\.\d+)?)\s*(?:±\s*\d+(?:\.\d+)?)?\s*(nm|μm)',
            text, re.IGNORECASE
        )
        if wavelength_matches:
            specs['wavelengths'] = [f"{v}{u}" for v, u in wavelength_matches]
        
        # Power specifications
        power_matches = re.findall(
            r'(?:Output Power|Power).*?(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*(mW|W)',
            text, re.IGNORECASE
        )
        if power_matches:
            specs['power_specs'] = [f"{v}{u}" for v, u in power_matches]
        
        # Noise specifications
        noise_matches = re.findall(
            r'(?:RMS Noise|Noise).*?([<>≤≥]?\s*\d+(?:\.\d+)?)\s*%',
            text, re.IGNORECASE
        )
        if noise_matches:
            specs['noise_specs'] = noise_matches
        
        # Temperature range
        temp_matches = re.findall(
            r'(?:Operating Temperature|Temperature).*?(-?\d+)\s*(?:to|–)\s*\+?(-?\d+)\s*°?C',
            text, re.IGNORECASE
        )
        if temp_matches:
            specs['temperature_range'] = [f"{t1} to {t2}°C" for t1, t2 in temp_matches]
        
        return specs
    
    def _parse_technical_value(self, value: str) -> str:
        """Parse technical values preserving important patterns."""
        if not value:
            return value
        
        # Preserve ratios
        if re.match(r'.*\d+\s*:\s*\d+.*', value):
            return value
        
        # Preserve inequalities and ranges
        if any(char in value for char in ['<', '>', '≤', '≥', '±', '-', '–', ' to ']):
            return value
        
        # Clean up common artifacts
        value = value.replace('\u00a0', ' ')  # Replace non-breaking spaces
        value = re.sub(r'\s+', ' ', value)  # Normalize whitespace
        
        return value.strip()
    
    def _dataframe_to_specs(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Convert DataFrame to specs dictionary with clean keys."""
        specs = {}
        
        # Check if this is a product comparison table
        if len(df.columns) > 1 and all(isinstance(col, str) for col in df.columns):
            # Each column is a product, rows are specs
            for col in df.columns:
                if col and not col.startswith('Unnamed'):
                    product_key = str(col).strip()
                    for index, row in df.iterrows():
                        spec_name = str(index).strip()
                        value = row[col]
                        if pd.notna(value):
                            # Clean the spec name
                            clean_spec = self._clean_spec_name(spec_name)
                            # Create key with product suffix
                            key = f"{clean_spec}_{product_key}"
                            specs[key] = self._parse_technical_value(str(value))
        else:
            # Standard extraction
            for index, row in df.iterrows():
                spec_name = str(index)
                for col in df.columns:
                    value = row[col]
                    if pd.notna(value):
                        # Clean the spec name
                        clean_spec = self._clean_spec_name(spec_name)
                        # Only append column if it's meaningful
                        if col and not str(col).startswith('Unnamed'):
                            key = f"{clean_spec}_{col}"
                        else:
                            key = clean_spec
                        specs[key] = self._parse_technical_value(str(value))
        
        return specs
    
    def _clean_spec_name(self, spec_name: str) -> str:
        """Clean a spec name to make it more normalizable."""
        import re
        
        # Remove footnote numbers (e.g., "Wavelength 1" -> "Wavelength")
        # Handle both "Name 1" and "Name 1  (unit)" patterns
        cleaned = re.sub(r'\s+\d+\s*', ' ', spec_name)
        
        # Remove units in parentheses
        cleaned = re.sub(r'\s*\([^)]+\)', '', cleaned)
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned