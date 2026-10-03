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
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
)
from pyvistaqt import QtInteractor


from common.agent_client import AgentError, load_settings, request_image, request_json, save_settings


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
        self.output_directory.mkdir(parents=True, exist_ok=False)
        self.led_count = settings["led"].get("capture_test_led_count", 5)
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

        self.image_label = QLabel("No capture yet")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(520, 360)
        self.image_label.setStyleSheet("background: #20242a; color: white;")
        layout.addWidget(self.image_label, 1)

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
        self._capture_current_led()

    def _capture_current_led(self):
        view = self.VIEWS[self.view_index]
        led_number = self.current_led
        filename = f"{view}_LED_{led_number:03d}.jpg"
        image_path = self.output_directory / filename

        def capture_and_save():
            image = request_image("laptop", "/capture", self.settings)
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
        reset_view.triggered.connect(lambda checked=False: self.plotter.reset_camera())
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

        hello = QAction("Hello", self)
        hello.triggered.connect(
            lambda checked=False: self.statusBar().showMessage("Hello, world!", 3000)
        )
        toolbar.addAction(hello)

        self.statusBar().showMessage("Ready")

    def _set_axes_visible(self, visible):
        if visible:
            self.plotter.show_axes()
        else:
            self.plotter.hide_axes()

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

    def _show_workflow(self, page):
        self.animation_timer.stop()
        page.finished.connect(lambda _result, finished_page=page: self._return_home(finished_page))
        self.central_stack.addWidget(page)
        self.central_stack.setCurrentWidget(page)

    def _return_home(self, page):
        self.central_stack.setCurrentWidget(self.home_page)
        self.central_stack.removeWidget(page)
        page.deleteLater()
        if self.isVisible():
            self.animation_start = time.monotonic()
            self.animation_timer.start()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()