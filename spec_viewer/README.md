# Laser Specification Comparison Viewer

A professional web-based tool for comparing laser specifications across multiple vendors with advanced filtering and export capabilities.

## Features

- **Multi-vendor Comparison**: Compare specifications from Coherent, Hübner Photonics, Lumencor, Omicron, and Oxxius
- **Dual Spec Views**: Toggle between normalized (standardized) and raw vendor specifications
- **Advanced Filtering**:
  - Multi-select vendor filtering
  - Specification field selection
  - Wavelength range filtering (nm)
  - Power range filtering (mW)
- **Multiple View Modes**:
  - Table view for side-by-side comparison
  - Card view for detailed product inspection
- **Export Functionality**: Export filtered data to CSV
- **Professional UI**: Coherent-branded interface with modern design

## Quick Start

### 1. Generate Data from Database

```bash
# From the spec_viewer directory
uv run python generate_data.py
```

This extracts the latest specification data from the SQLite database and generates `js/data.js`.

### 2. View the Application

#### Option A: Direct File Access
Simply open `spec_viewer/index.html` in a modern web browser.

#### Option B: Local Web Server
```bash
# From the spec_viewer directory
python -m http.server 8000
```
Then navigate to http://localhost:8000

## Usage Guide

### Filtering Products

1. **Select Vendors**: Click the vendor dropdown and check the vendors you want to compare
2. **Choose Specifications**: Select which specification fields to display
3. **Set Ranges** (optional): Enter min/max values for wavelength or power
4. **Apply Filters**: Click "Apply Filters" to update the display

### Viewing Options

- **Normalized vs Raw Specs**: Check "Show Raw Vendor Specs" to include original vendor field names and values
  - Normalized specs are standardized across vendors for direct comparison
  - Raw specs show the original vendor terminology and may include additional fields
  
- **Table vs Card View**: Toggle between:
  - Table view: Side-by-side comparison with products as rows
  - Card view: Individual product cards with all selected specifications

### Exporting Data

Click "Export CSV" to download the currently filtered data as a spreadsheet file.

## File Structure

```
spec_viewer/
├── index.html          # Main application
├── css/
│   └── styles.css      # Coherent-branded styling
├── js/
│   ├── app.js          # Application logic
│   └── data.js         # Generated data from database
├── generate_data.py    # Database extraction script
└── README.md           # This file
```

## Data Fields

### Normalized Specifications
- **Optical**: wavelength_nm, output_power_mw_nominal, linewidth_mhz, m2
- **Stability**: rms_noise_pct, power_stability_pct
- **Modulation**: modulation_analog_hz, modulation_digital_hz, ttl_shutter
- **Fiber**: fiber_output, fiber_na, fiber_mfd_um
- **Physical**: beam_diameter_mm, beam_divergence_mrad, warmup_time_min

### Raw Specifications
When enabled, displays original vendor field names prefixed with [RAW], shown with yellow highlighting.

## Updating Data

To refresh the viewer with the latest database content:

```bash
# 1. Run the main pipeline to update the database
uv run python -m src.laser_ci_lg.cli run

# 2. Regenerate the viewer data
cd spec_viewer
uv run python generate_data.py

# 3. Refresh the browser
```

## Browser Compatibility

- Chrome 90+ (recommended)
- Firefox 88+
- Safari 14+
- Edge 90+

## Customization

### Adding New Vendors
1. Add vendor to `config/competitors.yml`
2. Run scraper pipeline
3. Regenerate viewer data

### Modifying Displayed Fields
Edit the default selected specs in `app.js`:
```javascript
state.selectedSpecs = new Set(['wavelength_nm', 'output_power_mw', ...]);
```

### Styling Changes
All styling is in `css/styles.css` using CSS variables for easy color scheme updates.

## Troubleshooting

**No products showing**: 
- Ensure database has data: `sqlite3 ../data/laser-ci.sqlite "SELECT COUNT(*) FROM products"`
- Regenerate data: `uv run python generate_data.py`

**Filters not working**:
- Clear browser cache and reload
- Check browser console for JavaScript errors

**Export not working**:
- Ensure at least one product is visible
- Check browser allows downloads from local files

## License

© 2025 Coherent Corp. Internal Use Only.