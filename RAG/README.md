# uv-scripts for RAG

This directory contains Python utilities for building and querying RAG (Retrieval Augmented Generation) systems using Milvus as the vector database (local). The scripts support hybrid search combining dense and sparse embeddings using BGE-M3.

## Requirements

- Python 3.10+
- UV package manager
- Dependencies will be automatically installed by UV:
  - `pymilvus[milvus_lite]` - Vector database client for local database
  - `FlagEmbedding` - For BGE-M3 embeddings
  - `docling` - Document processing
  - `torch` - Deep learning backend
  - `tqdm` - Progress bars
  - `gradio` - Web UI for the RAG demo (used by `gradio_app.py`)

## Scripts Overview

### 1. Ingest Files (ingest_files.py)

Processes documents into chunks, generates embeddings, and stores them in Milvus.

```sh
uv run ingest_files.py \
  --files document1.txt document2.md \
  --collection rapports \
  --milvus-uri ./milvus.db \
  [--device cuda] \
  [--fp16] \
  [--batch-size 16] \
  [--drop-if-exists]
```

Key options:
- `--files`: One or more input documents
- `--collection`: Milvus collection name (default: "rapports")
- `--milvus-uri`: Path to Milvus Lite DB or server URI
- `--device`: CPU or CUDA (default: cpu)
- `--fp16`: Enable FP16 inference
- `--drop-if-exists`: Start fresh by dropping existing collection

### 2. Query Collection (query_hybrid.py)

Performs hybrid search using both dense and sparse embeddings.

```sh 
uv run query_hybrid.py \
  --collection rapports \
  --milvus-uri ./milvus.db \
  --query "Your search query here" \
  --k 5 \
  [--show-scores] \
  [--device cuda]
```

Key options:
- `--query`: Search query text
- `--k`: Number of results to return
- `--show-scores`: Include relevance scores in output
- `--device`: CPU or CUDA (default: cpu)
- `--milvus-uri`: Override default Milvus DB path/URI (also read from `MILVUS_URI` env)

### 3. Manage Collections (manage_collection.py)

Utilities for managing Milvus collections.

```sh
# List all collections
uv run manage_collection.py --milvus-uri ./milvus.db list

# Get collection info
uv run manage_collection.py --milvus-uri ./milvus.db info --collection rapports

# Drop a collection
uv run manage_collection.py --milvus-uri ./milvus.db drop --collection rapports
```

### 4. Gradio Web App (gradio_app.py)

A lightweight Gradio interface to run RAG queries and LLM inference. The app uses the local `query_hybrid.py` (for retrieval) and a remote/local LLM inference script (by default `llms-openai-inference.py` referenced via GH_RAW in the script).

Features:
- Run hybrid retrieval against a Milvus collection and view retrieved chunks/sources.
- Send retrieved context + user question to an LLM (via the configured provider and model).
- Editable system and user prompts.
- UI controls for provider, HF subpath, model, and API token.

CLI options:
- `--milvus-uri`: Optional. Override the default Milvus URI used by the app (falls back to `MILVUS_URI` environment variable or `./milvus.db`).

UI fields (Gradio):
- Provider: e.g., `huggingface` or other provider supported by the inference script.
- HF Subpath: Hugging Face subpath used when provider is `huggingface`.
- Model: Model identifier to use for inference.
- API Token: Secret token for model provider (entered in a password field).
- System Prompt: System-level instruction for the LLM.
- User Prompt: Free-form prompt for the LLM inference tab.
- JSON Output: Toggle to request JSON output from the inference script.
- RAG Query: Query text for retrieval.
- System Prompt for RAG: System prompt used when combining retrieved chunks with the query for LLM answering.

Run locally (example):
```sh
# Launch gradio app using local script (use -- to separate uv and script args)
uv run gradio_app.py -- --milvus-uri ./milvus.db

# Or run the published raw script
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG"
uv run "${GH_RAW}/gradio_app.py" -- --milvus-uri ./milvus.db
```

Notes:
- The Gradio app will call `query_hybrid.py` for retrieval. Ensure your Milvus collection (default `rapports`) exists and is populated.
- The Gradio app will call an LLM inference script (`llms-openai-inference.py` by default in the app). That script must be available locally or reachable via the GH_RAW URL configured inside `gradio_app.py`.
- Keep API tokens secure; the app uses a password field but tokens may appear in subprocess calls. Prefer running in a trusted environment.

## Environment Variables

- `MILVUS_URI`: Default Milvus connection URI (can be overridden via `--milvus-uri`).

## Remote Execution

All scripts can be run directly from GitHub using UV:

```sh
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG"

# Ingest documents
uv run "${GH_RAW}/ingest_files.py" -- [options]

# Query
uv run "${GH_RAW}/query_hybrid.py" -- [options]

# Gradio app
uv run "${GH_RAW}/gradio_app.py" -- --milvus-uri ./milvus.db
```

## Architecture

1. **Document Processing**
   - Uses `docling` for document parsing and chunking
   - Hybrid chunking strategy with contextual enrichment
   - Supports multiple document formats

2. **Embeddings**
   - BGE-M3 model for both dense and sparse embeddings
   - Batch processing for efficiency
   - Optional FP16 support

3. **Vector Storage**
   - Milvus for vector similarity search
   - Hybrid schema with dense and sparse vectors
   - Supports both Milvus Lite (file-based) and server deployments