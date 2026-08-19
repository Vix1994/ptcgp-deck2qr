"""Adapter for the external pokemon-tcg-pocket-database release."""

from .errors import DatabaseError, DatabaseSchemaError, IndexSourceMismatch
from .identities import parse_image_identity
from .loader import CardDatabase, load_database
from .models import CardEntityKey, CardPrint, CardPrintKey, CardVisual, SourceManifest

__all__ = [
    "CardDatabase",
    "CardEntityKey",
    "CardPrint",
    "CardPrintKey",
    "CardVisual",
    "DatabaseError",
    "DatabaseSchemaError",
    "IndexSourceMismatch",
    "SourceManifest",
    "load_database",
    "parse_image_identity",
]
