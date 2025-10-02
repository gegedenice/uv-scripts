# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import time, json, httpx, os, hashlib, subprocess, sys
INBOX_URL = os.getenv("INBOX_URL","http://localhost:8080/inbox")
RAW_BASE = os.getenv("RAW_BASE","")  # si besoin de réécrire les URLs
STATE = "state"; os.makedirs(STATE, exist_ok=True)
SEEN = os.path.join(STATE, "seen.txt")

def seen_ids():
    return set(open(SEEN).read().split()) if os.path.exists(SEEN) else set()
def mark_seen(msgid):
    with open(SEEN,"a") as f: f.write(msgid+"\n")

def sha(s: str) -> str: return hashlib.sha1(s.encode()).hexdigest()  # id simple

def post_announce(obj_name, path, who):
    payload = {
      "@context": ["https://www.w3.org/ns/activitystreams","https://www.w3.org/ns/prov#"],
      "type": "Announce",
      "actor": "https://smartbibl.ia/actors/runner",
      "object": {"type":"Document","id":f"urn:smartbibl:state:{obj_name}","name":obj_name,"url":f"file://{path}"},
      "prov:wasGeneratedBy": {"type":"Activity","prov:wasAssociatedWith": who}
    }
    httpx.post(INBOX_URL, headers={"Content-Type":"application/ld+json"}, json=payload, timeout=30)

def run(cmd):
    print("→", " ".join(cmd)); 
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(p.stdout); 
    if p.stderr: print(p.stderr, file=sys.stderr)

def main():
    done = seen_ids()
    while True:
        msgs = httpx.get(INBOX_URL, timeout=30).json()
        for m in msgs:
            msgid = sha(json.dumps(m, sort_keys=True))
            if msgid in done: continue
            if m.get("type") != "Create": continue
            inst = m.get("instrument",{}); 
            if inst.get("action") != "index": continue
            obj = m.get("object",{})
            url = obj.get("url") or obj.get("id")
            # 1) split
            run(["uv","run","<RAW_URL_WITH_SHA>/splitter.py","--in",url,"--out","state/chunks.jsonl"])
            post_announce("chunks", "state/chunks.jsonl", "splitter.py@<SHA>")
            # 2) embed
            run(["uv","run","<RAW_URL_WITH_SHA>/embedder.py","--in","state/chunks.jsonl","--out","state/embeddings.jsonl"])
            post_announce("embeddings", "state/embeddings.jsonl", "embedder.py@<SHA>")
            # 3) index
            run(["uv","run","<RAW_URL_WITH_SHA>/indexer.py","--in","state/embeddings.jsonl","--out","state/index.jsonl"])
            post_announce("index", "state/index.jsonl", "indexer.py@<SHA>")
            mark_seen(msgid); done.add(msgid)
        time.sleep(2)

if __name__ == "__main__":
    main()