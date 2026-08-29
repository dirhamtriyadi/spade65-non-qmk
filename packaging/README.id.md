# Packaging rilis

[English](README.md) · **Bahasa Indonesia**

Mengirim tag `vMAJOR.MINOR.PATCH` akan menjalankan
`.github/workflows/release.yml`. Tag harus sama dengan `project.version` di
`pyproject.toml`; ketidaksesuaian akan menghentikan rilis. Workflow menguji
source, melakukan build pada setiap sistem operasi target, dan memublikasikan
persis asset GitHub Release berikut:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Workflow dispatch manual dapat melanjutkan atau mengganti asset pada draft yang
belum dipublikasikan untuk tag yang sudah ada. Workflow sengaja menolak menimpa
rilis yang sudah dipublikasikan. Proses untuk tag yang sama dijalankan secara
berurutan agar pembuatan draft dan upload tidak saling bertabrakan.

Mulai v0.7.0, launcher frozen `Spade65` menjalankan GUI localhost yang
diautentikasi pada port 8765 di dalam jendela PyWebView mandiri. Antarmukanya
tetap menggunakan HTML, CSS, dan JavaScript lokal dari repository—bukan ditulis
ulang sebagai widget native sepenuhnya. Jika WebView platform tidak dapat
dimuat, launcher melaporkan kegagalannya lalu beralih ke browser default.

Peluncuran kedua aplikasi paket memverifikasi token Spade65 yang sudah berjalan,
memanggil route aktivasi yang diautentikasi, memulihkan jendela yang sudah ada,
lalu keluar, alih-alih gagal karena port terpakai. Perintah eksplisit `gui`
memakai coordinator yang sama. Kepemilikan port diklaim sebelum inisialisasi
WebView, dan aktivasi yang tiba selama startup akan diantrekan sampai jendela
tersedia. Service asing pada port 8765 tidak pernah dihentikan atau dianggap
sebagai Spade65. Menutup jendela desktop atau memakai **Quit application** akan
menutup jendela dan server localhost. Tidak ada ikon tray atau proses
minimize-to-tray. Dalam mode browser, menutup tab saja membiarkan server tetap
berjalan sampai **Quit application**, Ctrl+C, atau proses dihentikan.

Proses berjendela tanpa console menulis stdout/stderr ke log launcher per
pengguna dan menampilkan error startup native secara best-effort. Lokasi root
log adalah `%LOCALAPPDATA%\Spade65\Logs` pada Windows,
`${XDG_STATE_HOME:-~/.local/state}/spade65` pada Linux, dan
`~/Library/Logs/Spade65` pada macOS.

PyWebView memakai profil persisten khusus aplikasi. Ekspor profil dan backup
library memakai bridge dialog Save native pada Linux/macOS; Windows memakai
handler download WebView2 pada UI thread, dan mode browser eksplisit tetap
memakai download biasa. Lokasi penyimpanan khususnya adalah
`%LOCALAPPDATA%\Spade65\WebView` pada Windows dan
`${XDG_DATA_HOME:-~/.local/share}/spade65/webview` pada Linux. Pada macOS, Cocoa
WebKit menyimpan default website data store di lokasi yang dikelola OS untuk
bundle ID `io.github.dirhamtriyadi.spade65`; pywebview tidak menyediakan path
khusus untuk backend tersebut. Mode browser memiliki profil penyimpanan terpisah
yang dikelola browser; backup/restore menjadi penghubung portabel di antara
keduanya.

Linux dan macOS meneruskan argumen CLI ke executable paket. ZIP Windows berisi
`Spade65.exe` berjendela untuk GUI dan `Spade65CLI.exe` berbasis console agar
output serta error CLI terlihat. Flag CLI `gui --browser` memaksa mode browser;
`gui --no-browser` hanya menjalankan server loopback.

## Build lokal

Pasang lebih dahulu dependency HID, desktop, dan build:

```sh
python -m pip install -r requirements-build.txt ".[cross-platform,desktop]"
python -m pip check
```

Pada host build Debian/Ubuntu, pasang juga loader EGL yang digunakan ketika
backend QtWebEngine paket diimpor oleh smoke test headless:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  libegl1 libgl1 libxcb-shape0 libxcb-image0 libxcb-xkb1 libxcb-icccm4 \
  libxkbcommon-x11-0 libxcb-util1 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-render-util0 curl coreutils
```

Gunakan paket EGL, curl, dan utilitas SHA-256 yang setara pada distribusi Linux
lain. Desktop grafis normal sering kali sudah menyediakan EGL, tetapi build kini
menyatakan dependency ini secara eksplisit alih-alih bergantung pada asumsi
tersebut.

Untuk instalasi source editable yang tidak membuat artifact rilis, Linux dapat
memakai `python -m pip install -e ".[desktop]"`; Windows dan macOS memakai
`python -m pip install -e ".[cross-platform,desktop]"`. Instalasi dasar tetap
dapat menjalankan `gui --browser` atau `gui --no-browser` tanpa extra desktop
native.

Lakukan build pada komputer target dengan satu perintah lintas platform.
Perintah ini otomatis memilih script native dan memakai interpreter Python yang
sama dengan interpreter yang menjalankannya:

```sh
python packaging/build.py
```

Jalur ini tidak memerlukan GitHub Actions. Hasilnya memakai nama file yang sama
persis di dalam `artifacts/` dan menjalankan smoke test paket yang sama dengan
CI. Untuk melihat perintah yang dipilih tanpa melakukan build, gunakan
`python packaging/build.py --dry-run`; `--help` menampilkan seluruh opsi yang
didukung.

Script native tetap dapat dijalankan langsung ketika otomasi khusus platform
memerlukannya:

```sh
bash packaging/build_linux.sh
pwsh -File packaging/build_windows.ps1
bash packaging/build_macos.sh
```

Linux memerlukan loader EGL, `curl`, dan `sha256sum`; script mengunduh rilis
resmi `AppImage/appimagetool` 1.9.1 dan memverifikasi SHA-256 yang dipatok
sebelum menjalankannya. `APPIMAGETOOL_URL` khusus harus disertai
`APPIMAGETOOL_SHA256` yang sesuai. Runtime type-2 yang ditanam juga diunduh
berdasarkan ID asset GitHub immutable dan diperiksa hash-nya; override
`APPIMAGE_RUNTIME_URL` memerlukan `APPIMAGE_RUNTIME_SHA256` yang cocok.
Verifikasi tidak pernah dilewati, dan `--runtime-file` mencegah appimagetool
mengambil runtime `continuous` yang dapat berubah.

Paket Linux x86_64 membundel PySide6 dan QtWebEngine. Hal ini meningkatkan
ukuran AppImage secara material dibandingkan paket browser-only sebelumnya.
Artifact resmi dibuat dan di-smoke-test pada runner `ubuntu-22.04` x86_64
(glibc 2.35), yang menjadi baseline Linux yang didukung. Distribusi yang lebih
baru biasanya kompatibel, tetapi versi glibc saja bukan jaminan kompatibilitas
lengkap. Artifact manual mewarisi persyaratan libc dari host build, sehingga
lakukan build pada environment target tertua yang ingin didukung. Sesi grafis
dan dependency tampilan Qt normal diperlukan untuk membuka jendela, sedangkan
smoke test paket tetap headless.

AppImage sengaja tidak menyertakan `libstdc++`, `libgcc_s`, GBM, X11 core, ALSA,
Fontconfig, FreeType, Expat, dan library graphics-dispatch milik host build.
Library tersebut memuat driver GPU/audio atau membaca konfigurasi host, sehingga
harus tetap selaras dengan sistem target. Build akan gagal jika salah satunya
kembali masuk ke bundle. Hal ini mencegah library baseline Ubuntu menimpa
driver Mesa/Intel, plugin ALSA, atau instalasi Fontconfig yang lebih baru pada
distribusi rolling release.

Build PyInstaller memakai hook lokal untuk backend QtWebEngine widgets-only.
Hook tersebut menghilangkan QML tree yang tidak dipakai, Qt Data Visualization,
serta tooling virtual keyboard/Quick 3D opsional yang jika tidak dihilangkan akan
menarik modul Qt GPL-only ke dalam AppImage. `build_linux.sh` secara independen
menolak nama file Qt Graphs, Data Visualization, Quick 3D, Quick Timeline,
Virtual Keyboard, dan Wayland Compositor sebelum packaging. Script juga
mewajibkan library dukungan XCB generik terkumpul, tetapi menyerahkan dispatch
EGL/GL yang berhubungan dengan driver kepada graphics stack host. Jangan hapus
pemeriksaan ini saat menaikkan versi PySide6 atau PyInstaller; lakukan build
ulang, inspeksi, dan evaluasi lisensi payload aktual sebagai gantinya.

AppImage mendukung transport Linux `hidraw` yang telah diverifikasi dan sengaja
tidak membundel ekstensi HIDAPI opsional maupun library native vendornya.
Developer tetap dapat menguji override HIDAPI dari instalasi source dengan
extra `cross-platform`; override tersebut bukan bagian dari AppImage rilis.

Setelah PyInstaller selesai, `linux_legal_inventory.py` membaca
`COLLECT-00.toc` yang dihasilkan. Job Ubuntu resmi menetapkan
`SPADE65_STRICT_LINUX_LEGAL=1`, sehingga setiap binary native yang dikumpulkan
dari `/usr`, `/lib`, `/bin`, atau `/sbin` harus dapat dipetakan ke paket dpkg
terpasang dan file copyright Debian yang tersedia. AppImage menyimpan manifest
dan file hasil salinan di
`usr/share/doc/spade65/linux-system-libraries`. Build manual pada host non-dpkg
tetap didukung dan mendapat manifest source-path-only dengan peringatan eksplisit
bahwa atribusi sistem belum diverifikasi. File lisensi upstream yang tepat untuk
commit runtime type-2 dan appimagetool 1.9.1 yang dipatok disertakan di direktori
lisensi offline normal.

Windows memakai backend Edge Chromium dan memerlukan Microsoft Edge WebView2
Runtime pada host build/smoke-test maupun sistem pengguna akhir. Instalasi
Windows 10/11 terkini umumnya sudah menyediakannya, tetapi runtime tidak diganti
secara diam-diam dengan MSHTML lama; kegagalan akan mengaktifkan fallback browser
yang terdokumentasi.

macOS memerlukan Xcode command-line tools, Python universal2, dan dependency
native universal2. Workflow rilis melakukan build dengan installer universal2
Python.org 3.13.15 yang SHA-256-nya telah diverifikasi, bukan berasumsi bahwa
interpreter CI yang dipilih berdasarkan arsitektur sudah berupa binary fat.
Workflow kemudian membangun `hidapi` dari source untuk kedua arsitektur macOS
dan memindai setiap file Mach-O pada aplikasi akhir untuk menolak binary native
yang hanya memiliki satu arsitektur. Renderer desktop memakai Cocoa/WebKit
melalui PyObjC. Bundle mengizinkan jaringan lokal untuk UI loopback dan memuat
deskripsi penggunaan mikrofon; akses mikrofon hanya diminta ketika efek
audio-reactive diaktifkan.

Setiap executable paket menjalankan smoke test tanpa jendela, browser, atau
enumerasi perangkat sebelum di-upload. Smoke test mengimpor backend PyWebView
yang dipilih dan memeriksa resource HTTP paket tanpa membuat jendela interaktif.
Windows/macOS tetap memuat ekstensi HID native agar library tertaut yang hilang
menggagalkan build tanpa menyentuh keyboard.

Script Windows memvalidasi kedua executable, membuat ZIP, mengekstraknya ke
direktori sementara, lalu menjalankan `Spade65CLI.exe --smoke-test` dari archive
yang sudah diekstrak. Script macOS memverifikasi DMG, me-mount-nya secara
read-only, memeriksa aplikasi, lalu menjalankan kembali smoke test dari image
yang sudah di-mount.

Pada macOS, pasang ekstensi HID native sebagai universal2. Dalam virtual
environment bersih, verifikasi lebih dahulu bahwa Python yang dipilih memuat
kedua slice arsitektur, lalu gunakan helper yang sama dengan CI. Helper memaksa
build wheel dari source, memakai versi Cython/setuptools/wheel yang dipatok di
`requirements-build.txt`, dan memeriksa hash archive source `hidapi` yang
dipatok sebelum kompilasi. Helper menolak hasil thin sebelum packaging:

```sh
resolved_python=$(python -c \
  'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
lipo "$resolved_python" -verify_arch x86_64 arm64
bash packaging/build_macos_hidapi.sh
python packaging/build.py
```

GitHub Actions memasang paket Python.org yang dipatok setelah memverifikasi
SHA-256. Untuk build manual, pasang distribusi universal2 Python.org terbaru
lebih dahulu; helper akan gagal secara tertutup jika interpreter atau ekstensi
HID hasil build bersifat thin.

CI memiliki dua lapisan paket native. Setiap push ke `main` menjalankan job
preflight paket Windows, Linux, dan macOS yang tidak memublikasikan hasilnya. Tag
rilis membangun ulang ketiga artifact dari commit tag immutable, dan baru
setelahnya mengizinkan publikasi; artifact preflight tidak digunakan kembali
sebagai asset rilis. Kedua lapisan memakai kontrak dependency yang sama dengan
build manual: Windows memasang `.[cross-platform,desktop]`, Linux memasang
`.[desktop]` untuk AppImage hidraw-only, dan macOS memasang extra `desktop` lalu
membangun HIDAPI universal2 secara terpisah. Masing-masing juga memasang
`requirements-build.txt`. Ketiganya menjalankan `pip check`, smoke test paket,
dan verifikasi artifact native.

Script macOS membaca versi aplikasi dari `pyproject.toml`, memverifikasinya
terhadap `spade65.__version__`, dan menanamkannya ke aplikasi secara otomatis.

ZIP Windows dan aplikasi macOS saat ini belum ditandatangani. Build macOS hanya
menerima ad-hoc signature dan belum dinotarisasi, sehingga rilis yang diunduh
dapat menampilkan peringatan SmartScreen atau Gatekeeper. Kepercayaan produksi
memerlukan kredensial code-signing Windows privat serta Apple Developer
ID/notarization yang dikonfigurasi sebagai repository secret; signing key tidak
boleh di-commit.

PyWebView dan runtime platformnya tetap tunduk pada ketentuan lisensi upstream.
Tinjau [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md), yang disalin ke
setiap artifact rilis, bersama materi lisensi untuk
[pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE.md),
[Qt for Python/PySide6](https://doc.qt.io/qtforpython-6/licenses.html),
[Microsoft Edge WebView2](https://www.microsoft.com/legal/webview2terms), dan
[PyObjC](https://github.com/ronaldoussoren/pyobjc/blob/main/LICENSE.txt) ketika
mendistribusikan ulang artifact rilis. Salinan repository dari teks
[GPL-3.0](../licenses/GPL-3.0.txt) dan
[LGPL-3.0](../licenses/LGPL-3.0.txt) yang relevan juga tersedia untuk komponen Qt
yang didistribusikan menggunakan pilihan lisensi tersebut.
