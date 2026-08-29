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
effect was restored successfully. Dongle mode, keymap writes, macros, and reset
have not been tested. Firmware update is not implemented because it can brick
the device and no verified recovery procedure exists.

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

| Transport | VID | PID |
|---|---:|---:|
| Wired USB | `0603` | `0351` |
| 2.4 GHz dongle | `0603` | `0356` |

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
names `DeviceId_Set8Bytes` and `DeviceId_Output`. The hardware descriptor must
still confirm these pairs.

## Cross-platform transport

The Windows vendor application uses a native HIDAPI-based add-on. Its wrapper
passes the buffer's first byte as the report ID. This project uses `hidraw` with
the `HIDIOCSFEATURE(length)` ioctl on Linux and `hidapi` on Windows/macOS. Both
backends preserve the report ID as the first byte.

The CLI selects an interface only when all of the following conditions match:

1. VID `0603`.
2. PID `0351` or `0356`.
3. The appropriate usage-page/usage pair.
4. A feature-report ID and report length that match the descriptor.

Windows/macOS read the report descriptor through HIDAPI and then run the same
parser used on Linux. If the descriptor cannot be read, a collection may still
appear in `probe`, but it has no report shape and every write is therefore
rejected. There is no fallback that writes based only on a path or VID/PID.

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
profile, and write path with additional confirmation are implemented. Hardware
validation of remapping still requires comparing a single change against a
capture from the Windows application.

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

When hardware is available, retain:

1. `probe-wired.json`.
2. `probe-dongle.json`.
3. The success or failure of each command together with the wired/dongle mode.
4. If key remapping continues, a USBPcap capture of exactly one changed key—for
   example, `A` to `B`—followed by an immediate restore.

There is no need to begin with a firmware dump. The HID descriptor and a
single-delta capture are far safer and sufficient to validate the configuration
protocol.
