# spade65-non-qmk

Utilitas Linux eksperimental untuk mengatur keyboard **Noir Spade65 non-QMK** tanpa menjalankan software Windows resmi.

Proyek ini dibuat melalui analisis statis installer resmi `Spade65_SETUP_20240403.exe`. Implementasi saat ini belum pernah diuji pada perangkat fisik. Selalu mulai dari perintah `probe` dan `--dry-run` ketika keyboard sudah tersedia.

## Status

| Fitur | Implementasi | Diuji pada hardware |
|---|---:|---:|
| Deteksi USB dan dongle | Ya | Belum |
| Membaca HID report descriptor | Ya | Belum |
| Efek RGB bawaan | Ya | Belum |
| Brightness dan speed RGB | Ya | Belum |
| Debounce | Ya | Belum |
| Timer lampu/sleep untuk dongle | Ya | Belum |
| Reset pengaturan | Ya, dengan konfirmasi tambahan | Belum |
| Remap tombol/layer | Protokol dasar ditemukan | Belum diimplementasikan |
| Macro | Protokol dasar ditemukan | Belum diimplementasikan |
| Per-key RGB | Protokol dasar ditemukan | Belum diimplementasikan |
| Firmware update | Sengaja tidak diimplementasikan | Tidak |

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

Tes yang ada memvalidasi builder paket dan parser HID menggunakan descriptor sintetis. Tes belum membuktikan bahwa firmware menerima paket.

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
