**English** · [Bahasa Indonesia](id/parity.md)

# Original Spade65 software parity audit

This audit is based on a static extraction of `Spade65_SETUP_20240403.exe`, with
particular attention to `app.component.js`, `APModeModule.js`, `SupportData.js`,
`KeyBoardStyle.js`, and the `JupengSeries.deobfuscated.js` device backend. The
term **complete** below means every active Spade65 configuration function that
can be reproduced with the verified protocol, not every piece of generic code
bundled with the vendor application.

## Active device pages

The original software's `setPageData` enables only four areas for this device:

| Original area | Project implementation |
|---|---|
| Keyboard settings | Normal/FN1/FN2 editor, four physical layouts, assignments, shortcuts, macro binding, group disabling, Win Lock, WASD/arrow swap, local profiles, and import/export |
| Lighting setting / AP mode | Ten modes, up to ten layers, layer show/hide, key ranges, palettes, opacity, speed, bandwidth, angle, number, gap, fire, effect center, direction, bump, bidirectional, gradient, and audio-reactive controls |
| Built-in effects | All 20 firmware effect IDs, brightness, speed, palette index, multicolor, and custom per-key color |
| Macro settings | Up to ten device macros, 84 events per macro, delay, key-down/up, repeat, rename, keyboard recording, deletion, and key binding |

The vendor assignment list contains 132 entries representing 130 unique usages.
The project exposes every unique usage plus `disabled`: keyboard, numpad, media,
browser/system, mouse, profile next/previous, FN/FN2, copy/paste, and
modifier-based shortcuts.

Profiles in the original software are stored on the host. The backend selects a
profile and then writes the same keymap frame to the device; the profile number
is not serialized into the keymap report. The project's saved profiles and
import/export therefore provide equivalent behavior without inventing a new
profile opcode.

## Bundled code that is not an active Spade65 feature

Several components exist in the generic bundle but are not active device pages:

- `RELATEDPROGRAM` is a Windows host integration. The project now provides an
  opt-in, cross-platform equivalent through the background service on Linux,
  Windows, and macOS without copying the vendor executable integration.
- The `Custom Effect` timeline is not listed among the active Spade65 pages, but
  a safe local-streaming equivalent is now available for up to 200 frames.
- The polling-rate UI is commented out, and `reportRateIndex` is never
  serialized by the Jupeng backend.
- The UI model stores long/instant-press values, but Jupeng's `KeyAssigntoData`
  reads only the normal assignment (`keyAssignType[2]`). Displaying those
  controls would be misleading because the device never receives them.
- Login, telemetry, the application updater, and update checks are not keyboard
  configuration functions.

## Safety boundary

The firmware updater, bootloader, raw flash, and arbitrary HID packets
deliberately have no endpoint or packet builder. Reset requires typed
confirmation; overwriting the keymap requires two confirmations; and every
feature write must match the report-descriptor size. These exclusions are safety
decisions, not unfinished features.

## Hardware-test status

Descriptor detection, all 20 built-in RGB effects, per-key RGB, streaming/AP
mode, the custom timeline, the background service, debounce, keymap/macros, and
reset have been validated over USB on `0603:0351`; the keymap and macro test was
applied, confirmed by physical key input, and then restored, and the keyboard
re-enumerated correctly after the reset. Only the dongle timers remain
unexecuted on hardware, and the reason is known rather than incidental: the
original backend returns from `SetLightOffToDevice` when `BaseInfo.StateID` is
the wired state and resolves the write handle from `StateList[1]`, so the frame
is only ever addressed to `0603:0356`. That identity has never enumerated here.
The physical 2.4 GHz receiver enumerates as `0603:0352`, and its report
descriptors advertise no feature reports at all, so configuration over the
receiver is impossible rather than merely refused.
