import math

from common.animations.ai_base import SpatialAnimation, _rgb


class CircuitBoard(SpatialAnimation):
    name = "ai_circuit_board"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Branching circuits light from the trunk toward the tree tips."

    def _initialise_effect(self, _parameters):
        branch_count = 8
        self.branches = [[] for _ in range(branch_count)]
        for index, (x, y, _z) in enumerate(self.positions):
            angle = math.atan2(y, x) % (2 * math.pi)
            branch = round(angle / (2 * math.pi) * branch_count) % branch_count
            self.branches[branch].append(index)
        for path in self.branches:
            path.sort(key=lambda index: self.positions[index][2])
        self.phases = [self.generator.random() for _ in self.branches]
        self.speed = self.generator.uniform(0.32, 0.55)
        self.tail_fraction = 0.34
        self.colors = [_rgb(0.42 + branch * 0.07, 0.85, 1) for branch in range(len(self.branches))]

    def _render_frame(self, _delta):
        intensities = [0.0] * self.led_count
        frame = [(0, 0, 0)] * self.led_count
        for branch_index, path in enumerate(self.branches):
            if not path:
                continue
            progress = (self.elapsed * self.speed + self.phases[branch_index]) % 1.0
            head = progress * (len(path) - 1)
            tail_length = max(3.0, len(path) * self.tail_fraction)
            for offset, index in enumerate(path):
                intensity = max(0.0, 1.0 - abs(offset - head) / tail_length)
                if intensity > intensities[index]:
                    intensities[index] = intensity
                    frame[index] = tuple(round(channel * intensity) for channel in self.colors[branch_index])
        return frame