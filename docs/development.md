# Panduan pengembangan

## Arsitektur

```text
spade65ctl.py
  └── spade65.cli
        ├── spade65.protocol   # konstanta dan builder paket murni
        └── spade65.hidraw     # discovery sysfs, parser descriptor, ioctl
```

Pemisahan ini disengaja:

- `protocol.py` dapat diuji tanpa Linux maupun keyboard.
- `hidraw.py` tidak mengetahui arti opcode.
- `cli.py` menangani validasi keselamatan dan UX.

Tidak ada dependency runtime eksternal. Hindari menambahkan `hidapi` hanya untuk convenience sebelum terbukti diperlukan; ioctl Linux sudah menyediakan feature report yang dibutuhkan.

## Menjalankan quality checks

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py tests tools
python spade65ctl.py rgb fixed --dry-run
python spade65ctl.py sleep --light-off 10 --hibernate 30 --dry-run
```

Untuk perubahan transport, tambahkan descriptor sintetis ke `tests/test_hidraw.py`. Untuk perubahan paket, tambahkan assertion offset-by-offset ke `tests/test_protocol.py`.

## Aturan keselamatan implementasi

1. Semua command write harus tetap memerlukan `--confirm`.
2. Semua command write harus memiliki `--dry-run`.
3. Interface harus dipilih berdasarkan VID, PID, usage, report ID, dan report length.
4. Perbedaan descriptor adalah error, bukan warning.
5. Jangan implementasikan firmware update sebelum ada prosedur recovery yang telah diuji.
6. Jangan menulis report ke interface keyboard boot/consumer biasa.
7. Jika sebuah command hanya valid untuk dongle, batasi PID-nya di code.

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

## Rencana key remapping

Hal yang sudah diketahui:

- Report ID `07`, opcode `03`, panjang 620 byte.
- Data mulai di offset 8.
- Terdapat tiga layer.
- Setiap matrix slot memakai dua byte.
- Matrix internal wired memiliki 102 slot; layout UI memiliki 70 tombol.
- Default USB HID keycodes tersedia dalam modul `SKLocation` vendor.

Langkah implementasi berikutnya:

1. Selesai: ekstrak entry `0x06030x0351` dari `SKLocation.js` secara lokal.
2. Selesai: konversi mapping menjadi konstanta orisinal 102 slot di `spade65/keymap.py`.
3. Selesai: tambahkan model `KeyAssignment(modifiers, usage)` dan builder tiga layer.
4. Selesai: buat `keymap export-default` yang hanya menghasilkan JSON/frame offline.
5. Selesai: implementasikan profil JSON untuk assignment keyboard, macro, dan warna.
6. Selesai: aktifkan write dengan dry-run, validasi descriptor, dan konfirmasi tambahan.
7. Berikutnya: bandingkan satu remap dengan USB capture dan validasi macro pada hardware.

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
