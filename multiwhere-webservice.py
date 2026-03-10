#!/usr/bin/env python3
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests"
# ]
# ///
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

SUDOC_MULTIWHERE_URL = "https://www.sudoc.fr/services/multiwhere/{ppn}&format=text/json"
DEFAULT_LLM_URL = "http://localhost:8080/v1/chat/completions"


def fetch_multiwhere(ppn: str, timeout_s: int = 20) -> Any:
    url = SUDOC_MULTIWHERE_URL.format(ppn=ppn)
    resp = requests.get(url, timeout=timeout_s, headers={"Accept": "application/json"})
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return json.loads(resp.text)


def parse_multiwhere_payload(data: Any) -> List[Dict[str, Any]]:
    try:
        lib = data["sudoc"]["query"]["result"]["library"]
    except Exception as e:
        raise ValueError("Unexpected JSON structure: missing sudoc.query.result.library") from e

    if lib is None:
        return []

    if isinstance(lib, dict):
        libs = [lib]
    elif isinstance(lib, list):
        libs = lib
    else:
        raise ValueError(f"Unexpected type for library: {type(lib).__name__}")

    holdings: List[Dict[str, Any]] = []
    for it in libs:
        if not isinstance(it, dict):
            continue

        rcr = it.get("rcr")
        label = it.get("shortname")

        lat_raw: Optional[str] = it.get("latitude")
        lon_raw: Optional[str] = it.get("longitude")

        lat: Optional[float] = None
        lon: Optional[float] = None
        if lat_raw not in (None, ""):
            try:
                lat = float(lat_raw)
            except Exception:
                lat = None
        if lon_raw not in (None, ""):
            try:
                lon = float(lon_raw)
            except Exception:
                lon = None

        holdings.append(
            {
                "rcr": rcr,
                "label": label,
                "lat": lat,
                "lon": lon,
                "raw": it,  # audit/debug
            }
        )

    return holdings


def format_table(holdings: List[Dict[str, Any]]) -> str:
    cols = ["rcr", "label", "lat", "lon"]
    rows = [[str(h.get(c) if h.get(c) is not None else "") for c in cols] for h in holdings]

    widths = [max(len(cols[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(cols))]
    sep = " | "
    header = sep.join(cols[i].ljust(widths[i]) for i in range(len(cols)))
    line = "-+-".join("-" * widths[i] for i in range(len(cols)))
    body = "\n".join(sep.join(rows[j][i].ljust(widths[i]) for i in range(len(cols))) for j in range(len(rows)))
    return f"{header}\n{line}\n{body}"


def to_geojson(ppn: str, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    features: List[Dict[str, Any]] = []
    for h in holdings:
        lat = h.get("lat")
        lon = h.get("lon")
        if lat is None or lon is None:
            continue
        if not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0):
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {"ppn": ppn, "rcr": h.get("rcr"), "label": h.get("label")},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_csv(path: Path, ppn: str, holdings: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ppn", "rcr", "label", "lat", "lon"])
        for h in holdings:
            w.writerow([ppn, h.get("rcr") or "", h.get("label") or "", h.get("lat") or "", h.get("lon") or ""])


def call_llm_chat_completions(
    llm_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 600,
    timeout_s: int = 60,
    api_key: Optional[str] = None,
) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    r = requests.post(llm_url, json=payload, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise ValueError(f"Unexpected LLM response shape: {data}") from e


def llm_postprocess_holdings(
    ppn: str,
    holdings: List[Dict[str, Any]],
    llm_url: str,
    llm_model: str,
    mode: str,
    api_key: Optional[str],
) -> Any:
    """
    mode:
      - summary: returns {ppn,count,summary}
      - clean_json: returns {ppn,count,holdings:[{rcr,label,lat,lon}],summary}
    """
    clean_holdings = [
        {"rcr": h.get("rcr"), "label": h.get("label"), "lat": h.get("lat"), "lon": h.get("lon")}
        for h in holdings
    ]

    if mode == "summary":
        system = (
            "Tu es un assistant bibliothécaire. Résume de façon brève et factuelle une liste de bibliothèques "
            "détenant un document (PPN Sudoc)."
        )
        user = (
            f"PPN: {ppn}\n"
            f"Nombre de bibliothèques: {len(clean_holdings)}\n"
            f"Liste (JSON):\n{json.dumps(clean_holdings, ensure_ascii=False, indent=2)}\n\n"
            "Écris un résumé en 3-6 phrases. Pas d'invention."
        )
        content = call_llm_chat_completions(
            llm_url=llm_url,
            model=llm_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            api_key=api_key,
        )
        return {"ppn": ppn, "count": len(clean_holdings), "summary": content.strip()}

    # clean_json (default)
    system = (
        "Tu es un service de normalisation. Tu dois produire STRICTEMENT un JSON valide, "
        "sans texte autour, sans markdown. Ne jamais inventer d'informations. "
        "Conserve uniquement les champs rcr, label, lat, lon."
    )
    user = (
        "À partir de la liste ci-dessous, renvoie un JSON EXACT avec ce schéma:\n"
        "{\n"
        '  "ppn": string,\n'
        '  "count": number,\n'
        '  "holdings": [{"rcr": string|null, "label": string|null, "lat": number|null, "lon": number|null}],\n'
        '  "summary": string\n'
        "}\n\n"
        f"Données:\n{json.dumps(clean_holdings, ensure_ascii=False, indent=2)}"
    )
    content = call_llm_chat_completions(
        llm_url=llm_url,
        model=llm_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=900,
        api_key=api_key,
    )

    try:
        return json.loads(content)
    except Exception as e:
        return {
            "ppn": ppn,
            "count": len(clean_holdings),
            "holdings": clean_holdings,
            "summary": None,
            "_llm_parse_error": str(e),
            "_llm_raw": content,
        }


def read_json_stdin() -> Optional[Dict[str, Any]]:
    """
    Runner mode: if stdin is not a TTY and contains JSON, parse it.
    Expected minimal shape: {"ppn": "...", "format": "json|csv|table|geojson", ...}
    """
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ppn", nargs="?", help="PPN Sudoc (ex: 123456789). If omitted, read JSON from stdin.")
    ap.add_argument("--timeout", type=int, default=20, help="HTTP timeout (seconds)")
    ap.add_argument("--format", choices=["json", "table", "geojson", "csv"], default="json", help="Output format")

    # artifacts
    ap.add_argument("--outdir", default=os.getenv("SKILL_OUTPUT_DIR", "./outputs"), help="Output dir for artifacts")

    # LLM post-process (optional)
    ap.add_argument("--llm", action="store_true", help="Post-traiter la sortie via un endpoint chat completions.")
    ap.add_argument("--llm-url", default=os.getenv("LLM_URL", DEFAULT_LLM_URL), help="Chat completions endpoint.")
    ap.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "local-model"), help="Model name placeholder.")
    ap.add_argument("--llm-mode", choices=["clean_json", "summary"], default="clean_json", help="LLM postprocess mode.")
    ap.add_argument("--llm-api-key", default=os.getenv("LLM_API_KEY"), help="Bearer API key (optional).")

    args = ap.parse_args()

    # Runner mode: stdin JSON overrides CLI (except if ppn explicitly given)
    stdin_obj = read_json_stdin()
    if stdin_obj and not args.ppn:
        args.ppn = stdin_obj.get("ppn") or stdin_obj.get("PPN")
        args.format = stdin_obj.get("format", args.format)
        args.timeout = int(stdin_obj.get("timeout", args.timeout))
        args.outdir = stdin_obj.get("outdir", args.outdir)

        llm_cfg = stdin_obj.get("llm") or {}
        if isinstance(llm_cfg, dict):
            args.llm = bool(llm_cfg.get("enabled", args.llm))
            args.llm_url = llm_cfg.get("url", args.llm_url)
            args.llm_model = llm_cfg.get("model", args.llm_model)
            args.llm_mode = llm_cfg.get("mode", args.llm_mode)
            args.llm_api_key = llm_cfg.get("api_key", args.llm_api_key)

    if not args.ppn:
        print("[ERROR] Missing ppn (CLI positional or stdin JSON).", file=sys.stderr)
        return 1

    try:
        data = fetch_multiwhere(args.ppn, timeout_s=args.timeout)
        holdings = parse_multiwhere_payload(data)

        if args.format == "table":
            print(format_table(holdings))
            return 0

        if args.format == "geojson":
            gj = to_geojson(args.ppn, holdings)
            print(json.dumps(gj, ensure_ascii=False, indent=2))
            return 0

        if args.format == "csv":
            outdir = Path(args.outdir)
            csv_path = outdir / "abes_multiwhere.csv"
            write_csv(csv_path, args.ppn, holdings)
            # stdout stays JSON for runner-friendliness
            print(
                json.dumps(
                    {
                        "ppn": args.ppn,
                        "count": len(holdings),
                        "holdings": holdings,
                        "artifacts": [{"name": "result_csv", "path": str(csv_path)}],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        # json
        base_out: Dict[str, Any] = {"ppn": args.ppn, "count": len(holdings), "holdings": holdings}

        if args.llm:
            llm_out = llm_postprocess_holdings(
                ppn=args.ppn,
                holdings=holdings,
                llm_url=args.llm_url,
                llm_model=args.llm_model,
                mode=args.llm_mode,
                api_key=args.llm_api_key,
            )
            print(json.dumps(llm_out, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(base_out, ensure_ascii=False, indent=2))

        return 0

    except requests.HTTPError as e:
        print(f"[ERROR] HTTP error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())