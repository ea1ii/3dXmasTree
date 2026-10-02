#!/usr/bin/env python3

import sys
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
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
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


class ColorSetupDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.worker = None
        self.busy = False
        self.test_active = False
        self.current_order = None
        self.pending_result = None
        self.pending_error = None
        self.pending_success = None
        self.setWindowTitle("Setup Color")
        self.setModal(True)
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
        self._set_busy(False)
        self.status_label.setText(
            "Candidate {candidate_number} of {candidate_count}: {pixel_order}. "
            "Choose Yes if the strip matches the color below.".format(**status)
        )
        pixmap = QPixmap()
        if not pixmap.loadFromData(image):
            self._operation_failed("The laptop agent returned an unreadable image.")
            return
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _confirm(self):
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
            return status

        self._run_operation(save_selection, self._confirm_complete)

    def _confirm_complete(self, result):
        self.test_active = False
        QMessageBox.warning(
            self,
            "Setup Color Complete",
            f"Saved LED color order: {result['pixel_order']}.\n\n"
            "Stop the Pi agent and laptop camera agent in their remote terminals "
            "with Ctrl+Q or Ctrl+F4 (if the terminal forwards it), then close "
            "the SSH sessions.",
        )
        self.accept()

    def _abort(self):
        if not self.test_active:
            self.reject()
            return

        def abort_test():
            return request_json(
                "pi",
                "/color-test/decision",
                self.settings,
                method="POST",
                payload={"decision": "abort"},
            )

        self._run_operation(abort_test, self._abort_complete)

    def _abort_complete(self, _result):
        self.test_active = False
        self._set_busy(False)
        QMessageBox.warning(
            self,
            "Setup Color Aborted",
            "The LED test was stopped without saving. Stop the Pi agent and laptop "
            "camera agent in their remote terminals with Ctrl+Q or Ctrl+F4 "
            "(if the terminal forwards it), then close the SSH sessions.",
        )
        self.reject()

    def reject(self):
        if self.test_active and not self.busy:
            self._abort()
            return
        if self.busy:
            return
        super().reject()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3dXmasTree")
        self.resize(1100, 720)

        self.plotter = QtInteractor(self)
        central_widget = QWidget(self)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        button_panel = QWidget(central_widget)
        button_panel.setFixedWidth(180)
        button_layout = QVBoxLayout(button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        setup_color_button = QPushButton("Setup Color", button_panel)
        setup_color_button.setMinimumHeight(36)
        setup_color_button.clicked.connect(self._setup_color)
        button_layout.addWidget(setup_color_button)

        placeholder_button = QPushButton("Button 2", button_panel)
        placeholder_button.setMinimumHeight(36)
        button_layout.addWidget(placeholder_button)

        exit_button = QPushButton("Exit", button_panel)
        exit_button.setMinimumHeight(36)
        exit_button.clicked.connect(lambda checked=False: self.close())
        button_layout.addWidget(exit_button)
        button_layout.addStretch()

        main_layout.addWidget(button_panel)
        main_layout.addWidget(self.plotter, 1)
        self.setCentralWidget(central_widget)

        self.plotter.set_background("#f3f5f7")
        self.plotter.add_mesh(
            pv.Cube(),
            color="#d65a3a",
            show_edges=True,
            edge_color="#733b2d",
        )
        self.plotter.add_text(
            "Hello, world!",
            position="upper_left",
            font_size=16,
            color="#20242a",
        )
        self.plotter.add_axes()
        self.plotter.reset_camera()

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
        self.axes_action.setChecked(True)
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
        ColorSetupDialog(self, settings).exec()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()