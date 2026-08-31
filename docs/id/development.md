[English](../development.md) · **Bahasa Indonesia**

# Panduan pengembangan

## Arsitektur

```text
spade65ctl.py
  └── spade65.cli
        ├── spade65.protocol   # konstanta dan builder paket murni
        ├── spade65.device     # model + parser descriptor netral OS
        ├── spade65.transport  # pemilih backend lintas platform
        ├── spade65.hidraw     # backend Linux: sysfs + ioctl
        ├── spade65.application # ownership port + lifecycle GUI bersama
        ├── spade65.instance   # identitas/aktivasi instance localhost
        ├── spade65.gui        # API HTTP loopback + asset web
        ├── spade65.desktop    # lifecycle jendela + bridge native PyWebView
        ├── spade65.tray       # adapter tray Qt/WinForms/Cocoa
        ├── spade65.desktop_preferences # preferensi shell native
        ├── spade65.startup    # launcher login GUI + background service
        └── spade65.web        # HTML/CSS/JS + katalog locale

packaging/
  ├── build.py                 # dispatcher build manual sesuai OS host
  ├── launcher.py              # desktop default, browser fallback, smoke test
  ├── spade65.spec             # asset + backend WebView per platform
  └── build_*                  # paket native Windows, Linux, dan macOS
```

Pemisahan ini disengaja:

- `protocol.py` dapat diuji tanpa Linux maupun keyboard.
- `hidraw.py` tidak mengetahui arti opcode.
- `transport.py` mempertahankan hidraw di Linux dan memakai HIDAPI yang dapat
  membaca descriptor pada Windows/macOS.
- `cli.py` menangani validasi keselamatan dan UX.
- `gui.py` hanya bind ke loopback, membuat token sesi, memvalidasi authority
  `Host`/`Origin` untuk menolak DNS rebinding, dan melayani API serta asset yang
  sama untuk WebView maupun browser.
- `desktop.py` mengelola PyWebView, storage persisten, lifecycle server/window,
  download, aktivasi instance yang sudah berjalan, serta API JavaScript sempit
  untuk integrasi desktop.
- `tray.py` terhubung ke toolkit yang sudah dipilih PyWebView: Qt pada Linux,
  WinForms pada Windows, dan Cocoa pada macOS. Tidak ada toolkit tray kedua.
- `desktop_preferences.py` menyimpan close-to-tray secara terpisah dari
  `localStorage` WebView; `startup.py` menangani format launcher login GUI dan
  background service.
- `application.py` mengklaim port secara atomik, menyalakan server sebelum
  renderer, mengantrekan aktivasi selama window startup, dan berbagi alur yang
  sama antara executable tanpa argumen dan subcommand `gui`.
- `instance.py` hanya menerima instance yang halaman dan token Spade65-nya
  terverifikasi; layanan lain pada 8765 tidak diambil alih.
- `web/locales/index.json` mendaftarkan bahasa; `en.json` adalah canonical
  catalog/default dan locale lain harus memiliki key yang sama.
- `packaging/launcher.py` membuka jendela desktop pada port stabil 8765 tanpa
  argumen, beralih ke browser bila backend native gagal, mengaktifkan jendela
  existing pada peluncuran kedua, dan meneruskan argumen lain ke CLI.

GUI v0.7.0 bukan rewrite ke widget native. Layout dan logika antarmuka tetap
HTML/CSS/JavaScript, dirender di shell native PyWebView. Extra `desktop` memasang
backend platform: PySide6/QtWebEngine pada Linux, pythonnet/Edge WebView2 pada
Windows, dan PyObjC/Cocoa/WebKit pada macOS. Extra `cross-platform` tetap
memasang `hidapi` untuk Windows/macOS; jangan membuat fallback write bila HIDAPI
gagal membaca descriptor. Windows mengharuskan Edge WebView2 Runtime tersedia
pada host.

Desktop memakai `private_mode=False` dan direktori storage khusus aplikasi agar
`localStorage` tidak hilang ketika jendela ditutup. Lokasinya dipilih oleh
`desktop_storage_path()` untuk Local AppData pada Windows dan XDG data pada
Linux. Cocoa WebKit memakai default website data store persisten yang dikelola
macOS untuk bundle ID aplikasi, karena backend tersebut mengabaikan custom path
pywebview. Pada Linux/macOS, `DesktopApi` memvalidasi JSON dan membuka dialog
Save native untuk ekspor profil/library. Windows memakai handler download
WebView2 pada UI thread; mode browser tetap memakai download Blob. Handler
closing PyWebView sinkron hanya membatalkan close setelah adapter tray native
berhasil terpasang; bila tidak, close keluar secara normal. Quit eksplisit
menandai controller sebagai quitting sebelum menghancurkan jendela.
`gui --start-hidden` dipakai launcher login per pengguna, dan kegagalan tray
Linux memulihkan jendela yang terlihat. Mode browser dan `--no-browser` tetap
tersedia melalui CLI.

Layout GUI memakai koordinat `ItemCss` untuk `SPADE65-01` sampai `SPADE65-04`
yang ditemukan di `KeyBoardStyle.js`. Repository hanya menyimpan geometri dan
implementasi HTML/CSS orisinal; gambar PNG vendor tidak boleh disalin ke Git.
`web/layout-state.js` adalah resolver murni untuk enum layout, migrasi storage,
normalisasi USB/dongle, serta fallback disconnected. Firmware dan software
original tidak menyediakan readback layout fisik; frontend karena itu hanya
memulihkan preferensi host dan menyebutkannya secara eksplisit di UI.

## Mengubah antarmuka web

File di dalam `spade65/web/` adalah source frontend utama. File tersebut langsung
dilayani development server dan disalin ke paket release; repository tidak
menyimpan salinan hasil generate atau minify. Pertahankan HTML, JavaScript, CSS,
dan katalog JSON dalam bentuk terbaca agar GUI dapat dikembangkan tanpa harus
merekonstruksi production bundle.

Pasang formatter Python yang kecil dan versinya dikunci, lalu format seluruh
JavaScript dan CSS:

```bash
python -m pip install -e ".[dev]"
python tools/format_web.py
```

Untuk development GUI native, kedua extra dapat dipasang sekaligus:

```bash
python -m pip install -e ".[desktop,dev]"
```

`python tools/format_web.py --check` memeriksa format tanpa mengubah file.
Formatter sengaja tidak menulis ulang `index.html` atau JSON locale karena file
tersebut sudah disimpan sebagai source yang terbaca.

## Menjalankan quality checks

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py tests tools
python tools/format_web.py --check
node --check spade65/web/layout-state.js
node --check spade65/web/app.js
node tests/layout_state.test.js
python spade65ctl.py rgb fixed --dry-run
python spade65ctl.py sleep --light-off 10 --hibernate 30 --dry-run
```

Untuk perubahan transport, tambahkan descriptor sintetis ke `tests/test_hidraw.py`. Untuk perubahan paket, tambahkan assertion offset-by-offset ke `tests/test_protocol.py`.

Perubahan locale harus mempertahankan key parity terhadap `en.json`, placeholder
bernama `{...}`, serta fallback English. Ikuti
[`localization.md`](localization.md) dan uji teks statis maupun renderer dinamis.

Perubahan desktop packaging harus diuji pada OS target. Setiap executable wajib
lulus `--smoke-test` tanpa membuat jendela, membuka browser, enumerasi device,
atau HID write sebelum dikemas. Smoke test mengimpor backend WebView platform
dan memeriksa asset/route localhost; unit test lifecycle memakai WebView mock
agar tidak memerlukan display. Tetap lakukan uji manual untuk window close,
**Quit application**, second-launch activation, import, dan download ekspor pada
OS target.

Workflow test pada setiap push ke `main` menjalankan package preflight native
Windows, Linux, dan macOS tanpa publish. Workflow tag kemudian memasang extra
`desktop`, membangun ulang source immutable dari tag, memeriksa universal Mach-O
pada macOS, dan baru memublikasikan tiga asset setelah semuanya tersedia.
AppImage release dibangun dan di-smoke-test pada runner Ubuntu 22.04 x86_64
(glibc 2.35) serta membawa PySide6/QtWebEngine, sehingga audit ukuran artifact
merupakan bagian review packaging. AppImage yang dibuat manual mewarisi baseline
glibc mesin build dan tidak otomatis memiliki portabilitas yang sama. Lihat
[`releasing.md`](releasing.md).

## Aturan keselamatan implementasi

1. Semua command write harus tetap memerlukan `--confirm`.
2. Semua command write harus memiliki `--dry-run`.
3. Interface harus dipilih berdasarkan VID, PID, usage, report ID, dan report length.
4. Perbedaan descriptor adalah error, bukan warning.
5. Firmware update, raw flash, dan bootloader berada di luar scope sampai ada
   prosedur recovery yang telah diuji; jangan membuat endpoint atau builder-nya.
6. Jangan menulis report ke interface keyboard boot/consumer biasa.
7. Jika sebuah command hanya valid untuk dongle, batasi PID-nya di code.
8. GUI hanya boleh bind ke loopback, memakai token sesi, menolak `Host` asing
   serta `Origin` browser yang tidak cocok, dan mengekspos allowlist tindakan
   konfigurasi yang sudah memiliki builder tervalidasi.
9. Profil JSON adalah data deklaratif; jangan pernah menerima byte/report mentah.

## Workflow pengujian hardware

Buat branch terpisah dan kerjakan dari operasi paling kecil:

1. `probe` pada USB dan dongle.
2. RGB built-in satu kali.
3. Debounce dengan nilai default 5 ms terlebih dahulu.
4. Timer dongle.
5. Baca current state jika format get report sudah diketahui.
6. Per-key RGB.
7. Remap satu tombol.
8. Layer dan macro.

Setelah setiap write, uji input keyboard dengan tool seperti `evtest` atau halaman keyboard tester. Cabut-pasang perangkat sebelum menyimpulkan bahwa command gagal permanen.

## Menambahkan command baru

1. Buat builder yang mengembalikan `bytes` di `protocol.py`.
2. Validasi seluruh range sebelum membangun buffer.
3. Tambahkan test dengan panjang report dan offset penting.
4. Tambahkan handler CLI yang memakai `_write_report()`.
5. Tentukan usage dan PID yang paling sempit.
6. Dokumentasikan statusnya sebagai belum diuji sampai hardware test selesai.

## Status key remapping

Hal yang sudah diketahui:

- Report ID `07`, opcode `03`, panjang 620 byte.
- Data mulai di offset 8.
- Terdapat tiga layer.
- Setiap matrix slot memakai dua byte.
- Matrix internal wired memiliki 102 slot; layout UI memiliki 70 tombol.
- Default USB HID keycodes tersedia dalam modul `SKLocation` vendor.

Kemajuan implementasi:

1. Selesai: ekstrak entry `0x06030x0351` dari `SKLocation.js` secara lokal.
2. Selesai: konversi mapping menjadi konstanta orisinal 102 slot di `spade65/keymap.py`.
3. Selesai: tambahkan model `KeyAssignment(modifiers, usage)` dan builder tiga layer.
4. Selesai: buat `keymap export-default` yang hanya menghasilkan JSON/frame offline.
5. Selesai: implementasikan profil JSON untuk assignment keyboard, macro, dan warna.
6. Selesai: aktifkan write dengan dry-run, validasi descriptor, dan konfirmasi tambahan.
7. Selesai: terapkan keymap tiga layer dan macro sementara, verifikasi keduanya melalui input fisik, lalu kembalikan keymap default dan macro kosong.
8. Berikutnya: bandingkan satu remap dengan USB capture.

Jangan membangun keymap dari urutan fisik 70 tombol saja. Firmware menggunakan slot kosong dalam matrix 102 elemen, sehingga menghilangkan slot kosong dapat menggeser semua assignment.

## Melanjutkan reverse engineering lokal

Artefak vendor tidak berada di repository. Jika installer resmi tersedia di root checkout:

```bash
innoextract --extract --output-dir extracted Spade65_SETUP_20240403.exe
python tools/extract_asar.py extracted/app/resources/app.asar reverse_engineered --prefix backend
python tools/deobfuscate_jupeng.py \
  reverse_engineered/backend/protocol/device/keyborad/JupengSeries.js \
  reverse_engineered/backend/protocol/device/keyborad/JupengSeries.deobfuscated.js
```

`innoextract` adalah tool sistem dan tidak dibundel. Dua script Python dalam repository hanya memakai standard library.

## Capture Windows yang berguna

Jika dibutuhkan, gunakan USBPcap + Wireshark dan lakukan satu perubahan per capture:

- Capture A: RGB fixed, brightness 1.
- Capture B: RGB fixed, brightness 2.
- Capture C: tombol A menjadi B.
- Capture D: kembalikan tombol B menjadi A.

Perbandingan satu-delta mengurangi ambiguity. Catat mode kabel/dongle, versi firmware, dan timestamp tindakan. Hindari capture firmware update.

## Data sensitif dan artefak vendor

- `probe --json` tidak menampilkan `unique`/serial secara default. Jangan memakai `--include-unique` untuk artefak publik.
- Jangan commit installer, firmware, `app.asar`, binary `.node`, atau hasil ekstraksi source vendor.
- Commit hanya catatan interoperabilitas dan kode implementasi orisinal.
