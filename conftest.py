"""Marks this directory as pytest's rootdir.

Having a conftest.py here (even an empty one) makes pytest add the
project root to sys.path during test collection, so `import config`
and `from main import ...` resolve correctly no matter how pytest is
invoked (bare `pytest`, `python -m pytest`, from CI, etc.) -- without
this, tests/ has no __init__.py, so pytest would only add tests/
itself to sys.path, and imports of top-level modules would fail.
"""
