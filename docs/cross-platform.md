# Dukungan lintas platform

## Status

| Platform | Discovery dan write | Aplikasi aktif | Background launcher | Validasi fisik |
|---|---|---|---|---|
| Linux | `hidraw` + sysfs | X11, fallback proses Wayland | systemd user | Ya, USB `0603:0351` |
| Windows | HIDAPI / Win32 HID | Win32 foreground window | Startup `.cmd` | Belum diuji pada mesin Windows |
| macOS | HIDAPI / IOKit | System Events frontmost process | LaunchAgent `.plist` | Belum diuji pada mesin macOS |

GUI, profile compiler, macro, konverter vendor, AP renderer, timeline, dan aturan
keselamatan memakai source yang sama pada seluruh OS. Windows/macOS tidak memakai
`/dev/hidraw` atau sysfs.

Workflow CI menjalankan unit test pada Ubuntu, Windows, dan macOS untuk Python
3.10 serta 3.13. Ini memverifikasi import, compiler, transport simulasi, service,
dan launcher pada OS tersebut; status fisik tetap dipisahkan pada tabel di atas.

## Instalasi

Linux tidak memerlukan package runtime tambahan:

```bash
python -m pip install -e .
```

Windows dan macOS memerlukan HIDAPI 0.14 atau lebih baru agar report descriptor
dapat dibaca sebelum write:

```bash
python -m pip install -e ".[cross-platform]"
python -m spade65 probe
python -m spade65 gui
```

Apabila descriptor suatu collection tidak dapat dibaca, `probe` dapat tetap
menampilkannya tetapi command write menolak collection tersebut. VID/PID saja
tidak pernah cukup untuk melewati validasi.

## Background startup

Buat config service, lalu generator launcher untuk OS yang sedang digunakan:

```bash
spade65ctl service example spade65-service.json
spade65ctl service integration spade65-service.json launcher-output
```

- Linux: salin unit ke `~/.config/systemd/user/`, kemudian enable sebagai user.
- Windows: letakkan `.cmd` di folder Startup pengguna.
- macOS: letakkan `.plist` di `~/Library/LaunchAgents/`, lalu muat dengan
  `launchctl` pada sesi pengguna.

Generator hanya menulis file output yang diminta; tidak mengubah startup OS
secara otomatis. Pada macOS, asosiasi aplikasi dapat memerlukan izin
Automation/Accessibility untuk membaca aplikasi frontmost.

## Data persisten dan data host

Report keymap, macro, efek bawaan/per-key, debounce, dan timer dongle ditujukan
ke konfigurasi internal perangkat seperti software resmi. Setting tersebut tidak
memerlukan background service setelah diterapkan. Profil bernama, asosiasi
aplikasi, AP/streaming animation, dan custom timeline adalah data host; efeknya
memerlukan GUI atau service tetap berjalan.

Persistensi keymap/macro belum diuji melalui power-cycle karena perangkat tidak
menyediakan readback untuk membuat backup kondisi pengguna. Firmware flashing,
bootloader, raw flash, dan arbitrary HID tidak diimplementasikan pada OS mana pun.
