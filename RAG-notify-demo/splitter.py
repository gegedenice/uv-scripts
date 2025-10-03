# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import argparse, httpx, textwrap, json, os
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)   # URL ou file://
ap.add_argument("--out", required=True)
ap.add_argument("--chunk-size", type=int, default=900)  # ~900 caractères
a = ap.parse_args()

def fetch(u:str)->str:
    if u.startswith("file://"): 
        return open(u[7:], encoding="utf-8").read()
    r = httpx.get(u, timeout=60); r.raise_for_status(); return r.text

text = fetch(a.inp)
paras = [p.strip() for p in text.splitlines() if p.strip()]
chunks, buf = [], ""
for p in paras:
    if len(buf)+len(p)+1 <= a.chunk_size:
        buf = f"{buf}\n{p}" if buf else p
    else:
        chunks.append(buf); buf = p
if buf: chunks.append(buf)

os.makedirs(os.path.dirname(a.out), exist_ok=True)
with open(a.out,"w",encoding="utf-8") as f:
    for i,c in enumerate(chunks):
        f.write(json.dumps({"id":f"chunk-{i}","text":c}, ensure_ascii=False)+"\n")
print(f"Wrote {len(chunks)} chunks → {a.out}")