"""
Batch normalization with concurrent LLM processing for improved performance.
"""

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple, Optional
from sqlalchemy import select
from .db import SessionLocal
from .models import RawDocument, NormalizedSpec, Product
from .specs import canonical_key, parse_value_to_unit, CANONICAL_SPEC_KEYS
from .llm import llm_normalize


def process_model_with_llm(
    model_name: str, 
    model_specs: Dict[str, Any], 
    product_name: str,
    llm_model: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Process a single model with LLM normalization.
    Returns (model_name, normalized_specs).
    """
    # Initialize canonical fields
    canonical = {k: None for k in CANONICAL_SPEC_KEYS}
    extras = {}
    
    # Try heuristic mapping first
    for spec_name, spec_value in model_specs.items():
        ck = canonical_key(spec_name)
        if ck:
            parsed = parse_value_to_unit(ck, str(spec_value))
            if parsed is not None:
                canonical[ck] = parsed
        else:
            extras[spec_name] = spec_value
    
    # Add model name to extras
    extras['model'] = model_name
    canonical["vendor_fields"] = extras or None
    
    # Count non-null fields from heuristics
    mapped_count = sum(1 for v in canonical.values() if v is not None and v != {})
    
    # Use LLM for better normalization if heuristics didn't map enough fields
    if mapped_count < 10:
        try:
            context = f"Laser model: {model_name}\\nProduct family: {product_name}"
            llm_result = llm_normalize(model_specs, context, model=llm_model)
            
            # Merge LLM results
            for k in CANONICAL_SPEC_KEYS:
                if k in llm_result and llm_result[k] is not None:
                    value = llm_result[k]
                    if isinstance(value, dict):
                        # Extract from dict format
                        if 'value' in value:
                            canonical[k] = float(value['value']) if isinstance(value['value'], (int, float)) else value['value']
                        elif 'typical' in value:
                            canonical[k] = float(value['typical']) if isinstance(value['typical'], (int, float)) else value['typical']
                        elif 'nominal' in value:
                            canonical[k] = float(value['nominal']) if isinstance(value['nominal'], (int, float)) else value['nominal']
                    elif k in ['polarization', 'interfaces', 'dimensions_mm', 'vendor_fields']:
                        # Keep as-is for non-numeric fields
                        canonical[k] = value
                    else:
                        # Convert to float for numeric fields
                        try:
                            canonical[k] = float(value) if value is not None else None
                        except (ValueError, TypeError):
                            canonical[k] = value
            
            # Update vendor fields
            if 'vendor_fields' in llm_result:
                if isinstance(llm_result['vendor_fields'], dict):
                    extras.update(llm_result['vendor_fields'])
                    canonical['vendor_fields'] = extras
        except Exception as e:
            # Fail open; keep heuristic result
            print(f"  LLM error for {model_name}: {e}")
    
    return model_name, canonical


def normalize_all_batch(use_llm: bool = True, model: str | None = None, max_workers: int = 5) -> int:
    """
    Normalize all specs with concurrent LLM processing.
    Returns count of inserted NormalizedSpec rows.
    """
    s = SessionLocal()
    inserted = 0
    
    try:
        # Get all raw documents
        raw_docs = (
            s.execute(
                select(RawDocument).order_by(
                    RawDocument.product_id, RawDocument.fetched_at.desc()
                )
            )
            .scalars()
            .all()
        )
        
        # Group by product_id
        by_pid = {}
        for d in raw_docs:
            by_pid.setdefault(d.product_id, []).append(d)
        
        for pid, docs in by_pid.items():
            # Get product info
            product = s.get(Product, pid)
            if not product:
                continue
            
            # Merge all raw specs
            merged_raw = {}
            for d in docs:
                if d.raw_specs:
                    merged_raw.update(d.raw_specs)
            
            if not merged_raw:
                # Try extracting from text
                for d in docs:
                    merged_raw.update(simple_kv_from_text(d.text))
            
            if not merged_raw:
                continue
            
            # Extract individual models
            models = extract_models_from_specs(merged_raw)
            
            if not models:
                # No individual models found, treat as single product
                models = {product.name: merged_raw}
            
            print(f"\\nProcessing {product.name}: {len(models)} models")
            
            if use_llm and len(models) > 1:
                # Process multiple models concurrently
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all models for processing
                    futures = {}
                    for model_name, model_specs in models.items():
                        future = executor.submit(
                            process_model_with_llm,
                            model_name,
                            model_specs,
                            product.name,
                            model
                        )
                        futures[future] = model_name
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        model_name = futures[future]
                        try:
                            _, canonical = future.result(timeout=30)
                            
                            # Create normalized spec record
                            ns = NormalizedSpec(
                                product_id=pid,
                                source_raw_id=docs[0].id if docs else None,
                                **canonical
                            )
                            s.add(ns)
                            inserted += 1
                            
                            # Show progress
                            if canonical.get('wavelength_nm') and canonical.get('output_power_mw_nominal'):
                                print(f"  ✓ {model_name}: {canonical['wavelength_nm']:.0f}nm, {canonical['output_power_mw_nominal']:.0f}mW")
                            else:
                                print(f"  ✓ {model_name}")
                                
                        except Exception as e:
                            print(f"  ✗ {model_name}: {e}")
            else:
                # Process sequentially (single model or no LLM)
                for model_name, model_specs in models.items():
                    if use_llm:
                        _, canonical = process_model_with_llm(
                            model_name, 
                            model_specs, 
                            product.name,
                            model
                        )
                    else:
                        # Heuristic only
                        canonical = {k: None for k in CANONICAL_SPEC_KEYS}
                        extras = {}
                        
                        for spec_name, spec_value in model_specs.items():
                            ck = canonical_key(spec_name)
                            if ck:
                                parsed = parse_value_to_unit(ck, str(spec_value))
                                if parsed is not None:
                                    canonical[ck] = parsed
                            else:
                                extras[spec_name] = spec_value
                        
                        extras['model'] = model_name
                        canonical["vendor_fields"] = extras or None
                    
                    # Create normalized spec record
                    ns = NormalizedSpec(
                        product_id=pid,
                        source_raw_id=docs[0].id if docs else None,
                        **canonical
                    )
                    s.add(ns)
                    inserted += 1
        
        s.commit()
        print(f"\\n✅ Successfully normalized {inserted} models")
        return inserted
        
    finally:
        s.close()


def simple_kv_from_text(text: str) -> dict:
    """Extract simple key-value pairs from text."""
    kv = {}
    for line in text.splitlines():
        if ":" in line and len(line) < 120:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return kv


def extract_models_from_specs(raw_specs: dict) -> dict:
    """
    Extract individual laser models from raw specs.
    Returns dict of {model_name: {spec_name: value}}
    """
    models = defaultdict(dict)
    
    for key, value in raw_specs.items():
        # Try to identify model from key structure
        if '_' in key:
            parts = key.split('_', 1)
            
            # Check if first part looks like a spec name
            if any(spec_word in parts[0].lower() for spec_word in 
                   ['wavelength', 'power', 'beam', 'noise', 'stability', 'linewidth', 'm²', 'polarization']):
                spec_name = parts[0]
                model_name = parts[1] if len(parts) > 1 else 'Unknown'
            # Check if second part looks like a spec name
            elif len(parts) > 1 and any(spec_word in parts[1].lower() for spec_word in 
                   ['wavelength', 'power', 'beam', 'noise', 'stability', 'linewidth', 'm²', 'polarization']):
                model_name = parts[0]
                spec_name = parts[1]
            else:
                # Default: assume format is spec_model
                spec_name = parts[0]
                model_name = parts[1] if len(parts) > 1 else 'Unknown'
            
            # Only keep if model name looks valid (contains numbers or known patterns)
            if (re.search(r'\\d+', model_name) or 
                any(pattern in model_name.upper() for pattern in 
                    ['LX', 'LS', 'LBX', 'LCX', 'OBIS', 'LUXX', 'CELESTA', 'SPECTRA', 'SOLA'])):
                models[model_name][spec_name] = value
    
    return dict(models)