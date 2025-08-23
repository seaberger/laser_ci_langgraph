"""
Laser CI - Competitive Intelligence Pipeline
Built on LangGraph with OpenAI for intelligent spec normalization
"""

__version__ = "0.1.0"

from .graph import build_graph, GraphState
from .db import SessionLocal, engine, bootstrap_db
from .models import Manufacturer, Product, RawDocument, NormalizedSpec

__all__ = [
    "build_graph",
    "GraphState", 
    "SessionLocal",
    "engine",
    "bootstrap_db",
    "Manufacturer",
    "Product",
    "RawDocument",
    "NormalizedSpec",
]