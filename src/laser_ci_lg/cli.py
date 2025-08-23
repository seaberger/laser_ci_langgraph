import os
import typer
from tabulate import tabulate
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from .graph import GraphState, build_graph

load_dotenv()

app = typer.Typer(help="Laser Competitor Intelligence (LangGraph + OpenAI)")


@app.command()
def run(
    model: str = typer.Option(None, help="OpenAI model (e.g., gpt-4o-mini)"),
    use_llm: bool = typer.Option(True, help="Use LLM for spec normalization fallback"),
    config_path: str = typer.Option("config/competitors.yml", help="Path to config file"),
):
    """Run end-to-end pipeline once."""
    if not os.getenv("OPENAI_API_KEY"):
        typer.echo(
            "Warning: OPENAI_API_KEY not set; LLM fallback will fail if enabled."
        )
    graph = build_graph()
    final = graph.invoke(
        GraphState(config_path=config_path, openai_model=model, use_llm=use_llm)
    )
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
        os.makedirs("reports", exist_ok=True)
        import datetime

        fname = f"reports/{datetime.datetime.utcnow():%Y-%m}-report.md"
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


if __name__ == "__main__":
    app()
