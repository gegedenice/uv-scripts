# uv-scripts for RAG

This directory contains Python utilities for building and querying RAG (Retrieval Augmented Generation) systems using Milvus as the vector database (local). The scripts support hybrid search combining dense and sparse embeddings using BGE-M3.

## Requirements

- Python 3.10+
- UV package manager
- Dependencies will be automatically installed by UV:
  - `pymilvus[milvus-lite]` - Vector database client for local database
  - `FlagEmbedding` - For BGE-M3 embeddings
  - `docling` - Document processing
  - `torch` - Deep learning backend
  - `tqdm` - Progress bars

## Scripts Overview

### 1. Ingest Files (ingest_files.py)

Processes documents into chunks, generates embeddings, and stores them in Milvus.

```sh
uv run ingest_files.py \
  --files document1.txt document2.md \
  --collection rapports \
  --milvus-uri ./milvus.db \
  [--device cuda]
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

## Environment Variables

- `MILVUS_URI`: Default Milvus connection URI (can be overridden via `--milvus-uri`)

## Remote Execution

All scripts can be run directly from GitHub using UV:

```sh
GH_RAW="https://raw.githubusercontent.com/gegedenice/uv-scripts/main/RAG"

# Ingest documents
uv run "${GH_RAW}/ingest_files.py" [options]

# Query
uv run "${GH_RAW}/query_hybrid.py" [options]

# Manage
uv run "${GH_RAW}/manage_collection.py" [options]
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