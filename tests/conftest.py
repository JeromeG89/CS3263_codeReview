"""Shared fixtures. Tests import the package from src/ (no install needed)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from invcheck.dataset import Instance, load_dataset, load_examples  # noqa: E402


@pytest.fixture(scope="session")
def dataset() -> list[Instance]:
    return load_dataset()


@pytest.fixture(scope="session")
def by_id(dataset) -> dict[str, Instance]:
    return {i.id: i for i in dataset}


@pytest.fixture(scope="session")
def example() -> Instance:
    return load_examples()[0]
