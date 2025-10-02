# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26","sentence-transformers>=3.0"]
# ///
import argparse, json, numpy as np
from sentence_transformers import SentenceTransformer

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
a = ap.parse_args()

model = SentenceTransformer(a.model)  # CPU par défaut
rows = [json.loads(l) for l in open(a.inp, encoding="utf-8")]
embs = model.encode([r["text"] for r in rows], normalize_embeddings=True)
with open(a.out,"w",encoding="utf-8") as f:
    for r, e in zip(rows, embs):
        r["embedding"] = e.tolist()
        f.write(json.dumps(r, ensure_ascii=False)+"\n")
print(f"Embedded {len(rows)} chunks → {a.out}")