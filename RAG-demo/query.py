# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.26","sentence-transformers>=3.0"]
# ///
import argparse, json, numpy as np
from sentence_transformers import SentenceTransformer

ap = argparse.ArgumentParser()
ap.add_argument("--index", required=True)
ap.add_argument("--q", required=True)
ap.add_argument("--k", type=int, default=5)
ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
a = ap.parse_args()

idx = json.loads(open(a.index, encoding="utf-8").read())
model = SentenceTransformer(a.model)
qv = model.encode([a.q], normalize_embeddings=True)[0]
def cos(a,b): return float(np.dot(a,b))
scored = [(cos(qv, np.array(it["embedding"])), it) for it in idx["items"]]
scored.sort(key=lambda t: t[0], reverse=True)
for s,it in scored[:a.k]:
    print(f"{s:.3f}  {it['id']}: {it['text'][:120].replace('\n',' ')}…")