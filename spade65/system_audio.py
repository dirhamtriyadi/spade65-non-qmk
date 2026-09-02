"""Safe, host-only system-audio capture for live RGB effects.

The capture backends are intentionally lazy optional dependencies.  Only compact
level and spectrum measurements leave this module; raw audio is never exposed to
the WebView bridge or written to disk.
"""

from __future__ import annotations

import importlib
import math
import sys
import threading
import time
from array import array
from types import ModuleType
from typing import Any, Iterable, Sequence


SAMPLE_RATE = 48_000
CHANNELS = 2
ANALYSIS_FRAMES = 2_048
BAND_FREQUENCIES = (63, 125, 250, 500, 1_000, 2_000, 4_000, 8_000, 12_000, 16_000)
MAX_SOURCE_ID_LENGTH = 128
_UNSET = object()


class AudioCaptureError(RuntimeError):
    """Raised when a requested native system-audio source cannot be used."""


def _clean_text(value: object, fallback: str, *, maximum: int = 160) -> str:
    text = " ".join(
        str(value or "").replace("\x00", "").split()
    ).strip()
    return (text or fallback)[:maximum]


def _error_text(error: BaseException) -> str:
    return _clean_text(error, "System audio capture failed.", maximum=240)


class PCMAnalyzer:
    """Calculate normalized level and logarithmic spectrum data without NumPy."""

    def __init__(
        self,
        *,
        band_frequencies: Sequence[int] = BAND_FREQUENCIES,
        maximum_frames: int = ANALYSIS_FRAMES,
    ) -> None:
        if maximum_frames < 32:
            raise ValueError("maximum_frames must be at least 32")
        if not band_frequencies or any(
            frequency <= 0 for frequency in band_frequencies
        ):
            raise ValueError("band frequencies must be positive")
        self.band_frequencies = tuple(int(value) for value in band_frequencies)
        self.maximum_frames = int(maximum_frames)

    def analyze_pcm16(
        self,
        payload: bytes | bytearray | memoryview,
        *,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
    ) -> dict[str, object]:
        """Analyze little-endian, interleaved signed 16-bit PCM bytes."""

        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("PCM16 payload must be bytes-like")
        raw = bytes(payload)
        raw = raw[: len(raw) - (len(raw) % 2)]
        values = array("h")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        return self.analyze(
            values,
            sample_rate=sample_rate,
            channels=channels,
            scale=32_768.0,
        )

    def analyze(
        self,
        samples: object,
        *,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        scale: float = 1.0,
    ) -> dict[str, object]:
        """Analyze flat or frame-shaped numeric samples.

        ``soundcard`` returns a two-dimensional NumPy array of normalized floats,
        while the Windows/macOS backend is converted from PCM16 bytes.  Accepting
        both shapes here keeps native dependencies outside the analyzer.
        """

        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ValueError("sample_rate must be a positive integer")
        if not isinstance(channels, int) or channels <= 0:
            raise ValueError("channels must be a positive integer")
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("scale must be positive")

        mono = self._mono_samples(samples, channels=channels, scale=scale)
        if len(mono) > self.maximum_frames:
            mono = mono[-self.maximum_frames :]
        if not mono:
            return self._empty_result()

        squared = sum(value * value for value in mono)
        level = min(1.0, math.sqrt(squared / len(mono)))
        peak = min(1.0, max(abs(value) for value in mono))
        bands = self._spectrum(mono, sample_rate)
        return {
            "level": round(level, 6),
            "peak": round(peak, 6),
            "bands": [round(value, 6) for value in bands],
        }

    def _empty_result(self) -> dict[str, object]:
        return {
            "level": 0.0,
            "peak": 0.0,
            "bands": [0.0] * len(self.band_frequencies),
        }

    @staticmethod
    def _as_float(value: object, scale: float) -> float | None:
        try:
            numeric = float(value) / scale
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(numeric):
            return None
        return max(-1.0, min(1.0, numeric))

    def _mono_samples(
        self, samples: object, *, channels: int, scale: float
    ) -> list[float]:
        if isinstance(samples, (bytes, bytearray, memoryview)):
            raise TypeError("use analyze_pcm16 for bytes-like samples")
        try:
            iterator = iter(samples)  # type: ignore[arg-type]
        except TypeError as error:
            raise TypeError("samples must be iterable") from error

        values = list(iterator)
        if not values:
            return []

        first = values[0]
        frame_shaped = not isinstance(first, (str, bytes, bytearray)) and hasattr(
            first, "__iter__"
        )
        if frame_shaped:
            mono: list[float] = []
            for frame in values:
                try:
                    frame_values = list(iter(frame))
                except TypeError:
                    continue
                normalized = [
                    converted
                    for item in frame_values
                    if (converted := self._as_float(item, scale)) is not None
                ]
                if normalized:
                    # Preserve the signed sample from the strongest channel.
                    # Averaging can erase legitimate stereo material when the
                    # left and right channels happen to be phase-opposed.
                    mono.append(max(normalized, key=abs))
            return mono

        normalized = [
            converted
            for item in values
            if (converted := self._as_float(item, scale)) is not None
        ]
        if channels == 1:
            return normalized
        mono = []
        for offset in range(0, len(normalized) - channels + 1, channels):
            frame = normalized[offset : offset + channels]
            mono.append(max(frame, key=abs))
        return mono

    def _spectrum(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        """Return peak FFT magnitudes in perceptually spaced frequency bands."""

        if len(samples) < 2:
            return [0.0] * len(self.band_frequencies)
        size = 1 << (len(samples).bit_length() - 1)
        selected = samples[-size:]
        window_sum = 0.0
        spectrum: list[complex] = []
        for index, sample in enumerate(selected):
            window = (
                1.0
                if size == 1
                else 0.5 - 0.5 * math.cos(2 * math.pi * index / (size - 1))
            )
            window_sum += window
            spectrum.append(complex(sample * window, 0.0))

        # In-place radix-2 Cooley-Tukey transform.  Audio capture is bounded to
        # 2048 frames, keeping this inexpensive while avoiding a NumPy runtime
        # dependency on Windows and macOS.
        target = 0
        for index in range(1, size):
            bit = size >> 1
            while target & bit:
                target ^= bit
                bit >>= 1
            target ^= bit
            if index < target:
                spectrum[index], spectrum[target] = spectrum[target], spectrum[index]
        length = 2
        while length <= size:
            angle = -2 * math.pi / length
            root = complex(math.cos(angle), math.sin(angle))
            half = length // 2
            for offset in range(0, size, length):
                factor = complex(1.0, 0.0)
                for index in range(offset, offset + half):
                    even = spectrum[index]
                    odd = factor * spectrum[index + half]
                    spectrum[index] = even + odd
                    spectrum[index + half] = even - odd
                    factor *= root
            length <<= 1

        if window_sum <= 0:
            return [0.0] * len(self.band_frequencies)
        bin_magnitudes = [
            min(1.0, 2 * abs(value) / window_sum)
            for value in spectrum[: size // 2 + 1]
        ]
        nyquist = sample_rate / 2
        magnitudes = []
        frequencies = self.band_frequencies
        for index, frequency in enumerate(frequencies):
            if frequency >= nyquist:
                magnitudes.append(0.0)
                continue
            lower = (
                max(20.0, frequency / math.sqrt(frequencies[1] / frequency))
                if index == 0 and len(frequencies) > 1
                else (
                    math.sqrt(frequencies[index - 1] * frequency)
                    if index > 0
                    else 20.0
                )
            )
            upper = (
                math.sqrt(frequency * frequencies[index + 1])
                if index + 1 < len(frequencies)
                else min(nyquist, frequency * 1.5)
            )
            first_bin = max(1, math.ceil(lower * size / sample_rate))
            final_bin = min(
                len(bin_magnitudes), math.ceil(upper * size / sample_rate)
            )
            magnitudes.append(
                max(bin_magnitudes[first_bin:final_bin], default=0.0)
            )
        return magnitudes


class SystemAudioProvider:
    """Thread-safe adapter for output-loopback capture on supported desktops."""

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        soundcard_module: ModuleType | object = _UNSET,
        pysysaudio_module: ModuleType | object = _UNSET,
        analyzer: PCMAnalyzer | None = None,
    ) -> None:
        self._platform = platform_name or sys.platform
        self._soundcard_module = soundcard_module
        self._pysysaudio_module = pysysaudio_module
        self._analyzer = analyzer or PCMAnalyzer()
        self._control_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._source_handles: dict[str, object] = {}
        self._source_payloads: list[dict[str, object]] = []
        self._token = 0
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._native_stop: Any = None
        self._snapshot = self._new_snapshot()

    def _new_snapshot(self) -> dict[str, object]:
        return {
            "running": False,
            "source_id": None,
            "backend": self._backend_name(),
            "scale": "linear",
            "level": 0.0,
            "peak": 0.0,
            "bands": [0.0] * len(self._analyzer.band_frequencies),
            "band_frequencies": list(self._analyzer.band_frequencies),
            "sample_rate": SAMPLE_RATE,
            "updated_at": None,
            "error": None,
        }

    def _backend_name(self) -> str | None:
        if self._platform.startswith("linux"):
            return "pipewire-pulse-monitor"
        if self._platform in {"win32", "windows"}:
            return "wasapi-loopback"
        if self._platform == "darwin":
            return "coreaudio-system-output"
        return None

    @staticmethod
    def _load_optional(name: str, configured: object) -> ModuleType | object:
        if configured is _UNSET:
            return importlib.import_module(name)
        if configured is None:
            raise ImportError(f"optional dependency {name} is unavailable")
        return configured

    def list_sources(self) -> dict[str, object]:
        with self._control_lock:
            try:
                if self._platform.startswith("linux"):
                    sources = self._linux_sources()
                elif self._platform in {"win32", "windows", "darwin"}:
                    sources = self._pysysaudio_sources()
                else:
                    raise AudioCaptureError(
                        f"System audio capture is unsupported on {self._platform}."
                    )
            except Exception as error:
                self._source_handles = {}
                self._source_payloads = []
                return {
                    "available": False,
                    "backend": self._backend_name(),
                    "sources": [],
                    "error": _error_text(error),
                }
            self._source_payloads = sources
            return {
                "available": bool(sources),
                "backend": self._backend_name(),
                "sources": [dict(source) for source in sources],
                "error": None if sources else "No system-output source is available.",
            }

    @staticmethod
    def _device_identity(device: object) -> str:
        identifier = getattr(device, "id", None)
        if identifier is None:
            identifier = getattr(device, "name", None)
        return str(identifier or "")

    def _linux_sources(self) -> list[dict[str, object]]:
        soundcard = self._load_optional("soundcard", self._soundcard_module)
        all_microphones = getattr(soundcard, "all_microphones", None)
        if not callable(all_microphones):
            raise AudioCaptureError("The SoundCard loopback backend is incomplete.")

        ordinary: Iterable[object]
        try:
            ordinary = all_microphones(include_loopback=False)
            ordinary_ids = {
                self._device_identity(device) for device in ordinary
            }
            comparison_available = True
        except Exception:
            ordinary_ids = set()
            comparison_available = False
        devices = list(all_microphones(include_loopback=True))
        candidates = []
        for device in devices:
            identity = self._device_identity(device)
            text = f"{identity} {getattr(device, 'name', '')}".casefold()
            explicit = bool(getattr(device, "isloopback", False))
            named_monitor = "monitor" in text or "loopback" in text
            added_by_loopback = comparison_available and identity not in ordinary_ids
            if explicit or named_monitor or added_by_loopback:
                candidates.append(device)

        default_speaker = None
        default_speaker_getter = getattr(soundcard, "default_speaker", None)
        if callable(default_speaker_getter):
            try:
                default_speaker = default_speaker_getter()
            except Exception:
                default_speaker = None
        speaker_identity = (
            self._device_identity(default_speaker) if default_speaker else ""
        )
        speaker_name = str(getattr(default_speaker, "name", "") or "").casefold()

        def default_rank(device: object) -> int:
            identity = self._device_identity(device)
            name = str(getattr(device, "name", "") or "").casefold()
            matches = bool(
                speaker_identity
                and (identity == speaker_identity or speaker_identity in identity)
            ) or bool(speaker_name and speaker_name in name)
            return 0 if matches else 1

        candidates.sort(
            key=lambda device: (
                default_rank(device),
                str(getattr(device, "name", "")),
            )
        )
        self._source_handles = {}
        sources = []
        seen = set()
        for index, device in enumerate(candidates):
            identity = self._device_identity(device)
            if identity in seen:
                continue
            seen.add(identity)
            source_id = f"system:linux:{index}"
            self._source_handles[source_id] = device
            sources.append(
                {
                    "id": source_id,
                    "name": _clean_text(
                        getattr(device, "name", None), "System output monitor"
                    ),
                    "kind": "system-output",
                    "default": default_rank(device) == 0,
                }
            )
        if sources and not any(bool(source["default"]) for source in sources):
            sources[0]["default"] = True
        return sources

    def _pysysaudio_sources(self) -> list[dict[str, object]]:
        module = self._load_optional("pysysaudio", self._pysysaudio_module)
        if not callable(getattr(module, "SystemAudioRecorder", None)):
            raise AudioCaptureError("The native system-audio backend is incomplete.")
        source_id = "system:default"
        self._source_handles = {source_id: module}
        if self._platform == "darwin":
            name = "Default system output (CoreAudio)"
        else:
            name = "Default system output (WASAPI loopback)"
        return [
            {
                "id": source_id,
                "name": name,
                "kind": "system-output",
                "default": True,
            }
        ]

    def start(self, source_id: object) -> dict[str, object]:
        if (
            not isinstance(source_id, str)
            or not source_id
            or len(source_id) > MAX_SOURCE_ID_LENGTH
        ):
            raise ValueError("audio source ID must be a non-empty bounded string")
        with self._control_lock:
            self._stop_unlocked()
            if source_id not in self._source_handles:
                status = self.list_sources()
                if not status["available"]:
                    raise AudioCaptureError(
                        str(status.get("error") or "No audio source is available.")
                    )
            source = self._source_handles.get(source_id)
            if source is None:
                raise ValueError("audio source ID is not in the enumerated allowlist")

            self._token += 1
            token = self._token
            stop_event = threading.Event()
            with self._state_lock:
                self._snapshot = self._new_snapshot()
                self._snapshot.update({"running": True, "source_id": source_id})
            native_stop = None
            try:
                if self._platform.startswith("linux"):
                    target = self._linux_capture_loop
                    arguments = (source, source_id, token, stop_event)
                    native_stop = None
                else:
                    recorder_class = getattr(source, "SystemAudioRecorder")
                    recorder = recorder_class(
                        sample_rate=SAMPLE_RATE,
                        channels=CHANNELS,
                        format="bytes",
                        dtype="int16",
                    )
                    recorder.start_recording()
                    target = self._pysysaudio_capture_loop
                    arguments = (recorder, source_id, token, stop_event)
                    native_stop = recorder.stop_recording
                thread = threading.Thread(
                    target=target,
                    args=arguments,
                    name="spade65-system-audio",
                    daemon=True,
                )
                self._stop_event = stop_event
                self._native_stop = native_stop
                self._thread = thread
                thread.start()
            except Exception as error:
                stop_event.set()
                if callable(native_stop):
                    try:
                        native_stop()
                    except Exception:
                        pass
                self._stop_event = None
                self._native_stop = None
                self._thread = None
                with self._state_lock:
                    self._snapshot.update(
                        {"running": False, "error": _error_text(error)}
                    )
                raise AudioCaptureError(_error_text(error)) from error
            return self.snapshot()

    def _publish(
        self, source_id: str, token: int, measurement: dict[str, object]
    ) -> None:
        with self._state_lock:
            if token != self._token or not self._snapshot["running"]:
                return
            self._snapshot.update(measurement)
            self._snapshot.update(
                {
                    "source_id": source_id,
                    "updated_at": round(time.time(), 3),
                    "error": None,
                }
            )

    def _capture_failed(self, token: int, error: BaseException) -> None:
        with self._state_lock:
            if token != self._token or not self._snapshot["running"]:
                return
            self._snapshot.update(
                {"running": False, "error": _error_text(error)}
            )

    def _linux_capture_loop(
        self,
        device: object,
        source_id: str,
        token: int,
        stop_event: threading.Event,
    ) -> None:
        context = None
        try:
            context = device.recorder(
                samplerate=SAMPLE_RATE,
                # Capture the monitor's native channels. PCMAnalyzer chooses
                # the strongest signed sample per frame, so phase-opposed
                # stereo cannot disappear in a server-side mono mix.
                blocksize=ANALYSIS_FRAMES,
            )
            recorder = context.__enter__() if hasattr(context, "__enter__") else context
            while not stop_event.is_set():
                samples = recorder.record(numframes=ANALYSIS_FRAMES)
                if stop_event.is_set():
                    break
                shape = getattr(samples, "shape", ())
                channels = int(shape[1]) if len(shape) > 1 and shape[1] else CHANNELS
                measurement = self._analyzer.analyze(
                    samples, sample_rate=SAMPLE_RATE, channels=channels
                )
                self._publish(source_id, token, measurement)
        except Exception as error:
            if not stop_event.is_set():
                self._capture_failed(token, error)
        finally:
            if context is not None and hasattr(context, "__exit__"):
                try:
                    context.__exit__(None, None, None)
                except Exception as error:
                    if not stop_event.is_set():
                        self._capture_failed(token, error)

    def _pysysaudio_capture_loop(
        self,
        recorder: object,
        source_id: str,
        token: int,
        stop_event: threading.Event,
    ) -> None:
        window = bytearray()
        window_bytes = ANALYSIS_FRAMES * CHANNELS * 2
        try:
            for payload in recorder.stream(timeout=0.1):
                if stop_event.is_set():
                    break
                if not isinstance(payload, (bytes, bytearray, memoryview)):
                    raise AudioCaptureError(
                        "The native audio backend returned an invalid PCM frame."
                    )
                window.extend(payload)
                if len(window) < window_bytes:
                    continue
                if len(window) > window_bytes:
                    del window[:-window_bytes]
                measurement = self._analyzer.analyze_pcm16(
                    window, sample_rate=SAMPLE_RATE, channels=CHANNELS
                )
                self._publish(source_id, token, measurement)
            if not stop_event.is_set():
                self._capture_failed(
                    token, AudioCaptureError("System audio capture ended unexpectedly.")
                )
        except Exception as error:
            if not stop_event.is_set():
                self._capture_failed(token, error)

    def snapshot(self) -> dict[str, object]:
        with self._state_lock:
            result = dict(self._snapshot)
            result["bands"] = list(self._snapshot["bands"])  # type: ignore[arg-type]
            result["band_frequencies"] = list(
                self._snapshot["band_frequencies"]  # type: ignore[arg-type]
            )
            return result

    def stop(self) -> dict[str, object]:
        with self._control_lock:
            return self._stop_unlocked()

    def _stop_unlocked(self) -> dict[str, object]:
        stop_event = self._stop_event
        thread = self._thread
        native_stop = self._native_stop
        self._stop_event = None
        self._thread = None
        self._native_stop = None
        self._token += 1
        if stop_event is not None:
            stop_event.set()
        if callable(native_stop):
            try:
                native_stop()
            except Exception:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self._state_lock:
            self._snapshot = self._new_snapshot()
        return self.snapshot()

    def close(self) -> None:
        self.stop()


__all__ = [
    "ANALYSIS_FRAMES",
    "AudioCaptureError",
    "BAND_FREQUENCIES",
    "CHANNELS",
    "PCMAnalyzer",
    "SAMPLE_RATE",
    "SystemAudioProvider",
]
