# Panduan rilis desktop

## Hasil rilis

Workflow [`.github/workflows/release.yml`](../.github/workflows/release.yml)
berjalan saat tag berbentuk `vMAJOR.MINOR.PATCH` dikirim. Untuk versi `0.6.0`,
tag yang benar adalah `v0.6.0`. Setelah validasi dan ketiga build berhasil,
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

Executable GUI hasil build membuka localhost di `127.0.0.1:8765` ketika
dijalankan tanpa argumen dan membuka ulang sesi tervalidasi bila sudah berjalan.
ZIP Windows juga menyertakan `Spade65CLI.exe` agar output/error CLI terlihat;
Linux dan macOS meneruskan argumen pada executable yang sama ke command
`spade65ctl`.

## Menyiapkan tag

Versi harus sama di tiga tempat:

1. tag Git, misalnya `v0.6.0`;
2. `project.version` di `pyproject.toml`, misalnya `0.6.0`;
3. `spade65.__version__` di `spade65/__init__.py`, misalnya `0.6.0`.

Periksa versi dan jalankan test sebelum membuat tag:

```bash
python packaging/check_version.py v0.6.0
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py packaging tests
git status --short
```

Setelah commit rilis sudah berada di remote dan worktree sesuai harapan, buat
serta kirim tag:

```bash
git tag -a v0.6.0 -m "Spade65 v0.6.0"
git push origin v0.6.0
```

Jangan memindahkan tag yang telah dipublikasikan ke commit lain. Jika build
gagal, perbaiki source dan terbitkan versi patch baru. Eksekusi manual cocok
untuk mengulang kegagalan infrastruktur pada tag yang commit-nya tidak berubah.

## Apa yang divalidasi workflow

Sebelum memublikasikan asset, pipeline:

- menolak tag yang tidak sesuai format atau tidak cocok dengan kedua versi
  project;
- menjalankan unit test dan bytecode compilation;
- menyertakan HTML, CSS, JavaScript, serta seluruh katalog locale dalam bundle;
- menjalankan smoke test executable tanpa membuka browser, enumerasi perangkat,
  atau HID write; pada Windows/macOS test tetap memuat extension HID native agar
  dependency binary yang rusak terdeteksi;
- menguji route HTTP locale dari bundle agar data PyInstaller yang hilang
  terdeteksi;
- membuat AppImage x86_64 pada Ubuntu;
- mengekstrak ulang ZIP Windows dan menjalankan smoke test melalui executable
  console hasil ekstraksi;
- membangun aplikasi macOS universal dan memeriksa setiap file Mach-O agar
  memiliki slice `x86_64` dan `arm64`;
- memverifikasi serta mount DMG read-only sebelum smoke test terakhir;
- menolak publish bila salah satu dari tiga file keluaran hilang atau kosong.

Smoke test packaging hanya menguji startup dan resource aplikasi. Ia tidak
menggantikan pengujian keyboard fisik, dan tidak mengirim HID report.

## Build lokal

Pasang dependency project serta tool build:

```bash
python -m pip install -r requirements-build.txt ".[cross-platform]"
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
packaging. Build Linux membutuhkan `curl` dan `sha256sum`; script memverifikasi
hash `appimagetool` serta runtime type-2 yang dipin sebelum mengeksekusinya.
Rincian tingkat rendah ada di
[`packaging/README.md`](../packaging/README.md).

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
