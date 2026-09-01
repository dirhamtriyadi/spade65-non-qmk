[English](../protocol.md) · **Bahasa Indonesia**

# Catatan protokol Noir Spade65 non-QMK

Dokumen ini merangkum hasil reverse engineering statis dan validasi hardware bertahap. Nilai yang belum disebut dalam bagian validasi tetap harus dianggap **belum terverifikasi pada hardware**.

## Validasi hardware

Pada 29 Agustus 2026, unit kabel USB `0603:0351` bernama `JP Spade65`
memvalidasi descriptor feature report utama `0x07` sepanjang 620 byte dan report
pendek `0x08` sepanjang 8 byte. Pengiriman RGB `fixed` (brightness 2, speed 3)
mengembalikan hasil ioctl 620, dan debounce 5 ms mengembalikan hasil ioctl 8.
Per-key RGB opcode `0x07` dan satu frame streaming (aktivasi ditambah lima output
report 64 byte) juga berhasil dikirim, lalu efek `fixed` berhasil dipulihkan.
Seluruh 20 report efek bawaan, per-key RGB, streaming RGB, AP wave, custom
timeline, keymap tiga layer sementara beserta macro (diterapkan, dikonfirmasi
melalui input fisik, lalu dipulihkan), dan reset konfigurasi sejak itu berhasil
dijalankan pada unit kabel yang sama. Timer dongle tetap belum diuji karena
`0603:0356` belum pernah muncul pada hardware ini; receiver fisik 2,4 GHz
terdeteksi sebagai `0603:0352` dan descriptor-nya tidak mengiklankan satu pun
feature report, sehingga sama sekali tidak dapat dikonfigurasi. Report keymap,
macro, lighting, dan debounce secara individual memiliki bukti
penerimaan fisik, tetapi pemeliharaan visual lighting setelah transaksi profil
bergaya aplikasi resmi yang baru dilengkapi belum dikonfirmasi. Jumlah byte
report dan pengujian urutan otomatis tidak dianggap sebagai bukti visual
tersebut. Firmware
update tidak diimplementasikan karena dapat menyebabkan brick dan tidak ada
recovery procedure yang terverifikasi.

## Sumber analisis

- Installer: `Spade65_SETUP_20240403.exe`
- SHA-256: `73684f103ef792994141880288daf4fa51b72b3b828ed9849b089da43386b91f`
- Format installer: Inno Setup 6.1.0
- Aplikasi: Electron 4.0.0, aplikasi internal versi 1.0.0
- Arsip utama: `resources/app.asar`
- Router protokol dalam database vendor: `JupengSeries`

Installer dan hasil ekstraksi tidak dimasukkan ke Git. File tersebut masuk `.gitignore` untuk menghindari redistribusi artefak vendor.

## Identitas perangkat

| Transport | VID | PID | Konfigurasi |
|---|---:|---:|---|
| Kabel USB | `0603` | `0351` | descriptor-gated |
| Receiver 2,4 GHz | `0603` | `0352` | unsupported-read-only |
| State "Dongle" vendor | `0603` | `0356` | descriptor-gated |

`0352` adalah identitas yang dienumerasi receiver fisik. Satu-satunya vendor
usage page yang diekspos adalah `ff55`, dan descriptor-nya mengiklankan nol
feature report — `ff02:0001` dan `ff03:0001` tidak ada — sehingga identitas ini
dapat ditemukan untuk diagnostik, tetapi tidak pernah menjadi target write.
`0352` tidak muncul pada satu pun tabel perangkat software original. `0356`
adalah state dongle logis milik vendor dan belum pernah teramati pada hardware
ini.

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

Inferensi tersebut berasal dari parameter `FindDevice()` dan nama handle internal `DeviceId_Set8Bytes` serta `DeviceId_Output`. Descriptor kabel `0603:0351` mengonfirmasi keempat pasangan tersebut, bersama feature report `0x07` sepanjang 620 byte, feature report `0x08` sepanjang 8 byte, dan output report `0x06` sepanjang 64 byte.

## Transport lintas platform

Aplikasi vendor Windows memakai native addon berbasis HIDAPI. Wrapper meneruskan
byte pertama buffer sebagai report ID. Implementasi proyek memakai `hidraw` dan
ioctl `HIDIOCSFEATURE(length)` di Linux, serta `hidapi` di Windows/macOS. Kedua
backend mempertahankan report ID sebagai byte pertama.

CLI menemukan setiap interface dengan VID `0603` dan PID `0351`, `0352`, atau
`0356`, serta melaporkan `configuration_status` masing-masing. CLI hanya menulis
ke interface bila seluruh kondisi berikut cocok:

1. VID `0603`.
2. PID `0351` atau `0356`; `0352` bersifat hanya-baca dan tidak pernah menjadi
   target write.
3. Pasangan usage page/usage yang sesuai.
4. Feature report ID dan panjang report yang cocok dengan descriptor.

Windows/macOS membaca report descriptor melalui HIDAPI lalu menjalankan parser
yang sama dengan Linux. Jika descriptor tidak dapat dibaca, collection boleh
ditampilkan oleh `probe`, tetapi tidak memiliki report shape sehingga semua write
ditolak. Tidak ada fallback yang menulis berdasarkan path atau VID/PID saja.

Apply keymap memerlukan kedua bentuk feature report. Jika satu collection OS
mengiklankan keduanya, collection tersebut dipakai ulang. Jika terpisah,
companion report pendek harus memiliki VID/PID dan identitas serial/unique yang
sama dengan collection utama terpilih, termasuk ketika kedua identitas kosong.
Companion yang tidak ada atau lebih dari satu kemungkinan adalah error sebelum
report keymap pertama dikirim. Kedua handle dibuka sebelum write pertama;
handle utama tetap terbuka untuk seluruh report utama dan report pendek memakai
handle terbuka tersendiri.

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

Dua byte per slot digunakan sebagai modifier/status dan HID usage. Assignment sederhana menambahkan `0x80` pada byte pertama. Macro memakai keycode khusus pada rentang `f0...f9` dan dikirim terpisah. Mapping 102 slot, builder tiga layer, profil JSON, dan write dengan konfirmasi tambahan sudah diimplementasikan, dan keymap tiga layer sementara beserta macro terikat telah ditulis ke unit kabel `0603:0351`, dikonfirmasi melalui input fisik, lalu dipulihkan.

### Macro — opcode 0x05

Header yang ditemukan:

- Byte 0: `07`
- Byte 1: `05`
- Byte 2: `01`
- Byte 3: index macro, maksimal 10 macro yang dikirim dalam satu operasi UI
- Byte 8..263: maksimal 256 byte macro data

Entry macro memakai tiga byte: delay high/status key-down, delay low, dan HID keycode. Delay minimum dipaksa menjadi 20 ms oleh software vendor.

Implementasi menerima maksimal 84 event per macro agar header repeat dua byte dan
seluruh triplet tetap berada dalam payload 256 byte. Maksimal sepuluh macro dapat
direferensikan oleh keymap sebagai usage `f0` sampai `f9`.

### Transaksi apply profil / `SetKeyMatrix`

Analisis statis backend original menunjukkan bahwa apply keymap adalah transaksi
berurutan melalui handle feature report utama dan pendek:

| Urutan | Report | Jeda setelah berhasil |
|---:|---|---:|
| 1 | `0x07` utama, opcode `0x03`: ketiga layer keymap | 100 ms |
| 2 | `0x07` utama, opcode `0x05`: setiap macro yang benar-benar direferensikan keymap | 200 ms per macro |
| 3 | `0x07` utama, opcode `0x02`: efek lighting saat ini dari cache host | 100 ms |
| 4 | `0x07` utama, opcode `0x07`: palet per tombol persis, hanya untuk lighting custom | 50 ms |
| 5 | `0x08` pendek, opcode `0x09`: debounce profil | 10 ms |

Spade65 mengikuti urutan ini untuk setiap operasi profil yang menyertakan
cakupan `keymap`. GUI memasok lighting yang sedang dipilih dan debounce yang
ditampilkan; apply dari CLI dan background service memakai nilai yang tersimpan
di profil. Seluruh report dan kedua descriptor divalidasi sebelum opcode `0x03`
dikirim. Kegagalan report utama tetap memiliki recovery lighting best-effort.
Kegagalan report pendek terakhir ditampilkan sebagai transaksi parsial karena
keymap dan lighting mungkin sudah berhasil; lighting tersimpan sebelumnya
dikirim ulang secara best-effort sebelum error dikembalikan.

Backend original menginisialisasi profil baru dengan debounce 1 ms. Spade65
menyimpan `settings.debounce_ms` per profil dan memakai 5 ms untuk template
sendiri serta profil yang dibuat sebelum field tersebut ada, demi mempertahankan
perilaku proyek sebelumnya. Fallback kompatibilitas ini tidak boleh disebut
sebagai default profil baru vendor.

`SetLightOffToDevice` kembali tanpa mengirim pada state kabel. Karena itu
transaksi keymap di atas berakhir setelah debounce dan tidak pernah menambahkan
timer light-off/hibernate pada mode kabel.

### Custom/per-key RGB — opcode 0x07

- Byte 0: `07`
- Byte 1: `07`
- Mulai byte 8: triplet R, G, B menurut urutan matrix internal.

Pemetaan 70 tombol UI ke 102 slot matrix ditemukan dalam kode vendor dan
divalidasi khusus untuk identitas perangkat `0603:0351`.

Pemetaan tersebut kini dikonversi menjadi data interoperabilitas orisinal dalam
`spade65/keymap.py`. CLI menerima warna berdasarkan nama tombol UI, lalu menaruh
triplet pada slot matrix yang sesuai.

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

Kode vendor melewati pengiriman timer saat state adalah kabel USB. Implementasi
proyek karena itu membatasi perintah `sleep` ke PID dongle `0356` pada seluruh OS.

## Streaming RGB output

Untuk sinkronisasi real-time, aplikasi terlebih dahulu mengirim feature report pendek `[08, 06, ...]`. Berikutnya aplikasi mengirim lima output report sepanjang 64 byte melalui usage `ff55:0202`:

- Byte 0: report ID `06`.
- Byte 1: nomor chunk 1 sampai 5.
- Byte 2..63: 62 byte data RGB.

Builder dan transport streaming telah diimplementasikan. Pada unit USB
`0603:0351`, aktivasi dan lima output report berhasil dikirim, kemudian efek
`fixed` berhasil dipulihkan. GUI memakai jalur ini untuk satu frame, sepuluh pola
animasi AP-mode, dan modulasi audio reactive. Streaming tetap dibatasi ke PID USB
dan descriptor output report `0x06` sepanjang 64 byte.

## Data yang masih diperlukan

Simpan dari setiap sesi hardware:

1. `probe-wired.json` untuk `0603:0351`.
2. `probe-receiver.json` untuk `0603:0352`. Tidak ada probe dongle yang dapat
   diambil, karena `0603:0356` belum pernah muncul pada hardware ini.
3. Hasil sukses/gagal setiap command beserta mode kabel/dongle.
4. Jika keymap ditulis kembali, profil yang diterapkan dan profil yang dipakai
   untuk memulihkannya, agar perubahan dapat dibalik tanpa readback.

Tidak perlu memulai dari firmware dump. HID descriptor dan satu-delta capture jauh lebih aman dan cukup untuk memvalidasi protokol konfigurasi.
