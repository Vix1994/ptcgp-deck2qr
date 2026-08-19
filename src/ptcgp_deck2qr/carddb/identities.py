"""Upstream visual filename parsing."""

from __future__ import annotations

import re
from typing import cast

from .errors import DatabaseSchemaError
from .models import CardEntityKey, EntityType

_IMAGE_ID = re.compile(r"^(?P<prefix>cPK|cTR)_[^_]+_(?P<number>[0-9]{6})_")


def parse_image_identity(image_name: str) -> CardEntityKey:
    """Parse ``cPK``/``cTR`` and the six-digit game entity number."""

    match = _IMAGE_ID.match(image_name)
    if match is None:
        raise DatabaseSchemaError(f"unsupported card image filename: {image_name!r}")
    entity_type = "pokemon" if match.group("prefix") == "cPK" else "trainer"
    number = int(match.group("number"))
    if number <= 0:
        raise DatabaseSchemaError(f"invalid entity number in image filename: {image_name!r}")
    return CardEntityKey(entity_type=cast(EntityType, entity_type), number=number)
