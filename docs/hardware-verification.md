**English** · [Bahasa Indonesia](id/hardware-verification.md)

# Hardware verification

The wired tests were performed on August 29–31, 2026, using the USB Spade65
`0603:0351`. On August 31, the same keyboard's physical 2.4 GHz receiver was
also inspected and enumerated as `0603:0352`.

## Successful tests

- Wired mode enumerated as `0603:0351`. Its configuration interface advertises
  a 620-byte feature report `0x07`, an 8-byte feature report `0x08`, and a
  64-byte output report `0x06`.
- All 20 built-in RGB effect reports completed as 620-byte writes, and their
  visual effects were confirmed on the keyboard. Per-key RGB, streaming RGB,
  the AP wave, and a custom timeline were also confirmed visually.
- Debounce was set to 5 ms. An authenticated GUI RGB action also completed as a
  620-byte write.
- A temporary three-layer keymap and macro were applied and verified through
  physical input (`BXcD`). The default keymap and an empty test macro were then
  restored and verified through physical input (`asd`).
- With explicit user authorization, reset completed as an 8-byte write. A
  read-only probe immediately after reset still found the expected wired
  descriptor, so the keyboard remained operational.
- Application association and the background AP/timeline service completed on
  the wired streaming interface. These host effects do not write firmware,
  flash, or the bootloader.
- A sysfs read returned USB revision `01.00`. This value is not labeled as a
  firmware version.

## Observed 2.4 GHz receiver

PID `0603:0352` is recognized for read-only diagnostics, but it is not a
configuration target. It is also unknown to the original software: `0352`
appears in none of the vendor's support-device tables, in neither its protocol
layer nor its frontend, so no vendor behaviour exists to reproduce for it.

On August 31 the receiver was re-attached with the cable removed and the
keyboard operating over 2.4 GHz, confirmed by live input devices (`JP Spade65
Keyboard`). Even in that state the receiver still enumerates as `0603:0352`,
and its three HID report descriptors, parsed item by item from
`/sys/class/hidraw/*/device/report_descriptor` rather than through this
project's own parser, advertise **no feature reports at all**. The only vendor
usage page present is `0xff55`; `ff02:0001` and `ff03:0001` are absent. For
comparison, the wired interface advertises `ff01`, `ff02`, `ff03` and both
feature reports `0x07` and `0x08`.

So configuration over this receiver is not merely gated, it is impossible:
there is no feature report for a configuration packet to target. Six write
commands were tried against the connected receiver and each refused before
sending anything — `rgb`, `debounce`, `sleep`, `reset` (all `no matching HID
interface for usage ff02:0001` / `ff03:0001`), `stream-rgb` and `profile
apply`. `per-key-rgb` and the background streaming service were not tried.
`probe` and `info` continued to work and reported `unsupported-read-only`.
`0603:0356` has still never appeared on this hardware.

The receiver's three observed HID collections provide an ordinary keyboard
report, report-ID `0x06` input/output collections, and an `008c:0006`
input/output collection. They do **not** provide either configuration shape
required by this project:

- no `ff02:0001` feature report `0x07` with 620 bytes; and
- no `ff03:0001` feature report `0x08` with 8 bytes.

The timer packet is an 8-byte feature report `0x08` sent through the verified
`ff03:0001` collection for the original backend's logical dongle identity
`0603:0356`. Sending it to `0352` would therefore bypass both the verified
identity and descriptor shape. The application rejects that operation instead
of guessing that the receiver protocols are compatible. Merely seeing a
64-byte report `0x06` on `0352` is not sufficient evidence: the wired streaming
protocol also requires a verified short feature activation report, which this
receiver does not advertise.

## Bottom-row layout

The wired unit was inspected with `evtest` on its boot-keyboard input node,
which is the only node that reports modifiers. Pressing the spacebar reported
`MSC_SCAN 0x7002c`; the next key to its right reported nothing at all, because
Fn is resolved inside the firmware and never emits a usage; the key after that
reported `MSC_SCAN 0x700e6`, usage `0xe6`, Right Alt. Left Ctrl reported
`0x700e0` as expected.

So this board's bottom row is `Ctrl Win Alt Space Fn RAlt` plus the arrow
cluster, and it carries no Right Ctrl key. That is a fifth arrangement: the
vendor's own `KeyBoardStyle` data contains five bottom rows and every one of
them places `AltRight` before `Custom_Fnkey`, while this hardware has them the
other way round. The standard layouts now draw `ralt` in the position the
hardware actually uses and no longer draw `rctrl`, which had been placed over
the physical Right Alt. The split layouts are unchanged, because a split
spacebar is a different board and no hardware here contradicts the vendor data
for it.

One matrix anomaly remains unresolved: `rspace` names both slot 92 and slot 94,
and their default usages disagree — slot 92 is `0x00` and slot 94 is `0x2c`.
`BUTTON_TO_SLOT` resolves the name to slot 92 by first match. A board with a
split spacebar would be needed to establish which slot is the real right space,
so the table is left as transcribed rather than corrected on a guess.

## Tests not performed

- Dongle timers were not sent because the observed physical receiver is PID
  `0603:0352` and lacks the verified `ff03:0001` feature-report shape. The
  logical dongle configuration identity `0603:0356` was not detected.

  The timer is dongle-only in the original software as well, so this is not a
  gap in coverage. The vendor backend gates the packet on `BaseInfo.StateID`,
  an index into a two-entry `StateList` whose only records are
  `[0] = 0603:0351 "USB"` and `[1] = 0603:0356 "Dongle"`. Its
  `SetLightOffToDevice` begins with `if (0 == BaseInfo.StateID) return
  callback();`, so the wired identity is skipped before the frame is built; the
  vendor UI additionally renders the light-off and sleep controls only under
  `*ngIf="DeviceService.getCurrentDevice().StateID === 1"`, and the write
  handle itself is resolved as `hid.FindDevice(0xff03, 0x1,
  StateList[StateID].vid, StateList[StateID].pid)`. Three independent gates
  therefore keep opcode `0x0B` off `0603:0351`. Restricting `spade65ctl sleep`
  to `0603:0356` reproduces that behaviour rather than adding a restriction.
  Debounce (`0x09`) and reset (`0x08`) carry no such gate in the original
  backend, which is why they remain available on the wired connection.
- Firmware, bootloader, raw-flash, and arbitrary-HID operations are not
  available in the application.

The timer frame remains covered by unit tests against the report format
recovered from the original backend. A physical timer test requires a dongle
that enumerates as `0603:0356` and exposes the `ff03:0001` configuration
interface; it is not safe to substitute the descriptor-incompatible `0352`
receiver.
