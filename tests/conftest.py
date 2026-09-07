"""Fixtures for scripts/check_drift.py. No network, no installed CLI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import click
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_drift.py"


@pytest.fixture(scope="session")
def drift():
    spec = importlib.util.spec_from_file_location("check_drift", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_drift"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_cli() -> click.Group:
    """A Click tree shaped like the parts of portolan-cli the tests need."""

    @click.group()
    def cli():
        pass

    @cli.command()
    @click.argument("path", required=False)
    @click.option("--auto", is_flag=True)
    @click.option("--license")
    @click.option("--title")
    def init(path, auto, license, title):
        pass

    @cli.command()
    @click.argument("path")
    @click.option("--pmtiles", is_flag=True)
    @click.option("--collection", "-c")
    def add(path, pmtiles, collection):
        pass

    @cli.command()
    @click.argument("destination")
    @click.option("--collection", "-c", required=True)
    def sync(destination, collection):
        pass

    @cli.group()
    def metadata():
        pass

    @metadata.command()
    def validate():
        pass

    return cli


@pytest.fixture
def fixtures() -> Path:
    return Path(__file__).parent / "fixtures"
