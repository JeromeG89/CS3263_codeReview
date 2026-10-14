"""Extraction of verdicts and Python code from free-form model output."""
from __future__ import annotations

import pytest

from invcheck.parse import extract_python, parse_verdict


def test_fenced_json():
    text = ('Reasoning...\n```json\n{"verdict": "UNSAFE", "violation": "overflow", '
            '"witness": {"x": -2147483648, "d": -1}, "explanation": "INT_MIN / -1"}\n```\n')
    p = parse_verdict(text)
    assert p == {"verdict": "UNSAFE", "violation": "overflow", "witness": {"x": -2147483648, "d": -1},
                 "explanation": "INT_MIN / -1", "parse": "json"}


def test_bare_json_lowercase_verdict():
    p = parse_verdict('Answer: {"verdict": "safe", "violation": "none", "witness": null}')
    assert (p["verdict"], p["witness"], p["parse"]) == ("SAFE", None, "json")


def test_last_json_object_wins():
    text = '{"verdict": "SAFE"} on reflection {"verdict": "UNSAFE", "witness": {"a": [1, 2], "n": 2}}'
    p = parse_verdict(text)
    assert p["verdict"] == "UNSAFE" and p["witness"] == {"a": [1, 2], "n": 2}


def test_lenient_json():
    p = parse_verdict("{'verdict': 'UNSAFE', 'witness': {'x': INT_MIN, 'd': -1,}, 'explanation': 'x / d overflows',}")
    assert p["parse"] == "json" and p["verdict"] == "UNSAFE"
    assert p["witness"] == {"x": "INT_MIN", "d": -1}
    p = parse_verdict('{"verdict": "UNSAFE", "witness": {"x": 5}, // a comment\n "ok": True, "w": None}')
    assert p["parse"] == "json" and p["witness"] == {"x": 5}


def test_non_dict_witness_dropped():
    p = parse_verdict('{"verdict": "UNSAFE", "witness": [1, 2]}')
    assert p["verdict"] == "UNSAFE" and p["witness"] is None


def test_lenient_json_with_constant_in_explanation():
    p = parse_verdict('{"verdict": "UNSAFE", "witness": {"x": INT_MIN, "d": -1}, "explanation": "INT_MIN / -1"}')
    assert p["parse"] == "json" and p["witness"] == {"x": "INT_MIN", "d": -1}


@pytest.mark.parametrize("text, verdict, how", [
    ("The function is UNSAFE because n may be 0.", "UNSAFE", "keyword"),
    ("At first it looks UNSAFE, but it is SAFE.", "SAFE", "keyword"),
    ('{"verdict": "MAYBE"}', "UNKNOWN", "failed"),
    ("I am not sure.", "UNKNOWN", "failed"),
    ("", "UNKNOWN", "failed"),
    ("{{{ broken", "UNKNOWN", "failed"),
])
def test_keyword_fallback_and_garbage(text, verdict, how):
    p = parse_verdict(text)
    assert (p["verdict"], p["parse"]) == (verdict, how)
    if how != "json":
        assert p["witness"] is None


def test_extract_fenced_python():
    text = "Here:\n```python\nfrom z3 import *\ns = Solver()\n```\nDone."
    assert extract_python(text) == "from z3 import *\ns = Solver()\n"


def test_extract_prefers_z3_block():
    text = ("```python\nprint('helper')\n```\n"
            "```py\nfrom z3 import *\nx = Int('x')\ns = Solver()\n```\n")
    assert extract_python(text) == "from z3 import *\nx = Int('x')\ns = Solver()\n"


def test_extract_unlabelled_fence():
    assert extract_python("```\nimport z3\ns = z3.Solver()\n```") == "import z3\ns = z3.Solver()\n"


def test_extract_unfenced_python():
    text = "Sure, here is the script.\nfrom z3 import *\nx = Int('x')\ns = Solver()\n"
    assert extract_python(text) == "from z3 import *\nx = Int('x')\ns = Solver()\n"


def test_extract_no_code():
    assert extract_python("The function is SAFE.") is None
