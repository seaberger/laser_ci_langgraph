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
                            if len(values) == 1:
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
        """Convert a pandas DataFrame to a specs dictionary."""
        specs = {}
        
        for index, row in df.iterrows():
            spec_name = str(index)
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    key = f"{spec_name}_{col}" if col else spec_name
                    specs[key] = str(value)
        
        return specs


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
            # Get table as DataFrame if possible
            if hasattr(table, 'to_dataframe'):
                df = table.to_dataframe()
                specs.update(self._dataframe_to_specs(df))
            elif hasattr(table, 'data'):
                # Process raw table data
                table_data = table.data
                if hasattr(table_data, '__len__') and len(table_data) > 0:
                    # Detect if first row is headers
                    headers = []
                    data_start = 0
                    
                    if len(table_data[0]) > 1:
                        # Check if first row looks like headers
                        first_row = [str(cell).lower() for cell in table_data[0]]
                        if any(keyword in ' '.join(first_row) for keyword in 
                               ['wavelength', 'power', 'model', 'cellx', '405', '488', '561', '637']):
                            headers = table_data[0]
                            data_start = 1
                    
                    # Process each row
                    for row in table_data[data_start:]:
                        if len(row) >= 2:
                            spec_name = str(row[0]).strip()
                            
                            # Skip header-like rows
                            if spec_name.lower() in ['parameter', 'specification', 'spec', 'feature', '']:
                                continue
                            
                            # Process all columns
                            if len(headers) > 1:
                                # Map values to headers
                                for i, value in enumerate(row[1:], 1):
                                    if i < len(headers):
                                        header = str(headers[i]).strip()
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
        except Exception as e:
            # Continue even if table processing fails
            pass
        
        return specs
    
    def _extract_from_pdf_text(self, text: str) -> Dict[str, Any]:
        """Extract specs from PDF text using advanced patterns."""
        specs = {}
        lines = text.split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Look for spec patterns with colons (but don't split ratios)
            if ':' in line:
                # Check if it's a ratio (e.g., "50:1")
                if re.search(r'\d+\s*:\s*\d+', line):
                    # It's a ratio, extract the whole thing
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('#', '')
                        value = parts[1].strip()
                        if key and value:
                            specs[key] = value
                else:
                    # Regular key:value pattern
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('#', '')
                        value = parts[1].strip()
                        if key and value and len(key) < 100:  # Reasonable key length
                            specs[key] = self._parse_technical_value(value)
            
            # Look for patterns like "Parameter Value Unit"
            elif '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = '|'.join(parts[1:]).strip()
                    if key and value:
                        specs[key] = self._parse_technical_value(value)
        
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
        """Convert DataFrame to specs dictionary."""
        specs = {}
        
        for index, row in df.iterrows():
            spec_name = str(index)
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    key = f"{spec_name}_{col}" if str(col) else spec_name
                    specs[key] = self._parse_technical_value(str(value))
        
        return specs