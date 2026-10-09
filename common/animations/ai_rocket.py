import math

from common.animations.ai_base import SpatialAnimation, _rgb


class Rocket(SpatialAnimation):
    name = "ai_rocket"
    author = "Carlos Gil & AI"
    version = "0.1.0"
    description = "A full-brightness cone of color rises through the tree and slowly fades."

    def _initialise_effect(self, _parameters):
        self._launch()

    def _launch(self):
        self.color = _rgb(self.generator.random(), 1.0, 1.0)
        self.front_z = 0.0
        self.speed = self.generator.uniform(0.65, 1.25) * self.height
        self.fade_rate = self.generator.uniform(0.72, 1.2)
        self.fade_duration = -math.log(0.1) / self.fade_rate
        self.fade_speed = self.generator.uniform(0.35, 0.55) * self.height
        self.fade_elapsed = 0.0
        self.fading = False

    def _advance_rocket(self, delta_seconds):
        remaining = delta_seconds
        if not self.fading:
            time_to_top = max(0.0, (self.height - self.front_z) / self.speed)
            if remaining < time_to_top:
                self.front_z += self.speed * remaining
                return
            self.front_z = self.height
            self.fading = True
            remaining -= time_to_top

        self.fade_elapsed += remaining
        self.fade_front_z = min(self.height, self.fade_elapsed * self.fade_speed)

    def _render_frame(self, delta_seconds):
        self._advance_rocket(delta_seconds)
        frame = []
        for x, y, z in self.positions:
            cone_radius = self.tree_radius * max(0.0, self.front_z - z) / self.height
            if z > self.front_z or math.hypot(x, y) > cone_radius:
                frame.append((0, 0, 0))
                continue

            intensity = 1.0
            if self.fading and z <= self.fade_front_z:
                fade_age = max(0.0, self.fade_elapsed - z / self.fade_speed)
                intensity = max(0.0, 1.0 - fade_age / self.fade_duration)
                if intensity <= 0.0:
                    frame.append((0, 0, 0))
                    continue
            frame.append(tuple(round(channel * intensity) for channel in self.color))

        fade_finished = (
            self.fading
            and self.fade_front_z >= self.height
            and self.fade_elapsed - self.height / self.fade_speed >= self.fade_duration
        )
        if fade_finished:
            self._launch()
        return frame
