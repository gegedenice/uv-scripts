# /// script
# requires-python = ">=3.10"
# dependencies = ["fastapi>=0.112", "uvicorn>=0.30"]
# ///
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pathlib import Path
import json, time

app = FastAPI(title="LDN Inbox (POC)")
INBOX = Path("state/inbox"); INBOX.mkdir(parents=True, exist_ok=True)

@app.post("/inbox")
async def inbox_post(req: Request):
    data = await req.json()
    fname = INBOX / f"{int(time.time()*1000)}.json"
    fname.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"status":"ok","stored":fname.name})

@app.get("/inbox")
def inbox_list():
    items = []
    for p in sorted(INBOX.glob("*.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return items

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)