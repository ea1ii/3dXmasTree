import json
import re
from pathlib import Path

import numpy as np
from PIL import Image


VIEWS = ("front", "back", "left", "right")
FRAME_PATTERN = re.compile(r"^(front|back|left|right)_LED_(\d{3})\.(?:jpg|jpeg|png)$", re.IGNORECASE)
SESSION_PATTERN = re.compile(r"^\d{8}_\d{4}$")


def source_timestamp(folder):
    timestamp = Path(folder).name
    if not SESSION_PATTERN.fullmatch(timestamp):
        raise ValueError("Select a frame session folder named yyyymmdd_hhmm")
    return timestamp


def load_frame_paths(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Not a frame folder: {folder}")

    frames = {view: {} for view in VIEWS}
    for path in folder.iterdir():
        match = FRAME_PATTERN.match(path.name)
        if match and path.is_file():
            view = match.group(1).lower()
            led_index = int(match.group(2))
            frames[view][led_index] = path

    if any(not frames[view] for view in VIEWS):
        missing = [view for view in VIEWS if not frames[view]]
        raise ValueError(f"Frame folder is missing viewpoints: {', '.join(missing)}")

    index_sets = {view: set(frames[view]) for view in VIEWS}
    expected = index_sets["front"]
    mismatched = {
        view: sorted(indices.symmetric_difference(expected))
        for view, indices in index_sets.items()
        if indices != expected
    }
    if mismatched:
        details = "; ".join(
            f"{view} differs at LED indices {indices}"
            for view, indices in mismatched.items()
        )
        raise ValueError(f"Viewpoints must contain matching LED indices: {details}")

    return sorted(expected), frames


def detect_brightest_spot(image_path):
    with Image.open(image_path) as source:
        rgb = np.asarray(source.convert("RGB"), dtype=np.float32)

    height, width, _ = rgb.shape
    border = np.concatenate(
        (
            rgb[0, :, :].reshape(-1, 3),
            rgb[-1, :, :].reshape(-1, 3),
            rgb[:, 0, :].reshape(-1, 3),
            rgb[:, -1, :].reshape(-1, 3),
        ),
        axis=0,
    )
    background = float(np.median(np.max(border, axis=1)))
    brightness = np.max(rgb, axis=2)
    peak = float(brightness.max())
    contrast = peak - background
    if contrast < 20:
        raise ValueError(f"No distinct bright LED spot detected in {Path(image_path).name}")

    threshold = background + contrast * 0.68
    weights = np.maximum(brightness - threshold, 0.0)
    peak_y, peak_x = np.unravel_index(np.argmax(brightness), brightness.shape)
    crop_radius = max(12, round(min(width, height) * 0.12))
    top = max(0, peak_y - crop_radius)
    bottom = min(height, peak_y + crop_radius + 1)
    left = max(0, peak_x - crop_radius)
    right = min(width, peak_x + crop_radius + 1)
    local_weights = weights[top:bottom, left:right]
    total_weight = float(local_weights.sum())
    if total_weight <= 0:
        return {"x": float(peak_x), "y": float(peak_y), "width": width, "height": height}

    local_y, local_x = np.mgrid[top:bottom, left:right]
    center_x = float((local_x * local_weights).sum() / total_weight)
    center_y = float((local_y * local_weights).sum() / total_weight)
    return {"x": center_x, "y": center_y, "width": width, "height": height}


def _pixels_to_world(view, detection, frame_height_mm):
    image_width = detection["width"]
    image_height = detection["height"]
    frame_width_mm = frame_height_mm * image_width / image_height
    normalized_right = detection["x"] / image_width - 0.5
    z_mm = frame_height_mm * (1 - detection["y"] / image_height)

    if view == "front":
        return None, normalized_right * frame_width_mm, z_mm
    if view == "back":
        return None, -normalized_right * frame_width_mm, z_mm
    if view == "left":
        return normalized_right * frame_width_mm, None, z_mm
    if view == "right":
        return -normalized_right * frame_width_mm, None, z_mm
    raise ValueError(f"Unknown view: {view}")


def constrain_max_spacing(points, max_distance_mm):
    if max_distance_mm <= 0:
        raise ValueError("max_distance_mm must be positive")
    adjusted = []
    for point in points:
        candidate = {key: point[key] for key in ("index", "x", "y", "z", "valid", "match_error_mm", "warnings")}
        candidate["adjusted"] = False
        if adjusted:
            previous = adjusted[-1]
            delta = np.array(
                (candidate["x"] - previous["x"], candidate["y"] - previous["y"], candidate["z"] - previous["z"]),
                dtype=float,
            )
            distance = float(np.linalg.norm(delta))
            if distance > max_distance_mm:
                corrected = np.array((previous["x"], previous["y"], previous["z"])) + delta * (max_distance_mm / distance)
                candidate["x"], candidate["y"], candidate["z"] = map(float, corrected)
                candidate["adjusted"] = True
                candidate["warnings"] = list(candidate["warnings"]) + [
                    f"Moved to satisfy {max_distance_mm:g} mm maximum spacing"
                ]
        adjusted.append(candidate)
    return adjusted


def positions_from_detections(
    detections,
    led_indices,
    frame_height_mm,
    match_tolerance_mm,
    max_distance_mm,
):
    if frame_height_mm <= 0 or match_tolerance_mm < 0:
        raise ValueError("Frame height must be positive and tolerance cannot be negative")

    points = []
    for index in led_indices:
        front_x, front_y, front_z = _pixels_to_world("front", detections["front"][index], frame_height_mm)
        back_x, back_y, back_z = _pixels_to_world("back", detections["back"][index], frame_height_mm)
        left_x, left_y, left_z = _pixels_to_world("left", detections["left"][index], frame_height_mm)
        right_x, right_y, right_z = _pixels_to_world("right", detections["right"][index], frame_height_mm)

        y_error = abs(front_y - back_y)
        x_error = abs(left_x - right_x)
        z_values = (front_z, back_z, left_z, right_z)
        z_error = max(z_values) - min(z_values)
        match_error = max(y_error, x_error, z_error)
        warnings = []
        if y_error > match_tolerance_mm:
            warnings.append(f"Front/back mismatch {y_error:.1f} mm")
        if x_error > match_tolerance_mm:
            warnings.append(f"Left/right mismatch {x_error:.1f} mm")
        if z_error > match_tolerance_mm:
            warnings.append(f"View height mismatch {z_error:.1f} mm")

        points.append(
            {
                "index": index,
                "x": (left_x + right_x) / 2,
                "y": (front_y + back_y) / 2,
                "z": sum(z_values) / len(z_values),
                "valid": not warnings,
                "match_error_mm": match_error,
                "warnings": warnings,
            }
        )

    return constrain_max_spacing(points, max_distance_mm)


def calibrate_frame_set(
    frame_paths,
    led_indices,
    frame_height_mm,
    match_tolerance_mm,
    max_distance_mm,
):
    detections = {
        view: {index: detect_brightest_spot(frame_paths[view][index]) for index in led_indices}
        for view in VIEWS
    }
    points = positions_from_detections(
        detections,
        led_indices,
        frame_height_mm,
        match_tolerance_mm,
        max_distance_mm,
    )
    return points, detections


def save_positions(path, points, source_timestamp):
    payload = {
        "source_timestamp": source_timestamp,
        "units": "mm",
        "positions": [
            {
                "index": point["index"],
                "x": round(point["x"], 2),
                "y": round(point["y"], 2),
                "z": round(point["z"], 2),
            }
            for point in points
        ],
    }
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
