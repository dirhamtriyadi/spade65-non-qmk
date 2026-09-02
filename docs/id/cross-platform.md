[English](../cross-platform.md) · **Bahasa Indonesia**

# Dukungan lintas platform

## Status

| Platform | Discovery dan write | Renderer desktop v0.7.0 | Penangkapan output sistem pada paket | Aplikasi aktif | Background launcher | Validasi fisik |
|---|---|---|---|---|---|---|
| Linux | `hidraw` + sysfs | PySide6/QtWebEngine | SoundCard dengan monitor PipeWire/PulseAudio | X11, fallback proses Wayland | systemd user | Ya, USB `0603:0351` |
| Windows | HIDAPI / Win32 HID | Edge WebView2 | `pysysaudio` WASAPI loopback | Win32 foreground window | Startup `.cmd` | Belum diuji pada mesin Windows |
| macOS | HIDAPI / IOKit | Cocoa/WebKit | CoreAudio tap `pysysaudio` (macOS 14.2+) | System Events frontmost process | LaunchAgent `.plist` | Belum diuji pada mesin macOS |

GUI, profile compiler, macro, konverter vendor, AP renderer, timeline, dan aturan
keselamatan memakai source yang sama pada seluruh OS. Windows/macOS tidak memakai
`/dev/hidraw` atau sysfs. Jendela desktop memakai PyWebView sebagai shell native,
tetapi isi antarmukanya tetap HTML, CSS, dan JavaScript lokal yang sama dengan
mode browser; kontrolnya bukan widget native penuh.

Workflow CI menjalankan unit test pada Ubuntu, Windows, dan macOS untuk Python
3.10 serta 3.13. Ini memverifikasi import, compiler, transport simulasi, service,
dan launcher pada OS tersebut. Setiap push ke `main` juga menjalankan package
preflight native: ZIP Windows, AppImage Linux pada Ubuntu 22.04, dan DMG macOS
universal dibangun serta di-smoke-test tanpa dipublikasikan. Status fisik tetap
dipisahkan pada tabel di atas.

Selector sumber aplikasi desktop terpaket memprioritaskan jalur output sistem
native tersebut dan juga menawarkan input mikrofon sebagai fallback eksplisit.
Mode browser saja tidak memiliki bridge native sehingga dapat memakai mikrofon,
tetapi tidak dapat menangkap output sistem secara langsung. Implementasi
penangkapan dan import dependency diuji secara otomatis. Penangkapan monitor
Linux juga diuji pada 2026-09-02 memakai nada sistem 125 Hz dan mengidentifikasi
pita dominan yang benar. Output Windows dan macOS masih memerlukan uji fisik;
kolom validasi fisik pada tabel lainnya mengacu pada transport keyboard.

Tag rilis `vMAJOR.MINOR.PATCH` juga menjalankan build native per OS dan, hanya
jika semuanya berhasil, memublikasikan:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Paket tersebut sudah berisi runtime aplikasi; pengguna tidak perlu clone
repository atau menjalankan Python. Detail pipeline dan cara membuat tag ada di
[`releasing.md`](releasing.md).

## Instalasi

### Paket desktop

Unduh asset yang sesuai dari GitHub Releases.

- Windows x64: ekstrak ZIP sepenuhnya, lalu jalankan `Spade65.exe` untuk GUI.
  Gunakan `Spade65CLI.exe` dari terminal untuk command CLI beserta output/error
  console yang terlihat, misalnya `Spade65CLI.exe probe`. Jendela standalone
  memerlukan Microsoft Edge WebView2 Runtime; instalasi Windows 10/11 yang
  mutakhir biasanya sudah menyediakannya. Bila runtime tidak tersedia, launcher
  membuka GUI di browser default.
- Linux x86_64: beri izin eksekusi dengan
  `chmod +x Spade65-Linux-x86_64.AppImage`, lalu jalankan file tersebut. Jika
  FUSE tidak tersedia, gunakan
  `APPIMAGE_EXTRACT_AND_RUN=1 ./Spade65-Linux-x86_64.AppImage`. AppImage desktop
  membundel PySide6/QtWebEngine sehingga ukurannya lebih besar dan membutuhkan
  sesi grafis. Asset resmi dibangun serta di-smoke-test pada Ubuntu 22.04 x86_64
  (glibc 2.35), yang menjadi baseline dukungan. Distribusi yang lebih baru
  biasanya kompatibel; jalankan `--smoke-test` untuk memverifikasi paket pada
  distribusi lain.
- macOS Intel/Apple Silicon: buka DMG, lalu salin `Spade65.app` ke
  `Applications`. Bundle universal diperiksa agar native binary-nya memiliki
  slice `x86_64` dan `arm64`. Jendela memakai Cocoa/WebKit sistem. Bundle
  mendukung penangkapan output sistem langsung pada macOS 14.2 atau lebih baru
  dan dapat menampilkan prompt izin perekaman audio sistem; pemilihan fallback
  mikrofon dapat menampilkan prompt izin mikrofon secara terpisah. Kedua izin
  tidak diminta sampai sumber audio-reactive digunakan.

Tanpa argumen, paket membuka GUI lokal `http://127.0.0.1:8765/` di jendela
standalone. Peluncuran kedua memverifikasi token sesi lalu mengaktifkan,
menampilkan, dan memulihkan jendela yang sudah ada. Perintah eksplisit `gui`
melewati coordinator yang sama, sehingga invocation kedua tidak gagal dengan
`Address already in use`. Port diklaim sebelum renderer dimuat dan request
aktivasi yang datang selama startup ditunda sampai jendela siap. Layanan asing
di port 8765 tidak pernah dihentikan atau diambil alih; startup gagal dengan
pesan yang jelas. Bila **Pengaturan → Integrasi desktop → Tetap berjalan di
system tray** aktif dan desktop menyediakan tray, menutup jendela hanya
menyembunyikannya tanpa menghentikan server localhost. **Open Spade65**
memulihkannya; **Quit Spade65** pada tray atau **Keluar dari aplikasi** di GUI
menghentikan proses. Bila sesi Linux tidak menyediakan tray, opsi dinonaktifkan
dan menutup jendela akan keluar secara normal. Mode browser berbeda: menutup tab
tidak menghentikan server; gunakan **Keluar dari aplikasi** atau akhiri proses
terminal.

Executable Linux/macOS juga menerima command CLI; misalnya AppImage dapat
dijalankan dengan argumen `probe`. Pada Windows gunakan `Spade65CLI.exe` agar
output CLI tidak hilang di executable GUI tanpa console. Untuk memilih mode GUI
secara eksplisit gunakan subcommand `gui --browser` atau `gui --no-browser`
melalui executable CLI.

Executable GUI yang dibuka lewat file manager tidak selalu mempunyai terminal.
Dalam keadaan itu output/error ditulis ke log berikut dan startup failure juga
ditampilkan melalui dialog/notifikasi native yang tersedia:

- Windows: `%LOCALAPPDATA%\Spade65\Logs\launcher.log`;
- Linux: `${XDG_STATE_HOME:-~/.local/state}/spade65/launcher.log`;
- macOS: `~/Library/Logs/Spade65/launcher.log`.

Layout Keyboard dan Lighting memakai satu state. Bila interface konfigurasi
terdeteksi, aplikasi memulihkan pilihan host terakhir untuk Spade65; USB `0351`
dan dongle `0356` dianggap dua transport untuk model yang sama. Bila tidak ada
interface konfigurasi yang terdeteksi — termasuk saat hanya receiver hanya-baca
`0603:0352` yang terpasang — kedua preview memakai default Noir Spade65-04 ANSI
standard dan selector dinonaktifkan sementara. Firmware/descriptor tidak
menyediakan varian geometri, sehingga aplikasi tidak mengklaim membaca layout
fisik dari keyboard.
Frontend memeriksa perubahan koneksi setiap dua detik dan menyinkronkan kedua
preview otomatis tanpa mengubah isi editor profil yang sedang dikerjakan.

PyWebView memakai profil storage khusus aplikasi dengan `private_mode=False`.
Data `localStorage` untuk bahasa, layout, dan profil bertahan pada lokasi berikut:

- Windows: `%LOCALAPPDATA%\Spade65\WebView`;
- Linux: `${XDG_DATA_HOME:-~/.local/share}/spade65/webview`;
- macOS: default website data store Cocoa WebKit yang persisten dan dikelola OS
  untuk bundle ID `io.github.dirhamtriyadi.spade65`; backend ini tidak mengekspos
  custom path melalui pywebview.

Preferensi close-to-tray adalah state shell native, bukan data WebView. File-nya
berada di `${XDG_CONFIG_HOME:-~/.config}/spade65/desktop-settings.json` pada
Linux, `%APPDATA%\Spade65\desktop-settings.json` pada Windows, dan
`~/Library/Application Support/Spade65/desktop-settings.json` pada macOS.

Mode browser memakai storage profil browser dan tidak otomatis berbagi data
dengan WebView. Gunakan backup/restore library untuk memindahkannya. Download
ekspor profil dan backup JSON diizinkan di jendela standalone.

Paket Windows belum memiliki code signature. Aplikasi macOS hanya memiliki
ad-hoc signature dan belum dinotarization, sehingga SmartScreen atau Gatekeeper
dapat menampilkan peringatan. Pastikan file berasal dari release project yang
dipercaya. Instalasi source di bawah tetap menjadi fallback.

Linux tetap membutuhkan rule udev repository agar user biasa dapat membuka
`hidraw`. AppImage resmi hanya membundel transport `hidraw` yang diverifikasi;
override HIDAPI untuk eksperimen tetap dapat dipasang dari source melalui extra
`cross-platform`, tetapi tidak menjadi bagian dari AppImage. Kebutuhan izin
Automation/Accessibility macOS untuk association aplikasi juga tetap berlaku
pada paket desktop. Izin audio sistem macOS hanya relevan saat output sistem
dipilih bagi efek audio-reactive, sedangkan izin mikrofon hanya relevan bagi
fallback mikrofon. Localhost tidak mengekspos server ke jaringan eksternal.

Untuk efek langsung, selector sumber juga menyediakan sensitivitas 200–8000
(default 1000), noise gate, smoothing, dan respons spektrum, bass, atau
keras-lembut keseluruhan. Opasitas lapisan diterapkan sebelum lapisan
dikomposisikan; kecerahan utama menskalakan frame yang sudah selesai. Reaksi
audio berkelanjutan memerlukan GUI dan Pratinjau langsung tetap aktif melalui
USB berkabel `0603:0351`. Efek tidak disimpan di keyboard dan tidak ditangani
oleh background service. PCM mentah native tetap berada di worker penangkapan:
hanya nilai tingkat, puncak, dan pita yang ringkas yang melewati bridge desktop
lokal, dan tidak ada audio yang disimpan.

### Instalasi dari source

Untuk CLI saja, Linux tidak memerlukan package runtime tambahan:

```bash
python -m pip install -e .
```

Pasang extra desktop untuk jendela PySide6/QtWebEngine pada Linux:

```bash
python -m pip install -e ".[desktop]"
python -m spade65 gui
```

Windows dan macOS memerlukan HIDAPI 0.14 atau lebih baru agar report descriptor
dapat dibaca sebelum write. Gabungkan kedua extra untuk GUI standalone:

```bash
python -m pip install -e ".[cross-platform,desktop]"
python -m spade65 probe
python -m spade65 gui
```

Untuk instalasi source pada Windows atau macOS, penangkapan output sistem
langsung saat ini memerlukan Python 3.10–3.12 karena wheel native `pysysaudio`
yang dipin belum mendukung Python 3.13. Paket Windows dan macOS resmi memakai
Python 3.12.10. Dengan interpreter source lebih baru yang belum didukung, bagian
GUI lain tetap berjalan dan fallback mikrofon eksplisit tetap tersedia.
Penangkapan output sistem Linux memakai SoundCard dan tidak memiliki batasan
Python 3.12 tersebut.

Pada seluruh OS, `python -m spade65 gui` memilih jendela desktop secara default
dan beralih ke browser bila runtime native tidak dapat dimuat. Gunakan
`python -m spade65 gui --browser` untuk selalu membuka browser atau
`python -m spade65 gui --no-browser` untuk menjalankan server saja.

### Troubleshooting Wayland dan rolling distribution

AppImage v0.7.2 dan seterusnya memakai runtime C++, grafis, audio, serta font
milik host agar tetap cocok dengan driver dan konfigurasi distro. Rilis lama
dapat gagal pada EndeavourOS/Arch dengan pesan `CXXABI not found`, `EGL not
available`, atau error Fontconfig. Gunakan rilis terbaru; sebagai fallback
aman untuk v0.7.1, jalankan server tanpa membuka proses desktop lain:

```bash
./Spade65-Linux-x86_64.AppImage gui --no-browser
```

Lalu buka alamat `http://127.0.0.1:8765/` secara manual di browser. Jangan
membakukan workaround `LD_PRELOAD` di launcher karena lokasi dan ABI library
berbeda antar-distribusi; perbaikan produksi berada di isi AppImage v0.7.2.

Apabila descriptor suatu collection tidak dapat dibaca, `probe` dapat tetap
menampilkannya tetapi command write menolak collection tersebut. VID/PID saja
tidak pernah cukup untuk melewati validasi.

GUI pada semua paket menyediakan English sebagai bahasa default dan Bahasa
Indonesia sebagai pilihan. Preference bahasa tersimpan lokal di profil WebView
khusus aplikasi, atau di profil browser ketika fallback dipakai; lihat
[`localization.md`](localization.md) untuk struktur yang dapat diperluas.

## Startup GUI setelah login

Halaman Pengaturan native dapat mengaktifkan **Jalankan setelah login** bagi
pengguna saat ini. Aplikasi menulis satu launcher native OS milik pengguna dan
menjalankan release yang sama dengan `gui --start-hidden`:

- Linux: `${XDG_CONFIG_HOME:-~/.config}/autostart/io.github.dirhamtriyadi.spade65.desktop`;
- Windows: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\spade65-gui.cmd`;
- macOS: `~/Library/LaunchAgents/io.github.dirhamtriyadi.spade65.gui.plist`.

Menonaktifkan switch hanya menghapus launcher Spade65 tersebut. Pindahkan
AppImage, direktori hasil ekstraksi Windows, atau aplikasi macOS ke lokasi
permanen sebelum mengaktifkannya. Bila lokasi aplikasi kemudian berubah,
Pengaturan menandai launcher lama agar dapat dinonaktifkan lalu diaktifkan lagi.
Startup tersembunyi hanya diterima pada mode desktop native. Bila tray Linux
hilang di antara sesi, aplikasi menampilkan jendela agar proses tidak berjalan
tanpa dapat diakses.

Fitur ini menjalankan shell GUI dan terpisah dari service di bawah. Gunakan
service bila playback AP/timeline atau asosiasi aplikasi harus tetap berjalan
secara independen dari WebView.

## Startup background service

Untuk pengguna release, buka **Pengaturan → Layanan latar belakang**. GUI yang
sudah dipaketkan mendeteksi Linux, Windows, atau macOS dan menampilkan perintah
yang memakai executable release aktif. Pembuatan konfigurasi dipisahkan dari
aktivasi startup agar contoh path proses dan profil dapat diedit terlebih dahulu.
Pindahkan paket release ke lokasi permanen sebelum menjalankan perintah tersebut.

Bentuk `spade65ctl` berikut hanya untuk instalasi dari source atau paket Python.
Buat config service, lalu buat launcher untuk OS yang sedang digunakan:

```bash
spade65ctl service example spade65-service.json
spade65ctl service integration spade65-service.json launcher-output
```

- Linux: salin unit ke `~/.config/systemd/user/`, kemudian enable sebagai user.
- Windows: letakkan `.cmd` di folder Startup pengguna.
- macOS: letakkan `.plist` di `~/Library/LaunchAgents/`, lalu muat dengan
  `launchctl` pada sesi pengguna.

Generator hanya menulis file output yang diminta; tidak mengubah startup OS
secara otomatis. Pada macOS, asosiasi aplikasi dapat memerlukan izin
Automation/Accessibility untuk membaca aplikasi frontmost. Lihat [panduan fitur
host](host-features.md) untuk path khusus release, alur aktivasi, dan kontrol
keamanannya.

## Data persisten dan data host

Report keymap, macro, efek bawaan/per-key, debounce, dan timer dongle ditujukan
ke konfigurasi internal perangkat seperti software resmi. Setting tersebut tidak
memerlukan background service setelah diterapkan. Profil bernama, asosiasi
aplikasi, AP/streaming animation, dan custom timeline adalah data host; efeknya
memerlukan GUI atau service tetap berjalan. Efek langsung audio-reactive juga
merupakan data host, tetapi secara khusus memerlukan GUI karena service tidak
pernah membuka sumber audio sistem atau mikrofon.

Pada setiap OS, apply keymap menyelesaikan collection utama dan companion pendek
yang digerbangi descriptor serta membuka kedua handle sebelum menulis. Handle
utama tetap terbuka saat mengirim keymap, macro yang direferensikan, dan
lighting saat ini/tersimpan; handle pendek terpisah mengirim debounce per profil
sesuai urutan aplikasi original. Mode kabel berakhir setelah debounce;
transaksi ini tidak pernah mengirim timer dongle.

Keymap tiga layer dan macro sementara telah diterapkan pada unit berkabel
`0603:0351` dan diverifikasi melalui input fisik, lalu keymap default dan macro
kosong diterapkan ulang untuk memulihkannya. Persistensi melalui power-cycle
tetap belum diukur. Perangkat tidak menyediakan readback, sehingga profil
tersimpan tetap menjadi satu-satunya jalur restore. Jalur report individual
memiliki bukti hardware, tetapi pemeliharaan visual lighting setelah transaksi
gabungan yang baru dilengkapi masih menunggu konfirmasi. Firmware flashing,
bootloader, raw flash, dan arbitrary HID tidak diimplementasikan pada OS mana pun.
Paket desktop maupun build lokal tidak memiliki jalur tersembunyi untuk operasi
tersebut.
