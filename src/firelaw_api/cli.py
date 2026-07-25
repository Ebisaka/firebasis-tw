from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from .api import create_app
from .fetcher import fetch_source_payloads
from .ingest import build_database
from .semantic import DEFAULT_SEMANTIC_MODEL, SemanticUnavailableError, build_semantic_index
from .store import FirelawStore

app = typer.Typer(no_args_is_help=True)


@app.command()
def update(
    db: Path = typer.Option(Path("data/firelaw.sqlite"), "--db", help="SQLite database path."),
    live: bool = typer.Option(True, "--live/--no-live", help="Download official live datasets."),
) -> None:
    if not live:
        raise typer.BadParameter("--no-live is only for future fixture workflows; v1 update downloads official datasets.")
    typer.echo("Downloading official law datasets...")
    payloads = fetch_source_payloads()
    manifest = build_database(db, payloads)
    typer.echo(
        f"Updated {db}: {manifest['corpus']['law_count']} laws, "
        f"{manifest['corpus']['article_count']} articles."
    )
    changes = manifest.get("changes", {})
    counts = changes.get("counts", {})
    if changes.get("first_update"):
        typer.echo("Change baseline created.")
    elif changes.get("status") == "unavailable":
        reason = changes.get("unavailable_reason") or "previous database could not be compared"
        typer.echo(f"Change diff unavailable: {reason}")
    else:
        typer.echo(
            "Changes: "
            f"laws +{counts.get('law_added', 0)} ~{counts.get('law_modified', 0)} -{counts.get('law_removed', 0)}; "
            f"articles +{counts.get('article_added', 0)} ~{counts.get('article_modified', 0)} -{counts.get('article_removed', 0)}"
        )


@app.command()
def semantic_update(
    db: Path = typer.Option(Path("data/firelaw.sqlite"), "--db", help="SQLite database path."),
    model: str = typer.Option(DEFAULT_SEMANTIC_MODEL, "--model", help="Local embedding model name."),
) -> None:
    try:
        manifest = build_semantic_index(FirelawStore(db), model_name=model)
    except (FileNotFoundError, SemanticUnavailableError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Updated semantic beta index for {manifest['article_count']} articles "
        f"using {manifest['model']}."
    )


@app.command()
def serve(
    db: Path = typer.Option(Path("data/firelaw.sqlite"), "--db", help="SQLite database path."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", help="Port to bind."),
) -> None:
    uvicorn.run(create_app(db), host=host, port=port)
