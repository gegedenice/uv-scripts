# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymilvus",
#   "FlagEmbedding",
#   "tqdm",
#   "torch"
# ]
# ///
import argparse, json, os
from pymilvus import MilvusClient, RRFRanker, AnnSearchRequest
from FlagEmbedding import BGEM3FlagModel

DEFAULT_URI = os.environ.get("MILVUS_URI", "./milvus.db")

def main():
    ap = argparse.ArgumentParser(description="Hybrid retrieval over Milvus collection using BGE-M3 query embeddings")
    ap.add_argument("--query", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--collection", default="rapports")
    ap.add_argument("--milvus-uri", default=DEFAULT_URI)
    ap.add_argument("--device", default="cpu", choices=["cpu","cuda"])
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--show-scores", action="store_true")
    args = ap.parse_args()

    client = MilvusClient(uri=args.milvus_uri)
    if not client.has_collection(args.collection):
        raise SystemExit(f"Collection '{args.collection}' not found at {args.milvus_uri}")

    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=args.fp16, device=args.device)
    qemb = model.encode(
        [args.query],
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
        batch_size=1
    )
    # Prepare sparse + dense requests
    sparse_req = AnnSearchRequest(qemb["lexical_weights"], "sparse_vector", {"metric_type": "IP"}, limit=args.k)
    dense_req  = AnnSearchRequest(qemb["dense_vecs"],     "dense_vector",  {"metric_type": "COSINE"}, limit=args.k)

    res = client.hybrid_search(
        collection_name=args.collection,
        reqs=[sparse_req, dense_req],
        ranker=RRFRanker(100),
        limit=args.k,
        output_fields=["text", "source"]
    )

    hits = []
    for hit in res[0]:
        item = {
            "text": hit["entity"]["text"],
            "source": hit["entity"]["source"],
        }
        if args.show_scores:
            # hybrid score is in hit["distance"] after RRF; some builds label it "score"
            item["score"] = float(hit.get("distance", hit.get("score", 0.0)))
        hits.append(item)

    print(json.dumps({"query": args.query, "k": args.k, "results": hits}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
