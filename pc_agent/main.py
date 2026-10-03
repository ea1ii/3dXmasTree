#!/usr/bin/env python3

import math
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.Xmas_shared import require_platform

if __name__ == "__main__":
    require_platform("pc")

import pyvista as pv
from PySide6.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
)
from pyvistaqt import QtInteractor


from common.agent_client import AgentError, load_settings, request_image, request_json, save_settings
from calibration_model import (
    VIEWS as CALIBRATION_VIEWS,
    calibrate_frame_set,
    load_frame_paths,
    positions_from_detections,
    save_positions,
    source_timestamp,
)
from position_model import generate_strip_positions, render_led_frame


class OperationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.succeeded.emit(self.operation())
        except Exception as error:
            self.failed.emit(str(error))


def request_remote_agent_shutdowns(settings):
    failures = {}
    for agent_name in ("pi", "laptop"):
        try:
            request_json(
                agent_name,
                "/shutdown",
                settings,
                method="POST",
                payload={},
            )
        except AgentError as error:
            failures[agent_name] = str(error)
    return failures


class ColorSetupDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.worker = None
        self.image_worker = None
        self.busy = False
        self.test_active = False
        self.current_order = None
        self.current_candidate = None
        self.pending_dialog_result = None
        self.pending_result = None
        self.pending_error = None
        self.pending_success = None
        self.setWindowTitle("Setup Color")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setModal(False)
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Connecting to the Pi and laptop...")
        layout.addWidget(self.status_label)

        self.image_label = QLabel("Waiting for laptop camera...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(520, 300)
        self.image_label.setStyleSheet("background: #20242a; color: white;")
        layout.addWidget(self.image_label, 1)

        self.expected_color = QLabel("Expected strip color: #FF8040")
        self.expected_color.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.expected_color.setStyleSheet(
            "background: #FF8040; color: #20242a; padding: 8px; font-weight: bold;"
        )
        layout.addWidget(self.expected_color)

        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Yes")
        self.no_button = QPushButton("No")
        self.abort_button = QPushButton("Abort")
        self.yes_button.clicked.connect(self._confirm)
        self.no_button.clicked.connect(self._next_candidate)
        self.abort_button.clicked.connect(self._abort)
        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        button_layout.addWidget(self.abort_button)
        layout.addLayout(button_layout)

        self.image_refresh_timer = QTimer(self)
        self.image_refresh_timer.setInterval(1000)
        self.image_refresh_timer.timeout.connect(self._refresh_image)

        QTimer.singleShot(0, self._start_test)

    def _set_busy(self, busy):
        self.busy = busy
        self.yes_button.setEnabled(not busy and self.test_active)
        self.no_button.setEnabled(not busy and self.test_active)
        self.abort_button.setEnabled(not busy)

    def _run_operation(self, operation, on_success):
        self._set_busy(True)
        self.pending_result = None
        self.pending_error = None
        self.pending_success = on_success
        self.worker = OperationWorker(operation, self)
        self.worker.succeeded.connect(self._store_result)
        self.worker.failed.connect(self._store_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _store_result(self, result):
        self.pending_result = result

    def _store_error(self, message):
        self.pending_error = message

    def _worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        if self.pending_error is not None:
            message = self.pending_error
            self.pending_error = None
            self.pending_success = None
            self._operation_failed(message)
            return

        callback = self.pending_success
        result = self.pending_result
        self.pending_success = None
        self.pending_result = None
        self._set_busy(False)
        callback(result)

    def _operation_failed(self, message):
        self._set_busy(False)
        self.status_label.setText("The color setup could not continue.")
        QMessageBox.critical(
            self,
            "Setup Color",
            f"{message}\n\nIf either remote agent is still running, stop it in its terminal.",
        )

    def _start_test(self):
        def start_and_capture():
            status = request_json(
                "pi",
                "/color-test/start",
                self.settings,
                method="POST",
                payload={},
            )
            try:
                image = request_image("laptop", "/capture", self.settings)
            except Exception:
                try:
                    request_json(
                        "pi",
                        "/color-test/decision",
                        self.settings,
                        method="POST",
                        payload={"decision": "abort"},
                    )
                except AgentError:
                    pass
                raise
            return status, image

        self._run_operation(start_and_capture, self._show_candidate)

    def _next_candidate(self):
        def advance_and_capture():
            status = request_json(
                "pi",
                "/color-test/decision",
                self.settings,
                method="POST",
                payload={"decision": "no"},
            )
            try:
                image = request_image("laptop", "/capture", self.settings)
            except Exception:
                try:
                    request_json(
                        "pi",
                        "/color-test/decision",
                        self.settings,
                        method="POST",
                        payload={"decision": "abort"},
                    )
                except AgentError:
                    pass
                raise
            return status, image

        self._run_operation(advance_and_capture, self._show_candidate)

    def _show_candidate(self, result):
        status, image = result
        self.test_active = True
        self.current_order = status["pixel_order"]
        self.current_candidate = status
        self._set_busy(False)
        self._set_candidate_prompt()
        if not self._display_image(image):
            self._operation_failed("The laptop agent returned an unreadable image.")
            return
        self.image_refresh_timer.start()

    def _set_candidate_prompt(self):
        if self.current_candidate is None:
            return
        self.status_label.setText(
            "Candidate {candidate_number} of {candidate_count}: {pixel_order}. "
            "Choose Yes if the strip matches the color below.".format(
                **self.current_candidate
            )
        )

    def _display_image(self, image):
        pixmap = QPixmap()
        if not pixmap.loadFromData(image):
            return False
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return True

    def _refresh_image(self):
        if not self.test_active or self.busy or self.image_worker is not None:
            return

        worker = OperationWorker(
            lambda: request_image("laptop", "/capture", self.settings),
            self,
        )
        self.image_worker = worker
        worker.succeeded.connect(self._show_refreshed_image)
        worker.failed.connect(self._show_refresh_error)
        worker.finished.connect(lambda: self._image_refresh_finished(worker))
        worker.start()

    def _show_refreshed_image(self, image):
        if not self.test_active:
            return
        if self._display_image(image):
            self._set_candidate_prompt()
        else:
            self._show_refresh_error("The laptop returned an unreadable image")

    def _show_refresh_error(self, _message):
        if self.test_active and self.current_candidate is not None:
            self.status_label.setText(
                "Candidate {candidate_number} of {candidate_count}: {pixel_order}. "
                "Camera refresh failed; retrying.".format(**self.current_candidate)
            )

    def _image_refresh_finished(self, worker):
        if self.image_worker is worker:
            self.image_worker = None
        worker.deleteLater()
        if self.pending_dialog_result is not None:
            result = self.pending_dialog_result
            self.pending_dialog_result = None
            QDialog.done(self, result)

    def _confirm(self):
        self.image_refresh_timer.stop()

        def save_selection():
            status = request_json(
                "pi",
                "/color-test/decision",
                self.settings,
                method="POST",
                payload={"decision": "yes"},
            )
            if status["pixel_order"] != self.current_order:
                raise AgentError("The Pi did not confirm the selected pixel order")
            self.settings["led"]["pixel_order"] = status["pixel_order"]
            save_settings(self.settings)
            status["shutdown_failures"] = request_remote_agent_shutdowns(self.settings)
            return status

        self._run_operation(save_selection, self._confirm_complete)

    def _confirm_complete(self, result):
        self.test_active = False
        self.image_refresh_timer.stop()
        failures = result["shutdown_failures"]
        if failures:
            details = "\n".join(
                f"{agent}: {message}" for agent, message in failures.items()
            )
            QMessageBox.warning(
                self,
                "Setup Color Complete",
                f"Saved LED color order: {result['pixel_order']}.\n\n"
                "Could not stop every remote agent:\n"
                f"{details}\n\nStop those agents in their terminals, then "
                "close their SSH sessions.",
            )
        else:
            QMessageBox.information(
                self,
                "Setup Color Complete",
                f"Saved LED color order: {result['pixel_order']}.\n\n"
                "The Pi and laptop agents were asked to stop. Close their SSH sessions.",
            )
        self.accept()

    def _abort(self):
        if not self.test_active:
            self.reject()
            return
        self.image_refresh_timer.stop()

        def abort_test():
            result = {"abort_error": None}
            try:
                request_json(
                    "pi",
                    "/color-test/decision",
                    self.settings,
                    method="POST",
                    payload={"decision": "abort"},
                )
            except AgentError as error:
                result["abort_error"] = str(error)
            result["shutdown_failures"] = request_remote_agent_shutdowns(self.settings)
            return result

        self._run_operation(abort_test, self._abort_complete)

    def _abort_complete(self, result):
        self.test_active = False
        self.image_refresh_timer.stop()
        self._set_busy(False)
        shutdown_failures = result["shutdown_failures"]
        errors = []
        if result["abort_error"]:
            errors.append(f"Could not abort the Pi LED test: {result['abort_error']}")
        errors.extend(
            f"Could not stop {agent}: {message}"
            for agent, message in shutdown_failures.items()
        )
        if errors:
            QMessageBox.warning(
                self,
                "Setup Color Aborted",
                "The test was aborted without saving, but some remote cleanup failed:\n\n"
                + "\n".join(errors)
                + "\n\nStop any remaining agents in their terminals and close the SSH sessions.",
            )
        else:
            QMessageBox.information(
                self,
                "Setup Color Aborted",
                "The test was aborted without saving. The Pi and laptop agents were "
                "asked to stop. Close their SSH sessions.",
            )
        self.reject()

    def _finish_when_image_idle(self, result):
        self.image_refresh_timer.stop()
        if self.image_worker is not None and self.image_worker.isRunning():
            self.pending_dialog_result = result
            return
        QDialog.done(self, result)

    def accept(self):
        self._finish_when_image_idle(QDialog.DialogCode.Accepted)

    def reject(self):
        if self.test_active and not self.busy:
            self._abort()
            return
        if self.busy:
            return
        self._finish_when_image_idle(QDialog.DialogCode.Rejected)


class LengthSetupDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.worker = None
        self.image_worker = None
        self.busy = False
        self.test_active = False
        self.current_led = None
        self.pending_dialog_result = None
        self.pending_result = None
        self.pending_error = None
        self.pending_success = None
        self.setWindowTitle("Setup LED Length")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setModal(False)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Starting LED length test...")
        layout.addWidget(self.status_label)

        self.number_label = QLabel("LED -")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(self.number_label)

        self.image_label = QLabel("Waiting for laptop camera...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(520, 300)
        self.image_label.setStyleSheet("background: #20242a; color: white;")
        layout.addWidget(self.image_label, 1)

        button_layout = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.done_button = QPushButton("Done")
        self.abort_button = QPushButton("Abort")
        self.previous_button.clicked.connect(self._previous)
        self.next_button.clicked.connect(self._next)
        self.done_button.clicked.connect(self._done)
        self.abort_button.clicked.connect(self._abort)
        for button in (
            self.previous_button,
            self.next_button,
            self.done_button,
            self.abort_button,
        ):
            button.setMinimumHeight(36)
            button_layout.addWidget(button)
        layout.addLayout(button_layout)

        self.image_refresh_timer = QTimer(self)
        self.image_refresh_timer.setInterval(1000)
        self.image_refresh_timer.timeout.connect(self._refresh_image)
        QTimer.singleShot(0, self._start)

    def _set_busy(self, busy):
        self.busy = busy
        self.previous_button.setEnabled(
            not busy and self.test_active and self.current_led > 1
        )
        self.next_button.setEnabled(
            not busy
            and self.test_active
            and self.current_led < self.settings["led"]["test_count"]
        )
        self.done_button.setEnabled(not busy and self.test_active)
        self.abort_button.setEnabled(not busy)

    def _run_operation(self, operation, on_success):
        self._set_busy(True)
        self.pending_result = None
        self.pending_error = None
        self.pending_success = on_success
        self.worker = OperationWorker(operation, self)
        self.worker.succeeded.connect(self._store_result)
        self.worker.failed.connect(self._store_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _store_result(self, result):
        self.pending_result = result

    def _store_error(self, message):
        self.pending_error = message

    def _worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        if self.pending_error is not None:
            message = self.pending_error
            self.pending_error = None
            self.pending_success = None
            self._operation_failed(message)
            return

        callback = self.pending_success
        result = self.pending_result
        self.pending_success = None
        self.pending_result = None
        self._set_busy(False)
        callback(result)

    def _capture_for_step(self, endpoint):
        status = request_json(
            "pi",
            endpoint,
            self.settings,
            method="POST",
            payload={},
        )
        try:
            image = request_image("laptop", "/capture", self.settings)
        except Exception:
            self._stop_agents_after_failure()
            raise
        return status, image

    def _stop_agents_after_failure(self):
        try:
            request_json(
                "pi",
                "/length-test/abort",
                self.settings,
                method="POST",
                payload={},
            )
        except AgentError:
            pass
        request_remote_agent_shutdowns(self.settings)

    def _start(self):
        self._run_operation(
            lambda: self._capture_for_step("/length-test/start"),
            self._show_step,
        )

    def _next(self):
        self._run_operation(
            lambda: self._capture_for_step("/length-test/next"),
            self._show_step,
        )

    def _previous(self):
        self._run_operation(
            lambda: self._capture_for_step("/length-test/previous"),
            self._show_step,
        )

    def _show_step(self, result):
        status, image = result
        self.test_active = True
        self.current_led = status["current_led"]
        self._set_busy(False)
        self.number_label.setText(f"LED {self.current_led}")
        if status["can_next"]:
            self.status_label.setText(
                f"LED {self.current_led} is lit. When no LED lights, click Done "
                f"to save {self.current_led - 1} LEDs."
            )
        else:
            self.status_label.setText(
                f"Test limit reached ({status['test_count']}). Increase led.test_count "
                "to continue, or click Done if this LED is beyond the strip."
            )
        if not self._display_image(image):
            self._operation_failed("The laptop agent returned an unreadable image.")
            return
        self.image_refresh_timer.start()

    def _display_image(self, image):
        pixmap = QPixmap()
        if not pixmap.loadFromData(image):
            return False
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return True

    def _refresh_image(self):
        if not self.test_active or self.busy or self.image_worker is not None:
            return
        worker = OperationWorker(
            lambda: request_image("laptop", "/capture", self.settings),
            self,
        )
        self.image_worker = worker
        worker.succeeded.connect(self._show_refreshed_image)
        worker.failed.connect(self._show_refresh_error)
        worker.finished.connect(lambda: self._image_refresh_finished(worker))
        worker.start()

    def _show_refreshed_image(self, image):
        if self.test_active and not self._display_image(image):
            self._show_refresh_error("The laptop returned an unreadable image")

    def _show_refresh_error(self, _message):
        if self.test_active:
            self.status_label.setText("Camera refresh failed; retrying.")

    def _image_refresh_finished(self, worker):
        if self.image_worker is worker:
            self.image_worker = None
        worker.deleteLater()
        if self.pending_dialog_result is not None:
            result = self.pending_dialog_result
            self.pending_dialog_result = None
            QDialog.done(self, result)

    def _done(self):
        self.image_refresh_timer.stop()

        def finish_test():
            result = request_json(
                "pi",
                "/length-test/done",
                self.settings,
                method="POST",
                payload={},
            )
            self.settings["led"]["led_count"] = result["led_count"]
            save_settings(self.settings)
            result["shutdown_failures"] = request_remote_agent_shutdowns(
                self.settings
            )
            return result

        self._run_operation(finish_test, self._done_complete)

    def _done_complete(self, result):
        self.test_active = False
        self.image_refresh_timer.stop()
        failures = result["shutdown_failures"]
        if failures:
            details = "\n".join(
                f"{agent}: {message}" for agent, message in failures.items()
            )
            QMessageBox.warning(
                self,
                "LED Length Saved",
                f"Saved LED strip length: {result['led_count']} LEDs.\n\n"
                "Could not stop every remote agent:\n"
                f"{details}\n\nStop those agents in their terminals, then "
                "close their SSH sessions.",
            )
        else:
            QMessageBox.information(
                self,
                "LED Length Saved",
                f"Saved LED strip length: {result['led_count']} LEDs.\n\n"
                "The Pi and laptop agents were asked to stop. Close their SSH sessions.",
            )
        self.accept()

    def _abort(self):
        self.image_refresh_timer.stop()

        def abort_test():
            abort_error = None
            try:
                request_json(
                    "pi",
                    "/length-test/abort",
                    self.settings,
                    method="POST",
                    payload={},
                )
            except AgentError as error:
                abort_error = str(error)
            shutdown_failures = request_remote_agent_shutdowns(self.settings)
            return {
                "abort_error": abort_error,
                "shutdown_failures": shutdown_failures,
            }

        self._run_operation(abort_test, self._abort_complete)

    def _abort_complete(self, result):
        self.test_active = False
        self.image_refresh_timer.stop()
        self._set_busy(False)
        errors = []
        if result["abort_error"]:
            errors.append(f"Could not abort the Pi LED test: {result['abort_error']}")
        errors.extend(
            f"Could not stop {agent}: {message}"
            for agent, message in result["shutdown_failures"].items()
        )
        if errors:
            QMessageBox.warning(
                self,
                "LED Length Aborted",
                "The test was aborted without saving, but some remote cleanup failed:\n\n"
                + "\n".join(errors)
                + "\n\nStop any remaining agents in their terminals and close the SSH sessions.",
            )
        else:
            QMessageBox.information(
                self,
                "LED Length Aborted",
                "The test was aborted without saving. The Pi and laptop agents were "
                "asked to stop. Close their SSH sessions.",
            )
        self.reject()

    def _operation_failed(self, message):
        self.test_active = False
        self.image_refresh_timer.stop()
        self._set_busy(False)
        self.status_label.setText("The LED length test could not continue.")
        QMessageBox.critical(
            self,
            "Setup LED Length",
            f"{message}\n\nThe agents were asked to stop if possible.",
        )

    def _finish_when_image_idle(self, result):
        self.image_refresh_timer.stop()
        if self.image_worker is not None and self.image_worker.isRunning():
            self.pending_dialog_result = result
            return
        QDialog.done(self, result)

    def accept(self):
        self._finish_when_image_idle(QDialog.DialogCode.Accepted)

    def reject(self):
        if self.busy:
            return
        if self.test_active:
            self._abort()
            return
        self._finish_when_image_idle(QDialog.DialogCode.Rejected)


class PositionCapturePage(QDialog):
    VIEWS = ("front", "right", "left", "back")

    def __init__(self, parent, settings, output_directory):
        super().__init__(parent)
        self.settings = settings
        self.output_directory = output_directory
        self.led_count = settings["led"].get("capture_test_led_count", 5)
        led_settings = settings["led"]
        camera_settings = settings["camera"]
        self.max_led_distance_mm = led_settings["maxLEDdist"]
        self.frame_height_mm = camera_settings["frame_height_mm"]
        self.simulate_led_lights = camera_settings.get("simulate_led_lights", True)
        self.synthetic_background_level = camera_settings.get(
            "synthetic_background_level", 0.02
        )
        self.led_positions = generate_strip_positions(
            self.led_count,
            self.max_led_distance_mm,
            led_settings.get("simulated_tree_height_mm", 1200),
            self.frame_height_mm,
        )
        self.output_directory.mkdir(parents=True, exist_ok=False)
        self.model_plotter = None
        self.led_actors = []
        self.worker = None
        self.pending_result = None
        self.pending_error = None
        self.pending_success = None
        self.busy = False
        self.abort_requested = False
        self.cleanup_kind = None
        self.cleanup_error = None
        self.position_active = False
        self.view_index = 0
        self.current_led = None
        self.saved_count = 0

        self.setWindowTitle("Grab Positions")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setModal(False)

        layout = QVBoxLayout(self)
        self.title_label = QLabel("Grab Positions")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.instruction_label = QLabel()
        self.instruction_label.setWordWrap(True)
        layout.addWidget(self.instruction_label)

        self.progress_label = QLabel(f"0 / {len(self.VIEWS) * self.led_count} images")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.VIEWS) * self.led_count)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        preview_layout = QHBoxLayout()

        if self.simulate_led_lights:
            model_container = QWidget(self)
            model_layout = QVBoxLayout(model_container)
            model_layout.setContentsMargins(0, 0, 0, 0)
            model_layout.addWidget(QLabel("Synthetic tree and LED strip"))
            self.model_plotter = QtInteractor(model_container)
            model_layout.addWidget(self.model_plotter, 1)
            self._build_position_preview()
            preview_layout.addWidget(model_container, 1)

        self.image_label = QLabel("No capture yet")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(360, 300)
        self.image_label.setStyleSheet("background: #20242a; color: white;")
        preview_layout.addWidget(self.image_label, 1)
        layout.addLayout(preview_layout, 1)

        self.file_label = QLabel(str(output_directory))
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        button_layout = QHBoxLayout()
        self.begin_button = QPushButton()
        self.abort_button = QPushButton("Abort")
        self.begin_button.setMinimumHeight(36)
        self.abort_button.setMinimumHeight(36)
        self.begin_button.clicked.connect(self._begin_view)
        self.abort_button.clicked.connect(self._abort)
        button_layout.addWidget(self.begin_button)
        button_layout.addWidget(self.abort_button)
        layout.addLayout(button_layout)

        self._show_view_prompt()

    def _build_position_preview(self):
        tree_height = self.settings["led"].get("simulated_tree_height_mm", 1200)
        frame_height = self.frame_height_mm
        base_z = (frame_height - tree_height) / 2
        base_radius = tree_height * 0.34
        self.model_plotter.set_background("#17221f")

        tiers = (
            (base_z + tree_height * 0.30, tree_height * 0.60, base_radius, "#4A9A70"),
            (base_z + tree_height * 0.53, tree_height * 0.58, base_radius * 0.76, "#3F8B65"),
            (base_z + tree_height * 0.75, tree_height * 0.48, base_radius * 0.52, "#347D5A"),
        )
        for center_z, height, radius, color in tiers:
            self.model_plotter.add_mesh(
                pv.Cone(
                    center=(0, 0, center_z),
                    direction=(0, 0, 1),
                    height=height,
                    radius=radius,
                    resolution=48,
                ),
                color=color,
                opacity=0.28,
                smooth_shading=True,
            )

        self.model_plotter.add_mesh(
            pv.Cylinder(
                center=(0, 0, base_z + tree_height * 0.08),
                direction=(0, 0, 1),
                radius=base_radius * 0.08,
                height=tree_height * 0.16,
                resolution=24,
            ),
            color="#765438",
            opacity=0.75,
        )
        self.model_plotter.add_mesh(
            pv.Sphere(
                center=(0, 0, base_z + tree_height * 0.98),
                radius=tree_height * 0.035,
                theta_resolution=16,
                phi_resolution=12,
            ),
            color="#F2C451",
            smooth_shading=True,
        )

        for start, end in zip(self.led_positions, self.led_positions[1:]):
            link = pv.Line(start, end).tube(radius=max(2.5, self.max_led_distance_mm * 0.035))
            self.model_plotter.add_mesh(link, color="#D9B967", opacity=0.95)

        for position in self.led_positions:
            actor = self.model_plotter.add_mesh(
                pv.Sphere(
                    center=position,
                    radius=max(14, self.max_led_distance_mm * 0.16),
                    theta_resolution=16,
                    phi_resolution=12,
                ),
                color="#83B8A0",
                smooth_shading=True,
            )
            self.led_actors.append(actor)

        self.model_plotter.add_axes()
        self.model_plotter.view_isometric()
        self.model_plotter.reset_camera()

    def _highlight_model_led(self, led_number):
        for index, actor in enumerate(self.led_actors, start=1):
            if index == led_number:
                actor.GetProperty().SetColor(1.0, 0.93, 0.62)
                actor.GetProperty().SetAmbient(0.55)
            else:
                actor.GetProperty().SetColor(0.43, 0.68, 0.57)
                actor.GetProperty().SetAmbient(0.12)
        if self.model_plotter is not None:
            self.model_plotter.render()

    def _show_view_prompt(self):
        view = self.VIEWS[self.view_index]
        if view == "front":
            instruction = (
                "Face the FRONT of the tree toward the webcam. Confirm when it is "
                "steady; the Pi will light each test LED and capture it automatically."
            )
        else:
            instruction = (
                f"Rotate the tree so its {view.upper()} faces the webcam. "
                "Confirm when it is steady to start this sweep."
            )
        self.instruction_label.setText(instruction)
        self.begin_button.setText(f"Confirm {view.title()} and Begin")
        self.begin_button.setEnabled(not self.busy and not self.abort_requested)

    def _run_operation(self, operation, on_success):
        self.busy = True
        self.pending_result = None
        self.pending_error = None
        self.pending_success = on_success
        self.begin_button.setEnabled(False)
        self.abort_button.setEnabled(not self.abort_requested)
        self.worker = OperationWorker(operation, self)
        self.worker.succeeded.connect(self._store_result)
        self.worker.failed.connect(self._store_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _store_result(self, result):
        self.pending_result = result

    def _store_error(self, message):
        self.pending_error = message

    def _worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.busy = False

        if self.cleanup_kind is not None:
            kind = self.cleanup_kind
            self.cleanup_kind = None
            self._finish_cleanup(kind, self.pending_result, self.pending_error)
            return
        if self.abort_requested:
            self._begin_cleanup("abort")
            return
        if self.pending_error is not None:
            self._begin_cleanup("failure", self.pending_error)
            return

        callback = self.pending_success
        result = self.pending_result
        self.pending_success = None
        self.pending_result = None
        callback(result)

    def _begin_view(self):
        if self.busy or self.abort_requested:
            return
        view = self.VIEWS[self.view_index]
        self.instruction_label.setText(f"Starting {view.upper()} sweep...")
        self._run_operation(
            lambda: request_json(
                "pi",
                "/position/start",
                self.settings,
                method="POST",
                payload={},
            ),
            self._view_started,
        )

    def _view_started(self, status):
        self.position_active = True
        if status["led_count"] != self.led_count:
            self._begin_cleanup(
                "failure",
                AgentError(
                "PC and Pi capture_test_led_count settings do not match "
                    f"({self.led_count} vs {status['led_count']})"
                ),
            )
            return
        self.current_led = status["current_led"]
        self._highlight_model_led(self.current_led)
        self._capture_current_led()

    def _capture_current_led(self):
        view = self.VIEWS[self.view_index]
        led_number = self.current_led
        filename = f"{view}_LED_{led_number:03d}.jpg"
        image_path = self.output_directory / filename

        def capture_and_save():
            image = request_image("laptop", "/capture", self.settings)
            if self.simulate_led_lights:
                image = render_led_frame(
                    image,
                    self.led_positions[led_number - 1],
                    view,
                    self.max_led_distance_mm,
                    self.frame_height_mm,
                    self.synthetic_background_level,
                    seed=self.view_index * self.led_count + led_number,
                )
            temporary_path = image_path.with_suffix(".jpg.tmp")
            temporary_path.write_bytes(image)
            os.replace(temporary_path, image_path)
            return image, image_path

        self.instruction_label.setText(
            f"{view.upper()} sweep: capturing LED {led_number} of {self.led_count}..."
        )
        self._run_operation(capture_and_save, self._capture_saved)

    def _capture_saved(self, result):
        image, image_path = result
        pixmap = QPixmap()
        if not pixmap.loadFromData(image):
            self._begin_cleanup(
                "failure",
                AgentError(f"Saved image could not be displayed: {image_path.name}"),
            )
            return
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.saved_count += 1
        total = len(self.VIEWS) * self.led_count
        self.progress_bar.setValue(self.saved_count)
        self.progress_label.setText(f"{self.saved_count} / {total} images")
        self.file_label.setText(f"Saved: {image_path}")

        if self.current_led < self.led_count:
            self._advance_led()
        else:
            self._stop_view()

    def _advance_led(self):
        self._run_operation(
            lambda: request_json(
                "pi",
                "/position/next",
                self.settings,
                method="POST",
                payload={},
            ),
            self._led_advanced,
        )

    def _led_advanced(self, status):
        self.current_led = status["current_led"]
        self._highlight_model_led(self.current_led)
        self._capture_current_led()

    def _stop_view(self):
        self._run_operation(
            lambda: request_json(
                "pi",
                "/position/stop",
                self.settings,
                method="POST",
                payload={},
            ),
            self._view_stopped,
        )

    def _view_stopped(self, _result):
        self.position_active = False
        if self.view_index + 1 < len(self.VIEWS):
            self.view_index += 1
            self._show_view_prompt()
            return
        self.instruction_label.setText("All four viewpoints captured. Stopping agents...")
        self._begin_cleanup("complete")

    def _abort(self):
        if self.cleanup_kind is not None or self.abort_requested:
            return
        self.abort_requested = True
        self.begin_button.setEnabled(False)
        self.abort_button.setEnabled(False)
        self.instruction_label.setText("Abort requested; waiting for the current request...")
        if not self.busy:
            self._begin_cleanup("abort")

    def _begin_cleanup(self, kind, error=None):
        self.cleanup_kind = kind
        self.cleanup_error = error

        def stop_agents():
            failures = {}
            if self.position_active:
                try:
                    request_json(
                        "pi",
                        "/position/stop",
                        self.settings,
                        method="POST",
                        payload={},
                    )
                except AgentError as stop_error:
                    failures["pi position test"] = str(stop_error)
                self.position_active = False
            failures.update(request_remote_agent_shutdowns(self.settings))
            return failures

        self._run_operation(stop_agents, lambda _result: None)

    def _finish_cleanup(self, kind, failures, cleanup_error):
        failures = failures or {}
        if cleanup_error:
            failures["shutdown"] = cleanup_error

        if kind == "complete":
            title = "Position Capture Complete"
            message = (
                f"Saved {self.saved_count} images to:\n{self.output_directory}\n\n"
                "The Pi and laptop agents were asked to stop. Close their SSH sessions."
            )
            if failures:
                details = "\n".join(
                    f"{agent}: {failure}" for agent, failure in failures.items()
                )
                message += f"\n\nSome shutdown requests failed:\n{details}"
                QMessageBox.warning(self, title, message)
            else:
                QMessageBox.information(self, title, message)
            self.accept()
            return

        if kind == "abort":
            message = (
                f"Capture aborted. {self.saved_count} completed images remain in:\n"
                f"{self.output_directory}\n\n"
                "The Pi and laptop agents were asked to stop. Close their SSH sessions."
            )
            if failures:
                details = "\n".join(
                    f"{agent}: {failure}" for agent, failure in failures.items()
                )
                message += f"\n\nSome shutdown requests failed:\n{details}"
                QMessageBox.warning(self, "Position Capture Aborted", message)
            else:
                QMessageBox.information(self, "Position Capture Aborted", message)
            self.reject()
            return

        details = "\n".join(
            f"{agent}: {failure}" for agent, failure in failures.items()
        )
        QMessageBox.critical(
            self,
            "Position Capture Failed",
            f"{self.cleanup_error or 'Capture failed.'}\n\n"
            f"{self.saved_count} completed images remain in:\n{self.output_directory}\n\n"
            f"Shutdown issues:\n{details or 'None'}",
        )
        self.reject()

    def reject(self):
        if self.cleanup_kind is not None:
            return
        if self.busy:
            self._abort()
            return
        if self.saved_count or self.position_active:
            self._abort()
            return
        self._begin_cleanup("abort")


class CalibrationPage(QDialog):
    def __init__(self, parent, frame_folder, settings):
        super().__init__(parent)
        self.frame_folder = Path(frame_folder)
        self.settings = settings
        self.timestamp = source_timestamp(self.frame_folder)
        self.led_indices, self.frame_paths = load_frame_paths(self.frame_folder)
        self.current_frame_index = 0
        self.detections = None
        self.points = []
        self.analysis_worker = None
        self.point_actors = []
        self.link_actors = []
        self.tree_height_mm = settings["led"].get("simulated_tree_height_mm", 1200)
        self.frame_height_mm = settings["camera"]["frame_height_mm"]
        self.setWindowTitle("Calibrate LED Positions")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setModal(False)

        root_layout = QVBoxLayout(self)
        header = QLabel(f"Calibrate positions from {self.frame_folder}")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        root_layout.addWidget(header)

        workspace = QHBoxLayout()
        root_layout.addLayout(workspace, 1)

        view_container = QWidget(self)
        view_grid = QGridLayout(view_container)
        view_grid.setContentsMargins(0, 0, 0, 0)
        view_grid.setSpacing(6)
        self.view_modes = {}
        self.view_labels = {}
        grid_positions = {"front": (0, 0), "back": (0, 1), "left": (1, 0), "right": (1, 1)}
        for view in CALIBRATION_VIEWS:
            panel = QWidget(view_container)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(4, 4, 4, 4)
            toolbar = QHBoxLayout()
            toolbar.addWidget(QLabel(view.title()))
            mode = QComboBox(panel)
            mode.addItems(("Picture", "Model"))
            mode.currentTextChanged.connect(lambda _text, selected=view: self._refresh_view(selected))
            toolbar.addStretch()
            toolbar.addWidget(mode)
            panel_layout.addLayout(toolbar)

            image_label = QLabel("Detecting bright spots...")
            image_label.setMinimumSize(220, 150)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("background: #20242a; color: white;")
            panel_layout.addWidget(image_label, 1)
            view_grid.addWidget(panel, *grid_positions[view])
            self.view_modes[view] = mode
            self.view_labels[view] = image_label
        workspace.addWidget(view_container, 3)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("3D LED model"))
        self.model_plotter = QtInteractor(right_panel)
        right_layout.addWidget(self.model_plotter, 3)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("Previous Frame")
        self.next_button = QPushButton("Next Frame")
        self.frame_label = QLabel("Frame -")
        self.previous_button.clicked.connect(lambda: self._move_frame(-1))
        self.next_button.clicked.connect(lambda: self._move_frame(1))
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.frame_label, 1)
        navigation.addWidget(self.next_button)
        right_layout.addLayout(navigation)

        display_modes = QHBoxLayout()
        self.all_pictures_button = QPushButton("All Pictures")
        self.all_models_button = QPushButton("All Models")
        self.all_pictures_button.clicked.connect(lambda: self._set_all_modes("Picture"))
        self.all_models_button.clicked.connect(lambda: self._set_all_modes("Model"))
        display_modes.addWidget(self.all_pictures_button)
        display_modes.addWidget(self.all_models_button)
        right_layout.addLayout(display_modes)

        settings_layout = QGridLayout()
        settings_layout.addWidget(QLabel("View-match tolerance"), 0, 0)
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0, 1000)
        self.tolerance_spin.setDecimals(1)
        self.tolerance_spin.setSuffix(" mm")
        self.tolerance_spin.setValue(settings.get("calibration", {}).get("match_tolerance_mm", 50))
        settings_layout.addWidget(self.tolerance_spin, 0, 1)
        settings_layout.addWidget(QLabel("Maximum LED spacing"), 1, 0)
        self.max_distance_spin = QDoubleSpinBox()
        self.max_distance_spin.setRange(1, 10000)
        self.max_distance_spin.setDecimals(1)
        self.max_distance_spin.setSuffix(" mm")
        self.max_distance_spin.setValue(settings["led"]["maxLEDdist"])
        settings_layout.addWidget(self.max_distance_spin, 1, 1)
        right_layout.addLayout(settings_layout)

        self.points_table = QTableWidget(0, 6, right_panel)
        self.points_table.setHorizontalHeaderLabels(
            ("LED", "X mm", "Y mm", "Z mm", "Match mm", "Status")
        )
        self.points_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.points_table.currentCellChanged.connect(self._table_selection_changed)
        right_layout.addWidget(self.points_table, 2)
        workspace.addWidget(right_panel, 2)

        self.status_label = QLabel("Detecting the brightest spot in each frame...")
        root_layout.addWidget(self.status_label)
        footer = QHBoxLayout()
        footer.addStretch()
        self.save_button = QPushButton("Save Positions")
        self.close_button = QPushButton("Close")
        self.save_button.clicked.connect(self._save)
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.save_button)
        footer.addWidget(self.close_button)
        root_layout.addLayout(footer)

        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.tolerance_spin.valueChanged.connect(self._recalculate)
        self.max_distance_spin.valueChanged.connect(self._recalculate)
        self._build_3d_tree()
        QTimer.singleShot(0, self._start_detection)

    def _build_3d_tree(self):
        self.model_plotter.set_background("#17221f")
        base_z = (self.frame_height_mm - self.tree_height_mm) / 2
        self.model_plotter.add_mesh(
            pv.Cone(
                center=(0, 0, base_z + self.tree_height_mm / 2),
                direction=(0, 0, 1),
                height=self.tree_height_mm,
                radius=self.tree_height_mm * 0.34,
                resolution=64,
            ),
            color="#39855F",
            opacity=0.24,
        )
        self.model_plotter.add_axes()
        self.model_plotter.view_isometric()
        self.model_plotter.reset_camera()

    def _start_detection(self):
        def analyze():
            return calibrate_frame_set(
                self.frame_paths,
                self.led_indices,
                self.frame_height_mm,
                self.tolerance_spin.value(),
                self.max_distance_spin.value(),
            )

        self.analysis_worker = OperationWorker(analyze, self)
        self.analysis_worker.succeeded.connect(self._analysis_succeeded)
        self.analysis_worker.failed.connect(self._analysis_failed)
        self.analysis_worker.finished.connect(self._analysis_finished)
        self.analysis_worker.start()

    def _analysis_succeeded(self, result):
        self.points, self.detections = result
        self.previous_button.setEnabled(len(self.led_indices) > 1)
        self.next_button.setEnabled(len(self.led_indices) > 1)
        self.save_button.setEnabled(bool(self.points))
        self._update_results()

    def _analysis_failed(self, message):
        self.status_label.setText("Calibration could not detect all LED spots.")
        QMessageBox.critical(self, "Calibrate", message)

    def _analysis_finished(self):
        worker = self.analysis_worker
        self.analysis_worker = None
        if worker is not None:
            worker.deleteLater()

    def _recalculate(self, *_args):
        if self.detections is None:
            return
        try:
            self.points = positions_from_detections(
                self.detections,
                self.led_indices,
                self.frame_height_mm,
                self.tolerance_spin.value(),
                self.max_distance_spin.value(),
            )
        except ValueError as error:
            self.status_label.setText(str(error))
            return
        self._update_results()

    def _update_results(self):
        valid_count = sum(point["valid"] for point in self.points)
        adjusted_count = sum(point["adjusted"] for point in self.points)
        self.status_label.setText(
            f"{valid_count}/{len(self.points)} points match within tolerance; "
            f"{adjusted_count} adjusted to the max spacing."
        )
        self.points_table.setRowCount(len(self.points))
        for row, point in enumerate(self.points):
            status = "Adjusted" if point["adjusted"] else "Matched" if point["valid"] else "Mismatch"
            values = (
                str(point["index"]),
                f"{point['x']:.1f}",
                f"{point['y']:.1f}",
                f"{point['z']:.1f}",
                f"{point['match_error_mm']:.1f}",
                status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.points_table.setItem(row, column, item)
        self.points_table.selectRow(self.current_frame_index)
        self._refresh_all_views()
        self._refresh_3d_points()

    def _refresh_all_views(self):
        led_index = self.led_indices[self.current_frame_index]
        self.frame_label.setText(f"LED {led_index}")
        self.previous_button.setEnabled(self.current_frame_index > 0 and self.detections is not None)
        self.next_button.setEnabled(
            self.detections is not None and self.current_frame_index + 1 < len(self.led_indices)
        )
        for view in CALIBRATION_VIEWS:
            label = self.view_labels[view]
            if self.view_modes[view].currentText() == "Picture":
                pixmap = QPixmap(str(self.frame_paths[view][led_index]))
            else:
                pixmap = self._flat_model_pixmap(view, label.size())
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

    def _refresh_view(self, view):
        if self.detections is not None:
            self._refresh_all_views()

    def _set_all_modes(self, mode):
        for combo in self.view_modes.values():
            combo.setCurrentText(mode)

    def _move_frame(self, delta):
        if not self.led_indices:
            return
        self.current_frame_index = min(
            max(0, self.current_frame_index + delta), len(self.led_indices) - 1
        )
        if self.detections is not None:
            self._refresh_all_views()
            self.points_table.selectRow(self.current_frame_index)
            self._refresh_3d_points()

    def _table_selection_changed(self, row, *_args):
        if 0 <= row < len(self.led_indices) and row != self.current_frame_index:
            self.current_frame_index = row
            self._refresh_all_views()
            self._refresh_3d_points()

    def _flat_model_pixmap(self, view, size):
        width = max(1, size.width())
        height = max(1, size.height())
        image = QPixmap(width, height)
        image.fill(QColor("#F5F7F5"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 18
        frame_width_mm = self.frame_height_mm * 4 / 3
        scale = min(
            (width - 2 * margin) / frame_width_mm,
            (height - 2 * margin) / self.frame_height_mm,
        )

        def to_screen(point):
            if view == "front":
                horizontal = point["y"]
            elif view == "back":
                horizontal = -point["y"]
            elif view == "left":
                horizontal = point["x"]
            else:
                horizontal = -point["x"]
            return (
                width / 2 + horizontal * scale,
                height - margin - point["z"] * scale,
            )

        axis_pen = QPen(QColor("#AAB5AE"), 1)
        painter.setPen(axis_pen)
        painter.drawLine(margin, height - margin, width - margin, height - margin)
        painter.drawLine(width / 2, margin, width / 2, height - margin)

        if self.points:
            screen_points = [to_screen(point) for point in self.points]
            painter.setPen(QPen(QColor("#648070"), 2))
            for first, second in zip(screen_points, screen_points[1:]):
                painter.drawLine(*first, *second)
            for index, (point, screen_point) in enumerate(zip(self.points, screen_points)):
                if point["adjusted"]:
                    color = QColor("#E49B38")
                elif point["valid"]:
                    color = QColor("#358B5F")
                else:
                    color = QColor("#D44F4F")
                if index == self.current_frame_index:
                    color = QColor("#F2B83F")
                painter.setBrush(color)
                painter.setPen(QPen(QColor("#20352A"), 1))
                painter.drawEllipse(screen_point[0] - 5, screen_point[1] - 5, 10, 10)
        painter.end()
        return image

    def _refresh_3d_points(self):
        for actor in self.point_actors + self.link_actors:
            self.model_plotter.remove_actor(actor, render=False)
        self.point_actors.clear()
        self.link_actors.clear()

        for index, point in enumerate(self.points):
            if point["adjusted"]:
                color = "#E49B38"
            elif point["valid"]:
                color = "#358B5F"
            else:
                color = "#D44F4F"
            if index == self.current_frame_index:
                color = "#F2B83F"
            actor = self.model_plotter.add_mesh(
                pv.Sphere(center=(point["x"], point["y"], point["z"]), radius=20),
                color=color,
                smooth_shading=True,
            )
            self.point_actors.append(actor)
            if index:
                previous = self.points[index - 1]
                link = pv.Line(
                    (previous["x"], previous["y"], previous["z"]),
                    (point["x"], point["y"], point["z"]),
                ).tube(radius=5)
                self.link_actors.append(
                    self.model_plotter.add_mesh(link, color="#D9B967")
                )
        self.model_plotter.render()

    def _save(self):
        if not self.points:
            return
        output_path = self.frame_folder / f"positions_{self.timestamp}.json"
        if output_path.exists():
            response = QMessageBox.warning(
                self,
                "Overwrite positions?",
                f"{output_path.name} already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return
        try:
            save_positions(output_path, self.points, self.timestamp)
            self.settings.setdefault("calibration", {})[
                "match_tolerance_mm"
            ] = self.tolerance_spin.value()
            self.settings["led"]["maxLEDdist"] = self.max_distance_spin.value()
            save_settings(self.settings)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Calibrate", f"Could not save positions: {error}")
            return
        QMessageBox.information(self, "Calibrate", f"Saved positions to:\n{output_path}")
        self.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.detections is not None:
            QTimer.singleShot(0, self._refresh_all_views)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3dXmasTree")
        self.resize(1100, 720)

        self.plotter = QtInteractor(self)
        self.central_stack = QStackedWidget(self)
        self.home_page = QWidget(self.central_stack)
        main_layout = QHBoxLayout(self.home_page)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        button_panel = QWidget(self.home_page)
        button_panel.setFixedWidth(180)
        button_layout = QVBoxLayout(button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        setup_color_button = QPushButton("Setup Color", button_panel)
        setup_color_button.setMinimumHeight(36)
        setup_color_button.clicked.connect(self._setup_color)
        button_layout.addWidget(setup_color_button)

        setup_length_button = QPushButton("Setup LED Length", button_panel)
        setup_length_button.setMinimumHeight(36)
        setup_length_button.clicked.connect(self._setup_length)
        button_layout.addWidget(setup_length_button)

        grab_positions_button = QPushButton("Grab Positions", button_panel)
        grab_positions_button.setMinimumHeight(36)
        grab_positions_button.clicked.connect(self._grab_positions)
        button_layout.addWidget(grab_positions_button)

        calibrate_button = QPushButton("Calibrate", button_panel)
        calibrate_button.setMinimumHeight(36)
        calibrate_button.clicked.connect(self._calibrate)
        button_layout.addWidget(calibrate_button)

        exit_button = QPushButton("Exit", button_panel)
        exit_button.setMinimumHeight(36)
        exit_button.clicked.connect(lambda checked=False: self.close())
        button_layout.addWidget(exit_button)
        button_layout.addStretch()

        main_layout.addWidget(button_panel)
        main_layout.addWidget(self.plotter, 1)
        self.central_stack.addWidget(self.home_page)
        self.setCentralWidget(self.central_stack)

        self.plotter.set_background("#f3f5f7")
        self.orbiters = []
        self._build_tree_scene()
        self._update_orbiter_positions(0)
        self.plotter.view_isometric()
        self.plotter.reset_camera()

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(33)
        self.animation_timer.timeout.connect(self._animate_orbiters)
        self.animation_start = time.monotonic()

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        reset_view = QAction("Reset View", self)
        reset_view.setShortcut(QKeySequence("Ctrl+0"))
        reset_view.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        reset_view.triggered.connect(lambda checked=False: self._reset_current_3d_view())
        self.addAction(reset_view)
        toolbar.addAction(reset_view)

        close_window = QAction("Close Window", self)
        close_window.setShortcuts(
            [QKeySequence("Ctrl+F4"), QKeySequence("Ctrl+Q")]
        )
        close_window.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        close_window.triggered.connect(lambda checked=False: self.close())
        self.addAction(close_window)

        self.axes_action = QAction("Axes", self)
        self.axes_action.setCheckable(True)
        self.axes_action.setChecked(False)
        self.axes_action.toggled.connect(self._set_axes_visible)
        toolbar.addAction(self.axes_action)

        self.statusBar().showMessage("Ready")

    def _current_3d_viewport(self):
        current_page = self.central_stack.currentWidget()
        if isinstance(current_page, QtInteractor):
            return current_page
        viewports = current_page.findChildren(QtInteractor)
        return viewports[0] if viewports else None

    def _reset_current_3d_view(self):
        viewport = self._current_3d_viewport()
        if viewport is not None:
            viewport.reset_camera()

    def _set_axes_visible(self, visible):
        viewport = self._current_3d_viewport()
        if viewport is None:
            return
        if visible:
            viewport.show_axes()
        else:
            viewport.hide_axes()

    def _build_tree_scene(self):
        tiers = (
            (0.95, 2.0, 1.0, "#15543E"),
            (1.75, 2.0, 0.78, "#1B6649"),
            (2.55, 1.9, 0.56, "#237653"),
        )
        for center_z, height, radius, color in tiers:
            self.plotter.add_mesh(
                pv.Cone(
                    center=(0, 0, center_z),
                    direction=(0, 0, 1),
                    height=height,
                    radius=radius,
                    resolution=64,
                ),
                color=color,
                smooth_shading=True,
            )

        self.plotter.add_mesh(
            pv.Cylinder(
                center=(0, 0, -0.14),
                direction=(0, 0, 1),
                radius=0.46,
                height=0.48,
                resolution=48,
            ),
            color="#B94F36",
            smooth_shading=True,
        )
        self.plotter.add_mesh(
            pv.Cylinder(
                center=(0, 0, 0.10),
                direction=(0, 0, 1),
                radius=0.49,
                height=0.08,
                resolution=48,
            ),
            color="#D16A46",
            smooth_shading=True,
        )
        self.plotter.add_mesh(
            pv.Cylinder(
                center=(0, 0, 0.57),
                direction=(0, 0, 1),
                radius=0.12,
                height=0.96,
                resolution=24,
            ),
            color="#79523A",
            smooth_shading=True,
        )
        self.plotter.add_mesh(
            pv.Sphere(center=(0, 0, 3.66), radius=0.16, theta_resolution=20, phi_resolution=16),
            color="#F2C451",
            smooth_shading=True,
        )

        generator = random.Random()
        light_colors = ("#F4C95D", "#E25C4A", "#62B7D0", "#F4EFE3")
        for _ in range(24):
            height = generator.uniform(0.30, 3.30)
            radius = self._tree_surface_radius(height) + generator.uniform(0.025, 0.10)
            phase = generator.uniform(0, math.tau)
            speed = generator.choice((-1, 1)) * generator.uniform(0.28, 0.82)
            color = generator.choice(light_colors)
            actor = self.plotter.add_mesh(
                pv.Sphere(radius=0.065, theta_resolution=12, phi_resolution=10),
                color=color,
                smooth_shading=True,
            )
            self.orbiters.append((actor, height, radius, phase, speed))

        ground_ring = pv.Disc(
            center=(0, 0, -0.39),
            inner=0.52,
            outer=1.55,
            normal=(0, 0, 1),
            r_res=1,
            c_res=64,
        )
        self.plotter.add_mesh(ground_ring, color="#D9E5DE")

    @staticmethod
    def _tree_surface_radius(height):
        tiers = ((0.95, 2.0, 1.0), (1.75, 2.0, 0.78), (2.55, 1.9, 0.56))
        radii = []
        for center_z, tier_height, base_radius in tiers:
            lower = center_z - tier_height / 2
            upper = center_z + tier_height / 2
            if lower <= height <= upper:
                radii.append(base_radius * (upper - height) / tier_height)
        return max(radii, default=0.08)

    def _animate_orbiters(self):
        elapsed = time.monotonic() - self.animation_start
        self._update_orbiter_positions(elapsed)
        self.plotter.render()

    def _update_orbiter_positions(self, elapsed):
        for actor, height, radius, phase, speed in self.orbiters:
            angle = phase + elapsed * speed
            actor.SetPosition(
                radius * math.cos(angle),
                radius * math.sin(angle),
                height,
            )

    def showEvent(self, event):
        super().showEvent(event)
        if not self.animation_timer.isActive():
            self.animation_start = time.monotonic()
            self.animation_timer.start()

    def closeEvent(self, event):
        self.animation_timer.stop()
        super().closeEvent(event)

    def _setup_color(self):
        response = QMessageBox.warning(
            self,
            "Setup Color",
            "Start these scripts first, using the same XMAS_AGENT_TOKEN on both "
            "devices:\n\n"
            "Pi: python pi_agent/agent_server.py\n"
            "Laptop: python laptop_agent/camera_server.py\n\n"
            "Continue when both agents are running and reachable.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return

        try:
            settings = load_settings()
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Setup Color", f"Could not read settings: {error}")
            return
        self._show_workflow(ColorSetupDialog(self.central_stack, settings))

    def _setup_length(self):
        response = QMessageBox.warning(
            self,
            "Setup LED Length",
            "Start the Pi agent and laptop camera agent first. For a real strip, "
            "start the Pi with --hardware; otherwise it will run in simulation.\n\n"
            "Continue when both agents are running and reachable.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return

        try:
            settings = load_settings()
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Setup LED Length",
                f"Could not read settings: {error}",
            )
            return
        self._show_workflow(LengthSetupDialog(self.central_stack, settings))

    def _grab_positions(self):
        response = QMessageBox.warning(
            self,
            "Grab Positions",
            "Start the Pi agent and laptop camera agent first. For a real strip, "
            "start the Pi with --hardware; otherwise captures will use simulation.\n\n"
            "You will be asked to orient the tree to FRONT, RIGHT, LEFT, and BACK.\n\n"
            "Continue when both agents are running and reachable.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return

        try:
            settings = load_settings()
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Grab Positions",
                f"Could not read settings: {error}",
            )
            return

        led_count = settings["led"].get("capture_test_led_count", 5)
        if not isinstance(led_count, int) or not 1 <= led_count <= 10000:
            QMessageBox.critical(
                self,
                "Grab Positions",
                "Set led.capture_test_led_count to a value from 1 to 10000.",
            )
            return

        session_name = datetime.now().strftime("%Y%m%d_%H%M")
        output_directory = PROJECT_ROOT / "pc_agent" / "frames" / session_name
        if output_directory.exists():
            QMessageBox.warning(
                self,
                "Grab Positions",
                f"A capture folder already exists for {session_name}. "
                "Start another session after the minute changes to avoid overwriting it.",
            )
            return
        try:
            page = PositionCapturePage(self.central_stack, settings, output_directory)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Grab Positions",
                f"Could not create the capture folder: {error}",
            )
            return
        self._show_workflow(page)

    def _calibrate(self):
        frame_root = PROJECT_ROOT / "pc_agent" / "frames"
        frame_folder = QFileDialog.getExistingDirectory(
            self,
            "Select captured frame session",
            str(frame_root),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not frame_folder:
            return

        try:
            settings = load_settings()
            source_timestamp(frame_folder)
            load_frame_paths(frame_folder)
            page = CalibrationPage(self.central_stack, frame_folder, settings)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Calibrate", str(error))
            return
        self._show_workflow(page)

    def _show_workflow(self, page):
        self.animation_timer.stop()
        page.finished.connect(lambda _result, finished_page=page: self._return_home(finished_page))
        self.central_stack.addWidget(page)
        self.central_stack.setCurrentWidget(page)

    def _return_home(self, page):
        self.animation_timer.stop()
        self.central_stack.setCurrentWidget(self.home_page)
        self.central_stack.removeWidget(page)
        page.deleteLater()
        QTimer.singleShot(0, self._restore_home_viewport)

    def _restore_home_viewport(self):
        if not self.isVisible() or self.central_stack.currentWidget() is not self.home_page:
            return
        self.plotter.show()
        self.plotter.reset_camera_clipping_range()
        self.plotter.render()
        self.animation_start = time.monotonic()
        self.animation_timer.start()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()