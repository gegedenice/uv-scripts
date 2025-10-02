# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
import argparse, json, httpx, sys
ap = argparse.ArgumentParser()
ap.add_argument("--inbox", required=True)
ap.add_argument("--payload", required=True, help="JSON file")
a = ap.parse_args()
response = httpx.get(a.payload)
response.raise_for_status() # Raise an exception for bad status codes
data = json.loads(response.text)
r = httpx.post(a.inbox, headers={"Content-Type":"application/ld+json"}, json=data, timeout=30)
r.raise_for_status()
print("Sent:", r.json())