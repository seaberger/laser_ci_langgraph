import os
import shutil
import typer
from tabulate import tabulate
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from .graph import GraphState, build_graph
from .db import SessionLocal
from .models import Manufacturer, Product, RawDocument

load_dotenv()

app = typer.Typer(help="Laser Competitor Intelligence (LangGraph + OpenAI)")


@app.command()
def run(
    model: str = typer.Option(None, help="OpenAI model (e.g., gpt-4o-mini)"),
    use_llm: bool = typer.Option(True, help="Use LLM for spec normalization fallback"),
    config_path: str = typer.Option("config/competitors.yml", help="Path to config file"),
    force_refresh: bool = typer.Option(False, help="Force re-download and re-process all documents"),
    scraper: str = typer.Option(None, help="Run specific scraper (e.g., coherent, hubner, omicron, oxxius)"),
):
    """Run end-to-end pipeline once."""
    if not os.getenv("OPENAI_API_KEY"):
        typer.echo(
            "Warning: OPENAI_API_KEY not set; LLM fallback will fail if enabled."
        )
    if scraper:
        typer.echo(f"Running scraper: {scraper}")
    
    graph = build_graph()
    result = graph.invoke(
        GraphState(
            config_path=config_path, 
            openai_model=model, 
            use_llm=use_llm,
            force_refresh=force_refresh,
            scraper_filter=scraper
        )
    )
    
    # Handle both dict and GraphState returns
    if hasattr(result, 'report_md'):
        final = result
    else:
        final = GraphState(**result)
    
    typer.echo(final.report_md or "# Report generation failed\n")
    if final.bench_rows:
        typer.echo("\n## Benchmark vs Coherent (diode_instrumentation)\n")
        print(tabulate(final.bench_rows, headers="keys"))
    if final.errors:
        typer.echo("\n## Errors")
        for e in final.errors:
            typer.echo(f"- {e}")


@app.command()
def schedule(
    cron: str = typer.Option("3 10 1 * *", help="Cron expression"),
    model: str = typer.Option(None, help="OpenAI model"),
    use_llm: bool = typer.Option(True, help="Use LLM for normalization"),
    config_path: str = typer.Option("config/competitors.yml", help="Config file path"),
):
    """
    Schedule a monthly run (default: 03:10 on the 1st).
    Cron format: 'M H DOM MON DOW'
    """
    M, H, DOM, MON, DOW = cron.split()
    graph = build_graph()

    def job():
        state = GraphState(config_path=config_path, openai_model=model, use_llm=use_llm)
        res = graph.invoke(state)
        os.makedirs("outputs/reports", exist_ok=True)
        import datetime

        fname = f"outputs/reports/{datetime.datetime.utcnow():%Y-%m}-report.md"
        with open(fname, "w") as f:
            f.write(res.report_md or "# No report\n")
        print(f"Wrote {fname}")

    sched = BlockingScheduler()
    sched.add_job(
        job,
        "cron",
        minute=int(M),
        hour=int(H),
        day=int(DOM) if DOM != "*" else None,
        month=int(MON) if MON != "*" else None,
        day_of_week=DOW if DOW != "*" else None,
    )
    print(f"Scheduled job with cron '{cron}'")
    sched.start()


@app.command()
def clean(
    vendor: str = typer.Argument(..., help="Vendor name to clean (e.g., omicron, oxxius, hubner, coherent)"),
    cache: bool = typer.Option(True, help="Clean PDF cache"),
    database: bool = typer.Option(True, help="Clean database entries"),
    dry_run: bool = typer.Option(False, help="Show what would be deleted without actually deleting"),
):
    """Clean vendor data from cache and/or database."""
    
    # Normalize vendor name for cache directory
    vendor_lower = vendor.lower().replace(" ", "_")
    
    # Map common vendor aliases
    vendor_aliases = {
        "hubner": "hübner_photonics_cobolt",
        "cobolt": "hübner_photonics_cobolt",
        "coherent": "coherent",
        "omicron": "omicron",
        "luxx": "omicron",
        "oxxius": "oxxius",
        "lbx": "oxxius"
    }
    
    cache_vendor = vendor_aliases.get(vendor_lower, vendor_lower)
    
    # Clean PDF cache
    if cache:
        cache_path = f"data/pdf_cache/{cache_vendor}"
        if os.path.exists(cache_path):
            pdf_files = os.listdir(cache_path)
            typer.echo(f"\n📁 PDF Cache: {cache_path}")
            typer.echo(f"   Found {len(pdf_files)} PDF files")
            if dry_run:
                typer.echo("   [DRY RUN] Would delete:")
                for pdf in pdf_files[:5]:  # Show first 5
                    typer.echo(f"     - {pdf}")
                if len(pdf_files) > 5:
                    typer.echo(f"     ... and {len(pdf_files) - 5} more")
            else:
                shutil.rmtree(cache_path)
                typer.echo(f"   ✅ Deleted {len(pdf_files)} PDF files")
        else:
            typer.echo(f"\n📁 PDF Cache: No cache found for {cache_vendor}")
    
    # Clean database entries
    if database:
        session = SessionLocal()
        try:
            # Find manufacturer
            manufacturer = session.query(Manufacturer).filter(
                Manufacturer.name.ilike(f"%{vendor}%")
            ).first()
            
            if manufacturer:
                typer.echo(f"\n🗄️  Database: {manufacturer.name}")
                
                # Count related data
                products = session.query(Product).filter(
                    Product.manufacturer_id == manufacturer.id
                ).all()
                
                doc_count = 0
                for product in products:
                    docs = session.query(RawDocument).filter(
                        RawDocument.product_id == product.id
                    ).all()
                    doc_count += len(docs)
                
                typer.echo(f"   Found {len(products)} products, {doc_count} documents")
                
                if dry_run:
                    typer.echo("   [DRY RUN] Would delete:")
                    for product in products:
                        typer.echo(f"     - Product: {product.name}")
                else:
                    # Delete documents first (foreign key constraint)
                    for product in products:
                        session.query(RawDocument).filter(
                            RawDocument.product_id == product.id
                        ).delete()
                    
                    # Delete products
                    session.query(Product).filter(
                        Product.manufacturer_id == manufacturer.id
                    ).delete()
                    
                    # Delete manufacturer
                    session.delete(manufacturer)
                    
                    session.commit()
                    typer.echo(f"   ✅ Deleted {len(products)} products and {doc_count} documents")
                    typer.echo(f"   ✅ Deleted manufacturer: {manufacturer.name}")
            else:
                typer.echo(f"\n🗄️  Database: No manufacturer found matching '{vendor}'")
                
        except Exception as e:
            session.rollback()
            typer.echo(f"❌ Database error: {e}")
        finally:
            session.close()
    
    if dry_run:
        typer.echo("\n⚠️  DRY RUN - No data was actually deleted")
    else:
        typer.echo(f"\n✨ Cleanup complete for {vendor}")


@app.command()
def list_vendors():
    """List all vendors in the database with their data counts."""
    session = SessionLocal()
    try:
        manufacturers = session.query(Manufacturer).all()
        
        if not manufacturers:
            typer.echo("No vendors found in database")
            return
        
        typer.echo("\n📊 Vendors in Database:\n")
        
        data = []
        for mfr in manufacturers:
            products = session.query(Product).filter(
                Product.manufacturer_id == mfr.id
            ).all()
            
            doc_count = 0
            pdf_count = 0
            html_count = 0
            
            for product in products:
                docs = session.query(RawDocument).filter(
                    RawDocument.product_id == product.id
                ).all()
                doc_count += len(docs)
                
                for doc in docs:
                    if doc.content_type == 'pdf_text':
                        pdf_count += 1
                    elif doc.content_type == 'html':
                        html_count += 1
            
            # Check cache
            cache_names = ["coherent", "hübner_photonics_cobolt", "omicron", "oxxius"]
            cache_pdfs = 0
            for cache_name in cache_names:
                if mfr.name.lower() in cache_name or cache_name in mfr.name.lower():
                    cache_path = f"data/pdf_cache/{cache_name}"
                    if os.path.exists(cache_path):
                        cache_pdfs = len(os.listdir(cache_path))
                        break
            
            data.append({
                "Vendor": mfr.name,
                "Products": len(products),
                "HTML Docs": html_count,
                "PDF Docs": pdf_count,
                "Cached PDFs": cache_pdfs
            })
        
        print(tabulate(data, headers="keys", tablefmt="grid"))
        
    except Exception as e:
        typer.echo(f"❌ Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    app()
