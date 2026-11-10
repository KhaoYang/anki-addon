"""Anki entry point. Importing the package outside Anki keeps core modules testable."""

try:
    from aqt import mw
except ImportError:
    mw = None

if mw is not None:
    from .integration import install

    install()
