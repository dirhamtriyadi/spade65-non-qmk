import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65.tray import TrayController, TrayUnavailable


class FakeEvent:
    def __init__(self) -> None:
        self.handlers = []
        self.event = threading.Event()

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        values = [handler() for handler in self.handlers]
        self.event.set()
        return any(value is False for value in values)

    def wait(self, timeout=None):
        return self.event.wait(timeout)

    def is_set(self):
        return self.event.is_set()


def fake_window():
    return SimpleNamespace(
        events=SimpleNamespace(
            before_show=FakeEvent(),
            closing=FakeEvent(),
            shown=FakeEvent(),
        ),
        show=MagicMock(),
        restore=MagicMock(),
        hide=MagicMock(),
        destroy=MagicMock(),
        native=SimpleNamespace(),
    )


class TrayControllerTests(unittest.TestCase):
    def test_close_is_cancelled_and_window_is_hidden_when_tray_is_available(self):
        window = fake_window()
        native = SimpleNamespace(
            hide_window=MagicMock(),
            notify_hidden=MagicMock(),
            dispose=MagicMock(),
        )
        controller = TrayController(platform_name="linux")
        with patch("spade65.tray._create_native_tray", return_value=native) as create:
            controller.bind(window)
            window.events.before_show.fire()

        self.assertTrue(controller.ready)
        self.assertTrue(controller.available)
        create.assert_called_once()
        self.assertTrue(window.events.closing.fire())
        native.hide_window.assert_called_once_with()
        window.hide.assert_not_called()
        native.notify_hidden.assert_called_once_with()

        self.assertTrue(window.events.closing.fire())
        self.assertEqual(native.hide_window.call_count, 2)
        native.notify_hidden.assert_called_once_with()
        controller.show()
        window.show.assert_called_once_with()
        window.restore.assert_called_once_with()

        controller.dispose()
        native.dispose.assert_called_once_with()
        self.assertFalse(controller.available)

    def test_close_exits_normally_when_close_to_tray_is_disabled(self):
        window = fake_window()
        controller = TrayController(close_to_tray=False)
        with patch(
            "spade65.tray._create_native_tray", return_value=SimpleNamespace()
        ):
            controller.bind(window)
            window.events.before_show.fire()

        self.assertFalse(window.events.closing.fire())
        window.hide.assert_not_called()
        controller.set_close_to_tray(True)
        self.assertTrue(window.events.closing.fire())
        window.hide.assert_called_once_with()

    def test_explicit_quit_bypasses_close_interception(self):
        window = fake_window()
        controller = TrayController()
        with patch(
            "spade65.tray._create_native_tray", return_value=SimpleNamespace()
        ):
            controller.bind(window)
            window.events.before_show.fire()

        controller.quit()
        controller.quit()
        window.destroy.assert_called_once_with()
        self.assertFalse(window.events.closing.fire())
        window.hide.assert_not_called()

    def test_hidden_startup_restores_window_when_tray_is_unavailable(self):
        window = fake_window()
        controller = TrayController(start_hidden=True)
        with (
            patch(
                "spade65.tray._create_native_tray",
                side_effect=TrayUnavailable("no tray"),
            ),
            patch("spade65.tray.threading.Thread") as thread,
            patch("spade65.tray.sys.stderr", None),
        ):
            controller.bind(window)
            window.events.before_show.fire()
            thread.assert_called_once()
            window.events.shown.fire()
            thread.call_args.kwargs["target"]()

        window.show.assert_called_once_with()
        window.restore.assert_called_once_with()
        self.assertTrue(controller.ready)
        self.assertFalse(controller.available)

    def test_setting_validation_rejects_truthy_non_booleans(self):
        controller = TrayController()
        with self.assertRaisesRegex(ValueError, "boolean"):
            controller.set_close_to_tray(1)


if __name__ == "__main__":
    unittest.main()
