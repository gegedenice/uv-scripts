# /// script
# requires-python = ">=3.10"
# dependencies = ["pymilvus"]
# ///
import argparse, json, os
from pymilvus import MilvusClient

DEFAULT_URI = os.environ.get("MILVUS_URI", "./milvus.db")

def main():
    ap = argparse.ArgumentParser(description="Small utilities for Milvus collections")
    ap.add_argument("--milvus-uri", default=DEFAULT_URI)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List collections")

    p_info = sub.add_parser("info", help="Get collection schema and index info")
    p_info.add_argument("--collection", required=True)

    p_drop = sub.add_parser("drop", help="Drop a collection")
    p_drop.add_argument("--collection", required=True)

    args = ap.parse_args()
    client = MilvusClient(uri=args.milvus_uri)

    if args.cmd == "list":
        cols = client.list_collections()
        print(json.dumps(cols, ensure_ascii=False, indent=2))
    elif args.cmd == "info":
        schema = client.describe_collection(args.collection)
        idx = client.list_indexes(args.collection)
        print(json.dumps({"schema": schema, "indexes": idx}, ensure_ascii=False, indent=2))
    elif args.cmd == "drop":
        client.drop_collection(args.collection)
        print(f"Dropped '{args.collection}'.")

if __name__ == "__main__":
    main()
