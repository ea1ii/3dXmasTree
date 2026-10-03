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
    first_z = base_z + tree_height_mm * generator.uniform(0.025, 0.075)
    first_radius = base_radius * (1 - (first_z - base_z) / tree_height_mm)
    radius = first_radius * generator.uniform(0.68, 0.9)
    angle = generator.uniform(0, math.tau)
    positions = [(radius * math.cos(angle), radius * math.sin(angle), first_z)]

    for _ in range(1, led_count):
        previous_x, previous_y, previous_z = positions[-1]
        previous_radius = math.hypot(previous_x, previous_y)
        previous_angle = math.atan2(previous_y, previous_x)
        accepted = None

        for _attempt in range(4000):
            step = generator.uniform(0.76, 0.96) * max_distance_mm
            vertical_step = step * generator.uniform(0.35, 0.78)
            next_z = previous_z + vertical_step
            relative_height = next_z - base_z
            if not 0.02 * tree_height_mm <= relative_height <= 0.96 * tree_height_mm:
                continue

            surface_radius = base_radius * (1 - relative_height / tree_height_mm)
            horizontal_limit = math.sqrt(step * step - vertical_step * vertical_step)
            radial_limit = horizontal_limit * 0.68
            minimum_radius = max(0.0, previous_radius - radial_limit)
            maximum_radius = min(surface_radius * 0.97, previous_radius + radial_limit)
            if minimum_radius > maximum_radius:
                continue

            next_radius = generator.uniform(minimum_radius, maximum_radius)
            radial_change = abs(next_radius - previous_radius)
            remaining_horizontal = math.sqrt(
                max(0.0, horizontal_limit * horizontal_limit - radial_change * radial_change)
            )
            mean_radius = (previous_radius + next_radius) / 2
            if mean_radius <= 1e-9:
                maximum_angle = math.tau
            else:
                angle_ratio = min(1.0, remaining_horizontal / (2 * mean_radius))
                maximum_angle = 2 * math.asin(angle_ratio)
            next_angle = previous_angle + generator.uniform(-maximum_angle, maximum_angle)
            candidate = (
                next_radius * math.cos(next_angle),
                next_radius * math.sin(next_angle),
                next_z,
            )
            distance = math.dist(positions[-1], candidate)
            if 0.7 * max_distance_mm <= distance <= max_distance_mm:
                accepted = candidate
                break

        if accepted is None:
            raise RuntimeError("Could not generate a valid LED strip path inside the tree")
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
