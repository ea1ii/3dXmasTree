import math

from common.animations.ai_base import SpatialAnimation, _rgb


class CircuitBoard(SpatialAnimation):
    name = "ai_circuit_board"
    author = "Carlos Gil & AI"
    description = "Branching circuits light from the trunk toward the tree tips."

    def _initialise_effect(self, _parameters):
        ordered = sorted(range(self.led_count), key=lambda index: self.positions[index][2])
        self.branches = []
        for branch in range(6):
            path = []
            previous_angle = branch * 2 * math.pi / 6
            for index in ordered:
                x, y, z = self.positions[index]
                angle = math.atan2(y, x)
                expected = previous_angle + z * 2.2
                difference = abs((angle - expected + math.pi) % (2 * math.pi) - math.pi)
                if difference < 0.8 and (not path or z > self.positions[path[-1]][2]):
                    path.append(index)
                    previous_angle = angle
            if path:
                self.branches.append(path)
        self.speed = self.generator.uniform(0.2, 0.45)
        self.colors = [_rgb(0.42 + branch * 0.07, 0.85, 1) for branch in range(len(self.branches))]

    def _render_frame(self, _delta):
        frame = [(0, 0, 0)] * self.led_count
        for branch_index, path in enumerate(self.branches):
            lit_count = int((self.elapsed * self.speed + branch_index * 0.21) * len(path))
            for index in path[:min(len(path), lit_count + 1)]:
                frame[index] = self.colors[branch_index]
        return frame