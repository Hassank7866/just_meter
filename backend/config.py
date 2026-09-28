from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMERA_AREAS = (
    "Federal Territory",
    "Pakistan Provinces",
    "Mzd. Division",
    "Mirpur Division",
    "Poonch Division",
)
LOCAL_TIMEZONE = "Asia/Karachi"

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo(LOCAL_TIMEZONE)
except Exception:
    from datetime import timezone, timedelta
    LOCAL_TZ = timezone(timedelta(hours=5))


def get_local_now():
    from datetime import datetime
    return datetime.now(LOCAL_TZ)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = PROJECT_ROOT / "data"
    snapshots_dir: Path = data_dir / "snapshots"
    csv_path: Path = data_dir / "detections.csv"
    approved_vehicles_path: Path = data_dir / "approved_government_vehicles.csv"
    government_sightings_path: Path = data_dir / "government_vehicles_spotted.csv"
    min_plate_confidence: float = float(os.getenv("MIN_PLATE_CONFIDENCE", "0.70"))
    min_vehicle_confidence: float = float(os.getenv("MIN_VEHICLE_CONFIDENCE", "0.45"))
    duplicate_cooldown_seconds: int = int(os.getenv("DUPLICATE_COOLDOWN_SECONDS", "15"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


settings = Settings()
