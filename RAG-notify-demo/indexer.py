# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import argparse, json, time
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

rows = [json.loads(l) for l in open(a.inp, encoding="utf-8")]
index = {
  "created_at": time.time(),
  "dim": len(rows[0]["embedding"]) if rows else 0,
  "items": rows
}
with open(a.out,"w",encoding="utf-8") as f:
    f.write(json.dumps(index))
print(f"Indexed {len(rows)} items → {a.out}")