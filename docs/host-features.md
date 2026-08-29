# Fitur host Linux

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
seluruh profil localStorage, profil aktif, dan pilihan layout. **Restore library**
memvalidasi setiap profil melalui backend sebelum meminta konfirmasi penggantian
library lokal.

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

Edit `associations` menjadi nama proses Linux dan path profil. Jalankan:

```bash
spade65ctl service run ~/.config/spade65/default.json
```

Pada X11, service memakai `_NET_ACTIVE_WINDOW` dan `_NET_WM_PID`. Pada Wayland
tidak ada API foreground-window yang portabel, sehingga fallback memilih rule
pertama dengan proses yang sedang berjalan. Urutan rule karena itu signifikan.

Secara default service hanya menjalankan AP effect/timeline. Agar pergantian
aplikasi juga menulis keymap, dua izin harus aktif sekaligus:

1. `"allow_profile_writes": true` di file config.
2. Flag runtime `--allow-profile-writes`.

Semua write tetap diperiksa terhadap HID descriptor. Template systemd user ada
di `contrib/systemd/spade65-background@.service`; salin ke
`~/.config/systemd/user/`, lalu sesuaikan `ExecStart` jika lokasi executable
berbeda.

Service/systemd ini adalah komponen background yang tetap berjalan tanpa GUI;
tidak ada ikon tray dan tidak diperlukan toolkit desktop tambahan. Audio-reactive
tetap dijalankan dari GUI karena service tidak meminta akses mikrofon secara
diam-diam.

## Informasi read-only

```bash
spade65ctl info
```

Perintah ini hanya membaca sysfs. `usb_revision` berasal dari `bcdDevice`, bukan
diklaim sebagai versi firmware. Versi firmware software original berasal dari
fungsi `GetFWVersion` dalam native addon Windows tertutup; tanpa metode request
yang dapat diverifikasi, proyek tidak mengirim tebakan HID. Baterai hanya
ditampilkan jika kernel mengekspornya melalui `power_supply` untuk perangkat yang
sama.

Hasil pengujian fisik dan batas operasi yang sengaja tidak dikirim dicatat di
[`hardware-verification.md`](hardware-verification.md).
