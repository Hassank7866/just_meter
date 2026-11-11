"""Helpers for enforcing the existing warning-to-challan escalation stage."""
from __future__ import annotations


def is_challan_stage(record: dict) -> bool:
    """Use the violations summary stage, with the current threshold as fallback."""
    stage_type = str(record.get("stage_type") or "").strip().lower()
    if stage_type:
        return stage_type == "challan"

    try:
        total_violations = int(record.get("total_violations") or record.get("violation_count") or 0)
    except (TypeError, ValueError):
        return False
    return total_violations >= 4
