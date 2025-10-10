#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests"
# ]
# ///

import requests
import argparse
import json
import sys

idref_ws_url = "https://www.idref.fr/services/"
json_suffix = "&format=text/json"

def get_abes_data(web_service: str, id: str):
    url = f"{idref_ws_url}{web_service}/{id}{json_suffix}"
    response = requests.get(url)
    return response.json()

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idref webservice basic."
    )
    parser.add_argument("--web-service", required=True, help="biblio |references | merged| merged_inv | idref2id | id2idref | iln2rcr | rcr2ilnata | idref2rnsr | iln2td3")
    parser.add_argument("--id", required=True, help="single id or list of id separated by comma")
    parser.add_argument("--json-output", required=False, action="store_true", help="Print raw JSON.")
    return parser.parse_args(argv)

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if args.json_output:
        print(json.dumps({"text": get_abes_data(args.web_service, args.id)}, ensure_ascii=False, indent=2))
    else:
        print(get_abes_data(args.web_service, args.id))
