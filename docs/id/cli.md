**Bahasa Indonesia** · [English](../cli.md)

# Panduan CLI dan pengguna

Panduan ini membahas penggunaan harian Spade65 dari paket rilis atau source
checkout. Aplikasi menyediakan antarmuka lokal yang sama dalam jendela desktop
mandiri maupun browser, ditambah CLI untuk inspeksi, otomasi, dan penulisan
konfigurasi secara eksplisit.

Spade65 mendukung identitas USB berkabel `0603:0351` dan identitas dongle 2,4 GHz
`0603:0356` milik Noir Spade65 non-QMK. Validasi hardware dilakukan secara
bertahap: deteksi berkabel, parsing descriptor, RGB bawaan, brightness, speed,
debounce, RGB per tombol, dan streaming telah diuji pada keyboard fisik. Builder
report keymap, macro, reset, dan timer dongle tercakup tes otomatis, tetapi belum
dikirim ke hardware yang tersedia. Lihat [catatan verifikasi hardware
terkini](hardware-verification.md) untuk batas pengujian yang tepat.

> **Batas keselamatan:** proyek ini tidak mengimplementasikan flashing firmware,
> penulisan raw flash, akses bootloader, atau paket HID arbitrer. Setiap write ke
> perangkat hanya diizinkan setelah descriptor konfigurasi cocok dengan bentuk
> report yang telah diverifikasi. Perintah konfigurasi langsung membutuhkan flag
> konfirmasi yang didokumentasikan. Background service dapat melakukan streaming
> frame AP/timeline tanpa flag `--confirm`, tetapi write profil otomatis tetap
> nonaktif kecuali diaktifkan secara terpisah dalam konfigurasi dan CLI. Jangan
> pernah melewati error descriptor atau panjang report.

## Memasang atau menjalankan Spade65

### Paket rilis

Asset rilis sudah berisi runtime, sehingga pengguna akhir tidak memerlukan Git,
Python, atau clone repository:

- **Windows x64:** ekstrak `Spade65-Windows-x64.zip` sepenuhnya. Buka
  `Spade65.exe` untuk GUI dan gunakan `Spade65CLI.exe` melalui PowerShell atau
  Command Prompt agar output CLI terlihat.
- **Linux x86_64:** beri izin eksekusi pada
  `Spade65-Linux-x86_64.AppImage`, lalu jalankan:

  ```bash
  chmod +x Spade65-Linux-x86_64.AppImage
  ./Spade65-Linux-x86_64.AppImage
  ```

  Jika FUSE tidak tersedia, tambahkan `APPIMAGE_EXTRACT_AND_RUN=1` di depan
  perintah.
- **macOS Intel/Apple Silicon:** buka `Spade65-macOS-universal.dmg`, salin
  `Spade65.app` ke Applications, lalu buka. Aplikasi universal ini berisi kode
  untuk Intel dan Apple Silicon.

Paket Windows belum code-signed, sedangkan aplikasi macOS memakai ad-hoc
signature dan belum dinotariskan. Pastikan unduhan berasal dari rilis GitHub
proyek ini sebelum menerima peringatan SmartScreen atau Gatekeeper. Persyaratan
platform dan penanganan masalah khusus paket tersedia di [panduan lintas
platform](cross-platform.md).

### Memasang dari source

Python 3.10 atau lebih baru diperlukan. Untuk instalasi CLI saja pada Linux:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
spade65ctl --help
```

Pasang runtime desktop pada Linux dengan:

```bash
python -m pip install -e ".[desktop]"
```

Windows dan macOS memerlukan HIDAPI untuk akses yang divalidasi melalui
descriptor. Pasang kedua extra jika jendela desktop juga diperlukan:

```bash
python -m pip install -e ".[cross-platform,desktop]"
```

Dari checkout yang belum diinstal, ganti `spade65ctl` pada contoh berikut
dengan `python spade65ctl.py`. `python -m spade65` adalah entry point lain untuk
source yang sudah diinstal.

## Membuka GUI atau memakai CLI

Membuka aplikasi paket tanpa argumen akan menjalankan jendela desktop mandiri.
Dari terminal, mode berikut juga tersedia:

```bash
spade65ctl gui
spade65ctl gui --browser
spade65ctl gui --no-browser
```

Mode desktop default menjalankan antarmuka lokal di
`http://127.0.0.1:8765/` dan menampilkannya dalam jendela PyWebView. `--browser`
membuka antarmuka yang sama di browser default. `--no-browser` hanya menjalankan
server lokal; mode ini berguna pada desktop Linux ketika renderer tertanam tidak
kompatibel dengan konfigurasi Wayland atau grafis saat ini.

Server hanya mendengarkan koneksi loopback. API-nya membutuhkan token sesi acak
dan menolak nilai `Host` asing serta `Origin` yang tidak cocok. Peluncuran
desktop kedua mengaktifkan aplikasi yang sudah berjalan, bukan mengambil port
8765 lagi. Jika proses lain yang tidak terkait memakai port tersebut, Spade65
melaporkan konflik dan tidak menghentikan proses itu. Menutup jendela desktop
atau memilih **Quit application** menghentikan server. Dalam mode browser,
menutup tab saja tidak menghentikan proses di terminal.

GUI dan CLI menggunakan implementasi protokol serta pemeriksaan keselamatan
yang sama. GUI menambahkan profil, assignment tombol tiga layer, perekaman macro,
warna per tombol, pencahayaan bawaan dan streaming host, timeline kustom, import
vendor, backup/restore, informasi perangkat, debounce, timer, dan reset. Bahasa
default antarmuka adalah English; Bahasa Indonesia dapat dipilih melalui GUI.

Contoh CLI dari paket:

```powershell
# Windows
.\Spade65CLI.exe probe
.\Spade65CLI.exe info
```

```bash
# Linux
./Spade65-Linux-x86_64.AppImage probe

# macOS, setelah aplikasi disalin
/Applications/Spade65.app/Contents/MacOS/Spade65 probe
```

Bagian selanjutnya memakai perintah instalasi `spade65ctl` agar mudah dibaca.

## Izin perangkat Linux

Pengguna Linux sebaiknya memasang udev rule yang tersedia agar aplikasi dapat
membuka interface `hidraw` terverifikasi sebagai pengguna biasa:

```bash
sudo install -Dm644 udev/99-spade65.rules /etc/udev/rules.d/99-spade65.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Cabut dan sambungkan kembali keyboard atau dongle setelahnya. Jalankan Spade65
sebagai pengguna biasa. `sudo` dapat membantu memastikan penyebab masalah izin,
tetapi tidak seharusnya menjadi cara normal untuk membuka aplikasi.

## Pemeriksaan hardware pertama yang disarankan

Mulailah dengan inspeksi read-only dan perubahan lampu yang mudah dikenali serta
dikembalikan. Jangan memulai dengan apply profil, timer, atau reset.

1. Hubungkan keyboard dengan kabel USB dan simpan probe yang aman bagi privasi:

   ```bash
   spade65ctl probe --json > probe-wired.json
   ```

   Serial dan identitas unik tidak disertakan kecuali `--include-unique`
   diberikan secara eksplisit.
2. Pastikan collection konfigurasi memiliki usage `ff02:0001`, feature report
   ID `0x07`, dan report 620 byte. Perintah konfigurasi pendek memakai usage
   `ff03:0001`, report ID `0x08`, dan report 8 byte.
3. Buat, tetapi jangan kirim, perintah RGB yang sudah dikenal:

   ```bash
   spade65ctl rgb fixed --brightness 2 --speed 3 --dry-run
   ```

4. Hanya jika descriptor cocok, kirim perubahan yang mudah dikembalikan:

   ```bash
   spade65ctl rgb fixed --brightness 2 --speed 3 --confirm
   ```

5. Jika ingin, coba efek bawaan kedua:

   ```bash
   spade65ctl rgb rainbow-wheel --brightness 4 --speed 5 \
     --multicolor --confirm
   ```

6. Jika dongle tersedia, ulangi `probe --json` ketika terhubung melalui dongle
   dan simpan hasilnya secara terpisah.

Setiap perintah penulisan dapat menerima `--device PATH` bila lebih dari satu
perangkat yang cocok terhubung. Gunakan hanya path yang ditampilkan `probe`.
VID/PID yang cocok saja tidak cukup untuk mengizinkan penulisan; validasi
descriptor juga harus berhasil.

## Perintah read-only

### Memeriksa interface HID

```bash
spade65ctl probe
spade65ctl probe --json
```

`probe` membaca informasi enumerasi dan descriptor; perintah ini tidak mengirim
report konfigurasi.

### Menampilkan informasi perangkat yang tersedia

```bash
spade65ctl info
```

`info` tidak mengirim paket HID. Pada Linux, perintah ini dapat menampilkan
revisi USB dari sysfs dan informasi baterai hanya bila sistem operasi
menyediakan power-supply yang cocok. Windows dan macOS memakai metadata
enumerasi. Revisi USB yang ditampilkan **bukan** diklaim sebagai versi firmware
keyboard: request versi firmware vendor belum diverifikasi dengan aman, sehingga
Spade65 tidak menebak atau mengirim request tersebut.

### Mengekspor frame default secara offline

```bash
spade65ctl keymap export-default > keymap-default.json
spade65ctl keymap export-default --format hex
```

Perintah ini menghasilkan mapping/frame default hasil rekonstruksi tanpa
membaca atau menulis keyboard. Perangkat tidak menyediakan readback keymap yang
telah diverifikasi, sehingga file profil yang diterapkan tetap menjadi backup
dan sumber utama.

## Perintah konfigurasi perangkat

Semua contoh terlebih dahulu menampilkan validasi atau `--dry-run` jika
tersedia. Penulisan nyata membutuhkan `--confirm`; operasi luas atau destruktif
tertentu membutuhkan acknowledgement tambahan.

### Efek RGB bawaan

```bash
spade65ctl rgb EFFECT [options] --dry-run
spade65ctl rgb EFFECT [options] --confirm
```

Jalankan `spade65ctl rgb --help` untuk daftar efek terkini. Opsi umum:

- `--brightness 0..4`
- `--speed 1..5`
- `--color-index 0..7`
- `--multicolor`
- `--device PATH`

Contoh:

```bash
spade65ctl rgb breathe --brightness 3 --speed 2 --color-index 0 --confirm
```

Penulisan RGB bawaan, brightness, dan speed telah divalidasi pada keyboard
berkabel yang tersedia.

### Debounce

Nilai default vendor adalah 5 ms:

```bash
spade65ctl debounce 5 --dry-run
spade65ctl debounce 5 --confirm
```

Penulisan debounce 5 ms telah divalidasi pada keyboard berkabel yang tersedia.

### Profil, keymap, dan macro

Buat dan validasi profil lengkap yang dapat diedit sebelum mengompilasi
penulisan:

```bash
spade65ctl profile create spade65-profile.json
spade65ctl profile validate spade65-profile.json
spade65ctl profile apply spade65-profile.json --dry-run
```

Objek `layers` berisi `normal`, `fn1`, dan `fn2`. Assignment dapat memakai nama
HID seperti `"b"`, usage numerik seperti `5`, usage dengan modifier seperti
`{"usage":"b","modifiers":2}`, atau referensi macro seperti `{"macro":0}`.

Macro berisi event key-down/key-up beserta delay-nya:

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

Apply profil menimpa ketiga layer keymap dan menulis setiap macro yang disertakan
dalam profil tersebut. Karena itu, perintah ini membutuhkan dua acknowledgement
eksplisit:

```bash
spade65ctl profile apply spade65-profile.json \
  --confirm --i-understand-profile-overwrite
```

Simpan profil yang tervalidasi dan backup library GUI sebelum menerapkannya.
Keyboard fisik yang tersedia belum dipakai untuk menguji penulisan keymap atau
macro karena konfigurasi yang ada tidak dapat dibaca dahulu lalu dipulihkan.

### RGB per tombol dan streaming satu frame

Tambahkan objek `colors` ke profil, misalnya:

```json
{"esc":"#ff0000", "a":[0,255,0]}
```

Kemudian validasi dan kirim konfigurasi RGB per tombol tersimpan atau satu frame
real-time:

```bash
spade65ctl per-key-rgb spade65-profile.json --dry-run
spade65ctl per-key-rgb spade65-profile.json --confirm
spade65ctl stream-rgb spade65-profile.json --dry-run
spade65ctl stream-rgb spade65-profile.json --confirm
```

Tombol yang tidak ada dalam `colors` bernilai hitam/mati dalam frame yang
dihasilkan. Transport per-key dan streaming telah divalidasi melalui USB
berkabel. `stream-rgb` mengirim satu frame yang digerakkan host; efek AP
kontinu dan timeline kustom membutuhkan GUI atau service tetap aktif dan tidak
disimpan sebagai animasi firmware yang berjalan mandiri.

### Timer lampu dan sleep dongle

Perintah timer sengaja hanya mencari PID dongle `0356`:

```bash
spade65ctl sleep --light-off 10 --hibernate 30 --dry-run
spade65ctl sleep --light-off 10 --hibernate 30 --confirm
```

Nilai light-off yang valid adalah 1, 2, 5, 10, 15, 20, 25, atau 30 menit. Nilai
hibernation yang valid adalah 3, 5, 10, 15, 20, 25, 30, atau 60 menit. Report ini
belum diuji secara fisik karena dongle yang cocok tidak tersedia.

### Reset

Reset dapat menghapus pengaturan yang disimpan keyboard. Periksa paket dengan
dry-run terlebih dahulu dan gunakan acknowledgement tambahan hanya bila reset
benar-benar diperlukan:

```bash
spade65ctl reset --dry-run --i-understand-reset
spade65ctl reset --confirm --i-understand-reset
```

GUI memakai konfirmasi tambahan tertulis yang setara. Reset belum dikirim ke
keyboard yang tersedia karena tidak ada jalur readback/pemulihan keymap yang
terjamin.

## Mengimpor profil dari software original

Converter menerima wrapper JSON original yang memuat `Keyboard_Export`,
`Macro_Export`, dan `Light_Export`. Konversi berlangsung offline dan tidak
pernah meneruskan paket arbitrer dari file input:

```bash
spade65ctl vendor-import original.KeyAssign profile.json
spade65ctl vendor-import original.Macro profile.json \
  --base profile.json --force
spade65ctl vendor-import original.APMode profile.json \
  --base profile.json --force
spade65ctl profile validate profile.json
```

`--base` menggabungkan bagian vendor berikutnya ke profil native yang sudah ada,
sedangkan `--force` mengizinkan penggantian file output. Import tidak menulis ke
keyboard. Tinjau dan validasi profil hasil konversi sebelum perintah apply.

## Efek latar belakang dan asosiasi aplikasi

Buat konfigurasi service host, edit path profil dan asosiasi nama proses, lalu
jalankan:

```bash
spade65ctl service example spade65-service.json
spade65ctl service run spade65-service.json
```

Secara default, service hanya menjalankan efek AP dan timeline kustom. Service
dapat menjaga pencahayaan streaming host tetap aktif setelah GUI ditutup serta
memilih profil berdasarkan aplikasi aktif. Service tidak memiliki ikon tray.
Pada Wayland, yang tidak menyediakan API jendela foreground portabel, fallback
memilih rule pertama dengan proses yang sedang berjalan; urutan rule penting.

Penulisan keymap/profil otomatis nonaktif secara default. Mengaktifkannya
membutuhkan `"allow_profile_writes": true` dalam konfigurasi dan flag runtime
yang terpisah:

```bash
spade65ctl service run spade65-service.json \
  --allow-profile-writes
```

Buat, tetapi jangan langsung instal, file integrasi startup dengan:

```bash
spade65ctl service integration spade65-service.json launcher-output
```

Perintah ini membuat systemd user unit pada Linux, launcher Startup `.cmd` pada
Windows, atau LaunchAgent `.plist` pada macOS. Tinjau file hasilnya sebelum
memasang. Perilaku asosiasi lengkap dan batasan OS tersedia di [panduan fitur
host](host-features.md).

## Data yang tersimpan pada keyboard dan yang digerakkan host

Perintah untuk efek bawaan, debounce, timer, keymap, macro, dan konfigurasi RGB
per tombol tersimpan mengirim report konfigurasi vendor yang ditujukan bagi
perangkat. Pengaturan tersebut diharapkan tetap digunakan saat keyboard
dipindahkan ke sistem operasi lain, seperti pada software original. Fitur yang
melakukan streaming frame—efek AP, efek audio-reactive, timeline kustom, dan
asosiasi aplikasi—digerakkan host dan hanya bekerja selama GUI atau service
aktif.

Spade65 tidak dapat membaca seluruh keymap, macro, atau setiap pengaturan saat
ini kembali dari keyboard dengan aman. Profil tersimpan dan backup library GUI
karena itu menjadi sumber pemulihan, bukan asumsi readback firmware.

## Penanganan masalah

### `Spade65 not found`

Pada Linux, periksa identitas USB yang dikenal:

```bash
lsusb -d 0603:0351
lsusb -d 0603:0356
```

Sambungkan ulang kabel atau dongle dan jalankan `spade65ctl probe` lagi. Jika
unit produksi memakai VID/PID berbeda, simpan informasi USB serta descriptor
sebelum mengubah konstanta source; perangkat tersebut mungkin merupakan revisi
hardware lain.

### `Permission denied: /dev/hidrawN`

Pasang udev rule, sambungkan ulang perangkat, dan periksa node sebagai pengguna
biasa:

```bash
getfacl /dev/hidrawN
```

### `report length mismatch` atau kegagalan validasi descriptor

Jangan paksa penulisan dan jangan menambahkan fallback raw HID arbitrer. Simpan
output `spade65ctl probe --json` lalu bandingkan dengan descriptor yang telah
diverifikasi. Perbedaan dapat menandakan interface yang salah atau revisi
firmware/hardware yang belum didukung.

### Port 8765 sudah dipakai

Peluncuran GUI kedua yang normal seharusnya mengaktifkan jendela pertama. Jika
port dimiliki program lain, hentikan sendiri program tersebut atau pilih port
lokal lain secara eksplisit:

```bash
spade65ctl gui --port 8875
```

Spade65 tidak pernah menghentikan atau mengambil alih listener yang tidak
terkait.

### Jendela desktop Linux kosong atau menampilkan error EGL/grafis

Gunakan AppImage terbaru. Sebagai fallback yang tidak bergantung renderer,
jalankan:

```bash
./Spade65-Linux-x86_64.AppImage gui --no-browser
```

Kemudian buka `http://127.0.0.1:8765/` pada browser yang sudah ada. Catatan
Wayland dan runtime khusus distribusi tersedia di [panduan lintas
platform](cross-platform.md).

### Keyboard berhenti merespons sementara

Hentikan service streaming, lalu cabut dan sambungkan kembali kabel atau dongle.
Jangan mengulang perintah reset dan jangan mencoba file firmware hasil ekstraksi
dari installer resmi. Catat perintah serta output `probe --json` sebelum membuat
issue.

### Executable yang dibuka dari file manager tidak menampilkan error

Kegagalan startup ditampilkan melalui notifikasi/dialog desktop yang tersedia
dan ditulis ke log pengguna:

- Windows: `%LOCALAPPDATA%\Spade65\Logs\launcher.log`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/spade65/launcher.log`
- macOS: `~/Library/Logs/Spade65/launcher.log`

Jalankan executable CLI dari terminal bila output perintah perlu tetap terlihat.

## Dokumentasi lanjutan

- [Instalasi lintas platform dan perilaku runtime](cross-platform.md)
- [Detail service host, import, timeline, dan backup](host-features.md)
- [Hasil verifikasi hardware](hardware-verification.md)
- [Audit kesetaraan fitur](parity.md)
- [Riset protokol](protocol.md)
- [Panduan pengembangan](development.md)

Detail internal protokol dan pengembangan sengaja berada dalam dokumen khusus
tersebut agar panduan ini tetap berfokus pada alur pengguna yang aman.
