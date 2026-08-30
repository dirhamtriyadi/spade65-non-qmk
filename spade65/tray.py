"""Native system-tray integration using the desktop toolkit already in use."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable


TRAY_TITLE = "Spade65 Control Center"
_MAC_DELEGATE_CLASS: type | None = None


class TrayUnavailable(RuntimeError):
    """Raised when the active desktop session has no usable system tray."""


def _warn(message: str) -> None:
    if sys.stderr is not None:
        print(f"Spade65 tray: {message}", file=sys.stderr)


def _show_window(window: object) -> None:
    show = getattr(window, "show", None)
    restore = getattr(window, "restore", None)
    if callable(show):
        show()
    if callable(restore):
        restore()


class TrayController:
    """Coordinate close-to-tray behavior with a pywebview window."""

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        close_to_tray: bool = True,
        start_hidden: bool = False,
    ) -> None:
        self.platform_name = platform_name or sys.platform
        self.close_to_tray = close_to_tray
        self.start_hidden = start_hidden
        self._window: object | None = None
        self._native: object | None = None
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._attaching = False
        self._quitting = False
        self._fallback_started = False
        self._hidden_notice_shown = False

    @property
    def available(self) -> bool:
        with self._lock:
            return self._native is not None

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def wait_until_ready(self, timeout: float | None = None) -> bool:
        return self._ready.wait(timeout)

    def bind(self, window: object) -> None:
        """Bind tray setup and close interception to a pywebview window."""

        self._window = window
        events = getattr(window, "events", None)
        before_show = getattr(events, "before_show", None)
        closing = getattr(events, "closing", None)
        if before_show is not None:
            before_show += self._attach_native
        else:
            self._ready.set()
            if self.start_hidden:
                self._defer_visible_fallback()
        if closing is not None:
            closing += self._handle_closing

    def _attach_native(self) -> None:
        with self._lock:
            if self._ready.is_set() or self._attaching:
                return
            self._attaching = True
            window = self._window
        try:
            if window is None:
                raise TrayUnavailable("desktop window is not ready")
            native = _create_native_tray(
                self.platform_name,
                window,
                self.show,
                self.quit,
            )
            with self._lock:
                self._native = native
        except Exception as error:
            _warn(str(error))
        finally:
            with self._lock:
                self._attaching = False
                available = self._native is not None
                self._ready.set()
            if self.start_hidden and not available:
                self._defer_visible_fallback()

    def _defer_visible_fallback(self) -> None:
        with self._lock:
            if self._fallback_started:
                return
            self._fallback_started = True
            window = self._window

        def restore_after_startup() -> None:
            shown = getattr(getattr(window, "events", None), "shown", None)
            wait = getattr(shown, "wait", None)
            if callable(wait):
                wait(20)
            with self._lock:
                should_restore = not self._quitting and self._native is None
            if should_restore and window is not None:
                try:
                    _show_window(window)
                except Exception as error:
                    _warn(f"could not show startup fallback window: {error}")

        threading.Thread(
            target=restore_after_startup,
            name="spade65-tray-fallback",
            daemon=True,
        ).start()

    def _handle_closing(self) -> bool | None:
        with self._lock:
            native = self._native
            should_hide = (
                not self._quitting and self.close_to_tray and native is not None
            )
            window = self._window
        if not should_hide or window is None:
            return None
        try:
            hide_native = getattr(native, "hide_window", None)
            if callable(hide_native):
                hide_native()
            else:
                hide = getattr(window, "hide")
                hide()
            with self._lock:
                show_notice = not self._hidden_notice_shown
                self._hidden_notice_shown = True
            if show_notice:
                notify_hidden = getattr(native, "notify_hidden", None)
                if callable(notify_hidden):
                    notify_hidden()
        except Exception as error:
            _warn(f"could not hide the desktop window: {error}")
            return None
        # A locked pywebview closing event treats an exact False as cancel.
        return False

    def show(self) -> None:
        window = self._window
        if window is not None:
            _show_window(window)

    def set_close_to_tray(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("close-to-tray state must be a boolean")
        with self._lock:
            self.close_to_tray = enabled

    def quit(self) -> None:
        with self._lock:
            if self._quitting:
                return
            self._quitting = True
            window = self._window
        if window is not None:
            destroy = getattr(window, "destroy", None)
            if callable(destroy):
                destroy()

    def dispose(self) -> None:
        with self._lock:
            native = self._native
            self._native = None
        dispose = getattr(native, "dispose", None)
        if callable(dispose):
            try:
                dispose()
            except Exception as error:
                _warn(f"could not dispose native tray icon: {error}")


def _create_native_tray(
    platform_name: str,
    window: object,
    on_open: Callable[[], None],
    on_quit: Callable[[], None],
) -> object:
    if platform_name.startswith("linux"):
        return _QtTray(window, on_open, on_quit)
    if platform_name == "win32" or platform_name == "windows":
        return _WindowsTray(window, on_open, on_quit)
    if platform_name == "darwin" or platform_name == "macos":
        return _MacTray(window, on_open, on_quit)
    raise TrayUnavailable(f"system tray is unsupported on {platform_name}")


class _QtTray:
    def __init__(
        self,
        window: object,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        from qtpy import QtCore, QtGui, QtWidgets

        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            raise TrayUnavailable(
                "this Linux desktop session does not expose a system tray"
            )
        native_window = getattr(window, "native", None)
        if native_window is None:
            raise TrayUnavailable("Qt desktop window is not ready")
        self._window = native_window
        icon = native_window.windowIcon()
        if icon is None or icon.isNull():
            pixmap = QtGui.QPixmap(64, 64)
            pixmap.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#c9a75d"))
            painter.drawRoundedRect(4, 4, 56, 56, 13, 13)
            painter.setPen(QtGui.QColor("#172019"))
            font = QtGui.QFont("Sans Serif", 32, QtGui.QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "S"
            )
            painter.end()
            icon = QtGui.QIcon(pixmap)

        self._tray = QtWidgets.QSystemTrayIcon(icon, native_window)
        self._menu = QtWidgets.QMenu(native_window)
        self._open_action = self._menu.addAction("Open Spade65")
        self._menu.addSeparator()
        self._quit_action = self._menu.addAction("Quit Spade65")
        self._open_action.triggered.connect(lambda _checked=False: on_open())
        self._quit_action.triggered.connect(lambda _checked=False: on_quit())

        activation = QtWidgets.QSystemTrayIcon.ActivationReason
        open_reasons = {activation.Trigger, activation.DoubleClick}

        def activate(reason: object) -> None:
            if reason in open_reasons:
                on_open()

        self._activate = activate
        self._tray.activated.connect(activate)
        self._tray.setContextMenu(self._menu)
        self._tray.setToolTip(TRAY_TITLE)
        self._tray.show()

    def notify_hidden(self) -> None:
        self._tray.showMessage(
            "Spade65 is still running",
            "Open it from the system tray, or choose Quit Spade65 to exit.",
        )

    def hide_window(self) -> None:
        self._window.hide()

    def dispose(self) -> None:
        try:
            self._tray.hide()
            self._tray.setContextMenu(None)
            self._tray.deleteLater()
            self._menu.deleteLater()
        except RuntimeError:
            # The QMainWindow owns these objects and may already have deleted
            # them while the Qt event loop was shutting down.
            return


class _WindowsTray:
    def __init__(
        self,
        window: object,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        from System.Drawing import SystemIcons
        from System.Windows.Forms import (
            ContextMenuStrip,
            NotifyIcon,
            ToolStripMenuItem,
            ToolStripSeparator,
        )

        native_window = getattr(window, "native", None)
        if native_window is None:
            raise TrayUnavailable("Windows desktop window is not ready")
        self._window = native_window
        icon = getattr(native_window, "Icon", None) or SystemIcons.Application
        self._menu = ContextMenuStrip()
        self._open_item = ToolStripMenuItem("Open Spade65")
        self._quit_item = ToolStripMenuItem("Quit Spade65")
        self._separator = ToolStripSeparator()
        self._open_handler = lambda _sender, _event: on_open()
        self._quit_handler = lambda _sender, _event: on_quit()
        self._double_click_handler = lambda _sender, _event: on_open()
        self._open_item.Click += self._open_handler
        self._quit_item.Click += self._quit_handler
        self._menu.Items.Add(self._open_item)
        self._menu.Items.Add(self._separator)
        self._menu.Items.Add(self._quit_item)

        self._tray = NotifyIcon()
        self._tray.Icon = icon
        self._tray.Text = TRAY_TITLE
        self._tray.ContextMenuStrip = self._menu
        self._tray.DoubleClick += self._double_click_handler
        self._tray.Visible = True

    def notify_hidden(self) -> None:
        from System.Windows.Forms import ToolTipIcon

        self._tray.ShowBalloonTip(
            2500,
            "Spade65 is still running",
            "Open it from the system tray, or choose Quit Spade65 to exit.",
            ToolTipIcon.Info,
        )

    def hide_window(self) -> None:
        self._window.Hide()

    def dispose(self) -> None:
        self._tray.Visible = False
        self._tray.Dispose()
        self._menu.Dispose()


def _mac_delegate_class() -> type:
    global _MAC_DELEGATE_CLASS
    if _MAC_DELEGATE_CLASS is not None:
        return _MAC_DELEGATE_CLASS

    import Foundation
    import objc

    class Spade65TrayDelegate(Foundation.NSObject):
        @objc.namedSelector(b"spade65Show:")
        def show_spade65(self, _sender):
            self.open_callback()

        @objc.namedSelector(b"spade65Quit:")
        def quit_spade65(self, _sender):
            self.quit_callback()

    _MAC_DELEGATE_CLASS = Spade65TrayDelegate
    return Spade65TrayDelegate


class _MacTray:
    def __init__(
        self,
        window: object,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        import AppKit

        self._window = getattr(window, "native", None)
        if self._window is None:
            raise TrayUnavailable("macOS desktop window is not ready")
        delegate_class = _mac_delegate_class()
        self._delegate = delegate_class.alloc().init()
        self._delegate.open_callback = on_open
        self._delegate.quit_callback = on_quit
        self._status_bar = AppKit.NSStatusBar.systemStatusBar()
        self._status_item = self._status_bar.statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        button = self._status_item.button()
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "keyboard", "Spade65"
        )
        if image is not None:
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_("S")
        button.setToolTip_(TRAY_TITLE)

        self._menu = AppKit.NSMenu.alloc().initWithTitle_("Spade65")
        self._menu.setAutoenablesItems_(False)
        self._open_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Open Spade65", b"spade65Show:", ""
        )
        self._open_item.setTarget_(self._delegate)
        self._open_item.setEnabled_(True)
        self._menu.addItem_(self._open_item)
        self._menu.addItem_(AppKit.NSMenuItem.separatorItem())
        self._quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Spade65", b"spade65Quit:", ""
        )
        self._quit_item.setTarget_(self._delegate)
        self._quit_item.setEnabled_(True)
        self._menu.addItem_(self._quit_item)
        self._status_item.setMenu_(self._menu)

    def notify_hidden(self) -> None:
        return

    def hide_window(self) -> None:
        self._window.orderOut_(self._window)

    def dispose(self) -> None:
        self._status_item.setMenu_(None)
        self._status_bar.removeStatusItem_(self._status_item)
