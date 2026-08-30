import errno
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65 import application
from spade65.desktop import DesktopUnavailable


class ApplicationTests(unittest.TestCase):
    def test_claim_server_uses_bind_as_the_single_instance_authority(self) -> None:
        server = MagicMock()
        with (
            patch.object(
                application,
                "create_gui_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ) as create,
            patch.object(application, "_reuse_existing") as reuse,
        ):
            self.assertEqual(
                application._claim_server("127.0.0.1", 8765, "desktop"),
                (server, "http://127.0.0.1:8765/"),
            )
        create.assert_called_once_with(host="127.0.0.1", port=8765)
        reuse.assert_not_called()

    def test_address_collision_reuses_only_a_verified_instance(self) -> None:
        collision = OSError(errno.EADDRINUSE, "already in use")
        with (
            patch.object(application, "create_gui_server", side_effect=collision),
            patch.object(application, "running_gui_token", return_value="token"),
            patch.object(application, "_reuse_existing", return_value=True) as reuse,
            patch.object(application.sys, "stdout", None),
        ):
            self.assertIsNone(
                application._claim_server("127.0.0.1", 8765, "desktop")
            )
        reuse.assert_called_once_with("http://127.0.0.1:8765/", "desktop")

    def test_windows_exclusive_bind_collision_reuses_verified_instance(self) -> None:
        collision = OSError(10013, "permission denied by exclusive bind")
        with (
            patch.object(application, "create_gui_server", side_effect=collision),
            patch.object(application, "running_gui_token", return_value="token"),
            patch.object(application, "_reuse_existing", return_value=True),
            patch.object(application.sys, "stdout", None),
        ):
            self.assertIsNone(
                application._claim_server("127.0.0.1", 8765, "desktop")
            )

    def test_localhost_spelling_uses_the_canonical_instance_authority(self) -> None:
        collision = OSError(errno.EADDRINUSE, "already in use")
        with (
            patch.object(
                application, "create_gui_server", side_effect=collision
            ) as create,
            patch.object(
                application, "running_gui_token", return_value="token"
            ) as token,
            patch.object(application, "_reuse_existing", return_value=True),
            patch.object(application.sys, "stdout", None),
        ):
            self.assertIsNone(
                application._claim_server("localhost", 8765, "desktop")
            )
        create.assert_called_once_with(host="127.0.0.1", port=8765)
        token.assert_called_with("http://127.0.0.1:8765/")

    def test_foreign_port_and_unrelated_os_errors_are_not_silenced(self) -> None:
        collision = OSError(errno.EADDRINUSE, "already in use")
        with (
            patch.object(application, "create_gui_server", side_effect=collision),
            patch.object(application, "running_gui_token", return_value=None),
            patch.object(application, "_reuse_existing", return_value=False),
            patch.object(application.time, "monotonic", side_effect=(0.0, 6.0)),
        ):
            with self.assertRaises(application.GuiPortInUse):
                application._claim_server("127.0.0.1", 8765, "desktop")

        denied = OSError(errno.EACCES, "denied")
        with patch.object(application, "create_gui_server", side_effect=denied):
            with self.assertRaises(OSError) as raised:
                application._claim_server("127.0.0.1", 8765, "desktop")
        self.assertIs(raised.exception, denied)

    def test_verified_but_unactivatable_instance_fails_without_browser_spam(self) -> None:
        collision = OSError(errno.EADDRINUSE, "already in use")
        with (
            patch.object(application, "create_gui_server", side_effect=collision),
            patch.object(application, "running_gui_token", return_value="token"),
            patch.object(application, "_reuse_existing", return_value=False) as reuse,
        ):
            with self.assertRaisesRegex(application.GuiPortInUse, "could not be activated"):
                application._claim_server("127.0.0.1", 8765, "desktop")
        reuse.assert_called_once_with("http://127.0.0.1:8765/", "desktop")

    def test_desktop_failure_falls_back_on_the_same_bound_server(self) -> None:
        server = SimpleNamespace(
            on_activate=None,
            on_quit=None,
            shutdown=MagicMock(),
            server_close=MagicMock(),
        )
        worker = MagicMock()
        worker.is_alive.return_value = False

        def fail_after_binding_window(**_arguments: object) -> None:
            server.on_quit = MagicMock()
            raise DesktopUnavailable("missing runtime")

        with (
            patch.object(
                application,
                "_claim_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ),
            patch.object(application, "_start_server", return_value=worker),
            patch.object(
                application,
                "run_desktop_session",
                side_effect=fail_after_binding_window,
            ),
            patch.object(application, "_open_browser", return_value=True),
            patch.object(application, "_wait_for_server") as wait,
            patch.object(application.sys, "stderr", None),
        ):
            application.launch_gui()
        wait.assert_called_once_with(server, worker)
        self.assertTrue(callable(server.on_activate))
        self.assertIsNone(server.on_quit)
        server.server_close.assert_called_once_with()

    def test_browser_open_failure_is_reported_and_server_is_closed(self) -> None:
        server = SimpleNamespace(
            on_activate=None,
            on_quit=None,
            shutdown=MagicMock(),
            server_close=MagicMock(),
        )
        worker = MagicMock()
        worker.is_alive.return_value = False
        with (
            patch.object(
                application,
                "_claim_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ),
            patch.object(application, "_start_server", return_value=worker),
            patch.object(application, "_open_browser", return_value=False),
        ):
            with self.assertRaisesRegex(DesktopUnavailable, "default browser"):
                application.launch_gui(mode="browser")
        server.server_close.assert_called_once_with()

    def test_hidden_startup_is_forwarded_only_to_the_desktop_session(self) -> None:
        server = SimpleNamespace(
            on_activate=None,
            on_quit=None,
            shutdown=MagicMock(),
            server_close=MagicMock(),
        )
        worker = MagicMock()
        worker.is_alive.return_value = False
        with (
            patch.object(
                application,
                "_claim_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ),
            patch.object(application, "_start_server", return_value=worker),
            patch.object(application, "run_desktop_session") as desktop,
        ):
            application.launch_gui(start_hidden=True)
        desktop.assert_called_once_with(
            server=server,
            url="http://127.0.0.1:8765/",
            activation=server.on_activate,
            start_hidden=True,
        )

        with self.assertRaisesRegex(ValueError, "only for the desktop"):
            application.launch_gui(mode="browser", start_hidden=True)

    def test_server_is_closed_when_worker_thread_cannot_start(self) -> None:
        server = SimpleNamespace(
            on_activate=None,
            on_quit=None,
            shutdown=MagicMock(),
            server_close=MagicMock(),
        )
        with (
            patch.object(
                application,
                "_claim_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ),
            patch.object(
                application, "_start_server", side_effect=RuntimeError("no thread")
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "no thread"):
                application.launch_gui()
        server.shutdown.assert_not_called()
        server.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
