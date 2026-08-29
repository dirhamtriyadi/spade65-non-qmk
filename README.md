# spade65-non-qmk

Utilitas lintas platform untuk mengatur keyboard **Noir Spade65 non-QMK** tanpa
bergantung pada software Windows resmi.

Proyek ini dibuat melalui analisis statis installer resmi `Spade65_SETUP_20240403.exe`. Jalur USB telah diuji bertahap pada unit fisik; fitur yang belum diuji tetap ditandai secara eksplisit di bawah.

## Status

| Fitur | Implementasi | Diuji pada hardware |
|---|---:|---:|
| Deteksi USB dan dongle | Linux hidraw + Windows/macOS HIDAPI | Ya, Linux mode USB `0603:0351` |
| Membaca HID report descriptor | Ya | Ya, mode USB `0603:0351` |
| Efek RGB bawaan | Ya | Ya, `fixed` via USB |
| Brightness dan speed RGB | Ya | Ya, via USB |
| Debounce | Ya | Ya, 5 ms via USB |
| Timer lampu/sleep untuk dongle | Ya | Belum |
| Reset pengaturan | Ya, dengan konfirmasi tambahan | Belum |
| Remap tombol/layer | Ya, seluruh kategori assignment vendor + tiga layer | Belum |
| Macro | Ya, maksimal 10 macro/84 event, recorder, repeat dan binding | Belum |
| Per-key RGB | Ya, tersimpan dan streaming | Ya, mode USB `0603:0351` |
| GUI lokal | Ya, jendela desktop PyWebView; HTML/CSS/JS lokal dengan fallback browser | Ya, browser lokal + deteksi hardware Linux |
| Animasi app/AP mode | Ya, 10 pola/layer + range, palet, parameter lanjut dan audio | Streaming USB tervalidasi |
| Custom timeline | Ya, 200 frame + playback/background streaming | Service mengirim frame via USB |
| Import file vendor | Ya, KeyAssign/Macro/APMode JSON | Diuji offline |
| Asosiasi aplikasi/background service | Linux, Windows, dan macOS | Seleksi tiap platform diuji; output service via USB Linux |
| Informasi read-only | USB revision + baterai jika diekspos OS | Ya, tanpa HID write |
| Firmware/raw flash/bootloader | Sengaja tidak diimplementasikan | Tidak; risiko brick |

Fitur konfigurasi keyboard yang aman dari aplikasi vendor sudah tersedia melalui
CLI dan GUI. Asosiasi profil Windows `RELATEDPROGRAM` digantikan service host
opt-in pada Linux, Windows, dan macOS. Updater aplikasi, login, dan telemetri vendor tidak direplikasi karena
bukan konfigurasi keyboard. Tidak ada endpoint, builder paket, atau fallback raw
HID untuk flash firmware dan bootloader.

Matriks audit terhadap halaman dan backend software original tersedia di
[`docs/parity.md`](docs/parity.md). Komponen generik yang tersembunyi, dikomentari,
atau tidak pernah diserialisasi oleh backend Jupeng tidak dihitung sebagai fitur
Spade65 aktif.

## Persyaratan

- Python 3.10 atau lebih baru.
- Linux: `hidraw` dan `sysfs` standar untuk CLI; extra `desktop` memasang
  PySide6/QtWebEngine untuk jendela desktop. Runtime native memakai library
  C++, Mesa/GBM, X11/Wayland, ALSA, dan font milik host; desktop Linux normal
  biasanya sudah menyediakannya (`libegl1` adalah loader EGL Debian/Ubuntu).
- Windows/macOS: package `hidapi` melalui extra `cross-platform`; gabungkan
  dengan extra `desktop` untuk GUI standalone dari source.
- Windows memerlukan Microsoft Edge WebView2 Runtime. Windows 10/11 yang mutakhir
  biasanya sudah memilikinya; bila runtime tidak tersedia, GUI beralih ke
  browser default.

Persyaratan Python di atas hanya berlaku untuk instalasi dari source. Setelah
workflow tag berhasil, pengguna dapat mengunduh paket siap jalan dari halaman
GitHub Releases:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Ketiga paket dibuat otomatis pada runner OS masing-masing ketika tag semantik,
misalnya `v0.7.0`, dikirim. Versi tag harus sama dengan versi project. Paket
Windows belum ditandatangani dan aplikasi macOS baru memiliki ad-hoc signature,
belum Developer ID/notarization; SmartScreen atau Gatekeeper karena itu dapat
menampilkan peringatan. Lihat [panduan rilis](docs/releasing.md) dan
[panduan lintas platform](docs/cross-platform.md) untuk instalasi, verifikasi,
serta fallback menjalankan dari source.

AppImage desktop membundel PySide6/QtWebEngine dan karena itu lebih besar daripada
rilis browser-only. Asset Linux resmi dibangun dan di-smoke-test pada runner
Ubuntu 22.04 x86_64 (glibc 2.35); itulah baseline Linux yang didukung. Distribusi
yang lebih baru biasanya kompatibel, tetapi kompatibilitas tidak disimpulkan
hanya dari nomor glibc. Pada macOS, jendela memakai Cocoa/WebKit sistem; bundle
mengizinkan koneksi localhost dan meminta izin mikrofon hanya ketika efek
audio-reactive diaktifkan.

Build tanpa CI juga didukung pada komputer target dengan
`python packaging/build.py`; command ini memakai script dan smoke test native
yang sama dengan GitHub Actions serta menulis file bernama sama ke `artifacts/`.
Portabilitas AppImage hasil build manual mengikuti OS/glibc mesin build; gunakan
asset resmi bila membutuhkan baseline Ubuntu 22.04.
Setiap push ke `main` juga menjalankan package preflight native terpisah untuk
Windows, Linux, dan macOS tanpa memublikasikan release; workflow tag membangun
ulang ketiganya dari commit tag sebelum publish.
ZIP Windows berisi `Spade65.exe` untuk GUI dan `Spade65CLI.exe` untuk command
terminal dengan output yang terlihat. Menjalankan aplikasi paket tanpa argumen
membuka jendela standalone. Peluncuran kedua mengaktifkan dan memulihkan jendela
yang sudah ada; subcommand `gui` memakai coordinator instance yang sama sehingga
tidak lagi mencoba membuka port 8765 untuk kedua kalinya. Jika startup gagal
ketika executable dibuka tanpa terminal, aplikasi menampilkan dialog/notifikasi
dan menulis log diagnostik pengguna. Menutup jendela atau memilih **Quit
application** menghentikan server localhost; aplikasi tidak memiliki system tray
atau mode minimize-to-tray.

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

Pada Windows atau macOS:

```bash
python -m pip install -e ".[cross-platform,desktop]"
spade65ctl probe
spade65ctl gui
```

Untuk jendela desktop dari source pada Linux:

```bash
python -m pip install -e ".[desktop]"
spade65ctl gui
```

Detail backend, izin, serta status pengujian setiap OS tersedia di
[`docs/cross-platform.md`](docs/cross-platform.md).

## Izin hidraw Linux melalui udev

Pasang rule yang tersedia dalam repository:

```bash
sudo install -Dm644 udev/99-spade65.rules /etc/udev/rules.d/99-spade65.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Cabut dan pasang kembali keyboard/dongle setelah itu. Jalankan CLI sebagai user biasa; jangan memakai `sudo` kecuali hanya untuk diagnosis izin.

AppImage resmi menggunakan backend `hidraw` dan tidak membundel HIDAPI yang
tidak diperlukan di Linux. Override HIDAPI tetap tersedia untuk instalasi dari
source dengan extra `cross-platform`.

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

### GUI desktop dan browser

```bash
python spade65ctl.py gui
python spade65ctl.py gui --browser
python spade65ctl.py gui --no-browser
```

Mode default membuka `http://127.0.0.1:8765/` di jendela PyWebView standalone.
Jika extra/runtime desktop tidak dapat dimuat, aplikasi menjelaskan kegagalannya
di stderr lalu otomatis membuka browser default. `--browser` memilih browser
secara eksplisit, sedangkan `--no-browser` hanya menjalankan server localhost
untuk otomasi atau akses manual. GUI tetap dibuat dengan HTML, CSS, dan
JavaScript di dalam WebView—bukan kumpulan widget native penuh—sementara backend
dan asset tetap lokal. Server hanya menerima koneksi loopback dan setiap API
call memerlukan token sesi acak; `Host` asing dan `Origin` browser yang tidak
sesuai ditolak untuk mencegah DNS rebinding ke server lokal.

GUI menyediakan pemilihan device, editor tiga layer dengan geometri asli empat
varian Spade65 (ANSI/ISO dan standard/split spacebar), seluruh kategori
assignment vendor, macro recorder, import/export profil, seluruh efek RGB
bawaan, warna per-key, kompositor 10 layer animasi streaming dengan parameter
original, audio reactive, debounce, timer dongle, reset, serta diagnostics.
Ekspor profil dan backup library memakai dialog Save native pada Linux/macOS,
handler download WebView2 pada Windows, serta download biasa ketika GUI sengaja
dijalankan di browser.

Pemilih layout tersedia dan selalu sinkron pada halaman Keyboard serta Lighting.
Saat interface konfigurasi Spade65 terdeteksi, GUI otomatis memulihkan layout
yang terakhir dipilih secara lokal untuk model itu (USB dan dongle berbagi
pilihan). Saat perangkat tidak terdeteksi, preview kembali ke layout default Noir
`Spade65-04 · ANSI standard` tanpa menimpa pilihan tersimpan. Ini bukan readback
firmware: software original juga menyimpan `layouttype` sebagai preferensi host,
karena descriptor keyboard tidak membedakan keempat geometri tersebut.
Perubahan koneksi diperiksa ringan setiap dua detik, sehingga kedua halaman ikut
beralih otomatis saat keyboard disambungkan atau dilepas tanpa perlu reload GUI.

Antarmuka tersedia dalam English dan Bahasa Indonesia. English adalah bahasa
default; pilihan bahasa, layout, dan profil tersimpan memakai profil WebView
khusus aplikasi sehingga bertahan setelah jendela ditutup. Mode browser memakai
storage milik browser dan karena itu terpisah. Katalog dipisahkan per bahasa agar
bahasa baru dapat ditambahkan tanpa mengubah protokol atau backend. Panduan
kontributor tersedia di [`docs/localization.md`](docs/localization.md).

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
profil menurut aplikasi aktif di Linux, Windows, atau macOS. Write keymap otomatis nonaktif secara default dan
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
- `--device PATH` memakai path yang ditampilkan `probe` jika lebih dari satu Spade65 terhubung

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
- [docs/cross-platform.md](docs/cross-platform.md) — instalasi dan batas validasi per OS.
- [docs/releasing.md](docs/releasing.md) — build desktop dan rilis otomatis dari tag.
- [docs/localization.md](docs/localization.md) — struktur katalog dan cara menambah bahasa.
- [tools/extract_asar.py](tools/extract_asar.py) — extractor minimal untuk arsip Electron ASAR.
- [tools/deobfuscate_jupeng.py](tools/deobfuscate_jupeng.py) — resolver tabel string modul protokol vendor.

## Catatan hukum dan keselamatan

Repository tidak menyertakan installer, firmware, source vendor hasil ekstraksi, atau binary native vendor. Gunakan proyek ini hanya pada perangkat milik sendiri. Firmware update sengaja berada di luar scope sampai recovery procedure dan hardware revision dapat diverifikasi.

## Lisensi

Kode asli dalam repository ini menggunakan lisensi MIT. Runtime desktop
membundel atau memakai komponen third-party dengan ketentuan lisensinya
masing-masing, termasuk
[pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE.md),
[Qt for Python/PySide6](https://doc.qt.io/qtforpython-6/licenses.html),
[Microsoft Edge WebView2](https://www.microsoft.com/legal/webview2terms), dan
[PyObjC](https://github.com/ronaldoussoren/pyobjc/blob/main/LICENSE.txt).
Daftar versi, copyright, source, dan petunjuk penggantian library tersedia di
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) dan disertakan dalam setiap
paket rilis.
Salinan teks [GPL-3.0](licenses/GPL-3.0.txt) dan
[LGPL-3.0](licenses/LGPL-3.0.txt) juga tersedia di repository untuk komponen Qt
yang didistribusikan berdasarkan pilihan lisensi tersebut.
Software, firmware, nama merek, dan asset vendor tetap menjadi milik pemegang
hak masing-masing.
