# Catatan protokol Noir Spade65 non-QMK

Dokumen ini merangkum hasil reverse engineering statis dan validasi hardware bertahap. Nilai yang belum disebut dalam bagian validasi tetap harus dianggap **belum terverifikasi pada hardware**.

## Validasi hardware

Pada 29 Agustus 2026, unit kabel USB `0603:0351` bernama `JP Spade65`
memvalidasi descriptor feature report utama `0x07` sepanjang 620 byte dan report
pendek `0x08` sepanjang 8 byte. Pengiriman RGB `fixed` (brightness 2, speed 3)
mengembalikan hasil ioctl 620, dan debounce 5 ms mengembalikan hasil ioctl 8.
Mode dongle, keymap write, macro, per-key RGB, reset, serta firmware update belum
diuji.

## Sumber analisis

- Installer: `Spade65_SETUP_20240403.exe`
- SHA-256: `73684f103ef792994141880288daf4fa51b72b3b828ed9849b089da43386b91f`
- Format installer: Inno Setup 6.1.0
- Aplikasi: Electron 4.0.0, aplikasi internal versi 1.0.0
- Arsip utama: `resources/app.asar`
- Router protokol dalam database vendor: `JupengSeries`

Installer dan hasil ekstraksi tidak dimasukkan ke Git. File tersebut masuk `.gitignore` untuk menghindari redistribusi artefak vendor.

## Identitas perangkat

| Transport | VID | PID |
|---|---:|---:|
| Kabel USB | `0603` | `0351` |
| Dongle 2.4 GHz | `0603` | `0356` |

Database vendor mendefinisikan:

| Fungsi | Usage page | Usage |
|---|---:|---:|
| Get/main input | `ff01` | `0001` |
| Set/main feature | `ff02` | `0001` |

Kode `InitialDevice` juga mencari:

| Fungsi hasil inferensi | Usage page | Usage |
|---|---:|---:|
| Feature report pendek | `ff03` | `0001` |
| Streaming output RGB | `ff55` | `0202` |

Inferensi tersebut berasal dari parameter `FindDevice()` dan nama handle internal `DeviceId_Set8Bytes` serta `DeviceId_Output`. Descriptor hardware tetap harus mengonfirmasi pasangan ini.

## Transport Linux

Aplikasi Windows memakai native addon berbasis HIDAPI. Wrapper meneruskan byte pertama buffer sebagai report ID. Implementasi Linux memakai `hidraw` dan ioctl `HIDIOCSFEATURE(length)`, dengan report ID tetap menjadi byte pertama.

CLI memilih interface berdasarkan seluruh kondisi berikut:

1. VID `0603`.
2. PID `0351` atau `0356`.
3. Pasangan usage page/usage yang sesuai.
4. Feature report ID dan panjang report yang cocok dengan descriptor.

Tidak ada fallback yang menulis berdasarkan nomor `/dev/hidrawN` saja.

## Report utama ID 0x07

Ukuran buffer vendor adalah `0x26c` atau 620 byte, termasuk report ID.

### Efek RGB bawaan — opcode 0x02

| Offset | Panjang | Arti |
|---:|---:|---|
| `0x00` | 1 | Report ID `07` |
| `0x01` | 1 | Opcode `02` |
| `0x02` | 1 | Nilai tetap `01` |
| `0x03..0x08` | 6 | Nol |
| `0x09` | 1 | Effect ID `00..13` |
| `0x0a` | 1 | Brightness `0..4` |
| `0x0b` | 1 | Speed `1..5` |
| `0x0c..0x1f` | 20 | Indeks warna per effect; `07` dipakai untuk multicolor |
| sisanya | | Nol |

Effect ID:

| ID | Nama CLI | Nama internal vendor |
|---:|---|---|
| `00` | `neon-stream` | `Neon_stream` |
| `01` | `fixed` | `Fixed_on` |
| `02` | `breathe` | `Respire` |
| `03` | `ripples-shining` | `Ripples_shining` |
| `04` | `rainbow-wheel` | `Rainbow_wheel` |
| `05` | `ripple-band-up-down` | `RippleBandUpDown` |
| `06` | `reaction` | `Reaction` |
| `07` | `two-block` | `TwoBlock` |
| `08` | `random-color` | `RandomColor` |
| `09` | `double-wave` | `DoubleWave` |
| `0a` | `retro-snake` | `RetroSnake` |
| `0b` | `double-spiral` | `DoubleSpiral` |
| `0c` | `ripple-band` | `RippleBand` |
| `0d` | `kamehameha` | `Kamehemeha` (ejaan vendor) |
| `0e` | `wave-90` | `Wave90` |
| `0f` | `intersect` | `Intersect` |
| `10` | `shadow-disappear` | `Shadow_disappear` |
| `11` | `follow` | `Follow` |
| `12` | `snake-up-down` | `SnakeUpDown` |
| `13` | `custom` | `Customize` |

### Keymap — opcode 0x03

Struktur awal yang ditemukan:

| Offset | Arti |
|---:|---|
| `0x00` | Report ID `07` |
| `0x01` | Opcode `03` |
| `0x02` | `fnModeindex + 1` |
| `0x08...` | Tiga layer, dua byte per matrix slot |

Kode vendor membangun data untuk layer normal dan dua layer Fn. Matrix kabel `0603:0351` memiliki 102 slot internal (`0x66`), sementara profil UI memiliki 70 tombol logis. Slot kosong penting untuk menjaga urutan matrix.

Dua byte per slot digunakan sebagai modifier/status dan HID usage. Assignment sederhana menambahkan `0x80` pada byte pertama. Macro memakai keycode khusus pada rentang `f0...` dan dikirim terpisah. Mapping 102 slot dan builder frame tiga layer sudah diimplementasikan untuk ekspor offline. Pengiriman ke perangkat belum diaktifkan karena satu remap pada software Windows perlu dicapture dan dibandingkan dengan frame hasil analisis agar semantics byte pertama tidak merusak layer.

### Macro — opcode 0x05

Header yang ditemukan:

- Byte 0: `07`
- Byte 1: `05`
- Byte 2: `01`
- Byte 3: index macro, maksimal 10 macro yang dikirim dalam satu operasi UI
- Byte 8..263: maksimal 256 byte macro data

Entry macro memakai tiga byte: delay high/status key-down, delay low, dan HID keycode. Delay minimum dipaksa menjadi 20 ms oleh software vendor.

### Custom/per-key RGB — opcode 0x07

- Byte 0: `07`
- Byte 1: `07`
- Mulai byte 8: triplet R, G, B menurut urutan matrix internal.

Pemetaan 70 tombol UI ke 102 slot matrix sudah berada dalam kode vendor, tetapi belum disalin ke implementasi agar tidak mengasumsikan revisi hardware yang salah.

## Report pendek ID 0x08

Interface ini dinamai `DeviceId_Set8Bytes` oleh aplikasi vendor. Tool mengharapkan feature report sepanjang 8 byte termasuk report ID.

| Byte 1/opcode | Payload | Fungsi |
|---:|---|---|
| `08` | kosong | Reset pengaturan |
| `09` | byte 2 = milliseconds | Debounce |
| `0b` | byte 2 = index light-off + 1; byte 3 = index hibernate + 1 | Timer mode dongle |

Pilihan timer berasal langsung dari profil default vendor:

- Light-off: 1, 2, 5, 10, 15, 20, 25, 30 menit.
- Hibernate: 3, 5, 10, 15, 20, 25, 30, 60 menit.

Kode vendor melewati pengiriman timer saat state adalah kabel USB. Implementasi Linux karena itu membatasi perintah `sleep` ke PID dongle `0356`.

## Streaming RGB output

Untuk sinkronisasi real-time, aplikasi terlebih dahulu mengirim feature report pendek `[08, 06, ...]`. Berikutnya aplikasi mengirim lima output report sepanjang 64 byte melalui usage `ff55:0202`:

- Byte 0: report ID `06`.
- Byte 1: nomor chunk 1 sampai 5.
- Byte 2..63: 62 byte data RGB.

Fitur ini belum diimplementasikan karena streaming perlu diuji untuk latency dan tidak diperlukan untuk konfigurasi tersimpan dasar.

## Data yang masih diperlukan

Saat hardware tersedia, simpan:

1. `probe-wired.json`.
2. `probe-dongle.json`.
3. Hasil sukses/gagal setiap command beserta mode kabel/dongle.
4. Jika key remapping dilanjutkan, capture USBPcap untuk perubahan satu tombol saja, misalnya `A` menjadi `B`, lalu kembalikan segera.

Tidak perlu memulai dari firmware dump. HID descriptor dan satu-delta capture jauh lebih aman dan cukup untuk memvalidasi protokol konfigurasi.
