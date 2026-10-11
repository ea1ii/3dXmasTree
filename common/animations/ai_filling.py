from common.animations.ai_base import SpatialAnimation, _rgb


class Filling(SpatialAnimation):
    name = "ai_filling"
    author = "Carlos Gil & AI"
    description = "LEDs fade in and out in randomized order with a new color each cycle."

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(self, _parameters):
        self.phase_elapsed = 0.0
        self._start_cycle()

    def _start_cycle(self):
        self.color = _rgb(self.generator.random(), 0.9, 1.0)
        self.fade_duration = self.generator.uniform(0.01, 0.2)
        self.step_gap = self.fade_duration * self.generator.uniform(2.4, 4.8)
        self.phase = "filling"
        self.fill_rank = self._random_ranks()
        self.empty_rank = self._random_ranks()

    def _random_ranks(self):
        order = self.generator.sample(range(self.led_count), self.led_count)
        ranks = [0] * self.led_count
        for rank, led_index in enumerate(order):
            ranks[led_index] = rank
        return ranks

    def _advance_cycle(self, delta_seconds):
        self.phase_elapsed += delta_seconds
        while True:
            phase_duration = (self.led_count - 1) * self.step_gap + self.fade_duration
            if self.phase_elapsed < phase_duration:
                break

            self.phase_elapsed -= phase_duration
            if self.phase == "filling":
                self.phase = "emptying"
            else:
                self._start_cycle()

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta_seconds):
        self._advance_cycle(delta_seconds)
        frame = []
        for index in range(self.led_count):
            if self.phase == "filling":
                fade_age = self.phase_elapsed - self.fill_rank[index] * self.step_gap
                intensity = min(1.0, max(0.0, fade_age / self.fade_duration))
            else:
                fade_start = self.empty_rank[index] * self.step_gap
                fade_age = self.phase_elapsed - fade_start
                intensity = 1.0 - min(1.0, max(0.0, fade_age / self.fade_duration))
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame
