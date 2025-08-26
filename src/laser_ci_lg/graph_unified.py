"""
Unified LangGraph pipeline with smart discovery and batch normalization.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from .crawler_unified import bootstrap_db, seed_from_unified_config, run_unified_scrapers
from .normalize_batch import normalize_all_batch
from .reporter import monthly_report
from .benchmark import benchmark_vs_coherent


class UnifiedGraphState(BaseModel):
    """State for unified pipeline with smart discovery."""
    config_path: str = "config/target_products.yml"
    discovery_mode: str = "smart"  # "smart" or "static"
    force_refresh: bool = False
    vendor_filter: Optional[str] = None
    max_workers: int = 5  # For parallel LLM normalization
    
    # Results
    scrapers_run: int = 0
    products_discovered: int = 0
    normalized: int = 0
    report_md: Optional[str] = None
    bench_rows: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Tracking
    errors: List[str] = Field(default_factory=list)
    
    # LLM settings
    use_llm: bool = True
    openai_model: Optional[str] = "gpt-4o-mini"


def node_bootstrap(state: UnifiedGraphState) -> UnifiedGraphState:
    """Bootstrap database and seed manufacturers."""
    try:
        print("\n=== Bootstrap Phase ===")
        bootstrap_db()
        seed_from_unified_config(state.config_path)
        print("  ✓ Database initialized")
    except Exception as e:
        state.errors.append(f"bootstrap: {e}")
        print(f"  ✗ Bootstrap error: {e}")
    return state


def node_discover_and_crawl(state: UnifiedGraphState) -> UnifiedGraphState:
    """
    Combined discovery and crawl phase.
    Uses smart discovery or static URLs based on configuration.
    """
    try:
        print("\n=== Discovery & Crawl Phase ===")
        print(f"  Mode: {state.discovery_mode}")
        
        # Determine if using smart discovery
        use_smart = state.discovery_mode == "smart"
        
        # Run unified scrapers
        state.scrapers_run = run_unified_scrapers(
            config_path=state.config_path,
            force_refresh=state.force_refresh,
            vendor_filter=state.vendor_filter,
            use_smart=use_smart
        )
        
        print(f"  ✓ Ran {state.scrapers_run} scrapers")
        
        # Count discovered products
        from .db import SessionLocal
        from .models import Product
        s = SessionLocal()
        try:
            state.products_discovered = s.query(Product).count()
            print(f"  ✓ Total products in database: {state.products_discovered}")
        finally:
            s.close()
            
    except Exception as e:
        state.errors.append(f"discover_crawl: {e}")
        print(f"  ✗ Discovery/crawl error: {e}")
    return state


def node_normalize_batch(state: UnifiedGraphState) -> UnifiedGraphState:
    """
    Batch normalization with parallel LLM processing.
    Uses enhanced extraction and model-level processing.
    """
    try:
        print("\n=== Normalization Phase ===")
        print(f"  LLM: {state.openai_model}")
        print(f"  Workers: {state.max_workers}")
        
        # Use batch normalization with parallel processing
        state.normalized = normalize_all_batch(
            use_llm=state.use_llm,
            model=state.openai_model,
            max_workers=state.max_workers
        )
        
        print(f"  ✓ Normalized {state.normalized} models")
        
    except Exception as e:
        state.errors.append(f"normalize: {e}")
        print(f"  ✗ Normalization error: {e}")
    return state


def node_report(state: UnifiedGraphState) -> UnifiedGraphState:
    """Generate monthly delta report."""
    try:
        print("\n=== Report Phase ===")
        state.report_md = monthly_report()
        
        if state.report_md:
            # Save report
            from pathlib import Path
            from datetime import datetime
            
            report_dir = Path("reports")
            report_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = report_dir / f"report_{timestamp}.md"
            report_path.write_text(state.report_md)
            
            print(f"  ✓ Report saved: {report_path}")
        else:
            print("  → No report generated")
            
    except Exception as e:
        state.errors.append(f"report: {e}")
        print(f"  ✗ Report error: {e}")
    return state


def node_benchmark(state: UnifiedGraphState) -> UnifiedGraphState:
    """Benchmark competitors against Coherent."""
    try:
        print("\n=== Benchmark Phase ===")
        state.bench_rows = benchmark_vs_coherent("diode_instrumentation")
        
        if state.bench_rows:
            print(f"  ✓ Benchmarked {len(state.bench_rows)} products")
            
            # Show top competitors
            print("\n  Top competitors by wavelength coverage:")
            from collections import defaultdict
            by_vendor = defaultdict(set)
            
            for row in state.bench_rows:
                vendor = row.get('vendor', 'Unknown')
                wavelength = row.get('wavelength_nm')
                if wavelength:
                    by_vendor[vendor].add(int(wavelength))
            
            for vendor, wavelengths in sorted(by_vendor.items(), key=lambda x: -len(x[1]))[:5]:
                print(f"    {vendor}: {len(wavelengths)} wavelengths")
        else:
            print("  → No benchmark data")
            
    except Exception as e:
        state.errors.append(f"benchmark: {e}")
        print(f"  ✗ Benchmark error: {e}")
    return state


def node_summary(state: UnifiedGraphState) -> UnifiedGraphState:
    """Final summary of pipeline execution."""
    print("\n=== Pipeline Summary ===")
    print(f"  Scrapers run: {state.scrapers_run}")
    print(f"  Products discovered: {state.products_discovered}")
    print(f"  Models normalized: {state.normalized}")
    print(f"  Report generated: {'Yes' if state.report_md else 'No'}")
    print(f"  Benchmark rows: {len(state.bench_rows)}")
    
    if state.errors:
        print(f"\n  Errors encountered: {len(state.errors)}")
        for error in state.errors[:5]:
            print(f"    - {error}")
    
    return state


def build_unified_graph():
    """
    Build the unified pipeline graph with smart discovery.
    
    Flow:
    1. Bootstrap (setup DB, seed manufacturers)
    2. Discover & Crawl (smart discovery or static URLs)
    3. Normalize (batch processing with parallel LLM)
    4. Report (generate delta report)
    5. Benchmark (compare to Coherent)
    6. Summary (final stats)
    """
    g = StateGraph(UnifiedGraphState)
    
    # Add nodes
    g.add_node("bootstrap", node_bootstrap)
    g.add_node("discover_crawl", node_discover_and_crawl)
    g.add_node("normalize", node_normalize_batch)
    g.add_node("report", node_report)
    g.add_node("benchmark", node_benchmark)
    g.add_node("summary", node_summary)
    
    # Set entry point
    g.set_entry_point("bootstrap")
    
    # Add edges (linear flow)
    g.add_edge("bootstrap", "discover_crawl")
    g.add_edge("discover_crawl", "normalize")
    g.add_edge("normalize", "report")
    g.add_edge("report", "benchmark")
    g.add_edge("benchmark", "summary")
    g.add_edge("summary", END)
    
    return g.compile()


def run_unified_pipeline(
    config_path: str = "config/target_products.yml",
    discovery_mode: str = "smart",
    force_refresh: bool = False,
    vendor_filter: Optional[str] = None,
    max_workers: int = 5,
    use_llm: bool = True,
    openai_model: str = "gpt-4o-mini"
) -> UnifiedGraphState:
    """
    Run the complete unified pipeline.
    
    Args:
        config_path: Path to configuration file
        discovery_mode: "smart" or "static"
        force_refresh: Force refresh all content
        vendor_filter: Optional vendor name to process
        max_workers: Number of parallel workers for LLM
        use_llm: Whether to use LLM for normalization
        openai_model: OpenAI model to use
    
    Returns:
        Final pipeline state with results
    """
    # Build graph
    graph = build_unified_graph()
    
    # Create initial state
    initial_state = UnifiedGraphState(
        config_path=config_path,
        discovery_mode=discovery_mode,
        force_refresh=force_refresh,
        vendor_filter=vendor_filter,
        max_workers=max_workers,
        use_llm=use_llm,
        openai_model=openai_model
    )
    
    print("="*60)
    print("UNIFIED PIPELINE WITH SMART DISCOVERY")
    print("="*60)
    print(f"Config: {config_path}")
    print(f"Discovery: {discovery_mode}")
    print(f"Force refresh: {force_refresh}")
    print(f"Vendor filter: {vendor_filter or 'All'}")
    print(f"LLM: {openai_model if use_llm else 'Disabled'}")
    print(f"Workers: {max_workers}")
    
    # Run pipeline
    final_state = graph.invoke(initial_state)
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    
    return final_state