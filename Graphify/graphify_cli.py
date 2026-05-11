#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "graphifyy",
#   "typer",
# ]
# ///

"""

"""
#!/usr/bin/env python3

import typer
import subprocess
from pathlib import Path

import graphify.extract as extract_mod
import graphify.build as build_mod
import graphify.cluster as cluster_mod
import graphify.analyze as analyze_mod
import graphify.report as report_mod
import graphify.export as export_mod

app = typer.Typer(help="Graphify CLI wrapper (fixed pipeline + native commands)")

# --------------------------------------------------
# 🔥 1. FULL PIPELINE (missing in official CLI)
# --------------------------------------------------

@app.command()
def run(
    path: str = ".",
    out: str = "graphify-out",
):
    """
    Run full pipeline (equivalent to /graphify <path>)
    """

    root = Path(path)
    out_dir = Path(out)

    typer.echo(f"📂 Running graphify pipeline on: {root}")

    # 1. Collect files (REAL entrypoint)
    files = extract_mod.collect_files(root)
    typer.echo(f"🔍 {len(files)} files detected")

    # 2. Extract
    extractions = []
    for f in files:
        try:
            extractions.append(extract_mod.extract(f))
        except Exception as e:
            typer.echo(f"⚠️ {f}: {e}")

    typer.echo(f"🧠 Extracted {len(extractions)} items")

    # 3. Build graph
    G = build_mod.build_graph(extractions)
    typer.echo(f"🕸 {len(G.nodes)} nodes / {len(G.edges)} edges")

    # 4. Cluster
    G = cluster_mod.cluster(G)

    # 5. Analyze
    analysis = analyze_mod.analyze(G)

    # 6. Report
    report = report_mod.render_report(G, analysis)

    # 7. Export
    export_mod.export(G, out_dir)
    (out_dir / "GRAPH_REPORT.md").write_text(report)

    typer.echo("✅ Pipeline complete")


# --------------------------------------------------
# 🔥 2. DEFAULT COMMAND (mimics `graphify ./path`)
# --------------------------------------------------

@app.callback(invoke_without_command=True)
def default(ctx: typer.Context, path: str = "."):
    if ctx.invoked_subcommand is None:
        ctx.invoke(run, path=path)


# --------------------------------------------------
# 🔁 3. BRIDGE COMMANDS → native graphify CLI
# --------------------------------------------------

def forward_to_graphify(args: list):
    """
    Forward command to native graphify CLI
    """
    cmd = ["graphify"] + args
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        typer.echo("❌ graphify CLI not found. Is it installed?")
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Command failed: {e}")


@app.command()
def add(url: str, author: str = None, contributor: str = None):
    args = ["add", url]
    if author:
        args += ["--author", author]
    if contributor:
        args += ["--contributor", contributor]
    forward_to_graphify(args)


@app.command()
def query(question: str, dfs: bool = False, budget: int = None):
    args = ["query", question]
    if dfs:
        args.append("--dfs")
    if budget:
        args += ["--budget", str(budget)]
    forward_to_graphify(args)


@app.command()
def path(src: str, dst: str):
    forward_to_graphify(["path", src, dst])


@app.command()
def explain(node: str):
    forward_to_graphify(["explain", node])


# --------------------------------------------------

if __name__ == "__main__":
    app()