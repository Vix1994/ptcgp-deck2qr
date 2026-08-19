"""Rights-cleared synthetic database and screenshot builders for tests."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


def make_database(root: Path, *, count: int = 10) -> Path:
    """Create a tiny upstream-shaped database using generated geometric art."""

    dist = root / "dist"
    image_root = dist / "images" / "cards-by-set" / "A1"
    image_root.mkdir(parents=True)
    cards: list[dict[str, object]] = []
    for number in range(1, count + 1):
        is_pokemon = number <= max(1, count // 2)
        prefix = "cPK" if is_pokemon else "cTR"
        entity = number if is_pokemon else number + 100
        image_name = f"{prefix}_10_{entity:06d}_00_SYNTH_{number}_C.webp"
        image = synthetic_card(number)
        cv2.imwrite(str(image_root / f"{number}.webp"), image)
        cards.append(
            {
                "set": "A1",
                "number": number,
                "rarity": "C",
                "name": f"Synthetic Card {number}",
                "image": image_name,
            }
        )
    (dist / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
    (dist / "sets.json").write_text(
        json.dumps(
            {
                "A": [
                    {
                        "code": "A1",
                        "releaseDate": "2024-01-01",
                        "count": count,
                        "name": {"en": "Synthetic"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return dist


def synthetic_card(number: int) -> Image:
    image = np.zeros((170, 120, 3), dtype=np.uint8)
    image[:] = ((number * 19) % 255, (number * 37) % 255, (number * 61) % 255)
    cv2.rectangle(image, (2, 2), (117, 167), (255, 255, 255), 2)
    cv2.putText(
        image,
        str(number),
        (20, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        2,
        (0, 0, 0),
        3,
        cv2.LINE_AA,
    )
    return image


def make_screenshot(path: Path, *, copies: int = 20, card_count: int = 10) -> None:
    canvas = np.full((4 * 210, 5 * 160, 3), 255, dtype=np.uint8)
    for index in range(copies):
        number = index % card_count + 1
        card = synthetic_card(number)
        y = (index // 5) * 210
        x = (index % 5) * 160
        canvas[y : y + card.shape[0], x : x + card.shape[1]] = card
    cv2.imwrite(str(path), canvas)


def make_quantity_screenshot(path: Path, *, card_count: int = 10) -> None:
    """Build a quantity-cell deck-list fixture with ten ``x2`` entries."""

    canvas = np.full((2 * 210, 5 * 240, 3), 255, dtype=np.uint8)
    for index in range(10):
        number = index % card_count + 1
        # A landscape thumbnail is derived from the same illustration area used
        # by the matcher, rather than embedding any external card asset.
        artwork = cv2.resize(synthetic_card(number)[13:95, 10:110], (215, 135))
        x = (index % 5) * 240 + 10
        y = (index // 5) * 210 + 10
        canvas[y : y + 135, x : x + 215] = artwork
        cv2.rectangle(canvas, (x, y + 143), (x + 215, y + 185), (65, 65, 65), -1)
        cv2.putText(
            canvas,
            "Quantity",
            (x + 65, y + 164),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            "2",
            (x + 103, y + 183),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), canvas)


def make_count_text_screenshot(path: Path, *, card_count: int = 10) -> None:
    """Build a dark deck-list fixture with a right-aligned ``x2`` label."""

    canvas = np.full((2 * 270, 5 * 170, 3), (12, 20, 30), dtype=np.uint8)
    for index in range(10):
        number = index % card_count + 1
        card = synthetic_card(number)
        x = (index % 5) * 170 + 20
        y = (index // 5) * 270 + 10
        canvas[y : y + 170, x : x + 120] = card
        cv2.putText(
            canvas,
            f"Card {number}",
            (x + 8, y + 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (60, 150, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            "x2",
            (x + 82, y + 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (60, 150, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), canvas)


def make_badge_screenshot(path: Path, *, card_count: int = 10) -> None:
    """Build a card grid with realistic external red count badges."""

    canvas = np.full((2 * 240, 5 * 170, 3), (25, 25, 25), dtype=np.uint8)
    for index in range(10):
        number = index % card_count + 1
        card = synthetic_card(number)
        x = (index % 5) * 170 + 20
        y = (index // 5) * 240 + 10
        canvas[y : y + 170, x : x + 120] = card
        # The marker is just outside the lower-right corner, matching the
        # common badge treatment while leaving the card contour detectable.
        center = (x + 136, y + 180)
        cv2.circle(canvas, center, 16, (20, 20, 220), -1)
        cv2.putText(
            canvas,
            "2",
            (center[0] - 6, center[1] + 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), canvas)
