"""IDP package exports."""

from importlib.metadata import version

__all__ = ["__version__"]


def __getattr__(name: str):  # pragma: no cover
    if name == "__version__":
        try:
            return version("intelligent-document-understanding")
        except Exception:
            return "0.0.0"
    raise AttributeError(name)
