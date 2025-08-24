// ===== Application State =====
let state = {
    selectedVendors: new Set(),
    selectedSpecs: new Set(),
    wavelengthRange: { min: null, max: null },
    powerRange: { min: null, max: null },
    currentView: 'table',
    showRawSpecs: false,
    filteredProducts: []
};

// ===== Initialize Application =====
document.addEventListener('DOMContentLoaded', () => {
    initializeDropdowns();
    initializeFilters();
    initializeViewControls();
    loadInitialData();
    setupEventListeners();
});

// ===== Dropdown Management =====
function initializeDropdowns() {
    // Vendor Dropdown
    const vendorTrigger = document.getElementById('vendor-trigger');
    const vendorDropdown = document.getElementById('vendor-dropdown');
    
    vendorTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDropdown('vendor');
    });
    
    // Spec Dropdown
    const specTrigger = document.getElementById('spec-trigger');
    const specDropdown = document.getElementById('spec-dropdown');
    
    specTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDropdown('spec');
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        closeAllDropdowns();
    });
    
    // Prevent dropdown from closing when clicking inside
    vendorDropdown.addEventListener('click', (e) => e.stopPropagation());
    specDropdown.addEventListener('click', (e) => e.stopPropagation());
}

function toggleDropdown(type) {
    const trigger = document.getElementById(`${type}-trigger`);
    const dropdown = document.getElementById(`${type}-dropdown`);
    const isActive = dropdown.classList.contains('active');
    
    closeAllDropdowns();
    
    if (!isActive) {
        trigger.classList.add('active');
        dropdown.classList.add('active');
    }
}

function closeAllDropdowns() {
    document.querySelectorAll('.multi-select-trigger').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.multi-select-dropdown').forEach(d => d.classList.remove('active'));
}

// ===== Filter Initialization =====
function initializeFilters() {
    // Populate vendor list
    const vendorList = document.getElementById('vendor-list');
    const vendors = [...new Set(LASER_DATA.products.map(p => p.vendor))].sort();
    
    vendors.forEach(vendor => {
        const item = createDropdownItem(vendor, 'vendor');
        vendorList.appendChild(item);
    });
    
    // Populate spec list
    const specList = document.getElementById('spec-list');
    const specs = getAvailableSpecs();
    
    specs.forEach(spec => {
        const item = createDropdownItem(spec, 'spec');
        specList.appendChild(item);
    });
    
    // Setup select all/clear all buttons
    setupSelectButtons('vendor', vendors);
    setupSelectButtons('spec', specs);
    
    // Setup search functionality
    setupSearch('vendor');
    setupSearch('spec');
}

function createDropdownItem(value, type) {
    const div = document.createElement('div');
    div.className = 'dropdown-item';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'dropdown-checkbox';
    checkbox.id = `${type}-${value.replace(/\s+/g, '-')}`;
    checkbox.value = value;
    
    const label = document.createElement('label');
    label.className = 'dropdown-label';
    label.htmlFor = checkbox.id;
    label.textContent = value;
    
    checkbox.addEventListener('change', () => {
        updateSelection(type, value, checkbox.checked);
    });
    
    div.appendChild(checkbox);
    div.appendChild(label);
    
    return div;
}

function updateSelection(type, value, checked) {
    if (type === 'vendor') {
        if (checked) {
            state.selectedVendors.add(value);
        } else {
            state.selectedVendors.delete(value);
        }
        updateDropdownText('vendor');
    } else if (type === 'spec') {
        if (checked) {
            state.selectedSpecs.add(value);
        } else {
            state.selectedSpecs.delete(value);
        }
        updateDropdownText('spec');
    }
}

function updateDropdownText(type) {
    const trigger = document.getElementById(`${type}-trigger`);
    const textSpan = trigger.querySelector('.selected-text');
    const selected = type === 'vendor' ? state.selectedVendors : state.selectedSpecs;
    
    if (selected.size === 0) {
        textSpan.textContent = `Select ${type}s...`;
        textSpan.classList.remove('has-selection');
    } else if (selected.size === 1) {
        textSpan.textContent = [...selected][0];
        textSpan.classList.add('has-selection');
    } else {
        textSpan.textContent = `${selected.size} ${type}s selected`;
        textSpan.classList.add('has-selection');
    }
}

function setupSelectButtons(type, allValues) {
    const selectAllBtn = document.getElementById(`${type}-select-all`);
    const clearAllBtn = document.getElementById(`${type}-clear-all`);
    
    selectAllBtn.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll(`#${type}-list .dropdown-checkbox`);
        checkboxes.forEach(cb => {
            cb.checked = true;
            updateSelection(type, cb.value, true);
        });
    });
    
    clearAllBtn.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll(`#${type}-list .dropdown-checkbox`);
        checkboxes.forEach(cb => {
            cb.checked = false;
            updateSelection(type, cb.value, false);
        });
    });
}

function setupSearch(type) {
    const searchInput = document.getElementById(`${type}-search`);
    
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const items = document.querySelectorAll(`#${type}-list .dropdown-item`);
        
        items.forEach(item => {
            const label = item.querySelector('.dropdown-label').textContent.toLowerCase();
            item.style.display = label.includes(searchTerm) ? 'flex' : 'none';
        });
    });
}

// ===== View Controls =====
function initializeViewControls() {
    const tableBtn = document.getElementById('view-table');
    const cardsBtn = document.getElementById('view-cards');
    
    tableBtn.addEventListener('click', () => setView('table'));
    cardsBtn.addEventListener('click', () => setView('cards'));
}

function setView(view) {
    state.currentView = view;
    
    // Update button states
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // Show/hide views
    document.getElementById('table-view').style.display = view === 'table' ? 'block' : 'none';
    document.getElementById('card-view').style.display = view === 'cards' ? 'block' : 'none';
    
    // Re-render current data
    renderResults();
}

// ===== Event Listeners =====
function setupEventListeners() {
    // Apply Filters button
    document.getElementById('apply-filters').addEventListener('click', applyFilters);
    
    // Reset Filters button
    document.getElementById('reset-filters').addEventListener('click', resetFilters);
    
    // Export CSV button
    document.getElementById('export-csv').addEventListener('click', exportToCSV);
    
    // Show Raw Specs checkbox
    document.getElementById('show-raw-specs').addEventListener('change', (e) => {
        state.showRawSpecs = e.target.checked;
        if (state.showRawSpecs) {
            // Add raw spec fields to selected specs
            updateSpecListForRawSpecs();
        }
        renderResults();
    });
    
    // Range inputs
    document.getElementById('wavelength-min').addEventListener('input', (e) => {
        state.wavelengthRange.min = e.target.value ? parseFloat(e.target.value) : null;
    });
    
    document.getElementById('wavelength-max').addEventListener('input', (e) => {
        state.wavelengthRange.max = e.target.value ? parseFloat(e.target.value) : null;
    });
    
    document.getElementById('power-min').addEventListener('input', (e) => {
        state.powerRange.min = e.target.value ? parseFloat(e.target.value) : null;
    });
    
    document.getElementById('power-max').addEventListener('input', (e) => {
        state.powerRange.max = e.target.value ? parseFloat(e.target.value) : null;
    });
}

// ===== Data Loading =====
function loadInitialData() {
    // Update header stats
    const vendors = [...new Set(LASER_DATA.products.map(p => p.vendor))];
    document.getElementById('vendor-count').textContent = `${vendors.length} Vendors`;
    document.getElementById('product-count').textContent = `${LASER_DATA.products.length} Products`;
    document.getElementById('last-updated').textContent = `Updated: ${LASER_DATA.lastUpdated}`;
    
    // Set default selections
    state.selectedVendors = new Set(vendors);
    state.selectedSpecs = new Set(['wavelength_nm', 'output_power_mw', 'rms_noise_pct', 'power_stability_pct']);
    
    // Check default checkboxes
    state.selectedVendors.forEach(vendor => {
        const checkbox = document.querySelector(`#vendor-list input[value="${vendor}"]`);
        if (checkbox) checkbox.checked = true;
    });
    
    state.selectedSpecs.forEach(spec => {
        const checkbox = document.querySelector(`#spec-list input[value="${spec}"]`);
        if (checkbox) checkbox.checked = true;
    });
    
    updateDropdownText('vendor');
    updateDropdownText('spec');
    
    // Initial render
    applyFilters();
}

// ===== Filtering Logic =====
function applyFilters() {
    // Filter products based on selected criteria
    state.filteredProducts = LASER_DATA.products.filter(product => {
        // Vendor filter
        if (state.selectedVendors.size > 0 && !state.selectedVendors.has(product.vendor)) {
            return false;
        }
        
        // Wavelength filter
        if (state.wavelengthRange.min !== null || state.wavelengthRange.max !== null) {
            const wavelength = product.specs.wavelength_nm;
            if (wavelength) {
                if (state.wavelengthRange.min !== null && wavelength < state.wavelengthRange.min) return false;
                if (state.wavelengthRange.max !== null && wavelength > state.wavelengthRange.max) return false;
            }
        }
        
        // Power filter
        if (state.powerRange.min !== null || state.powerRange.max !== null) {
            const power = product.specs.output_power_mw;
            if (power) {
                if (state.powerRange.min !== null && power < state.powerRange.min) return false;
                if (state.powerRange.max !== null && power > state.powerRange.max) return false;
            }
        }
        
        return true;
    });
    
    renderResults();
}

function resetFilters() {
    // Clear all selections
    state.selectedVendors.clear();
    state.selectedSpecs.clear();
    state.wavelengthRange = { min: null, max: null };
    state.powerRange = { min: null, max: null };
    
    // Uncheck all checkboxes
    document.querySelectorAll('.dropdown-checkbox').forEach(cb => cb.checked = false);
    
    // Clear range inputs
    document.getElementById('wavelength-min').value = '';
    document.getElementById('wavelength-max').value = '';
    document.getElementById('power-min').value = '';
    document.getElementById('power-max').value = '';
    
    // Update dropdown texts
    updateDropdownText('vendor');
    updateDropdownText('spec');
    
    // Re-apply default selections
    loadInitialData();
}

// ===== Rendering =====
function renderResults() {
    if (state.currentView === 'table') {
        renderTableView();
    } else {
        renderCardView();
    }
}

function renderTableView() {
    const tableHeader = document.getElementById('table-header');
    const tableBody = document.getElementById('table-body');
    const noResults = document.getElementById('no-results-table');
    
    // Clear existing content
    tableBody.innerHTML = '';
    
    // Show/hide no results message
    if (state.filteredProducts.length === 0) {
        noResults.style.display = 'flex';
        document.querySelector('.table-wrapper').style.display = 'none';
        return;
    } else {
        noResults.style.display = 'none';
        document.querySelector('.table-wrapper').style.display = 'block';
    }
    
    // Build header
    let headerHTML = '<th class="sticky-col">Product</th>';
    state.selectedSpecs.forEach(spec => {
        headerHTML += `<th>${formatSpecName(spec)}</th>`;
    });
    tableHeader.innerHTML = headerHTML;
    
    // Build rows
    state.filteredProducts.forEach(product => {
        const row = document.createElement('tr');
        
        // Product name cell
        let productCell = `<td class="sticky-col">${product.name}`;
        if (product.vendor === 'Coherent') {
            productCell += '<span class="vendor-badge coherent">Coherent</span>';
        } else {
            productCell += `<span class="vendor-badge">${product.vendor}</span>`;
        }
        productCell += '</td>';
        row.innerHTML = productCell;
        
        // Spec cells
        state.selectedSpecs.forEach(spec => {
            let value;
            if (spec.startsWith('raw_')) {
                // Get value from raw_specs
                const rawSpecName = spec.substring(4);
                value = product.raw_specs ? product.raw_specs[rawSpecName] : null;
            } else {
                // Get value from normalized specs
                value = product.specs[spec];
            }
            const cell = document.createElement('td');
            cell.textContent = formatSpecValue(value, spec);
            if (spec.startsWith('raw_')) {
                cell.style.background = '#FFF9E6'; // Light yellow background for raw specs
            }
            row.appendChild(cell);
        });
        
        tableBody.appendChild(row);
    });
}

function renderCardView() {
    const cardsContainer = document.getElementById('cards-container');
    const noResults = document.getElementById('no-results-cards');
    
    // Clear existing content
    cardsContainer.innerHTML = '';
    
    // Show/hide no results message
    if (state.filteredProducts.length === 0) {
        noResults.style.display = 'flex';
        cardsContainer.style.display = 'none';
        return;
    } else {
        noResults.style.display = 'none';
        cardsContainer.style.display = 'grid';
    }
    
    // Build cards
    state.filteredProducts.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card';
        
        let cardHTML = `
            <div class="card-header">
                <div class="card-title">${product.name}</div>
                <div class="card-vendor">${product.vendor}</div>
            </div>
            <div class="card-specs">
        `;
        
        state.selectedSpecs.forEach(spec => {
            let value;
            if (spec.startsWith('raw_')) {
                // Get value from raw_specs
                const rawSpecName = spec.substring(4);
                value = product.raw_specs ? product.raw_specs[rawSpecName] : null;
            } else {
                // Get value from normalized specs
                value = product.specs[spec];
            }
            
            if (value !== null && value !== undefined) {
                const rowClass = spec.startsWith('raw_') ? 'spec-row raw-spec-row' : 'spec-row';
                cardHTML += `
                    <div class="${rowClass}">
                        <span class="spec-name">${formatSpecName(spec)}</span>
                        <span class="spec-value">${formatSpecValue(value, spec)}</span>
                    </div>
                `;
            }
        });
        
        cardHTML += '</div>';
        card.innerHTML = cardHTML;
        cardsContainer.appendChild(card);
    });
}

// ===== Export Functionality =====
function exportToCSV() {
    if (state.filteredProducts.length === 0) {
        alert('No data to export');
        return;
    }
    
    // Build CSV content
    let csv = 'Product,Vendor,';
    csv += Array.from(state.selectedSpecs).map(spec => formatSpecName(spec)).join(',');
    csv += '\n';
    
    state.filteredProducts.forEach(product => {
        csv += `"${product.name}","${product.vendor}",`;
        csv += Array.from(state.selectedSpecs).map(spec => {
            const value = product.specs[spec];
            return value !== null && value !== undefined ? `"${formatSpecValue(value, spec)}"` : '""';
        }).join(',');
        csv += '\n';
    });
    
    // Download CSV
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `laser_specs_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// ===== Helper Functions =====
function getAvailableSpecs() {
    const specs = new Set();
    LASER_DATA.products.forEach(product => {
        // Add normalized specs
        Object.keys(product.specs).forEach(spec => {
            if (spec !== 'vendor_fields' && spec !== 'interfaces' && spec !== 'dimensions_mm') {
                specs.add(spec);
            }
        });
        
        // If showing raw specs, add raw spec fields
        if (state.showRawSpecs && product.raw_specs) {
            Object.keys(product.raw_specs).forEach(spec => {
                specs.add(`raw_${spec}`);
            });
        }
    });
    return Array.from(specs).sort();
}

function updateSpecListForRawSpecs() {
    // Regenerate spec list with raw specs included
    const specList = document.getElementById('spec-list');
    const currentSpecs = Array.from(state.selectedSpecs);
    
    // Clear the list
    specList.innerHTML = '';
    
    // Get all available specs (including raw if enabled)
    const specs = getAvailableSpecs();
    
    specs.forEach(spec => {
        const item = createDropdownItem(spec, 'spec');
        // Restore selection state
        if (currentSpecs.includes(spec)) {
            item.querySelector('input').checked = true;
        }
        specList.appendChild(item);
    });
}

function formatSpecName(spec) {
    // Check if it's a raw spec
    if (spec.startsWith('raw_')) {
        return '[RAW] ' + spec.substring(4).replace(/_/g, ' ');
    }
    
    // Convert snake_case to Title Case
    return spec
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase())
        .replace(/Nm\b/g, '(nm)')
        .replace(/Mw\b/g, '(mW)')
        .replace(/Pct\b/g, '(%)')
        .replace(/Mhz\b/g, '(MHz)')
        .replace(/Hz\b/g, '(Hz)')
        .replace(/Mm\b/g, '(mm)')
        .replace(/Mfd Um\b/g, 'MFD (μm)')
        .replace(/Mrad\b/g, '(mrad)')
        .replace(/Min\b/g, '(min)')
        .replace(/Na\b/g, 'NA')
        .replace(/M2\b/g, 'M²')
        .replace(/Ttl/g, 'TTL')
        .replace(/\bTs\b/g, 'Timestamp');
}

function formatSpecValue(value, spec) {
    if (value === null || value === undefined) return '—';
    
    // Boolean values
    if (typeof value === 'boolean') {
        return value ? '✓' : '✗';
    }
    
    // Numeric values with units
    if (typeof value === 'number') {
        if (spec.includes('wavelength')) return `${value} nm`;
        if (spec.includes('power')) return `${value} mW`;
        if (spec.includes('pct') || spec.includes('noise') || spec.includes('stability')) return `${value}%`;
        if (spec.includes('mhz')) return `${value} MHz`;
        if (spec.includes('hz')) return `${value} Hz`;
        if (spec.includes('mm')) return `${value} mm`;
        if (spec.includes('um')) return `${value} μm`;
        if (spec.includes('mrad')) return `${value} mrad`;
        if (spec.includes('min')) return `${value} min`;
        return value.toString();
    }
    
    // Handle JSON objects (interfaces, dimensions, vendor_fields)
    if (typeof value === 'object' && value !== null) {
        if (spec === 'vendor_fields') {
            // Format vendor fields as key-value pairs
            return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(', ');
        }
        if (spec === 'interfaces') {
            return Array.isArray(value) ? value.join(', ') : JSON.stringify(value);
        }
        if (spec === 'dimensions_mm') {
            return JSON.stringify(value);
        }
        return JSON.stringify(value);
    }
    
    return value.toString();
}