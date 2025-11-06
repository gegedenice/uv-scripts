# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymilvus[milvus-lite]",
#   "FlagEmbedding",
#   "docling",
#   "torch",
#   "tqdm"
# ]
# ///
import argparse, os, sys, json
from pathlib import Path
from tqdm import tqdm

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from FlagEmbedding import BGEM3FlagModel
from pymilvus import MilvusClient, DataType, RRFRanker, AnnSearchRequest

DEFAULT_URI = os.environ.get("MILVUS_URI", "./milvus.db")

def get_client(uri: str) -> MilvusClient:
    return MilvusClient(uri=uri)

def ensure_collection(client: MilvusClient, collection: str):
    if client.has_collection(collection_name=collection):
        return
    schema = client.create_schema()
    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("text", DataType.VARCHAR, max_length=65535)
    schema.add_field("source", DataType.VARCHAR, max_length=2048)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)

    index_params = client.prepare_index_params()
    index_params.add_index(field_name="id")
    index_params.add_index(field_name="dense_vector", index_type="FLAT", metric_type="COSINE")
    index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="IP")

    client.create_collection(collection_name=collection, schema=schema, index_params=index_params)

def embed_batch(model, texts, batch_size: int):
    out_dense, out_sparse = [], []
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
        chunk = texts[i:i+batch_size]
        embs = model.encode(
            chunk,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=batch_size
        )
        out_dense.extend(embs["dense_vecs"])
        out_sparse.extend(embs["lexical_weights"])
    return out_dense, out_sparse

def main():
    ap = argparse.ArgumentParser(description="PDF → chunks → embeddings → Milvus (Lite) ingest")
    ap.add_argument("--files", nargs="+", required=True, help="One or more files paths. ONLY tx or mf supported for now")
    ap.add_argument("--collection", default="rapports")
    ap.add_argument("--milvus-uri", default=DEFAULT_URI, help="Milvus Lite file path or server URI")
    ap.add_argument("--device", default="cpu", choices=["cpu","cuda"])
    ap.add_argument("--fp16", action="store_true", help="Use fp16 with BGE-M3 (GPU or CPU that supports it)")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--tokenizer", default="BAAI/bge-m3")
    ap.add_argument("--drop-if-exists", action="store_true", help="Drop collection before ingest (fresh build)")
    args = ap.parse_args()

    client = get_client(args.milvus_uri)

    if args.drop_if_exists and client.has_collection(args.collection):
        client.drop_collection(args.collection)

    ensure_collection(client, args.collection)

    # Load model once
    model = BGEM3FlagModel(
        "BAAI/bge-m3",
        use_fp16=args.fp16,
        device=args.device
    )
    chunker = HybridChunker(tokenizer=args.tokenizer)
    converter = DocumentConverter()

    total_inserted = 0
    for file in args.files:
        file_path = Path(file)
        if not file_path.exists():
            print(f"[warn] Missing file: {file}", file=sys.stderr)
            continue

        dl = converter.convert(str(file_path)).document
        texts, sources = [], []

        for chunk in chunker.chunk(dl_doc=dl):
            enriched = chunker.contextualize(chunk=chunk)
            texts.append(enriched)
            # keep granular filename + (optional) page info if present
            src = getattr(chunk.meta.origin, "filename", file_path.name)
            if hasattr(chunk.meta, "page_no"):
                src = f"{src}#page={chunk.meta.page_no}"
            sources.append(src)

        if not texts:
            print(f"[info] No text extracted from {file_path.name}")
            continue

        dense, sparse = embed_batch(model, texts, args.batch_size)

        data = []
        for t, s, dv, sv in zip(texts, sources, dense, sparse):
            data.append({
                "text": t,
                "source": s,
                "dense_vector": dv,
                "sparse_vector": sv
            })
        client.insert(collection_name=args.collection, data=data)
        total_inserted += len(data)
        print(f"[ok] {file_path.name}: inserted {len(data)} chunks.")

    state = client.get_load_state(collection_name=args.collection)
    print(json.dumps({"collection": args.collection, "load_state": state, "inserted": total_inserted}, ensure_ascii=False))

if __name__ == "__main__":
    main()