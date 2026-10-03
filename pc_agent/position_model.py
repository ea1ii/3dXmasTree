import math
import random
from io import BytesIO

import numpy as np
from PIL import Image


VIEW_RIGHT_AXES = {
    "front": "y",
    "right": "-x",
    "left": "x",
    "back": "-y",
}


def generate_strip_positions(led_count, max_distance_mm, tree_height_mm, frame_height_mm, seed=None):
    if led_count < 1:
        raise ValueError("led_count must be positive")
    if max_distance_mm <= 0:
        raise ValueError("max_distance_mm must be positive")
    if not 0 < tree_height_mm < frame_height_mm:
        raise ValueError("tree_height_mm must be positive and less than frame_height_mm")

    generator = random.Random(seed)
    base_z = (frame_height_mm - tree_height_mm) / 2
    base_radius = tree_height_mm * 0.34
    minimum_height = tree_height_mm * 0.05
    maximum_height = tree_height_mm * 0.95
    positions = [(0.0, 0.0, base_z)]

    height_bands = [0.12, 0.88, 0.36, 0.68, 0.22, 0.94, 0.52, 0.78, 0.16, 0.60, 0.32, 0.84]
    generator.shuffle(height_bands)
    band_size = max(1, math.ceil(max(1, led_count - 1) / len(height_bands)))

    for index in range(1, led_count):
        previous = positions[-1]
        band = height_bands[min((index - 1) // band_size, len(height_bands) - 1)]
        target_height = minimum_height + band * (maximum_height - minimum_height)
        accepted = None

        for _attempt in range(2000):
            direction_x = generator.gauss(0, 1)
            direction_y = generator.gauss(0, 1)
            direction_z = generator.gauss(0, 1)
            vertical_bias = max(
                -1.0,
                min(1.0, (base_z + target_height - previous[2]) / (max_distance_mm * 2)),
            )
            direction_z += vertical_bias * 2.2
            direction_length = math.sqrt(
                direction_x * direction_x
                + direction_y * direction_y
                + direction_z * direction_z
            )
            step_length = generator.uniform(0.65, 0.90) * max_distance_mm
            candidate = (
                previous[0] + direction_x / direction_length * step_length,
                previous[1] + direction_y / direction_length * step_length,
                previous[2] + direction_z / direction_length * step_length,
            )
            relative_height = candidate[2] - base_z
            if not minimum_height <= relative_height <= maximum_height:
                continue
            surface_radius = base_radius * (1 - relative_height / tree_height_mm) * 0.94
            if candidate[0] * candidate[0] + candidate[1] * candidate[1] > surface_radius * surface_radius:
                continue
            accepted = candidate
            break

        if accepted is None:
            raise RuntimeError("Could not generate a randomized LED path inside the tree")
        positions.append(accepted)

    return positions


def project_led_to_frame(position, view, image_width, image_height, frame_height_mm):
    if view not in VIEW_RIGHT_AXES:
        raise ValueError(f"Unknown view: {view}")
    if image_width <= 0 or image_height <= 0 or frame_height_mm <= 0:
        raise ValueError("Image dimensions and frame height must be positive")

    x, y, z = position
    screen_right = {
        "front": y,
        "right": -x,
        "left": x,
        "back": -y,
    }[view]
    frame_width_mm = frame_height_mm * image_width / image_height
    pixel_x = round(image_width * (0.5 + screen_right / frame_width_mm))
    pixel_y = round(image_height * (1 - z / frame_height_mm))
    return pixel_x, pixel_y


def add_synthetic_led_glow(
    image_bytes,
    pixel_position,
    max_led_distance_mm,
    frame_height_mm,
    background_level=0.02,
    seed=0,
):
    if not 0 <= background_level <= 1:
        raise ValueError("background_level must be between 0 and 1")
    if max_led_distance_mm <= 0 or frame_height_mm <= 0:
        raise ValueError("LED distance and frame height must be positive")

    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
    pixels = np.asarray(image, dtype=np.float32).copy()
    pixels *= background_level

    image_height, image_width = pixels.shape[:2]
    center_x, center_y = pixel_position
    radius = max(4, round(0.525 * max_led_distance_mm / frame_height_mm * image_height))
    left = max(0, center_x - radius)
    right = min(image_width, center_x + radius + 1)
    top = max(0, center_y - radius)
    bottom = min(image_height, center_y + radius + 1)
    if left >= right or top >= bottom:
        output = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
        buffer = BytesIO()
        output.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()

    yy, xx = np.mgrid[top:bottom, left:right]
    dx = xx - center_x
    dy = yy - center_y
    distance = np.sqrt(dx * dx + dy * dy)
    angle = np.arctan2(dy, dx)
    edge_warp = (
        1.0
        + 0.20 * np.sin(2 * angle + seed)
        + 0.13 * np.sin(5 * angle - seed * 0.7)
        + 0.09 * np.sin(9 * angle + seed * 0.3)
        + 0.05 * np.sin(13 * angle - seed * 0.2)
    )
    normalized_distance = distance / (radius * edge_warp)
    inside_blob = normalized_distance <= 1.35
    alpha = np.exp(-3.4 * normalized_distance * normalized_distance) * inside_blob
    core = np.exp(-14.0 * normalized_distance * normalized_distance)

    warm_color = np.array((255.0, 145.0, 36.0), dtype=np.float32)
    hot_color = np.array((255.0, 248.0, 205.0), dtype=np.float32)
    glow_color = warm_color + core[..., None] * (hot_color - warm_color)
    region = pixels[top:bottom, left:right]
    region[:] = region * (1 - alpha[..., None]) + glow_color * alpha[..., None]

    output = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
    buffer = BytesIO()
    output.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def render_led_frame(
    image_bytes,
    position,
    view,
    max_led_distance_mm,
    frame_height_mm,
    background_level=0.02,
    seed=0,
):
    with Image.open(BytesIO(image_bytes)) as source:
        image_width, image_height = source.size
    pixel_position = project_led_to_frame(
        position,
        view,
        image_width,
        image_height,
        frame_height_mm,
    )
    return add_synthetic_led_glow(
        image_bytes,
        pixel_position,
        max_led_distance_mm,
        frame_height_mm,
        background_level,
        seed,
    )
