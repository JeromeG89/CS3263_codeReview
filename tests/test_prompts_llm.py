"""Prompts must not leak ground truth; run configs must build valid LLM clients (no network)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from invcheck import prompts
from invcheck.dataset import ROOT
from invcheck.llm import Gemini, Ollama, make_llm

CONFIGS = sorted((ROOT / "configs").glob("*.yaml"))


def _all_prompts(inst, example) -> list[str]:
    return [prompts.direct(inst), prompts.direct_cot(inst), prompts.z3(inst), prompts.z3_guided(inst, example)]


def test_prompts_do_not_leak_ground_truth(dataset, example):
    for inst in dataset:
        for text in _all_prompts(inst, example):
            assert inst.id not in text and inst.pair not in text
            assert inst.reference_z3.strip() not in text
            for secret in (inst.description, inst.bug_explanation):
                assert not secret or secret not in text, inst.id
            assert inst.code.strip() in text


def test_guided_prompt_contains_example(by_id, example):
    text = prompts.z3_guided(by_id["T1-DIV-01-U"], example)
    assert example.reference_z3.strip() in text and "Now the actual task." in text
    assert text.count(prompts.Z3_PROTOCOL) == 2


def test_repair_messages():
    assert "name_error" in prompts.repair_error("name_error", "NameError: foo")
    assert "spurious" in prompts.repair_counterexample({"x": 1}, "", "not_reproduced")
    assert "preconditions" in prompts.repair_counterexample({"x": 1}, "x > 0", "precondition_violated")


@pytest.mark.parametrize("path", CONFIGS, ids=[p.stem for p in CONFIGS])
def test_configs_build_clients(path: Path):
    cfg = yaml.safe_load(path.read_text())
    assert {"run_name", "models", "approaches"} <= cfg.keys()
    assert set(cfg["approaches"]) <= {"direct", "direct_cot", "z3", "z3_guided", "z3_repair"}
    names = [make_llm(spec).name for spec in cfg["models"]]
    assert len(names) == len(set(names)), "two model entries would write records under the same name"


def test_gemini_config():
    cfg = yaml.safe_load((ROOT / "configs" / "gemini.yaml").read_text())
    assert cfg["run_name"] == "gemini" and cfg["workers"] == 2 and cfg["max_repairs"] == 3
    llms = [make_llm(spec) for spec in cfg["models"]]
    assert [type(m) for m in llms] == [Gemini, Gemini]
    assert [m.name for m in llms] == ["gemini:gemini-3.5-flash-lite", "gemini:gemini-3.8-flash"]
    for m in llms:
        assert (m.temperature, m.max_tokens) == (0.0, 4096)
    # flash-lite rejects thinkingBudget, so only 3.8 Flash sets it
    assert [m.opts for m in llms] == [{"rpm": 10}, {"thinking_budget": 0, "rpm": 10}]


def test_cache_key_depends_on_options():
    a = make_llm({"provider": "gemini", "model": "g", "thinking_budget": 0})
    b = make_llm({"provider": "gemini", "model": "g", "thinking_budget": -1})
    c = make_llm({"provider": "gemini", "model": "g", "thinking_budget": 0, "label_suffix": "+x"})
    msgs = [{"role": "user", "content": "hi"}]
    assert a._key("sys", msgs) != b._key("sys", msgs)
    assert a._key("sys", msgs) == c._key("sys", msgs)  # the label does not change the request
    assert c.name == "gemini:g+x"
    assert isinstance(make_llm({"provider": "ollama", "model": "m"}), Ollama)


def test_parse_wait_formats():
    from invcheck.llm import _parse_wait
    assert _parse_wait("Please try again in 7m12.5s.") == 432.5
    assert _parse_wait("850ms") == 0.85
    assert _parse_wait("30") == 30.0
    assert _parse_wait("no hint here") is None


def test_groq_config_builds_without_network():
    from invcheck.llm import Groq
    cfg = yaml.safe_load((ROOT / "configs" / "groq.yaml").read_text())
    llms = [make_llm(spec) for spec in cfg["models"]]
    assert all(isinstance(m, Groq) for m in llms)
    assert all(m.temperature == 0.0 for m in llms)
