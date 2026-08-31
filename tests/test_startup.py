import plistlib
import sys
import tempfile
import unittest
from os import environ
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

from spade65.startup import (
    default_gui_startup_path,
    platform_family,
    default_service_paths,
    gui_auto_start_status,
    gui_startup_filename,
    release_service_setup,
    render_gui_startup,
    render_startup,
    set_gui_auto_start,
    startup_filename,
)


class StartupTests(unittest.TestCase):
    def test_default_service_paths_are_user_owned(self):
        linux = default_service_paths(
            "linux",
            environ={"XDG_CONFIG_HOME": "/config"},
            home=PurePosixPath("/home/test"),
        )
        windows = default_service_paths(
            "windows",
            environ={"APPDATA": "C:/Users/test/Roaming"},
            home=PureWindowsPath("C:/Users/test"),
        )
        macos = default_service_paths(
            "macos", environ={}, home=PurePosixPath("/Users/test")
        )

        self.assertEqual(linux[0], PurePosixPath("/config/spade65/background.json"))
        self.assertEqual(linux[1].name, "spade65-background.service")
        self.assertEqual(windows[1].name, "spade65-background.cmd")
        self.assertEqual(
            macos[1],
            PurePosixPath(
                "/Users/test/Library/LaunchAgents/com.spade65.background.plist"
            ),
        )

    def test_release_linux_setup_uses_current_appimage(self):
        setup = release_service_setup(
            "linux",
            environ={
                "APPIMAGE": "/home/test/Applications/Spade65.AppImage",
                "XDG_CONFIG_HOME": "/home/test/.config",
            },
            home=PurePosixPath("/home/test"),
            frozen=True,
        )

        self.assertTrue(setup["packaged"])
        self.assertIn(
            "Spade65.AppImage service example", setup["prepare_commands"]
        )
        self.assertIn("systemctl --user enable --now", setup["activate_commands"])
        self.assertNotIn("spade65ctl", setup["prepare_commands"])
        self.assertNotIn("spade65ctl", setup["activate_commands"])

    def test_release_windows_setup_uses_console_executable(self):
        setup = release_service_setup(
            "windows",
            environ={"APPDATA": "C:/Users/test/AppData/Roaming"},
            home=PureWindowsPath("C:/Users/test"),
            executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
            frozen=True,
        )

        self.assertIn("Spade65CLI.exe", setup["prepare_commands"])
        self.assertIn("Spade65CLI.exe", setup["activate_commands"])
        self.assertIn(
            "Windows/Start Menu/Programs/Startup",
            setup["launcher_path"].replace("\\", "/"),
        )
        self.assertNotIn("spade65ctl", setup["prepare_commands"])
        self.assertNotIn("spade65ctl", setup["activate_commands"])

    def test_release_macos_setup_uses_launch_agent(self):
        setup = release_service_setup(
            "macos",
            environ={},
            home=PurePosixPath("/Users/test"),
            executable=PurePosixPath(
                "/Applications/Spade65.app/Contents/MacOS/Spade65"
            ),
            frozen=True,
        )

        self.assertIn("launchctl bootstrap", setup["activate_commands"])
        self.assertIn(
            "Spade65.app/Contents/MacOS/Spade65", setup["prepare_commands"]
        )

    def test_source_setup_keeps_commands_out_of_gui_metadata(self):
        setup = release_service_setup(
            "linux",
            environ={},
            home=PurePosixPath("/home/test"),
            frozen=False,
        )

        self.assertFalse(setup["packaged"])
        self.assertEqual(setup["prepare_commands"], "")
        self.assertEqual(setup["activate_commands"], "")

    def test_foreign_platform_setup_refuses_to_guess_host_values(self):
        # A launcher for another operating system must never inherit this
        # machine's home directory, environment, or interpreter.
        foreign = "windows" if sys.platform != "win32" else "linux"
        with self.assertRaisesRegex(ValueError, "target runtime is required"):
            release_service_setup(foreign)
        with self.assertRaisesRegex(ValueError, "target home directory"):
            release_service_setup(foreign, frozen=True)
        with self.assertRaisesRegex(ValueError, "target executable is required"):
            release_service_setup(
                foreign, frozen=True, home=PureWindowsPath("C:/Users/test")
            )

    def test_local_startup_paths_still_describe_the_current_user(self):
        # default_*_path answers "where does this user's own startup file live",
        # so a simulated platform still resolves against the real home.
        foreign = "windows" if sys.platform != "win32" else "linux"
        config, launcher = default_service_paths(foreign)
        self.assertIn(str(Path.home()).replace("\\", "/"), str(config).replace("\\", "/"))
        self.assertEqual(launcher.name, startup_filename(foreign))
        self.assertEqual(
            default_gui_startup_path(foreign).name, gui_startup_filename(foreign)
        )

    def test_foreign_platform_launchers_refuse_to_guess_host_values(self):
        foreign = "windows" if sys.platform != "win32" else "linux"
        with self.assertRaisesRegex(ValueError, "target runtime is required"):
            render_gui_startup(platform=foreign)
        with self.assertRaisesRegex(ValueError, "target executable is required"):
            render_gui_startup(platform=foreign, frozen=True)
        with self.assertRaisesRegex(ValueError, "target runtime is required"):
            render_startup(
                PureWindowsPath("C:/Users/test/background.json"),
                platform=foreign,
                python_executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
            )
        with self.assertRaisesRegex(ValueError, "must be an absolute"):
            render_gui_startup(
                platform=foreign,
                frozen=True,
                executable=PureWindowsPath("Spade65.exe"),
            )

    def test_cross_host_output_never_contains_a_host_path(self):
        # Live host values are useless as markers: '/usr/local/bin' is the real
        # interpreter directory inside the official python Docker images, and a
        # short cwd matches everything. Plant sentinels instead, and compare in
        # both separator flavours so a re-rendered leak cannot hide.
        home = "/__SPADE65_HOST_HOME__"
        executable = "/__SPADE65_HOST_PY__/python3"
        sentinels = []
        for value in (home, executable, "/__SPADE65_HOST_CWD__"):
            sentinels.extend((value, str(PureWindowsPath(value))))

        def generate() -> list[str]:
            outputs = [
                render_startup(
                    PureWindowsPath("C:/Users/test/background.json"),
                    platform="windows",
                    python_executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
                    frozen=True,
                ),
                render_startup(
                    PurePosixPath("/Users/test/background.json"),
                    platform="macos",
                    python_executable=PurePosixPath("/opt/py/python3"),
                    frozen=False,
                ),
                render_gui_startup(
                    platform="windows",
                    frozen=True,
                    executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
                ),
                render_gui_startup(
                    platform="macos",
                    frozen=True,
                    executable=PurePosixPath("/Applications/Spade65.app/S"),
                ),
            ]
            setups = [
                # No APPDATA, so the target home is what builds every path and a
                # host-home fallback would actually show up.
                release_service_setup(
                    "windows",
                    frozen=True,
                    home=PureWindowsPath("C:/Users/test"),
                    environ={},
                    executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
                ),
                release_service_setup(
                    "macos",
                    frozen=True,
                    home=PurePosixPath("/Users/test"),
                    environ={},
                    executable=PurePosixPath("/Applications/Spade65.app/S"),
                ),
            ]
            # str(dict) would repr-escape every backslash, so a Windows-rendered
            # leak could never match. Check the raw values instead.
            for setup in setups:
                outputs.extend(
                    value for value in setup.values() if isinstance(value, str)
                )
            return outputs

        with (
            patch("spade65.startup.sys.executable", executable),
            patch("spade65.startup.Path.home", return_value=Path(home)),
            patch.dict("os.environ", {"APPIMAGE": home + "/App.AppImage"}),
        ):
            generated = generate()
        for index, text in enumerate(generated):
            for sentinel in sentinels:
                with self.subTest(output=index, sentinel=sentinel):
                    self.assertNotIn(sentinel, text)

    def test_percent_in_paths_survives_every_launcher_format(self):
        # '%' prefixes a systemd unit specifier and a cmd.exe variable, so both
        # generators have to double it.
        service = render_startup(
            PurePosixPath("/home/test/100%data/background.json"),
            platform="linux",
            python_executable=PurePosixPath("/opt/Spa%de65/Spade65"),
            frozen=True,
        )
        self.assertIn(
            'ExecStart="/opt/Spa%%de65/Spade65" service run '
            '"/home/test/100%%data/background.json"',
            service,
        )
        command = render_startup(
            PureWindowsPath("C:/cfg/100%data/background.json"),
            platform="windows",
            python_executable=PureWindowsPath("C:/Prog%ram/Spade65.exe"),
            frozen=True,
        )
        self.assertIn(r'"C:\Prog%%ram\Spade65.exe"', command)
        self.assertIn(r'"C:\cfg\100%%data\background.json"', command)

    def test_systemd_expansions_are_escaped_in_the_unit(self):
        # '$' introduces an environment expansion in ExecStart, so a literal one
        # has to be doubled or systemd substitutes the variable's value.
        service = render_startup(
            PurePosixPath("/srv/pre${HOME}post/background.json"),
            platform="linux",
            python_executable=PurePosixPath("/opt/Spade65/Spade65"),
            frozen=True,
        )
        self.assertIn('"/srv/pre$${HOME}post/background.json"', service)

    def test_launchers_the_target_would_discard_are_refused(self):
        # Each of these writes a file that is accepted and then silently never
        # runs, so the generator has to fail instead of emitting it.
        with self.assertRaisesRegex(ValueError, "must not contain '%'"):
            render_gui_startup(
                platform="linux",
                executable=PurePosixPath("/opt/Spa%de65/Spade65"),
                frozen=True,
            )
        for character in ("\\", '"', "'"):
            with self.subTest(character=character):
                with self.assertRaisesRegex(ValueError, "systemd refuses"):
                    render_startup(
                        PurePosixPath("/home/test/background.json"),
                        platform="linux",
                        python_executable=PurePosixPath(
                            f"/opt/a{character}b/Spade65"
                        ),
                        frozen=True,
                    )
        with self.assertRaisesRegex(ValueError, "control characters"):
            render_startup(
                PurePosixPath("/home/test/back\nground.json"),
                platform="linux",
                python_executable=PurePosixPath("/opt/Spade65/Spade65"),
                frozen=True,
            )

    def test_desktop_entry_escapes_every_shell_character_for_the_key_file(self):
        # The key-file general escape rule is applied before the Exec quoting
        # rule, so each backslash the quoting adds must itself be doubled.
        expected = {
            "$": r'"/opt/a\\$b/Spade65"',
            "`": r'"/opt/a\\`b/Spade65"',
            '"': r'"/opt/a\\"b/Spade65"',
            "\\": r'"/opt/a\\\\b/Spade65"',
        }
        for character, rendered in expected.items():
            with self.subTest(character=character):
                entry = render_gui_startup(
                    platform="linux",
                    executable=PurePosixPath(f"/opt/a{character}b/Spade65"),
                    frozen=True,
                )
                self.assertIn(f"Exec={rendered}", entry)

    def test_absolute_target_paths_are_never_anchored_to_a_host_drive(self):
        # A POSIX path carries no drive letter, so a Windows host's Path calls
        # "/opt/Spade65/Spade65" relative and resolving it would rewrite the
        # launcher to D:\opt\... . Absoluteness has to be judged with the
        # target's rules. PureWindowsPath stands in for the host Path class
        # here; it has no .resolve(), so reaching that branch raises loudly.
        with (
            patch("spade65.startup.sys.platform", "linux"),
            patch("spade65.startup.Path", PureWindowsPath),
        ):
            unit = render_startup(
                PurePosixPath("/etc/spade65/background.json"),
                platform="linux",
                python_executable=PurePosixPath("/opt/Spade65/Spade65"),
                frozen=True,
            )
        self.assertIn(
            'ExecStart="/opt/Spade65/Spade65" service run '
            '"/etc/spade65/background.json"',
            unit,
        )
        self.assertNotIn("\\", unit)

    def test_bare_program_names_are_not_anchored_to_the_working_directory(self):
        # A bare name is resolved from PATH at launch; anchoring it to whatever
        # directory generated the file produces a plausible but wrong path. Only
        # the host's own platform accepts a relative value, so test that one.
        host = platform_family()
        name = "spade65.exe" if host == "windows" else "spade65"
        launcher = render_gui_startup(
            platform=host, executable=name, frozen=True
        )
        if host == "macos":
            payload = plistlib.loads(launcher.encode("utf-8"))
            self.assertEqual(payload["ProgramArguments"][0], name)
        elif host == "linux":
            self.assertIn(f'Exec="{name}"', launcher)
        else:
            self.assertIn(f'/b "{name}"', launcher)
        self.assertNotIn(str(Path.cwd()), launcher)

    def test_login_items_for_another_platform_report_unsupported(self):
        # This host cannot install or compare another OS's login item, and
        # inventing one from host values is what produced Linux paths inside a
        # Windows .cmd. The GUI already disables the toggle on `supported`.
        foreign = "windows" if sys.platform != "win32" else "linux"
        status = gui_auto_start_status(platform=foreign)
        self.assertFalse(status["supported"])
        self.assertFalse(status["current"])
        self.assertEqual(status["platform"], foreign)
        with self.assertRaisesRegex(
            ValueError, "cannot manage a login item for another platform"
        ):
            set_gui_auto_start(True, platform=foreign)

        # The host's own login item is still fully supported.
        host = platform_family()
        self.assertTrue(gui_auto_start_status(platform=host)["supported"])

        # An explicit target executable makes rendering meaningful again. It
        # has to be absolute in the target's own flavour, not the host's.
        explicit = gui_auto_start_status(
            platform=foreign,
            frozen=True,
            executable=(
                PureWindowsPath("C:/Spade65/Spade65.exe") if foreign == "windows"
                else PurePosixPath("/opt/Spade65/Spade65")
            ),
        )
        self.assertTrue(explicit["supported"])

    def test_platform_specific_filenames(self):
        self.assertEqual(startup_filename("linux"), "spade65-background.service")
        self.assertEqual(startup_filename("windows"), "spade65-background.cmd")
        self.assertEqual(startup_filename("macos"), "com.spade65.background.plist")

    def test_launchers_run_same_cross_platform_service(self):
        linux = render_startup(
            PurePosixPath("/home/test/service & profile.json"),
            platform="linux",
            python_executable=PurePosixPath("/usr/bin/python3"),
            frozen=False,
        )
        windows = render_startup(
            PureWindowsPath("C:/Users/test/service & profile.json"),
            platform="windows",
            python_executable=PureWindowsPath("C:/Python/python.exe"),
            frozen=False,
        )
        macos = render_startup(
            PurePosixPath("/Users/test/service & profile.json"),
            platform="macos",
            python_executable=PurePosixPath("/usr/local/bin/python3"),
            frozen=False,
        )
        self.assertIn("-m spade65 service run", linux)
        self.assertIn("pythonw.exe", windows)
        self.assertIn("-m</string><string>spade65", macos)
        self.assertIn("&amp;", macos)

    def test_frozen_launcher_calls_bundled_executable_directly(self):
        linux = render_startup(
            PurePosixPath("/home/test/.config/spade65/background.json"),
            platform="linux",
            python_executable=PurePosixPath("/opt/Spade65/Spade65"),
            frozen=True,
        )
        windows = render_startup(
            PureWindowsPath("C:/Users/test/AppData/Roaming/Spade65/background.json"),
            platform="windows",
            python_executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
            frozen=True,
        )
        macos = render_startup(
            PurePosixPath(
                "/Users/test/Library/Application Support/Spade65/background.json"
            ),
            platform="macos",
            python_executable=PurePosixPath(
                "/Applications/Spade65.app/Contents/MacOS/Spade65"
            ),
            frozen=True,
        )
        for launcher in (linux, windows, macos):
            self.assertNotIn("-m spade65", launcher)
            self.assertIn("service", launcher)
        self.assertNotIn("pythonw.exe", windows)

    def test_frozen_appimage_launcher_uses_persistent_image_path(self):
        with (
            patch("spade65.startup.sys.platform", "linux"),
            patch.dict(environ, {"APPIMAGE": "/home/user/Spade65.AppImage"}),
        ):
            launcher = render_startup(
                Path("/tmp/service.json"), platform="linux", frozen=True
            )
        self.assertIn(
            '/home/user/Spade65.AppImage" service run', launcher.replace("\\", "/")
        )

    def test_windows_cli_generates_hidden_gui_service_launcher(self):
        launcher = render_startup(
            Path("C:/Users/test/service.json"),
            platform="windows",
            python_executable=Path("C:/Spade65/Spade65CLI.exe"),
            frozen=True,
        )
        self.assertIn("Spade65.exe", launcher)
        self.assertNotIn("Spade65CLI.exe", launcher)

    def test_cross_host_launcher_never_falls_back_to_host_executable(self):
        with (
            patch("spade65.startup.sys.platform", "linux"),
            self.assertRaisesRegex(ValueError, "target executable is required"),
        ):
            render_startup(
                PureWindowsPath(
                    "C:/Users/test/AppData/Roaming/Spade65/background.json"
                ),
                platform="windows",
                frozen=True,
            )

    def test_cross_host_launcher_requires_absolute_target_paths(self):
        with (
            patch("spade65.startup.sys.platform", "linux"),
            self.assertRaisesRegex(ValueError, "target service config must be"),
        ):
            render_startup(
                PureWindowsPath("background.json"),
                platform="windows",
                python_executable=PureWindowsPath("C:/Spade65/Spade65.exe"),
                frozen=True,
            )

    def test_gui_startup_paths_are_owned_by_the_current_user(self):
        linux = default_gui_startup_path(
            "linux",
            environ={"XDG_CONFIG_HOME": "/config"},
            home=PurePosixPath("/home/test"),
        )
        windows = default_gui_startup_path(
            "windows",
            environ={"APPDATA": "C:/Users/test/Roaming"},
            home=PureWindowsPath("C:/Users/test"),
        )
        macos = default_gui_startup_path(
            "macos", environ={}, home=PurePosixPath("/Users/test")
        )

        self.assertEqual(
            linux,
            PurePosixPath(
                "/config/autostart/io.github.dirhamtriyadi.spade65.desktop"
            ),
        )
        self.assertEqual(windows.name, "spade65-gui.cmd")
        self.assertEqual(
            macos,
            PurePosixPath(
                "/Users/test/Library/LaunchAgents/"
                "io.github.dirhamtriyadi.spade65.gui.plist"
            ),
        )
        self.assertEqual(
            gui_startup_filename("linux"),
            "io.github.dirhamtriyadi.spade65.desktop",
        )

    def test_gui_login_launchers_start_the_desktop_hidden(self):
        linux = render_gui_startup(
            platform="linux",
            executable=PurePosixPath("/opt/Spade65/Spade65"),
            frozen=True,
        )
        windows = render_gui_startup(
            platform="windows",
            executable=PureWindowsPath("C:/Python/python.exe"),
            frozen=False,
        )
        macos = render_gui_startup(
            platform="macos",
            executable=PurePosixPath(
                "/Applications/Spade65.app/Contents/MacOS/Spade65"
            ),
            frozen=True,
        )
        macos_payload = plistlib.loads(macos.encode("utf-8"))

        self.assertIn('"gui" "--start-hidden"', linux)
        self.assertIn("Terminal=false", linux)
        self.assertIn("pythonw.exe", windows)
        self.assertIn('"-m" "spade65" "gui" "--start-hidden"', windows)
        self.assertEqual(
            macos_payload["ProgramArguments"],
            [
                "/Applications/Spade65.app/Contents/MacOS/Spade65",
                "gui",
                "--start-hidden",
            ],
        )
        self.assertTrue(macos_payload["RunAtLoad"])
        self.assertFalse(macos_payload["KeepAlive"])
        self.assertEqual(macos_payload["ProcessType"], "Interactive")
        self.assertEqual(
            macos_payload["AssociatedBundleIdentifiers"],
            ["io.github.dirhamtriyadi.spade65"],
        )

    def test_gui_appimage_startup_uses_the_persistent_image_path(self):
        launcher = render_gui_startup(
            platform="linux",
            environ={"APPIMAGE": "/home/user/Applications/Spade65.AppImage"},
            frozen=True,
        )
        self.assertIn("/home/user/Applications/Spade65.AppImage", launcher)

    def test_gui_auto_start_can_be_enabled_refreshed_and_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "spade65.desktop"
            enabled = set_gui_auto_start(
                True,
                platform="linux",
                executable=PurePosixPath("/opt/Spade65/Spade65"),
                frozen=True,
                startup_path=target,
            )
            self.assertTrue(enabled["enabled"])
            self.assertTrue(enabled["current"])

            target.write_text("old launcher\n", encoding="utf-8")
            stale = gui_auto_start_status(
                platform="linux",
                executable=PurePosixPath("/opt/Spade65/Spade65"),
                frozen=True,
                startup_path=target,
            )
            self.assertTrue(stale["enabled"])
            self.assertFalse(stale["current"])

            disabled = set_gui_auto_start(
                False,
                platform="linux",
                executable=PurePosixPath("/opt/Spade65/Spade65"),
                frozen=True,
                startup_path=target,
            )
            self.assertFalse(disabled["enabled"])
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
