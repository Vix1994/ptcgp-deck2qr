"""Compatibility module exposing domain validation."""

from .model import DeckValidationError, validate_deck

__all__ = ["DeckValidationError", "validate_deck"]
