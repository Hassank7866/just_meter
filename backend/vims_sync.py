"""Offline adapter: preview by default; --apply revalidates then imports atomically."""
import argparse
import json
from pathlib import Path

from .vims_schema import VimsBatch
from .vims_store import VimsConflict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        with args.file.open("rb") as handle:
            content = handle.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Import exceeds the 5 MiB limit")
        batch = VimsBatch.model_validate_json(content)
        from .storage import store
        result = store.vims_sync(batch, "system:vims-offline-cli", preview=True)
        if args.apply:
            result = store.vims_sync(batch, "system:vims-offline-cli", expected_revision=result["base_revision"])
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, VimsConflict) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
