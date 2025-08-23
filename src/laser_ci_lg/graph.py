from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from .crawler import bootstrap_db, seed_from_config, run_scrapers_from_config
from .normalize import normalize_all
from .reporter import monthly_report
from .benchmark import benchmark_vs_coherent


class GraphState(BaseModel):
    config_path: str = "config/competitors.yml"
    crawled: int | None = None
    normalized: int | None = None
    report_md: str | None = None
    bench_rows: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    openai_model: Optional[str] = None
    use_llm: bool = True
    force_refresh: bool = False
    scraper_filter: Optional[str] = None


def node_bootstrap(state: GraphState) -> GraphState:
    try:
        bootstrap_db()
        seed_from_config(state.config_path)
    except Exception as e:
        state.errors.append(f"bootstrap/seed: {e}")
    return state


def node_crawl(state: GraphState) -> GraphState:
    try:
        run_scrapers_from_config(
            state.config_path, 
            force_refresh=state.force_refresh,
            scraper_filter=state.scraper_filter
        )
        state.crawled = 1
    except Exception as e:
        state.errors.append(f"crawl: {e}")
    return state


def node_normalize(state: GraphState) -> GraphState:
    try:
        n = normalize_all(use_llm=state.use_llm, model=state.openai_model)
        state.normalized = n
    except Exception as e:
        state.errors.append(f"normalize: {e}")
    return state


def node_report(state: GraphState) -> GraphState:
    try:
        state.report_md = monthly_report()
    except Exception as e:
        state.errors.append(f"report: {e}")
    return state


def node_bench(state: GraphState) -> GraphState:
    try:
        state.bench_rows = benchmark_vs_coherent("diode_instrumentation")
    except Exception as e:
        state.errors.append(f"bench: {e}")
    return state


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("bootstrap", node_bootstrap)
    g.add_node("crawl", node_crawl)
    g.add_node("normalize", node_normalize)
    g.add_node("report", node_report)
    g.add_node("bench", node_bench)

    g.set_entry_point("bootstrap")
    g.add_edge("bootstrap", "crawl")
    g.add_edge("crawl", "normalize")
    g.add_edge("normalize", "report")
    g.add_edge("report", "bench")
    g.add_edge("bench", END)
    return g.compile()
