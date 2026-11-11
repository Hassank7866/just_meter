"""Conservative one-to-one association of nearby boxes within one camera stream."""
from __future__ import annotations

from math import hypot


def match_score(previous: list[int], current: list[int]) -> float:
    """Return zero when boxes are too far apart to safely share an identity."""
    ax1, ay1, ax2, ay2 = previous
    bx1, by1, bx2, by2 = current
    if ax2 <= ax1 or ay2 <= ay1 or bx2 <= bx1 or by2 <= by1:
        return 0.0
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    overlap = intersection / union if union else 0.0
    center_distance = hypot((ax1 + ax2 - bx1 - bx2) / 2, (ay1 + ay2 - by1 - by2) / 2)
    scale = max(hypot(ax2 - ax1, ay2 - ay1), hypot(bx2 - bx1, by2 - by1))
    relative_distance = center_distance / scale if scale else 1.0
    if overlap < 0.15 and relative_distance > 0.35:
        return 0.0
    return overlap + max(0.0, 0.35 - relative_distance) * 0.5


def associate(vehicles: list[dict], recent_tracks: list) -> dict[int, object]:
    """Greedy global box matching; each track and detection is used at most once."""
    candidates = []
    for index, vehicle in enumerate(vehicles):
        for track in recent_tracks:
            if vehicle.get("label") != track.label:
                continue
            score = match_score(track.last_bbox, vehicle["bbox"])
            if score > 0:
                candidates.append((score, index, track))
    matches = {}
    used_tracks = set()
    for _, index, track in sorted(candidates, key=lambda item: item[0], reverse=True):
        if index not in matches and track.id not in used_tracks:
            matches[index] = track
            used_tracks.add(track.id)
    return matches


def crossing_direction(previous: list[int], current: list[int], width: int, height: int,
                       line: tuple[float, float, float, float]) -> str | None:
    """Return a finite-line crossing with a small dead band against box jitter."""
    if width <= 0 or height <= 0:
        return None
    ax, ay, bx, by = line
    dx, dy = bx - ax, by - ay
    length = hypot(dx, dy)
    if length < 0.05:
        return None
    first = ((previous[0] + previous[2]) / (2 * width),
             (previous[1] + previous[3]) / (2 * height))
    second = ((current[0] + current[2]) / (2 * width),
              (current[1] + current[3]) / (2 * height))
    side1 = (dx * (first[1] - ay) - dy * (first[0] - ax)) / length
    side2 = (dx * (second[1] - ay) - dy * (second[0] - ax)) / length
    if side1 * side2 >= 0 or min(abs(side1), abs(side2)) < 0.01:
        return None
    fraction = side1 / (side1 - side2)
    ix = first[0] + fraction * (second[0] - first[0])
    iy = first[1] + fraction * (second[1] - first[1])
    along = ((ix - ax) * dx + (iy - ay) * dy) / (length * length)
    if not 0 <= along <= 1:
        return None
    return "A_TO_B" if side1 > 0 else "B_TO_A"
