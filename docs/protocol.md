**English** · [Bahasa Indonesia](id/protocol.md)

# Noir Spade65 non-QMK protocol notes

This document summarizes the results of static reverse engineering and staged
hardware validation. Any value not explicitly covered by the validation section
must still be considered **unverified on hardware**.

## Hardware validation

On August 29, 2026, a wired USB `0603:0351` unit named `JP Spade65` validated
the descriptor for the 620-byte main feature report `0x07` and the 8-byte short
report `0x08`. Sending `fixed` RGB (brightness 2, speed 3) returned an ioctl
result of 620, and setting debounce to 5 ms returned an ioctl result of 8. The
per-key RGB opcode `0x07` and one streaming frame (activation followed by five
64-byte output reports) were also sent successfully, after which the `fixed`
effect was restored successfully. All 20 built-in effect reports, per-key RGB,
streaming RGB, AP wave, the custom timeline, a temporary three-layer keymap with
a macro (applied, confirmed by physical key input, then restored), and a
configuration reset have since been executed successfully on the same wired
unit. The dongle timers remain untested because `0603:0356` has never enumerated
on this hardware; the physical 2.4 GHz receiver enumerates as `0603:0352` and
its descriptor advertises no feature reports, so it cannot be configured at all.
The individual keymap, macro, lighting, and debounce reports have physical
acceptance evidence, but visual lighting preservation after the newly completed
official-style profile transaction has not yet been confirmed. Report byte
counts and automated ordering tests are not treated as that visual proof.
Firmware update is not implemented because it can brick the device and no
verified recovery procedure exists.

## Analysis sources

- Installer: `Spade65_SETUP_20240403.exe`
- SHA-256: `73684f103ef792994141880288daf4fa51b72b3b828ed9849b089da43386b91f`
- Installer format: Inno Setup 6.1.0
- Application: Electron 4.0.0, internal application version 1.0.0
- Main archive: `resources/app.asar`
- Protocol router in the vendor database: `JupengSeries`

The installer and extracted files are not committed to Git. They are listed in
`.gitignore` to prevent redistribution of vendor artifacts.

## Device identity

| Transport | VID | PID | Configuration |
|---|---:|---:|---|
| Wired USB | `0603` | `0351` | descriptor-gated |
| 2.4 GHz receiver | `0603` | `0352` | unsupported-read-only |
| Vendor "Dongle" state | `0603` | `0356` | descriptor-gated |

`0352` is the identity the physical receiver enumerates as. The only vendor
usage page it exposes is `ff55`, and its descriptor advertises zero feature
reports — `ff02:0001` and `ff03:0001` are absent — so it is discoverable for
diagnostics but is never a write target. `0352` appears in none of the original
software's device tables. `0356` is the vendor's logical dongle state and has
never been observed on this hardware.

The vendor database defines:

| Function | Usage page | Usage |
|---|---:|---:|
| Get/main input | `ff01` | `0001` |
| Set/main feature | `ff02` | `0001` |

The `InitialDevice` code also searches for:

| Inferred function | Usage page | Usage |
|---|---:|---:|
| Short feature report | `ff03` | `0001` |
| RGB streaming output | `ff55` | `0202` |

These inferences come from the `FindDevice()` parameters and the internal handle
names `DeviceId_Set8Bytes` and `DeviceId_Output`. The wired
`0603:0351` descriptor confirms all four pairs, together with feature report
`0x07` at 620 bytes, feature report `0x08` at 8 bytes, and output report `0x06`
at 64 bytes.

## Cross-platform transport

The Windows vendor application uses a native HIDAPI-based add-on. Its wrapper
passes the buffer's first byte as the report ID. This project uses `hidraw` with
the `HIDIOCSFEATURE(length)` ioctl on Linux and `hidapi` on Windows/macOS. Both
backends preserve the report ID as the first byte.

The CLI discovers any interface with VID `0603` and PID `0351`, `0352`, or
`0356`, and reports each one's `configuration_status`. It writes to an interface
only when all of the following conditions match:

1. VID `0603`.
2. PID `0351` or `0356`; `0352` is read-only and is never a write target.
3. The appropriate usage-page/usage pair.
4. A feature-report ID and report length that match the descriptor.

Windows/macOS read the report descriptor through HIDAPI and then run the same
parser used on Linux. If the descriptor cannot be read, a collection may still
appear in `probe`, but it has no report shape and every write is therefore
rejected. There is no fallback that writes based only on a path or VID/PID.

A keymap apply requires both feature-report shapes. If one OS collection
advertises both, it is reused. Otherwise the short-report companion must have
the same VID/PID and serial/unique identity as the selected main collection,
including both identities being empty. A missing companion or more than one
possible match is an error before the first keymap report is sent. Both handles
are opened before that first write; the main handle remains open across all
main reports and the short report uses its own open handle.

## Main report ID 0x07

The vendor buffer is `0x26c`, or 620 bytes, including the report ID.

### Built-in RGB effects — opcode 0x02

| Offset | Length | Meaning |
|---:|---:|---|
| `0x00` | 1 | Report ID `07` |
| `0x01` | 1 | Opcode `02` |
| `0x02` | 1 | Fixed value `01` |
| `0x03..0x08` | 6 | Zero |
| `0x09` | 1 | Effect ID `00..13` |
| `0x0a` | 1 | Brightness `0..4` |
| `0x0b` | 1 | Speed `1..5` |
| `0x0c..0x1f` | 20 | Per-effect color indices; `07` selects multicolor |
| remaining bytes | | Zero |

Effect IDs:

| ID | CLI name | Vendor internal name |
|---:|---|---|
| `00` | `neon-stream` | `Neon_stream` |
| `01` | `fixed` | `Fixed_on` |
| `02` | `breathe` | `Respire` |
| `03` | `ripples-shining` | `Ripples_shining` |
| `04` | `rainbow-wheel` | `Rainbow_wheel` |
| `05` | `ripple-band-up-down` | `RippleBandUpDown` |
| `06` | `reaction` | `Reaction` |
| `07` | `two-block` | `TwoBlock` |
| `08` | `random-color` | `RandomColor` |
| `09` | `double-wave` | `DoubleWave` |
| `0a` | `retro-snake` | `RetroSnake` |
| `0b` | `double-spiral` | `DoubleSpiral` |
| `0c` | `ripple-band` | `RippleBand` |
| `0d` | `kamehameha` | `Kamehemeha` (vendor spelling) |
| `0e` | `wave-90` | `Wave90` |
| `0f` | `intersect` | `Intersect` |
| `10` | `shadow-disappear` | `Shadow_disappear` |
| `11` | `follow` | `Follow` |
| `12` | `snake-up-down` | `SnakeUpDown` |
| `13` | `custom` | `Customize` |

### Keymap — opcode 0x03

The recovered initial structure is:

| Offset | Meaning |
|---:|---|
| `0x00` | Report ID `07` |
| `0x01` | Opcode `03` |
| `0x02` | `fnModeindex + 1` |
| `0x08...` | Three layers, two bytes per matrix slot |

The vendor code builds data for the normal layer and two Fn layers. The wired
`0603:0351` matrix has 102 internal slots (`0x66`), while the UI profile has 70
logical keys. Empty slots are essential to preserving matrix order.

Each slot uses two bytes for modifier/status and HID usage. A simple assignment
adds `0x80` to the first byte. Macros use special keycodes in the `f0...f9`
range and are sent separately. The 102-slot mapping, three-layer builder, JSON
profile, and write path with additional confirmation are implemented, and a
temporary three-layer keymap with a bound macro was written to the wired
`0603:0351` unit, confirmed by physical key input, and then restored.

### Macro — opcode 0x05

The recovered header is:

- Byte 0: `07`
- Byte 1: `05`
- Byte 2: `01`
- Byte 3: macro index; at most 10 macros are sent in one UI operation
- Bytes 8..263: at most 256 bytes of macro data

Each macro entry uses three bytes: delay high/key-down status, delay low, and HID
keycode. The vendor software enforces a minimum delay of 20 ms.

The implementation accepts at most 84 events per macro so that the two-byte
repeat header and every triplet remain within the 256-byte payload. The keymap
can reference at most ten macros as usages `f0` through `f9`.

### Profile apply / `SetKeyMatrix` transaction

Static analysis of the original backend shows that applying a keymap is an
ordered transaction across the main and short feature-report handles:

| Order | Report | Delay after success |
|---:|---|---:|
| 1 | Main `0x07`, opcode `0x03`: all three keymap layers | 100 ms |
| 2 | Main `0x07`, opcode `0x05`: each macro actually referenced by the keymap | 200 ms each |
| 3 | Main `0x07`, opcode `0x02`: host-cached current lighting effect | 100 ms |
| 4 | Main `0x07`, opcode `0x07`: exact per-key palette, custom lighting only | 50 ms |
| 5 | Short `0x08`, opcode `0x09`: profile debounce | 10 ms |

Spade65 follows this order for every profile operation that includes the
`keymap` scope. The GUI supplies its currently selected lighting and displayed
debounce; CLI and background-service applies use the values cached in the
profile. The full report set and both descriptors are validated before opcode
`0x03` is sent. Main-report failures retain best-effort lighting recovery. A
failure of the final short report is surfaced as a partial transaction because
the keymap and lighting may already have succeeded; the previous cached
lighting is replayed best-effort before the error is returned.

The original backend initializes a fresh profile with debounce 1 ms. Spade65
stores `settings.debounce_ms` per profile and uses 5 ms for its own templates
and profiles that predate the field, preserving the project's established
behavior. This compatibility fallback must not be described as the vendor's
fresh-profile default.

`SetLightOffToDevice` returns without sending on the wired state. Consequently,
the keymap transaction above ends after debounce and never appends a wired
light-off/hibernate timer.

### Custom/per-key RGB — opcode 0x07

- Byte 0: `07`
- Byte 1: `07`
- Starting at byte 8: R, G, B triplets in internal matrix order.

The mapping from 70 UI keys to 102 matrix slots was recovered from the vendor
code and validated specifically for device identity `0603:0351`.

That mapping is now expressed as original interoperability data in
`spade65/keymap.py`. The CLI accepts colors by UI key name and places each
triplet in the corresponding matrix slot.

## Short report ID 0x08

The vendor application calls this interface `DeviceId_Set8Bytes`. The tool
expects an 8-byte feature report including the report ID.

| Byte 1/opcode | Payload | Function |
|---:|---|---|
| `08` | empty | Reset settings |
| `09` | byte 2 = milliseconds | Debounce |
| `0b` | byte 2 = light-off index + 1; byte 3 = hibernate index + 1 | Dongle-mode timers |

The timer choices come directly from the default vendor profile:

- Light-off: 1, 2, 5, 10, 15, 20, 25, 30 minutes.
- Hibernate: 3, 5, 10, 15, 20, 25, 30, 60 minutes.

The vendor code skips timer transmission when the device is in wired USB state.
The project therefore restricts the `sleep` command to dongle PID `0356` on
every operating system.

## RGB streaming output

For real-time synchronization, the application first sends the short feature
report `[08, 06, ...]`. It then sends five 64-byte output reports through usage
`ff55:0202`:

- Byte 0: report ID `06`.
- Byte 1: chunk number 1 through 5.
- Bytes 2..63: 62 bytes of RGB data.

The streaming builder and transport are implemented. On USB unit `0603:0351`,
activation and all five output reports were sent successfully, after which the
`fixed` effect was restored successfully. The GUI uses this path for a single
frame, ten AP-mode animation patterns, and audio-reactive modulation. Streaming
remains restricted to the USB PID and a 64-byte output report `0x06` confirmed
by the descriptor.

## Data still required

Retain from each hardware session:

1. `probe-wired.json` for `0603:0351`.
2. `probe-receiver.json` for `0603:0352`. No dongle probe exists to capture,
   because `0603:0356` has never enumerated on this hardware.
3. The success or failure of each command together with the wired/dongle mode.
4. If the keymap is written again, the profile that was applied and the profile
   used to restore it, so the change can be reversed without a readback.

There is no need to begin with a firmware dump. The HID descriptor and a
single-delta capture are far safer and sufficient to validate the configuration
protocol.
