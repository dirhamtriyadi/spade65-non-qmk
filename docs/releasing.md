# Panduan rilis desktop

## Hasil rilis

Workflow [`.github/workflows/release.yml`](../.github/workflows/release.yml)
berjalan saat tag berbentuk `vMAJOR.MINOR.PATCH` dikirim. Untuk versi `0.7.2`,
tag yang benar adalah `v0.7.2`. Setelah validasi dan ketiga build berhasil,
workflow memublikasikan GitHub Release dengan tepat tiga asset:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Build dilakukan secara native pada runner Windows, Ubuntu, dan macOS; ketiga
format tidak dibuat melalui satu cross-compiler. Job publish baru berjalan
setelah seluruh job platform berhasil dan memastikan ketiga asset ada serta
tidak kosong. Eksekusi manual (`workflow_dispatch`) dapat membangun ulang tag
yang sudah ada hanya selama release masih draft. Workflow menolak menimpa
release yang telah dipublikasikan.

Sebelum tag dibuat, push ke branch `main` menjalankan package preflight native
melalui workflow test: ZIP Windows, AppImage Linux, dan DMG macOS dibangun serta
di-smoke-test tanpa publish. Workflow rilis tetap membangun ulang ketiga asset
dari commit tag yang immutable; hasil preflight tidak dipakai ulang sebagai
release asset.

Executable GUI hasil build membuka localhost di `127.0.0.1:8765` dalam jendela
standalone PyWebView ketika dijalankan tanpa argumen. UI tetap berupa
HTML/CSS/JavaScript lokal di dalam WebView, bukan widget native penuh. Jika
backend native tidak tersedia, launcher membuka browser sebagai fallback.
Peluncuran kedua mengaktifkan dan memulihkan jendela existing. Menutup jendela
atau memilih **Quit application** menghentikan server; tidak ada system tray.
Storage WebView bersifat persisten dan download ekspor profil/library diaktifkan.

ZIP Windows juga menyertakan `Spade65CLI.exe` agar output/error CLI terlihat;
Linux dan macOS meneruskan argumen pada executable yang sama ke command
`spade65ctl`. Mode eksplisit tersedia melalui subcommand `gui --browser` dan
`gui --no-browser`.

## Menyiapkan tag

Versi harus sama di tiga tempat:

1. tag Git, misalnya `v0.7.2`;
2. `project.version` di `pyproject.toml`, misalnya `0.7.2`;
3. `spade65.__version__` di `spade65/__init__.py`, misalnya `0.7.2`.

Periksa versi dan jalankan test sebelum membuat tag:

```bash
python packaging/check_version.py v0.7.2
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py packaging tests
git status --short
```

Setelah commit rilis sudah berada di remote dan worktree sesuai harapan, buat
serta kirim tag:

```bash
git tag -a v0.7.2 -m "Spade65 v0.7.2"
git push origin v0.7.2
```

Jangan memindahkan tag yang telah dipublikasikan ke commit lain. Jika build
gagal, perbaiki source dan terbitkan versi patch baru. Eksekusi manual cocok
untuk mengulang kegagalan infrastruktur pada tag yang commit-nya tidak berubah.

## Apa yang divalidasi workflow

Sebelum memublikasikan asset, pipeline:

- menolak tag yang tidak sesuai format atau tidak cocok dengan kedua versi
  project;
- menjalankan unit test dan bytecode compilation;
- memasang extra `desktop` dan memeriksa dependency environment sebelum build;
- menyertakan HTML, CSS, JavaScript, seluruh katalog locale, PyWebView, dan
  backend renderer platform dalam bundle;
- menjalankan smoke test executable tanpa membuat window, membuka browser,
  enumerasi perangkat, atau HID write; test mengimpor backend WebView, dan pada
  Windows/macOS tetap memuat extension HID native agar dependency binary yang
  rusak terdeteksi;
- menguji route HTTP locale dari bundle agar data PyInstaller yang hilang
  terdeteksi;
- membuat dan menjalankan smoke test AppImage x86_64 pada runner Ubuntu 22.04
  (glibc 2.35), sambil membundel PySide6/QtWebEngine;
- menolak modul Qt GPL-only yang tidak digunakan setelah PyInstaller selesai,
  sehingga perubahan hook/dependency tidak diam-diam memperluas scope lisensi;
- mengekstrak ulang ZIP Windows dan menjalankan smoke test melalui executable
  console hasil ekstraksi, termasuk validasi renderer Edge WebView2;
- membangun aplikasi macOS universal dan memeriksa setiap file Mach-O agar
  memiliki slice `x86_64` dan `arm64`; bundle memakai Cocoa/WebKit dan
  mendeklarasikan local networking serta penggunaan mikrofon untuk audio-reactive;
- memverifikasi serta mount DMG read-only sebelum smoke test terakhir;
- menolak publish bila salah satu dari tiga file keluaran hilang atau kosong.

Smoke test packaging hanya menguji startup, import runtime desktop, resource,
dan route aplikasi. Ia tidak membuka GUI interaktif, menggantikan pengujian
keyboard fisik, atau mengirim HID report. Uji manual per OS tetap harus mencakup
second-launch activation, close/quit, fallback browser, file picker, dan download
ekspor.

## Build lokal

Pasang dependency project serta tool build:

```bash
python -m pip install -r requirements-build.txt ".[cross-platform,desktop]"
python -m pip check
```

Jalankan dispatcher pada OS target. Command ini otomatis memilih script native,
memakai interpreter Python yang sedang aktif, menjalankan smoke test paket, dan
menghasilkan nama artifact yang sama dengan CI:

```bash
python packaging/build.py
```

Gunakan `python packaging/build.py --dry-run` untuk melihat script yang akan
dijalankan tanpa membangun. Script platform juga dapat dipanggil langsung untuk
otomasi yang memang spesifik OS:

```bash
# Linux
bash packaging/build_linux.sh

# Windows PowerShell
pwsh -File packaging/build_windows.ps1

# macOS
bash packaging/build_macos.sh
```

Script menulis hasil ke `artifacts/`. Build macOS universal membutuhkan Python
dan semua native dependency dalam format universal2; script sengaja gagal bila
menemukan Mach-O satu arsitektur. Wheel `hidapi` tipis tidak cukup; gunakan
perintah `ARCHFLAGS` dan `--no-binary=hidapi` yang dicantumkan di panduan
packaging. macOS memakai Cocoa/WebKit melalui PyObjC dan metadata bundle
mengizinkan localhost serta menjelaskan prompt mikrofon audio-reactive.

Build Windows serta smoke test-nya memerlukan Edge WebView2 Runtime pada host.
Build Linux membutuhkan loader EGL, `curl`, dan `sha256sum`; pada Debian/Ubuntu
pasang `libegl1`, `libgl1`, paket runtime XCB yang dicantumkan di
[`packaging/README.md`](../packaging/README.md), `curl`, dan `coreutils`. Script
memverifikasi hash
`appimagetool` serta runtime type-2 yang dipin sebelum mengeksekusinya. AppImage
PySide6/QtWebEngine jauh lebih besar daripada paket browser-only. Asset resmi
dibangun dan di-smoke-test pada Ubuntu 22.04 x86_64 (glibc 2.35); ini adalah
baseline yang didukung, bukan janji kompatibilitas berdasarkan nomor glibc saja.
Build manual mewarisi kebutuhan libc dari mesin yang menjalankan build, sehingga
sebaiknya dibuat pada OS target tertua yang ingin didukung.
Build Ubuntu resmi juga mengaktifkan inventaris legal dpkg yang ketat. Setiap
binary native dari direktori sistem yang masuk ke hasil PyInstaller harus
memiliki paket pemilik dan `/usr/share/doc/<paket>/copyright`; jika tidak,
workflow gagal sebelum AppImage dibuat. Manifest dan salinan copyright tersebut
tersimpan di `usr/share/doc/spade65/linux-system-libraries` dalam AppImage.
Build manual pada host non-dpkg tetap berjalan, tetapi manifest-nya diberi label
`source-path-only` dan tidak menyatakan atribusi library sistem telah lengkap.
Rincian tingkat rendah ada di
[`packaging/README.md`](../packaging/README.md).

Package preflight `main` dan workflow rilis memakai dependency desktop yang sama
dengan build manual: Windows memasang `.[cross-platform,desktop]`, Linux hanya
memasang `.[desktop]` karena paketnya memakai `hidraw`, sedangkan macOS memasang
extra `desktop` lalu membangun HIDAPI universal2 dengan helper terpisah. Jangan
menganggap unit test atau smoke test headless sebagai pengganti uji renderer
interaktif pada OS target.

Jika paket desktop belum tersedia untuk sebuah commit, instalasi dari source
tetap didukung sebagaimana dijelaskan di
[`docs/cross-platform.md`](cross-platform.md). Pengguna paket rilis tidak perlu
clone repository atau menjalankan Python secara manual.

## Signing dan distribusi

Paket Windows saat ini tidak memiliki code signature. Bundle macOS hanya
ditandatangani ad-hoc agar struktur aplikasi valid, bukan dengan Apple Developer
ID, dan DMG belum dinotarization. Karena itu Windows SmartScreen atau macOS
Gatekeeper dapat menampilkan peringatan pada file hasil unduhan. Hanya lanjutkan
jika asset berasal dari halaman release project dan tag/commit-nya dipercaya;
instalasi source adalah fallback yang transparan.

Signing produksi membutuhkan sertifikat privat Windows serta kredensial Apple
Developer ID/notarization. Jangan pernah commit sertifikat, password, token,
atau provisioning secret. Penambahan signing nantinya harus memakai repository
secrets dan tetap mempertahankan smoke test sebelum publish.

## Batas keselamatan

Paket desktop berisi fitur konfigurasi yang sama dengan source. Packaging tidak
menambahkan firmware flashing, bootloader, raw flash/write, ataupun arbitrary
HID packet. Operasi tersebut tetap tidak memiliki route backend atau packet
builder karena dapat menyebabkan brick dan belum ada prosedur recovery yang
terverifikasi. Jangan menyisipkannya ke workflow rilis, installer, atau launcher.
