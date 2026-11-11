"""Plate text normalization, correction suggestions, and prototype validation."""
from __future__ import annotations

import re


PLATE_PATTERN = re.compile(r"^[A-Z]{1,4}[0-9]{1,4}$")
TO_LETTER = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"})
TO_DIGIT = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8"})


def normalize_plate_text(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


def is_valid_plate(value: str) -> bool:
    return bool(PLATE_PATTERN.fullmatch(normalize_plate_text(value)))


def suggest_plate_correction(value: str) -> str | None:
    """Return the lowest-change letters+digits candidate for common OCR confusions."""
    normalized = normalize_plate_text(value)
    if is_valid_plate(normalized):
        return normalized
    candidates: list[tuple[int, str]] = []
    for split in range(1, len(normalized)):
        prefix, suffix = normalized[:split], normalized[split:]
        corrected = prefix.translate(TO_LETTER) + suffix.translate(TO_DIGIT)
        if PLATE_PATTERN.fullmatch(corrected):
            changes = sum(a != b for a, b in zip(normalized, corrected))
            candidates.append((changes, corrected))
    return min(candidates, default=(0, ""))[1] or None


def analyze_plate_text(raw_text: str, confidence: float, confidence_threshold: float) -> dict:
    normalized = normalize_plate_text(raw_text)
    raw_valid = is_valid_plate(normalized)
    suggestion = normalized if raw_valid else suggest_plate_correction(normalized)
    accepted = confidence >= confidence_threshold and raw_valid
    reasons = []
    if confidence < confidence_threshold:
        reasons.append("LOW_CONFIDENCE")
    if not raw_valid:
        reasons.append("INVALID_FORMAT")
    return {
        "raw_text": raw_text,
        "normalized_text": normalized,
        "suggested_text": suggestion,
        "final_text": normalized if accepted else "",
        "valid_format": raw_valid,
        "review_status": "ACCEPTED" if accepted else "REVIEW_REQUIRED",
        "review_reason": "|".join(reasons),
    }
