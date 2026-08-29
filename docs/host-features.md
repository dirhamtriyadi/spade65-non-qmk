# Fitur host lintas platform

## Konversi ekspor software original

File ekspor original adalah JSON dengan wrapper `filename`, `version`, dan
`value`. Konverter menerima bagian `Keyboard_Export`, `Macro_Export`, serta
`Light_Export` dan menggabungkannya ke profil native:

```bash
spade65ctl vendor-import profile.KeyAssign profile.json
spade65ctl vendor-import macro.Macro profile.json --base profile.json --force
spade65ctl vendor-import lighting.APMode profile.json --base profile.json --force
spade65ctl profile validate profile.json
```

GUI menyediakan tombol **Import vendor** untuk alur yang sama. Konversi selalu
offline; file vendor tidak pernah berisi atau mengirim paket HID bebas.

## Backup library GUI

**Backup library** mengunduh satu JSON berformat `spade65-library-v1` berisi
seluruh profil localStorage, profil aktif, bahasa, dan map pilihan layout per
model. **Restore library** memvalidasi setiap profil melalui backend sebelum
meminta konfirmasi penggantian library lokal. Backup lama yang hanya memiliki
field `layout` tetap dimigrasikan saat Spade65 berikutnya terdeteksi.

## Custom-effect timeline

Pada halaman Lighting, atur warna per-key lalu gunakan **Capture frame**.
Masing-masing frame memiliki durasi 20–60000 ms. Timeline maksimal 200 frame,
dapat di-loop, tersimpan dalam `settings.custom_timeline`, dan memakai transport
streaming USB yang sama dengan AP mode. Tidak ada data timeline yang ditulis ke
flash firmware.

## Background service dan asosiasi aplikasi

Buat konfigurasi awal:

```bash
mkdir -p ~/.config/spade65
spade65ctl service example ~/.config/spade65/default.json
```

Edit `associations` menjadi nama proses aplikasi dan path profil. Jalankan:

```bash
spade65ctl service run ~/.config/spade65/default.json
```

Pada X11, service memakai `_NET_ACTIVE_WINDOW` dan `_NET_WM_PID`. Pada Wayland
tidak ada API foreground-window yang portabel, sehingga fallback memilih rule
pertama dengan proses yang sedang berjalan. Urutan rule karena itu signifikan.
Windows memakai Win32 foreground-window API dan macOS memakai proses frontmost
melalui System Events. macOS dapat meminta izin Automation/Accessibility.

Secara default service hanya menjalankan AP effect/timeline. Agar pergantian
aplikasi juga menulis keymap, dua izin harus aktif sekaligus:

1. `"allow_profile_writes": true` di file config.
2. Flag runtime `--allow-profile-writes`.

Semua write tetap diperiksa terhadap HID descriptor. Launcher untuk OS aktif
dapat dibuat tanpa langsung memasangnya:

```bash
spade65ctl service integration ~/.config/spade65/default.json launcher-output
```

Gunakan `--platform linux`, `windows`, atau `macos` untuk menghasilkan launcher
platform lain. Linux menghasilkan unit systemd, Windows menghasilkan launcher
`.cmd` untuk folder Startup, dan macOS menghasilkan LaunchAgent `.plist`.

Service/launcher ini adalah komponen background yang tetap berjalan tanpa GUI;
tidak ada ikon tray dan tidak diperlukan toolkit desktop tambahan. Audio-reactive
tetap dijalankan dari GUI karena service tidak meminta akses mikrofon secara
diam-diam.

## Informasi read-only

```bash
spade65ctl info
```

Perintah ini tidak mengirim report HID. Di Linux, `usb_revision` dibaca dari
sysfs; di Windows/macOS nilainya berasal dari metadata enumerasi HIDAPI. Nilai
tersebut bukan versi firmware. Versi firmware software original berasal dari
fungsi `GetFWVersion` dalam native addon Windows tertutup; tanpa metode request
yang dapat diverifikasi, proyek tidak mengirim tebakan HID. Baterai hanya
ditampilkan jika Linux mengekspornya melalui `power_supply` untuk perangkat yang
sama; belum ada pembacaan baterai terverifikasi pada Windows/macOS.

Hasil pengujian fisik dan batas operasi yang sengaja tidak dikirim dicatat di
[`hardware-verification.md`](hardware-verification.md).
