import json
import math
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
    adjusted = [
        {
            key: point[key]
            for key in ("index", "x", "y", "z", "valid", "match_error_mm", "warnings")
        }
        for point in points
    ]
    for candidate, point in zip(adjusted, points):
        candidate["adjusted"] = bool(point.get("adjusted", False))

    if not adjusted:
        return adjusted

    anchor = min(
        range(len(adjusted)),
        key=lambda position: (adjusted[position]["z"], adjusted[position]["index"]),
    )
    for step in (1, -1):
        positions = range(anchor + 1, len(adjusted)) if step == 1 else range(anchor - 1, -1, -1)
        for position in positions:
            candidate = adjusted[position]
            parent = adjusted[position - step]
            delta = np.array(
                (
                    candidate["x"] - parent["x"],
                    candidate["y"] - parent["y"],
                    candidate["z"] - parent["z"],
                ),
                dtype=float,
            )
            distance = float(np.linalg.norm(delta))
            if distance > max_distance_mm:
                corrected = np.array((parent["x"], parent["y"], parent["z"])) + delta * (
                    max_distance_mm / distance
                )
                candidate["x"], candidate["y"], candidate["z"] = map(float, corrected)
                candidate["adjusted"] = True
                candidate["warnings"] = list(candidate["warnings"]) + [
                    f"Moved to satisfy {max_distance_mm:g} mm maximum spacing"
                ]
    return adjusted


def guess_cone_fit(points, default_tree_height_mm):
    if not points or default_tree_height_mm <= 0:
        raise ValueError("Points and a positive default tree height are required")

    origin = min(points, key=lambda point: (point["z"], point["index"]))
    normalized = [
        (
            point["x"] - origin["x"],
            point["y"] - origin["y"],
            point["z"] - origin["z"],
        )
        for point in points
    ]
    maximum_z = max(point[2] for point in normalized)
    height_guess = max(default_tree_height_mm * 0.5, maximum_z / 0.92)
    height_scale = min(3.0, max(0.25, height_guess / default_tree_height_mm))

    base_radius = default_tree_height_mm * 0.34
    radius_ratios = []
    for x, y, z in normalized[1:]:
        fraction = z / height_guess
        if 0.04 <= fraction <= 0.90:
            expected_radius = base_radius * (1 - fraction)
            if expected_radius > 0:
                radius_ratios.append(math.hypot(x, y) / expected_radius)
    width_scale = min(
        3.0,
        max(0.25, (max(radius_ratios) * 1.05) if radius_ratios else 1.0),
    )
    return {
        "height_scale": height_scale,
        "width_scale": width_scale,
        "axis_offset": (0.0, 0.0, 0.0),
    }


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
        _, front_y, front_z = _pixels_to_world("front", detections["front"][index], frame_height_mm)
        _, back_y, back_z = _pixels_to_world("back", detections["back"][index], frame_height_mm)
        left_x, _, left_z = _pixels_to_world("left", detections["left"][index], frame_height_mm)
        right_x, _, right_z = _pixels_to_world("right", detections["right"][index], frame_height_mm)

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

    if not points:
        return []

    base_point = min(points, key=lambda point: (point["z"], point["index"]))
    base_x, base_y, base_z = base_point["x"], base_point["y"], base_point["z"]
    for point in points:
        point["x"] -= base_x
        point["y"] -= base_y
        point["z"] = max(0.0, point["z"] - base_z)

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


def save_positions(path, points, source_timestamp, cone_parameters=None):
    payload = {
        "source_timestamp": source_timestamp,
        "units": "mm",
        "cone": cone_parameters or {},
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
