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

Tag rilis `vMAJOR.MINOR.PATCH` juga menjalankan build native per OS dan, hanya
jika semuanya berhasil, memublikasikan:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Paket tersebut sudah berisi runtime aplikasi; pengguna tidak perlu clone
repository atau menjalankan Python. Detail pipeline dan cara membuat tag ada di
[`releasing.md`](releasing.md).

## Instalasi

### Paket desktop

Unduh asset yang sesuai dari GitHub Releases.

- Windows x64: ekstrak ZIP sepenuhnya, lalu jalankan `Spade65.exe` untuk GUI.
  Gunakan `Spade65CLI.exe` dari terminal untuk command CLI beserta output/error
  console yang terlihat, misalnya `Spade65CLI.exe probe`.
- Linux x86_64: beri izin eksekusi dengan
  `chmod +x Spade65-Linux-x86_64.AppImage`, lalu jalankan file tersebut. Jika
  FUSE tidak tersedia, gunakan
  `APPIMAGE_EXTRACT_AND_RUN=1 ./Spade65-Linux-x86_64.AppImage`.
- macOS Intel/Apple Silicon: buka DMG, lalu salin `Spade65.app` ke
  `Applications`. Bundle universal diperiksa agar native binary-nya memiliki
  slice `x86_64` dan `arm64`.

Tanpa argumen, aplikasi membuka GUI lokal di `http://127.0.0.1:8765/`. Jika GUI
sudah berjalan, peluncuran kedua memverifikasi marker sesi Spade65 lalu membuka
tab browser ke sesi yang sama. Executable Linux/macOS juga menerima command CLI;
misalnya AppImage dapat dijalankan dengan argumen `probe`. Pada Windows gunakan
`Spade65CLI.exe` agar output CLI tidak hilang di executable GUI tanpa console.
Gunakan tombol **Quit application** di sidebar untuk menghentikan server desktop;
menutup tab browser saja tidak menghentikan proses agar sesi dapat dibuka ulang.

Paket Windows belum memiliki code signature. Aplikasi macOS hanya memiliki
ad-hoc signature dan belum dinotarization, sehingga SmartScreen atau Gatekeeper
dapat menampilkan peringatan. Pastikan file berasal dari release project yang
dipercaya. Instalasi source di bawah tetap menjadi fallback.

Linux tetap membutuhkan rule udev repository agar user biasa dapat membuka
`hidraw`. Kebutuhan izin Automation/Accessibility macOS untuk association
aplikasi juga tetap berlaku pada paket desktop.

### Instalasi dari source

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

GUI pada semua paket menyediakan English sebagai bahasa default dan Bahasa
Indonesia sebagai pilihan. Preference bahasa tersimpan lokal di browser; lihat
[`localization.md`](localization.md) untuk struktur yang dapat diperluas.

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
Paket desktop maupun build lokal tidak memiliki jalur tersembunyi untuk operasi
tersebut.
