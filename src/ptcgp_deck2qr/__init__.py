"""PTCG Pocket screenshot-to-deck-text toolkit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ptcgp-deck2qr")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0+uninstalled"

__all__ = ["__version__"]
