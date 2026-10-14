#!/usr/bin/env python
"""List the Gemini models this API key can call with generateContent.

Google renames and retires model ids; run this before a Gemini evaluation and make
sure the ids in configs/gemini.yaml appear in the output. Reads GEMINI_API_KEY
(or GOOGLE_API_KEY) from the environment or .env; the key is never printed.

  python scripts/list_gemini_models.py
  python scripts/list_gemini_models.py --filter flash
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
URL = "https://generativelanguage.googleapis.com/v1beta/models"


def list_models(key: str) -> list[dict]:
    models, token = [], None
    while True:
        params = {"pageSize": 1000, **({"pageToken": token} if token else {})}
        r = requests.get(URL, params=params, headers={"x-goog-api-key": key}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"error {r.status_code}: {r.text.replace(key, '<redacted>')[:500]}")
        d = r.json()
        models.extend(d.get("models", []))
        token = d.get("nextPageToken")
        if not token:
            return models


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default="", help="substring filter on model ids")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set (put it in .env)")
    rows = [m for m in list_models(key)
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and args.filter in m.get("name", "")]
    print(f"{'model id (use in configs/*.yaml)':<44} {'in tok':>8} {'out tok':>8} {'thinking':>8}  display name")
    for m in sorted(rows, key=lambda m: m["name"]):
        print(f"{m['name'].removeprefix('models/'):<44} {m.get('inputTokenLimit', '?'):>8} "
              f"{m.get('outputTokenLimit', '?'):>8} {str(m.get('thinking', '-')):>8}  {m.get('displayName', '')}")
    print(f"\n{len(rows)} models support generateContent")


if __name__ == "__main__":
    main()
