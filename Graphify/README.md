# Graphify CLI Wrapper (`graphify_cli.py`)

## Overview

graphify_cli.py is a drop-in CLI wrapper for the Graphify Python package.

It fixes a key limitation in Graphify:

The official CLI does not expose the main pipeline (/graphify <path>) even though it is documented.

This script:

- Recreates the full pipeline locally
- Preserves native CLI commands (add, query, path, explain)
- Works as a standalone executable via uv
- Does NOT require an AI agent (Claude, Codex, etc.)

---

## Why this wrapper exists

Graphify is designed primarily as an AI agent skill.

- /graphify ./path → works in agents
- graphify ./path → does NOT work in CLI

Yet the documentation suggests both should work.

This wrapper restores the expected CLI behavior.

---

## Features

### Full pipeline (fixed)

Equivalent to:

/graphify ./path

Now works locally:

uv run graphify_cli.py ./raw

---

### Native Graphify commands (delegated)

All existing commands are preserved:

uv run graphify_cli.py add https://arxiv.org/abs/1706.03762
uv run graphify_cli.py query "authentication flow"
uv run graphify_cli.py path "AuthModule" "Database"
uv run graphify_cli.py explain "SwinTransformer"

These are forwarded to the official Graphify CLI.

---

## Installation

### 1. Install uv

curl -Ls https://astral.sh/uv/install.sh | sh

---

### 2. Script header

Your script should include:

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "graphifyy",
#   "typer",
# ]
# ///

This makes it a self-contained executable script with automatic dependency handling.

---

## Usage

### Full pipeline

uv run graphify_cli.py ./project

Pipeline steps:

1. collect files (extract.collect_files)
2. extract entities & relationships
3. build graph
4. cluster nodes
5. analyze structure
6. generate report
7. export graph

Output:

graphify-out/
├── graph.json
├── graph.html
├── GRAPH_REPORT.md

---

### Add external content

uv run graphify_cli.py add https://arxiv.org/abs/1706.03762

With metadata:

uv run graphify_cli.py add https://example.com --author "Name"
uv run graphify_cli.py add https://example.com --contributor "Name"

---

### Query the graph

uv run graphify_cli.py query "authentication flow"

Options:

uv run graphify_cli.py query "auth flow" --dfs
uv run graphify_cli.py query "auth flow" --budget 1000

---

### Find paths

uv run graphify_cli.py path "AuthModule" "Database"

---

### Explain a node

uv run graphify_cli.py explain "SwinTransformer"

---

## Real pipeline architecture (v4)

collect_files (extract.py)
→ extract (extract.py)
→ build_graph (build.py)
→ cluster (cluster.py)
→ analyze (analyze.py)
→ report (report.py)
→ export (export.py)

Notes:

- collect_files is in extract.py, not detect.py
- Official architecture documentation is partially outdated

---

## Design choices

### Why not reimplement query/path/explain?

These commands:

- operate on graph.json
- rely on internal traversal logic
- evolve independently

So this wrapper delegates them to the native CLI.

---

### Why rebuild the pipeline?

Because:

- It exists in the codebase
- But is NOT exposed in CLI
- Only accessible via agent (/graphify)

---

## Troubleshooting

### graphify command not found

uv pip install graphifyy

---

### Extraction errors

Some files may fail due to:

- unsupported formats
- parsing issues
- LLM errors

They are skipped automatically.

---

### Empty graph

Check:

- input folder is not empty
- supported file types
- .graphifyignore

---

## Extensions

You can extend the wrapper with:

- --update (incremental rebuild)
- --neo4j (Cypher export)
- --watch (auto rebuild)
- FastAPI endpoint

---

## Summary

Feature                | Official Graphify | This wrapper
--------------------- | ---------------- | ------------
/graphify <path>      | Yes (agent only) | Yes
graphify <path>       | No               | Yes
CLI commands          | Yes              | Yes
Standalone usage      | No               | Yes

---

## Final note

This wrapper restores what Graphify claims to provide:

A usable CLI for graph generation  
Without requiring an AI agent