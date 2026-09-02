import math
import struct
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65.desktop import ActivationBridge, DesktopApi, run_desktop_session
from spade65.system_audio import AudioCaptureError, PCMAnalyzer, SystemAudioProvider


def stereo_sine(
    frequency: float, *, amplitude: float = 0.5, frames: int = 2048
) -> bytes:
    values = []
    for index in range(frames):
        sample = int(
            32767 * amplitude * math.sin(2 * math.pi * frequency * index / 48_000)
        )
        values.extend((sample, sample))
    return struct.pack(f"<{len(values)}h", *values)


def wait_until(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


class PCMAnalyzerTests(unittest.TestCase):
    def test_pcm16_level_peak_and_spectrum_are_normalized(self) -> None:
        result = PCMAnalyzer().analyze_pcm16(stereo_sine(1_000))

        self.assertAlmostEqual(result["level"], math.sqrt(0.125), delta=0.02)
        self.assertAlmostEqual(result["peak"], 0.5, delta=0.02)
        self.assertEqual(len(result["bands"]), 10)
        self.assertEqual(result["bands"].index(max(result["bands"])), 4)
        self.assertTrue(all(0 <= value <= 1 for value in result["bands"]))

    def test_low_and_high_tones_land_in_different_bands(self) -> None:
        analyzer = PCMAnalyzer()
        low = analyzer.analyze_pcm16(stereo_sine(125))["bands"]
        high = analyzer.analyze_pcm16(stereo_sine(8_000))["bands"]

        self.assertLess(low.index(max(low)), high.index(max(high)))
        self.assertEqual(low.index(max(low)), 1)
        self.assertEqual(high.index(max(high)), 7)

    def test_empty_and_partial_pcm_are_safe_silence(self) -> None:
        analyzer = PCMAnalyzer()
        empty = analyzer.analyze_pcm16(b"\x00")

        self.assertEqual(empty["level"], 0.0)
        self.assertEqual(empty["peak"], 0.0)
        self.assertEqual(empty["bands"], [0.0] * 10)

    def test_phase_opposed_stereo_does_not_cancel(self) -> None:
        values = []
        for index in range(2048):
            sample = int(
                32767 * 0.5 * math.sin(2 * math.pi * 500 * index / 48_000)
            )
            values.extend((sample, -sample))

        result = PCMAnalyzer().analyze_pcm16(
            struct.pack(f"<{len(values)}h", *values)
        )

        self.assertGreater(result["level"], 0.3)
        self.assertGreater(result["peak"], 0.45)
        self.assertEqual(result["bands"].index(max(result["bands"])), 3)


class FakeDevice:
    def __init__(self, identifier: str, name: str, *, loopback: bool = False):
        self.id = identifier
        self.name = name
        self.isloopback = loopback
        self.closed = threading.Event()

    def recorder(self, **_kwargs):
        device = self

        class Recorder:
            def __enter__(self):
                return self

            def record(self, *, numframes):
                time.sleep(0.005)
                return [[0.25, 0.25] for _ in range(numframes)]

            def __exit__(self, *_args):
                device.closed.set()

        return Recorder()


class SystemAudioProviderTests(unittest.TestCase):
    def test_linux_enumerates_only_loopback_monitor_sources(self) -> None:
        microphone = FakeDevice("mic", "Desk microphone")
        monitor = FakeDevice("speaker.monitor", "Monitor of Speakers", loopback=True)
        soundcard = SimpleNamespace(
            all_microphones=lambda include_loopback=False: (
                [microphone, monitor] if include_loopback else [microphone]
            ),
            default_speaker=lambda: SimpleNamespace(id="speaker", name="Speakers"),
        )
        provider = SystemAudioProvider(
            platform_name="linux", soundcard_module=soundcard
        )

        status = provider.list_sources()

        self.assertTrue(status["available"])
        self.assertEqual(status["backend"], "pipewire-pulse-monitor")
        self.assertEqual(len(status["sources"]), 1)
        self.assertEqual(status["sources"][0]["name"], "Monitor of Speakers")
        self.assertTrue(status["sources"][0]["default"])

    def test_linux_capture_publishes_measurements_and_stops_cleanly(self) -> None:
        monitor = FakeDevice("speaker.monitor", "Monitor of Speakers", loopback=True)
        soundcard = SimpleNamespace(
            all_microphones=lambda include_loopback=False: (
                [monitor] if include_loopback else []
            ),
            default_speaker=lambda: SimpleNamespace(id="speaker", name="Speakers"),
        )
        provider = SystemAudioProvider(
            platform_name="linux", soundcard_module=soundcard
        )
        source_id = provider.list_sources()["sources"][0]["id"]

        started = provider.start(source_id)
        self.assertTrue(started["running"])
        self.assertTrue(
            wait_until(lambda: provider.snapshot()["updated_at"] is not None)
        )
        snapshot = provider.snapshot()
        self.assertGreater(snapshot["level"], 0)
        self.assertEqual(snapshot["scale"], "linear")
        self.assertEqual(len(snapshot["bands"]), 10)

        stopped = provider.stop()
        self.assertFalse(stopped["running"])
        self.assertEqual(stopped["level"], 0.0)
        self.assertTrue(monitor.closed.wait(1))

    def test_windows_uses_pysysaudio_pcm16_stream(self) -> None:
        instances = []

        class Recorder:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.recording = False
                self.stopped = False
                instances.append(self)

            def start_recording(self):
                self.recording = True

            def stream(self, timeout=0.1):
                del timeout
                yield stereo_sine(250)
                while self.recording:
                    time.sleep(0.005)

            def stop_recording(self):
                self.recording = False
                self.stopped = True

        provider = SystemAudioProvider(
            platform_name="win32",
            pysysaudio_module=SimpleNamespace(SystemAudioRecorder=Recorder),
        )
        sources = provider.list_sources()
        self.assertEqual(sources["sources"][0]["id"], "system:default")

        provider.start("system:default")
        self.assertTrue(wait_until(lambda: provider.snapshot()["level"] > 0))
        self.assertEqual(
            instances[0].kwargs,
            {
                "sample_rate": 48_000,
                "channels": 2,
                "format": "bytes",
                "dtype": "int16",
            },
        )
        provider.stop()
        self.assertTrue(instances[0].stopped)

    def test_start_accepts_only_an_enumerated_source_id(self) -> None:
        provider = SystemAudioProvider(
            platform_name="win32",
            pysysaudio_module=SimpleNamespace(SystemAudioRecorder=MagicMock()),
        )
        provider.list_sources()

        with self.assertRaisesRegex(ValueError, "allowlist"):
            provider.start("system:../../microphone")

    def test_missing_optional_backend_is_reported_for_browser_fallback(self) -> None:
        provider = SystemAudioProvider(
            platform_name="linux", soundcard_module=None
        )

        status = provider.list_sources()

        self.assertFalse(status["available"])
        self.assertEqual(status["sources"], [])
        self.assertIn("unavailable", status["error"])


class DesktopAudioBridgeTests(unittest.TestCase):
    def test_bridge_forwards_compact_audio_calls_and_closes_provider(self) -> None:
        provider = SimpleNamespace(
            list_sources=MagicMock(
                return_value={"available": True, "sources": [{"id": "system:default"}]}
            ),
            start=MagicMock(return_value={"running": True}),
            snapshot=MagicMock(
                return_value={
                    "running": True,
                    "level": 0.2,
                    "peak": 0.4,
                    "bands": [0.1],
                }
            ),
            stop=MagicMock(return_value={"running": False}),
            close=MagicMock(),
        )
        api = DesktopApi(
            SimpleNamespace(), platform_name="win32", audio_provider=provider
        )

        self.assertTrue(api.audio_capture_sources()["available"])
        self.assertTrue(api.start_audio_capture("system:default")["running"])
        self.assertEqual(api.audio_snapshot()["level"], 0.2)
        self.assertFalse(api.stop_audio_capture()["running"])
        api._close()

        provider.list_sources.assert_called_once_with()
        provider.start.assert_called_once_with("system:default")
        provider.snapshot.assert_called_once_with()
        provider.stop.assert_called_once_with()
        provider.close.assert_called_once_with()

    def test_bridge_does_not_expose_raw_audio(self) -> None:
        public_methods = {
            name
            for name in dir(DesktopApi)
            if name.startswith("audio_") or name.endswith("audio_capture")
        }
        self.assertEqual(
            public_methods,
            {
                "audio_capture_sources",
                "audio_snapshot",
                "start_audio_capture",
                "stop_audio_capture",
            },
        )

    def test_desktop_session_closes_capture_before_disposing_tray(self) -> None:
        lifecycle = []
        provider = SimpleNamespace(close=lambda: lifecycle.append("audio"))
        tray = SimpleNamespace(
            ready=True,
            available=True,
            close_to_tray=False,
            bind=MagicMock(),
            quit=MagicMock(),
            dispose=lambda: lifecycle.append("tray"),
        )
        window = SimpleNamespace(show=MagicMock(), restore=MagicMock())
        webview = SimpleNamespace(
            settings={},
            create_window=MagicMock(return_value=window),
            start=MagicMock(),
        )
        server = SimpleNamespace(on_quit=None)
        with (
            patch("spade65.desktop.SystemAudioProvider", return_value=provider),
            patch("spade65.desktop.TrayController", return_value=tray),
            patch(
                "spade65.desktop.load_desktop_preferences",
                return_value={"close_to_tray": False},
            ),
            patch("spade65.desktop.sys.stdout", None),
        ):
            run_desktop_session(
                server=server,
                url="http://127.0.0.1:8765/",
                activation=ActivationBridge(),
                webview_module=webview,
                platform_name="linux",
            )

        self.assertEqual(lifecycle, ["audio", "tray"])


if __name__ == "__main__":
    unittest.main()
