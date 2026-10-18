#!/usr/bin/env python
"""Show the models and free-tier limits an OpenAI-compatible API key (Groq, OpenRouter) gives you.

  python scripts/list_llm_limits.py --provider groq --models          # model ids
  python scripts/list_llm_limits.py --provider groq                   # limits for the models in configs/groq.yaml

Limits are read from the x-ratelimit-* response headers of one tiny request per model.
The API key is never printed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.dataset import ROOT  # noqa: E402
from invcheck.llm import PROVIDERS  # noqa: E402,F401  (importing llm loads .env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="groq", choices=["groq", "openrouter"])
    ap.add_argument("--models", action="store_true", help="list available model ids instead")
    args = ap.parse_args()
    cls = PROVIDERS[args.provider]
    key = os.environ.get(cls.key_env)
    if not key:
        sys.exit(f"{cls.key_env} is not set (put it in .env)")
    hdr = {"Authorization": f"Bearer {key}"}
    if args.models:
        r = requests.get(f"{cls.base_url}/models", headers=hdr, timeout=60)
        r.raise_for_status()
        for m in sorted(r.json().get("data", []), key=lambda m: m["id"]):
            print(m["id"])
        return
    cfg = yaml.safe_load(open(ROOT / "configs" / f"{args.provider}.yaml"))
    for spec in cfg["models"]:
        r = requests.post(f"{cls.base_url}/chat/completions", headers=hdr, timeout=120,
                          json={"model": spec["model"], "max_tokens": 4, "messages": [{"role": "user", "content": "OK"}]})
        h = {k.lower(): v for k, v in r.headers.items()}
        print(f"{spec['model']}: HTTP {r.status_code}")
        if r.status_code != 200:
            print("   ", r.text[:300].replace(key, "<key>"))
        for k in ("x-ratelimit-limit-requests", "x-ratelimit-remaining-requests", "x-ratelimit-limit-tokens",
                  "x-ratelimit-remaining-tokens", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
            if k in h:
                print(f"    {k}: {h[k]}")


if __name__ == "__main__":
    main()
