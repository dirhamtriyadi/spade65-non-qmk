# spade65-non-qmk

Utilitas Linux eksperimental untuk mengatur keyboard **Noir Spade65 non-QMK** tanpa menjalankan software Windows resmi.

Proyek ini dibuat melalui analisis statis installer resmi `Spade65_SETUP_20240403.exe`. Jalur USB telah diuji bertahap pada unit fisik; fitur yang belum diuji tetap ditandai secara eksplisit di bawah.

## Status

| Fitur | Implementasi | Diuji pada hardware |
|---|---:|---:|
| Deteksi USB dan dongle | Ya | Ya, mode USB `0603:0351` |
| Membaca HID report descriptor | Ya | Ya, mode USB `0603:0351` |
| Efek RGB bawaan | Ya | Ya, `fixed` via USB |
| Brightness dan speed RGB | Ya | Ya, via USB |
| Debounce | Ya | Ya, 5 ms via USB |
| Timer lampu/sleep untuk dongle | Ya | Belum |
| Reset pengaturan | Ya, dengan konfirmasi tambahan | Belum |
| Remap tombol/layer | Ya, seluruh kategori assignment vendor + tiga layer | Belum |
| Macro | Ya, maksimal 10 macro/84 event, recorder, repeat dan binding | Belum |
| Per-key RGB | Ya, tersimpan dan streaming | Ya, mode USB `0603:0351` |
| GUI lokal | Ya, tanpa dependency eksternal | Ya, browser lokal + deteksi hardware |
| Animasi app/AP mode | Ya, 10 pola/layer + range, palet, parameter lanjut dan audio | Streaming USB tervalidasi |
| Custom timeline | Ya, 200 frame + playback/background streaming | Service mengirim frame via USB |
| Import file vendor | Ya, KeyAssign/Macro/APMode JSON | Diuji offline |
| Asosiasi aplikasi/background service | Ya, X11 + fallback proses Wayland | Seleksi diuji offline; output service via USB |
| Informasi read-only | USB revision + baterai jika diekspos kernel | Ya, tanpa HID write |
| Firmware/raw flash/bootloader | Sengaja tidak diimplementasikan | Tidak; risiko brick |

Fitur konfigurasi keyboard yang aman dari aplikasi vendor sudah tersedia melalui
CLI dan GUI. Asosiasi profil Windows `RELATEDPROGRAM` digantikan service Linux
opt-in. Updater aplikasi, login, dan telemetri vendor tidak direplikasi karena
bukan konfigurasi keyboard. Tidak ada endpoint, builder paket, atau fallback raw
HID untuk flash firmware dan bootloader.

Matriks audit terhadap halaman dan backend software original tersedia di
[`docs/parity.md`](docs/parity.md). Komponen generik yang tersembunyi, dikomentari,
atau tidak pernah diserialisasi oleh backend Jupeng tidak dihitung sebagai fitur
Spade65 aktif.

## Persyaratan

- Linux dengan `hidraw` dan `sysfs` standar.
- Python 3.10 atau lebih baru.
- Tidak membutuhkan package Python pihak ketiga.

## Menjalankan

Langsung dari checkout:

```bash
python spade65ctl.py --help
python spade65ctl.py probe
```

Atau pasang dalam virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
spade65ctl probe
```

`pip install -e .` di atas hanya memakai source lokal; aplikasi tidak memiliki dependency runtime eksternal.

## Izin hidraw melalui udev

Pasang rule yang tersedia dalam repository:

```bash
sudo install -Dm644 udev/99-spade65.rules /etc/udev/rules.d/99-spade65.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Cabut dan pasang kembali keyboard/dongle setelah itu. Jalankan CLI sebagai user biasa; jangan memakai `sudo` kecuali hanya untuk diagnosis izin.

## Urutan pengujian pertama di kantor

1. Hubungkan keyboard dengan kabel USB.
2. Simpan hasil probe:

   ```bash
   python spade65ctl.py probe --json > probe-wired.json
   ```

3. Pastikan ada interface dengan usage `ff02:0001`, feature report ID `0x07`, dan panjang 620 byte. Untuk perintah pendek, diharapkan ada usage `ff03:0001`, report ID `0x08`, panjang 8 byte.
4. Buat paket RGB tanpa mengirimnya:

   ```bash
   python spade65ctl.py rgb fixed --brightness 2 --speed 3 --dry-run
   ```

5. Jika descriptor cocok, kirim perubahan RGB yang mudah dikenali dan mudah dikembalikan:

   ```bash
   python spade65ctl.py rgb fixed --brightness 2 --speed 3 --confirm
   ```

6. Uji efek lain setelah perintah pertama berhasil:

   ```bash
   python spade65ctl.py rgb rainbow-wheel --brightness 4 --speed 5 --multicolor --confirm
   ```

7. Ulangi probe menggunakan dongle 2.4 GHz:

   ```bash
   python spade65ctl.py probe --json > probe-dongle.json
   ```

8. Unggah kedua file `probe-*.json` ke issue atau kirimkan kepada developer. Serial/unique ID tidak disertakan secara default.

CLI menolak menulis jika ukuran report yang dibaca dari descriptor berbeda dari ukuran hasil reverse engineering. Validasi ini disengaja untuk menghindari pengiriman paket ke interface yang salah.

## Penggunaan

### GUI lokal

```bash
python spade65ctl.py gui
```

Browser akan membuka `http://127.0.0.1:8765/`. GUI menyediakan pemilihan device,
editor tiga layer dengan geometri asli empat varian Spade65 (ANSI/ISO dan
standard/split spacebar), seluruh kategori assignment vendor, macro recorder,
import/export profil, seluruh efek RGB bawaan, warna per-key, kompositor 10 layer
animasi streaming dengan parameter original, audio reactive, debounce, timer dongle, reset,
serta diagnostics. Server hanya menerima koneksi localhost dan setiap API call
memerlukan token sesi acak.

GUI juga menyediakan konversi file ekspor original, backup/restore seluruh
library profil, serta custom-effect timeline. Panduan service background dan
asosiasi aplikasi ada di [`docs/host-features.md`](docs/host-features.md).
Hasil verifikasi perangkat terakhir ada di
[`docs/hardware-verification.md`](docs/hardware-verification.md).

### Import file software original

```bash
spade65ctl vendor-import original.KeyAssign profile.json
spade65ctl vendor-import original.Macro profile.json --base profile.json --force
spade65ctl vendor-import original.APMode profile.json --base profile.json --force
```

### Background service dan informasi read-only

```bash
spade65ctl service example ~/.config/spade65/default.json
spade65ctl service run ~/.config/spade65/default.json
spade65ctl info
```

Service dapat menjalankan AP effect/timeline setelah GUI ditutup dan memilih
profil menurut aplikasi Linux. Write keymap otomatis nonaktif secara default dan
memerlukan izin ganda. `info` tidak mengirim paket HID.

Apply profil meminta dua konfirmasi karena menimpa seluruh keymap. Reset meminta
teks `RESET SPADE65`. Firmware update, raw flash, dan bootloader ditampilkan dalam
keadaan nonaktif dan tidak memiliki endpoint backend.

### Efek RGB

```bash
python spade65ctl.py rgb EFFECT [opsi] --confirm
```

Lihat seluruh nama efek:

```bash
python spade65ctl.py rgb --help
```

Opsi penting:

- `--brightness 0..4`
- `--speed 1..5`
- `--color-index 0..7`
- `--multicolor`
- `--dry-run`
- `--device /dev/hidrawN` jika lebih dari satu Spade65 terhubung

Contoh:

```bash
python spade65ctl.py rgb breathe --brightness 3 --speed 2 --color-index 0 --confirm
```

### Debounce

Nilai default vendor adalah 5 ms.

```bash
python spade65ctl.py debounce 5 --dry-run
python spade65ctl.py debounce 5 --confirm
```

### Profil lengkap, keymap, dan macro

Buat profil yang dapat diedit, lalu validasi sebelum dry-run:

```bash
python spade65ctl.py profile create spade65-profile.json
python spade65ctl.py profile validate spade65-profile.json
python spade65ctl.py profile apply spade65-profile.json --dry-run
```

Bagian `layers` memakai nama `normal`, `fn1`, dan `fn2`. Assignment dapat berupa
nama HID seperti `"b"`, nilai numerik seperti `5`, kombinasi
`{"usage":"b","modifiers":2}`, atau referensi macro `{"macro":0}`.

Macro menyimpan event key-down/key-up dengan delay:

```json
{
  "index": 0,
  "repeat": 1,
  "events": [
    {"delay_ms": 20, "usage": "a", "pressed": true},
    {"delay_ms": 20, "usage": "a", "pressed": false}
  ]
}
```

Profil adalah sumber backup karena aplikasi vendor juga tidak menyediakan
readback keymap dari firmware. Apply menimpa tiga layer lengkap dan karena itu
memerlukan dua konfirmasi:

```bash
python spade65ctl.py profile apply spade65-profile.json \
  --confirm --i-understand-profile-overwrite
```

Mapping/frame default tetap dapat diperiksa secara offline:

```bash
python spade65ctl.py keymap export-default > keymap-default.json
python spade65ctl.py keymap export-default --format hex
```

### Per-key dan streaming RGB

Isi objek `colors` dalam profil dengan pasangan tombol dan warna, misalnya
`{"esc":"#ff0000", "a":[0,255,0]}`. Kemudian:

```bash
python spade65ctl.py per-key-rgb spade65-profile.json --dry-run
python spade65ctl.py per-key-rgb spade65-profile.json --confirm
python spade65ctl.py stream-rgb spade65-profile.json --dry-run
python spade65ctl.py stream-rgb spade65-profile.json --confirm
```

`stream-rgb` mengirim satu frame real-time; aplikasi yang membutuhkan animasi
dapat memanggilnya berulang dengan profil/frame berbeda.
Tombol yang tidak tercantum dalam `colors` bernilai hitam/mati.

### Timer mode dongle

Perintah ini sengaja hanya mencari PID dongle `0356`.

```bash
python spade65ctl.py sleep --light-off 10 --hibernate 30 --dry-run
python spade65ctl.py sleep --light-off 10 --hibernate 30 --confirm
```

Pilihan light-off: 1, 2, 5, 10, 15, 20, 25, atau 30 menit. Pilihan hibernate: 3, 5, 10, 15, 20, 25, 30, atau 60 menit.

### Reset

Reset dapat menghapus pengaturan tersimpan pada keyboard. Gunakan hanya jika diperlukan:

```bash
python spade65ctl.py reset --dry-run --i-understand-reset
python spade65ctl.py reset --confirm --i-understand-reset
```

## Pengujian developer

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py tests tools
```

Tes otomatis memvalidasi builder paket, parser HID, profil, safety allowlist GUI,
dan penolakan operasi flash. Validasi hardware yang sudah dilakukan tercantum di
tabel Status; tes otomatis tidak menggantikan pengujian fisik untuk fitur yang
masih bertanda belum diuji.

## Troubleshooting

### `Spade65 tidak ditemukan`

Periksa identitas USB:

```bash
lsusb -d 0603:0351
lsusb -d 0603:0356
```

Jika VID/PID keyboard produksi Anda berbeda, jangan langsung mengubah konstanta. Simpan output `lsusb` dan descriptor lebih dahulu karena mungkin merupakan revisi hardware berbeda.

### `Permission denied: /dev/hidrawN`

Pastikan udev rule sudah dipasang dan perangkat sudah dicabut-pasang. Periksa:

```bash
getfacl /dev/hidrawN
```

### `report length mismatch`

Jangan paksa pengiriman. Simpan hasil `probe --json`; perbedaan panjang dapat menandakan revisi firmware atau interface yang berbeda.

### Keyboard berhenti merespons sementara

Cabut dan pasang kembali kabel/dongle. Jangan menjalankan reset berulang dan jangan mencoba file firmware yang ditemukan dalam installer resmi.

## Dokumentasi teknis

- [docs/protocol.md](docs/protocol.md) — hasil reverse engineering dan format report.
- [docs/development.md](docs/development.md) — arsitektur, workflow pengembangan, dan rencana key remapping.
- [tools/extract_asar.py](tools/extract_asar.py) — extractor minimal untuk arsip Electron ASAR.
- [tools/deobfuscate_jupeng.py](tools/deobfuscate_jupeng.py) — resolver tabel string modul protokol vendor.

## Catatan hukum dan keselamatan

Repository tidak menyertakan installer, firmware, source vendor hasil ekstraksi, atau binary native vendor. Gunakan proyek ini hanya pada perangkat milik sendiri. Firmware update sengaja berada di luar scope sampai recovery procedure dan hardware revision dapat diverifikasi.

## Lisensi

Kode asli dalam repository ini menggunakan lisensi MIT. Software, firmware, nama merek, dan asset vendor tetap menjadi milik pemegang hak masing-masing.
