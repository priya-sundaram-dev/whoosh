#!python
# Metadata now lives in pyproject.toml (PEP 621). This shim remains only so that
# `pip install -e .` works on older toolchains; all configuration is declarative.
from setuptools import setup

if __name__ == "__main__":
    setup()
