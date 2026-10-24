"""LLM providers (Ollama local models, Google Gemini) behind one chat interface,
with a persistent SQLite cache so experiments are resumable and reproducible."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .dataset import ROOT

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

CACHE_PATH = ROOT / "results" / "cache" / "llm_cache.sqlite"


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    error: str | None = None


class Cache:
    def __init__(self, path: Path = CACHE_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT, ts REAL)")
        self._db.commit()

    def get(self, key: str) -> Completion | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM c WHERE k=?", (key,)).fetchone()
        if not row:
            return None
        d = json.loads(row[0])
        return Completion(**{**d, "cached": True})

    def put(self, key: str, comp: Completion) -> None:
        d = {k: v for k, v in comp.__dict__.items() if k != "cached"}
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO c VALUES (?,?,?)", (key, json.dumps(d), time.time()))
            self._db.commit()


_CACHE: Cache | None = None


def cache() -> Cache:
    global _CACHE
    if _CACHE is None:
        _CACHE = Cache()
    return _CACHE


class LLM:
    provider = "base"

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 2048, seed: int = 0, **opts):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self.opts = opts

    @property
    def name(self) -> str:
        suffix = self.opts.get("label_suffix", "")
        return f"{self.provider}:{self.model}{suffix}"

    def _key(self, system: str, messages: list[dict]) -> str:
        blob = json.dumps([self.provider, self.model, self.temperature, self.max_tokens, self.seed,
                           {k: v for k, v in self.opts.items() if k != "label_suffix"}, system, messages],
                          sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def chat(self, system: str, messages: list[dict]) -> Completion:
        key = self._key(system, messages)
        hit = cache().get(key)
        if hit is not None and hit.error is None:
            return hit
        comp = self._chat_with_retries(system, messages)
        if comp.error is None:
            cache().put(key, comp)
        return comp

    def _chat_with_retries(self, system: str, messages: list[dict], attempts: int = 6) -> Completion:
        delay = 5.0
        last = None
        for _ in range(attempts):
            try:
                return self._chat(system, messages)
            except QuotaExhausted as exc:
                return Completion(text="", error=f"quota exhausted: {exc}")
            except RetryableError as exc:
                last = exc
                time.sleep(exc.wait or delay)
                delay = min(delay * 2, 120)
            except requests.RequestException as exc:
                last = exc
                time.sleep(delay)
                delay = min(delay * 2, 120)
        return Completion(text="", error=f"failed after {attempts} attempts: {last}")

    def _chat(self, system: str, messages: list[dict]) -> Completion:  # pragma: no cover
        raise NotImplementedError


class QuotaExhausted(Exception):
    """A quota wall (e.g. a daily request cap) whose reset is too far away to wait for."""


class RetryableError(Exception):
    def __init__(self, msg: str, wait: float | None = None):
        super().__init__(msg)
        self.wait = wait


class Ollama(LLM):
    provider = "ollama"

    def _chat(self, system, messages):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens,
                        "num_ctx": self.opts.get("num_ctx", 8192), "seed": self.seed},
        }
        t0 = time.time()
        r = requests.post(f"{host}/api/chat", json=body, timeout=900)
        if r.status_code >= 500:
            raise RetryableError(f"ollama {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        d = r.json()
        return Completion(d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0),
                          time.time() - t0)


class Gemini(LLM):
    """Google Gemini via the public REST API (generativelanguage.googleapis.com).

    opts: thinking_budget (int; 0 reduces but does not fully disable thinking on gemini-3.8-flash), rpm (client-side rate limit)."""

    provider = "gemini"
    _lock = threading.Lock()
    _last_call = 0.0

    def _throttle(self):
        rpm = float(self.opts.get("rpm", 10))
        gap = 60.0 / rpm
        with Gemini._lock:
            wait = Gemini._last_call + gap - time.time()
            if wait > 0:
                time.sleep(wait)
            Gemini._last_call = time.time()

    def _chat(self, system, messages):
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")
        self._throttle()
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages]
        gen = {"temperature": self.temperature, "maxOutputTokens": self.max_tokens, "seed": self.seed}
        if "thinking_budget" in self.opts:
            gen["thinkingConfig"] = {"thinkingBudget": int(self.opts["thinking_budget"])}
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        t0 = time.time()
        r = _post_with_deadline(url, body, {"x-goog-api-key": key}, deadline_s=float(self.opts.get("deadline_s", 240)))
        if r.status_code in (429, 500, 502, 503, 504):
            wait = None
            try:
                for det in r.json().get("error", {}).get("details", []):
                    if "retryDelay" in det:
                        wait = float(det["retryDelay"].rstrip("s")) + 1
            except Exception:  # noqa: BLE001
                pass
            if wait is not None and wait > 900:  # waiting more than 15 minutes: report instead of sleeping for hours
                raise QuotaExhausted(f"gemini {r.status_code} on {self.model}; Google says retry in {wait / 3600:.1f} h")
            raise RetryableError(f"gemini {r.status_code}: {r.text[:300]}", wait)
        if r.status_code != 200:
            raise RuntimeError(f"gemini {r.status_code}: {r.text[:500]}")
        d = r.json()
        cands = d.get("candidates") or []
        text = ""
        if cands:
            parts = (cands[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        usage = d.get("usageMetadata", {})
        out_tok = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return Completion(text, usage.get("promptTokenCount", 0), out_tok, time.time() - t0)


def _post_with_deadline(url: str, body: dict, headers: dict, deadline_s: float) -> requests.Response:
    """POST with a hard wall-clock deadline. `requests`' timeout only bounds the gap between bytes, so a
    connection that trickles data (or a queued request) can block a run for hours. On expiry the request is
    abandoned and retried through the normal back-off path."""
    box: dict = {}

    def go():
        try:
            box["r"] = requests.post(url, json=body, headers=headers, timeout=(15, deadline_s))
        except Exception as exc:  # noqa: BLE001
            box["e"] = exc

    th = threading.Thread(target=go, daemon=True)
    th.start()
    th.join(deadline_s)
    if th.is_alive():
        raise RetryableError(f"gemini request exceeded the {deadline_s:.0f}s deadline", wait=2)
    if "e" in box:
        raise box["e"]
    return box["r"]


PROVIDERS = {"ollama": Ollama, "gemini": Gemini}


def make_llm(spec: dict) -> LLM:
    spec = dict(spec)
    cls = PROVIDERS[spec.pop("provider")]
    return cls(**spec)
