"""Compact image fingerprints used by the baseline matcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

ARTWORK_CROP_POLICY_VERSION = "artwork-inner-0.2"
ImageArray = NDArray[Any]


@dataclass(frozen=True, slots=True)
class Fingerprint:
    phash: int
    dhash: int
    artwork_phash: int
    artwork_dhash: int
    color: tuple[float, ...]
    correlation: tuple[float, ...]
    artwork_color: tuple[float, ...]
    artwork_correlation: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phash": self.phash,
            "dhash": self.dhash,
            "artwork_phash": self.artwork_phash,
            "artwork_dhash": self.artwork_dhash,
            "color": list(self.color),
            "correlation": list(self.correlation),
            "artwork_color": list(self.artwork_color),
            "artwork_correlation": list(self.artwork_correlation),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> Fingerprint:
        color = _numeric_list(raw.get("color"), "color")
        correlation = _numeric_list(raw.get("correlation"), "correlation")
        artwork_color = _numeric_list(raw.get("artwork_color"), "artwork_color")
        artwork_correlation = _numeric_list(raw.get("artwork_correlation"), "artwork_correlation")
        values = (
            raw.get("phash"),
            raw.get("dhash"),
            raw.get("artwork_phash"),
            raw.get("artwork_dhash"),
        )
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            raise ValueError("fingerprint hashes must be integers")
        return cls(
            phash=values[0],  # type: ignore[arg-type]
            dhash=values[1],  # type: ignore[arg-type]
            artwork_phash=values[2],  # type: ignore[arg-type]
            artwork_dhash=values[3],  # type: ignore[arg-type]
            color=tuple(float(value) for value in color),
            correlation=tuple(float(value) for value in correlation),
            artwork_color=tuple(float(value) for value in artwork_color),
            artwork_correlation=tuple(float(value) for value in artwork_correlation),
        )


def fingerprint_image(image: ImageArray) -> Fingerprint:
    """Compute full-card, artwork, dHash, and HSV color signatures."""

    if image.size == 0:
        raise ValueError("cannot fingerprint an empty image")
    bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    artwork = _artwork_crop(bgr)
    artwork_gray = cv2.cvtColor(artwork, cv2.COLOR_BGR2GRAY)
    return Fingerprint(
        phash=_phash(gray),
        dhash=_dhash(gray),
        artwork_phash=_phash(artwork_gray),
        artwork_dhash=_dhash(artwork_gray),
        color=_color_signature(bgr),
        correlation=_correlation_signature(gray),
        artwork_color=_color_signature(artwork),
        artwork_correlation=_correlation_signature(artwork_gray),
    )


def hash_similarity(first: Fingerprint, second: Fingerprint, *, artwork: bool = False) -> float:
    """Return normalized Hamming similarity, not a calibrated probability."""

    first_hash = first.artwork_phash if artwork else first.phash
    second_hash = second.artwork_phash if artwork else second.phash
    return 1.0 - _hamming(first_hash, second_hash) / 64.0


def fingerprint_distance(
    first: Fingerprint, second: Fingerprint, *, artwork: bool = False
) -> float:
    hash_distance = 1.0 - hash_similarity(first, second, artwork=artwork)
    first_dhash = first.artwork_dhash if artwork else first.dhash
    second_dhash = second.artwork_dhash if artwork else second.dhash
    first_color = first.artwork_color if artwork else first.color
    second_color = second.artwork_color if artwork else second.color
    first_correlation = first.artwork_correlation if artwork else first.correlation
    second_correlation = second.artwork_correlation if artwork else second.correlation
    d_distance = _hamming(first_dhash, second_dhash) / 64.0
    color_distance = float(np.mean(np.abs(np.asarray(first_color) - np.asarray(second_color))))
    correlation = _normalized_correlation(first_correlation, second_correlation)
    correlation_distance = 1.0 - (correlation + 1.0) / 2.0
    return (
        0.45 * hash_distance
        + 0.20 * d_distance
        + 0.20 * min(1.0, color_distance * 4.0)
        + 0.15 * correlation_distance
    )


def _artwork_crop(image: ImageArray) -> ImageArray:
    height, width = image.shape[:2]
    if width / max(1, height) > 1.05:
        return image
    # The lower part of a Pocket card contains text, attacks, and metadata.
    # Keep a stable interior crop of the illustration only; the policy version
    # is persisted in every generated index so it cannot silently drift.
    return image[int(height * 0.08) : int(height * 0.56), int(width * 0.08) : int(width * 0.92)]


def _numeric_list(value: object, name: str) -> list[int | float]:
    if not isinstance(value, list) or not all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"fingerprint {name} must be a numeric list")
    return value


def _phash(gray: ImageArray) -> int:
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(resized)
    low = dct[:8, :8]
    median = float(np.median([float(value) for value in low[1:, 1:].flat]))
    bits = 0
    for value in low.flat:
        bits = (bits << 1) | int(value > median)
    return bits


def _dhash(gray: ImageArray) -> int:
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = 0
    for row_index in range(8):
        row_values = [float(resized[row_index, column]) for column in range(9)]
        for index in range(len(row_values) - 1):
            left = row_values[index]
            right = row_values[index + 1]
            bits = (bits << 1) | int(left > right)
    return bits


def _color_signature(image: ImageArray) -> tuple[float, ...]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [8, 4], [0, 180, 0, 256]).flatten()
    total = float(histogram.sum()) or 1.0
    return tuple(float(value / total) for value in histogram)


def _correlation_signature(gray: ImageArray) -> tuple[float, ...]:
    resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA).astype(np.float32)
    values = resized.flatten()
    mean = float(values.mean())
    standard_deviation = float(values.std())
    if standard_deviation < 1e-6:
        return tuple(0.0 for _ in values)
    return tuple(float((value - mean) / standard_deviation) for value in values)


def _normalized_correlation(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    first_array = np.asarray(first, dtype=np.float32)
    second_array = np.asarray(second, dtype=np.float32)
    first_norm = float(np.linalg.norm(first_array))
    second_norm = float(np.linalg.norm(second_array))
    if first_norm < 1e-6 or second_norm < 1e-6:
        return 0.0
    return float(np.dot(first_array, second_array) / (first_norm * second_norm))


def _hamming(first: int, second: int) -> int:
    return (first ^ second).bit_count()
