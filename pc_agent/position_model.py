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
    start_height = tree_height_mm * 0.05
    vertical_span = min(
        tree_height_mm * 0.84,
        max_distance_mm * 0.55 * max(0, led_count - 1),
    )
    radial_fraction = generator.uniform(0.68, 0.86)
    phase = generator.uniform(0, math.tau)
    direction = generator.choice((-1, 1))
    angle = phase

    def coordinates(index):
        progress = index / max(1, led_count - 1)
        relative_height = start_height + vertical_span * progress
        z = base_z + relative_height
        surface_radius = base_radius * (1 - relative_height / tree_height_mm)
        radial_wobble = 0.035 * math.sin(phase + progress * math.tau * 3)
        radius = max(0.0, surface_radius * (radial_fraction + radial_wobble))
        return progress, z, radius

    progress, z, radius = coordinates(0)
    positions = [(radius * math.cos(angle), radius * math.sin(angle), z)]

    for index in range(1, led_count):
        previous = positions[-1]
        _, z, radius = coordinates(index)
        previous_radius = math.hypot(previous[0], previous[1])
        vertical_delta = z - previous[2]
        radial_delta = radius - previous_radius
        desired_step = generator.uniform(0.78, 0.88) * max_distance_mm
        chord = math.sqrt(
            max(0.0, desired_step * desired_step - vertical_delta * vertical_delta - radial_delta * radial_delta)
        )
        mean_radius = (radius + previous_radius) / 2
        if mean_radius > 1e-9:
            angular_step = 2 * math.asin(min(1.0, chord / (2 * mean_radius)))
            angle += direction * angular_step * generator.uniform(0.90, 1.06)
        else:
            angle += direction * generator.uniform(0.0, math.tau)

        candidate = (radius * math.cos(angle), radius * math.sin(angle), z)
        distance = math.dist(previous, candidate)
        if distance > max_distance_mm:
            allowance = math.sqrt(
                max(
                    0.0,
                    max_distance_mm * max_distance_mm
                    - vertical_delta * vertical_delta
                    - radial_delta * radial_delta,
                )
            )
            safe_radius = (radius + previous_radius) / 2
            safe_angle = 2 * math.asin(min(1.0, allowance / (2 * safe_radius)))
            angle = math.atan2(previous[1], previous[0]) + direction * safe_angle * 0.98
            candidate = (radius * math.cos(angle), radius * math.sin(angle), z)
        positions.append(candidate)

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
    radius = max(4, round(0.42 * max_led_distance_mm / frame_height_mm * image_height))
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
        + 0.13 * np.sin(3 * angle + seed)
        + 0.08 * np.sin(5 * angle - seed * 0.7)
        + 0.04 * np.sin(7 * angle + seed * 0.3)
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
