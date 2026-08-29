**English** · [Bahasa Indonesia](id/hardware-verification.md)

# Hardware verification

The latest tests were performed on August 29, 2026, using the USB Spade65
`0603:0351` available on the development machine.

## Successful tests

- Three interfaces were discovered: `/dev/hidraw3`, `/dev/hidraw4`, and
  `/dev/hidraw5`.
- The configuration interface advertises a 620-byte feature report `0x07`, an
  8-byte feature report `0x08`, and a 64-byte output report `0x06`.
- One custom-timeline frame was sent successfully to `/dev/hidraw4` through a
  background-service command. This path only activates streaming and sends five
  RGB output reports; it does not write flash, the keymap, macros, or the
  bootloader.
- A sysfs read returned USB revision `01.00`. This value is not labeled as a
  firmware version.

## Tests not performed

- The keymap and macros were not written because the device does not provide
  configuration readback from which to back up its current state. Testing these
  operations would overwrite the user's three layers and macros without a
  guaranteed restore path.
- Reset was not sent because it erases configuration.
- Dongle timers were not sent because dongle PID `0603:0356` was not detected.
- Firmware, bootloader, raw-flash, and arbitrary-HID operations are not
  available in the application.

The keymap, macro, reset, and timer frames are still covered by unit tests
against the report formats recovered from the original backend. Physical tests
will only be safe once a known backup profile or the appropriate dongle is
available.
