"""Lazy-loaded ML models used by the API."""
from __future__ import annotations

from statistics import mean
from threading import Lock

import numpy as np

from .config import settings

VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class DetectorService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._alpr = None
        self._vehicle_model = None

    def _models(self) -> tuple[object, object]:
        """Load only on the first frame, keeping server startup fast."""
        with self._lock:
            if self._alpr is None:
                from fast_alpr import ALPR
                self._alpr = ALPR(
                    detector_conf_thresh=0.4,
                    ocr_model="cct-xs-v2-global-model",
                )
            if self._vehicle_model is None:
                from ultralytics import YOLO
                self._vehicle_model = YOLO("yolo11n.pt")
        return self._alpr, self._vehicle_model

    def detect(self, frame: np.ndarray) -> tuple[list[dict], list[dict]]:
        alpr, vehicle_model = self._models()
        vehicles: list[dict] = []
        yolo_result = vehicle_model(frame, verbose=False, conf=settings.min_vehicle_confidence)[0]
        for box in yolo_result.boxes:
            class_id = int(box.cls[0].item())
            if class_id not in VEHICLE_CLASS_IDS:
                continue
            vehicles.append({
                "label": VEHICLE_CLASS_IDS[class_id],
                "confidence": round(float(box.conf[0].item()), 4),
                "bbox": [int(value) for value in box.xyxy[0].tolist()],
            })

        plates: list[dict] = []
        for result in alpr.predict(frame):
            ocr = result.ocr
            if ocr is None or not ocr.text or not ocr.confidence:
                continue
            confidence = mean(ocr.confidence) if isinstance(ocr.confidence, list) else ocr.confidence
            raw_text = str(ocr.text).strip().upper()
            text = "".join(raw_text.split())
            bbox = result.detection.bounding_box
            plates.append({
                "plate_number": text,
                "raw_text": raw_text,
                "confidence": round(float(confidence), 4),
                "bbox": [int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2)],
            })
        return vehicles, plates


detectors = DetectorService()
