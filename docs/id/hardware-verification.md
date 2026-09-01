[English](../hardware-verification.md) · **Bahasa Indonesia**

# Verifikasi hardware

Pengujian kabel dilakukan pada 29 Agustus–1 September 2026 menggunakan Spade65
USB `0603:0351`. Pada 31 Agustus, receiver fisik 2,4 GHz milik keyboard yang
sama juga diperiksa dan terdeteksi sebagai `0603:0352`.

## Berhasil

- Mode kabel terdeteksi sebagai `0603:0351`. Interface konfigurasinya
  mengiklankan feature report `0x07` sepanjang 620 byte, feature report `0x08`
  sepanjang 8 byte, serta output report `0x06` sepanjang 64 byte.
- Seluruh 20 report efek RGB bawaan berhasil ditulis sepanjang 620 byte dan efek
  visualnya dikonfirmasi pada keyboard. Per-key RGB, streaming RGB, AP wave, dan
  custom timeline juga dikonfirmasi secara visual.
- Debounce diatur ke 5 ms. Aksi RGB GUI yang terautentikasi juga berhasil
  sebagai write sepanjang 620 byte.
- Keymap tiga layer dan macro sementara diterapkan serta diverifikasi melalui
  input fisik (`BXcD`). Keymap default dan macro uji kosong lalu dipulihkan dan
  diverifikasi melalui input fisik (`asd`).
- Dengan izin eksplisit pengguna, reset berhasil sebagai write sepanjang 8
  byte. Probe hanya-baca tepat setelah reset tetap menemukan descriptor kabel
  yang sesuai, sehingga keyboard tetap beroperasi.
- Asosiasi aplikasi dan background service AP/timeline berhasil pada interface
  streaming kabel. Efek host ini tidak menulis firmware, flash, atau bootloader.
- Pembacaan sysfs menghasilkan USB revision `01.00`. Nilai ini tidak diberi label
  versi firmware.

## Transaksi keymap resmi dan temuan pencahayaan

Firmware berkabel menghapus state pencahayaan aktif saat menerima report keymap
opcode `0x03`. Analisis aplikasi resmi menjelaskan urutan penulisannya:
`SetKeyMatrix` mengirim key matrix, macro yang direferensikan, lalu mengirim
ulang `lightData` dari cache host. Setelah itu aplikasi mengirim nilai debounce
profil melalui handle report pendek. Jeda yang ditemukan pada jalur tersebut
adalah 100 ms setelah keymap `0x03`, 200 ms setelah setiap macro `0x05` yang
direferensikan, 100 ms setelah efek lighting `0x02`, 50 ms setelah palet custom
`0x07` opsional, dan 10 ms setelah debounce pendek `0x09`. Aplikasi resmi tidak
membaca pencahayaan saat ini dari keyboard, dan belum ada report readback
pencahayaan yang terverifikasi untuk proyek ini.

Spade65 sekarang mengirim urutan lengkap yang sama: keymap, hanya macro yang
direferensikan, lighting saat ini/tersimpan, dan debounce yang tersimpan di
profil. Collection utama 620 byte dan companion pendek 8 byte diselesaikan serta
divalidasi terhadap descriptor sebelum write keymap. Jalur kabel tidak
menambahkan timer, sesuai early return fungsi timer aplikasi original.

Bentuk report keymap, macro, lighting, dan debounce 5 ms secara individual
memiliki bukti penerimaan fisik seperti dicatat di atas. Apply keymap-saja dari
source juga pernah diamati tetap mematikan lighting sebelum ekor debounce
lengkap ini diimplementasikan. Pada 1 September, transaksi lengkap keymap
default + Aliran Neon + debounce 5 ms mengembalikan panjang write penuh untuk
ketiga report. Pemeliharaan visual lighting aktif setelah transaksi lengkap
tersebut **belum dikonfirmasi pada hardware**; jumlah byte report yang sukses
dan pengujian urutan otomatis tidak disebut sebagai bukti visual tersebut.

GUI memakai pilihan editor built-in/custom serta debounce yang sedang
ditampilkan untuk transaksi ini, lalu baru menyimpan kedua nilai persis tersebut
setelah report pendek terakhir berhasil. Aplikasi original memulai profil baru
pada 1 ms; Spade65 memakai 5 ms ketika profil lama tidak memiliki
`debounce_ms`, demi mempertahankan perilaku historis proyek. Profil Spade65 baru
juga mencatat 5 ms secara eksplisit.

Spade65 menyimpan snapshot pencahayaan terakhir yang berhasil ditulis di setiap
profil. Profil baru memakai default lighting resmi: Aliran Neon, kecerahan 4,
kecepatan 5, indeks warna 0, dan multiwarna aktif. Profil lama tanpa snapshot
lighting memakai default yang sama; warna per tombolnya tetap menjadi draft
editable sampai lighting custom dipilih secara eksplisit dan berhasil ditulis.
Fallback kompatibilitas ini dapat mengganti pencahayaan yang diubah melalui
shortcut keyboard atau host lain karena aplikasi tidak dapat mengamati
perubahan eksternal tersebut.

Untuk lighting custom, snapshot menyimpan salinan independen dari palet persis
yang berhasil. Karena itu edit berikutnya yang belum dikirim tidak dapat mengubah
recovery keymap. Jika penulisan multi-report gagal setelah keymap atau saat
mengirim palet custom baru, aplikasi mencoba satu kali mengirim ulang hanya
lighting tersimpan sebelumnya sebelum menampilkan error.

Cakupan profil bernama lama `colors` mengirim ulang lighting aktif yang
tersimpan; cakupan itu tidak mengaktifkan draft warna tingkat atas pada profil
modern secara independen. Mengedit warna per tombol di GUI memilih custom
sebagai intent editor saat ini; Apply Profile dengan keymap/lighting atau aksi
khusus per tombol kemudian menulis seluruh tabel tersebut. Tombol yang tidak
ada dalam tabel menjadi hitam, dan tabel persis itu baru menjadi snapshot custom
setelah seluruh penulisan berhasil.

## Receiver 2,4 GHz yang diamati

PID `0603:0352` dikenali untuk diagnostik hanya-baca, tetapi bukan target
konfigurasi. Identitas ini juga tidak dikenal software original: `0352` tidak
muncul pada tabel support-device vendor, tidak pada lapisan protokolnya, dan
tidak pada frontend-nya, sehingga tidak ada perilaku vendor yang bisa
direproduksi untuknya.

Pada 31 Agustus receiver dipasang kembali dengan kabel dilepas dan keyboard
beroperasi lewat 2,4 GHz, dikonfirmasi oleh perangkat input yang aktif (`JP
Spade65 Keyboard`). Bahkan dalam kondisi itu receiver tetap terdeteksi sebagai
`0603:0352`, dan ketiga report descriptor HID-nya — diurai item demi item
langsung dari `/sys/class/hidraw/*/device/report_descriptor`, bukan lewat
parser proyek ini — **tidak mengiklankan feature report sama sekali**. Satu-
satunya vendor usage page yang ada adalah `0xff55`; `ff02:0001` dan `ff03:0001`
tidak ada. Sebagai pembanding, interface kabel mengiklankan `ff01`, `ff02`,
`ff03` serta kedua feature report `0x07` dan `0x08`.

Jadi konfigurasi lewat receiver ini bukan sekadar digerbangi, melainkan tidak
mungkin: tidak ada feature report yang bisa dituju paket konfigurasi. Enam
perintah write dicoba terhadap receiver yang terhubung dan semuanya menolak
sebelum mengirim apa pun — `rgb`, `debounce`, `sleep`, `reset` (semuanya `no
matching HID interface for usage ff02:0001` / `ff03:0001`), `stream-rgb`, dan
`profile apply`. `per-key-rgb` dan background streaming service tidak dicoba.
`probe` dan `info` tetap berfungsi dan melaporkan `unsupported-read-only`.
`0603:0356` sampai kini belum pernah muncul pada hardware ini.

Ketiga koleksi HID receiver yang diamati menyediakan report keyboard biasa,
koleksi input/output report-ID `0x06`, serta koleksi input/output `008c:0006`.
Ketiganya **tidak** menyediakan dua bentuk konfigurasi yang diwajibkan proyek
ini:

- tidak ada feature report `0x07` sepanjang 620 byte pada `ff02:0001`; dan
- tidak ada feature report `0x08` sepanjang 8 byte pada `ff03:0001`.

Paket timer merupakan feature report `0x08` sepanjang 8 byte yang dikirim
melalui koleksi `ff03:0001` terverifikasi untuk identitas dongle logis
`0603:0356` milik backend original. Mengirimnya ke `0352` berarti melewati
validasi identitas sekaligus bentuk descriptor. Karena itu aplikasi menolak
operasi tersebut dan tidak menebak bahwa kedua protokol receiver kompatibel.
Keberadaan report `0x06` sepanjang 64 byte pada `0352` saja bukan bukti yang
cukup: protokol streaming kabel juga membutuhkan feature report aktivasi pendek
yang terverifikasi, sedangkan receiver ini tidak mengiklankannya.

## Layout baris bawah

Unit berkabel diperiksa dengan `evtest` pada node boot-keyboard-nya, satu-
satunya node yang melaporkan modifier. Menekan spacebar menghasilkan
`MSC_SCAN 0x7002c`; tombol berikutnya di sebelah kanannya tidak menghasilkan
apa pun, karena Fn diproses di dalam firmware dan tidak pernah mengirim usage;
tombol setelahnya menghasilkan `MSC_SCAN 0x700e6`, usage `0xe6`, Right Alt.
Left Ctrl menghasilkan `0x700e0` sesuai dugaan. Ini membuktikan usage dan
posisi fisiknya; event input tidak mengungkap nomor slot matrix konfigurasi
vendor.

Jadi baris bawah papan ini adalah `Ctrl Win Alt Space Fn RAlt` ditambah kluster
panah, dan tidak memiliki tombol Right Ctrl yang terlihat. Data layout standard
SPADE65-03/04 menyembunyikan assignment index 62, menampilkan Fn pada index 65,
dan menggambar index 66 pada posisi fisik tepat di kanan Fn. Keluaran `0xe6`
yang terukur menunjukkan bahwa posisi produksi tersebut merupakan tombol
Right Alt pada papan ini.

Record lokasi generik vendor `0x06030x0351` menyatakan hal yang berbeda: tabel
mentahnya menamai assignment index 62 / matrix slot 89 sebagai `ralt` dengan
default usage `0xe6`, sedangkan index 66 / slot 96 sebagai `rctrl` dengan
default usage `0xe4`. Nilai mentah itu dipertahankan secara eksplisit untuk
audit dan konversi profil original, tetapi tidak dipakai tanpa penyesuaian
sebagai peta semantik papan produksi.

Sebelumnya aplikasi hanya membetulkan gambar: `ralt` ditampilkan pada posisi
fisik index 66, tetapi backend masih menulis `ralt` ke slot 89 dan mempertahankan
`0xe4` pada slot 96. Akibatnya remap Right Alt tidak mencapai tombol fisik, dan
apply keymap default lengkap dapat mengubah tombol itu menjadi Right Ctrl.
Model kanonik varian RALT kini memetakan `ralt` ke slot 96 dengan default
`0xe6`, serta mempertahankan `rctrl` legacy yang tersembunyi pada slot 89 dengan
default `0xe4`. Keduanya tetap merupakan nama berbeda, sehingga assignment dan
warna per tombol tidak dapat saling menimpa melalui alias. Import vendor
posisional mengkanonisasi index mentah 66 menjadi `ralt` dan index mentah 62
menjadi `rctrl` legacy.

Keempat layout kini menggambar `ralt` di sebelah kanan `fn` dan tidak ada yang
menggambar `rctrl`. Geometri efek host menggunakan posisi semantik yang sama.
Matrix itu milik PCB, sehingga memasang spacebar terbelah tidak memindahkan
tombol kanonik slot 96: yang berubah hanya keycap mana yang menutupi slot-slot
space. Sebelumnya layout split memakai `ralt` sebagai tombol di antara segmen
spacebar — berarti satu slot menempati dua posisi — dan menaruh `rctrl` di kanan
Fn. Celah antar segmen kini diisi `mspace`, slot 91, yang default usage-nya
`0x2c`.

Hanya susunan standard yang terkonfirmasi terhadap hardware. Geometri split
diturunkan dari matrix yang tetap, bukan dari papan split yang memang tidak
tersedia.

Layout vendor lainnya tetap menggambar baris bawah papan ini secara keliru,
sehingga geometrinya bukan rujukan untuk varian produksi ini.
`SupportDevice.db` menetapkan SPADE65 ke `layoutIndex: 0`, yaitu layout
spacebar terbelah dengan `AltRight` sebelum `Custom_Fnkey` serta `ControlRight`
yang terlihat — tiga perbedaan dari hardware. Record yang sama mengisi `img`
dengan `image/GMMK`, gambar milik merek lain; kelas layout-nya bernama
`KB61Prohibit` padahal arraynya memuat 70 tombol; dan `KeyBoardStyle` memuat dua
belas style dengan lima baris-bawah berbeda, termasuk yang bernumpad. Itu
cangkang ODM generik untuk banyak model. Hardware terukur serta bukti RALT
spesifik model menentukan geometri dan semantik varian di sini; bundel vendor
tetap otoritatif untuk protokol wire, yang merupakan persoalan terpisah dan
sudah dikonfirmasi secara independen.

Satu anomali matrix masih terbuka: `rspace` menamai slot 92 sekaligus slot 94,
dan default usage-nya bertentangan — slot 92 `0x00`, slot 94 `0x2c`.
`BUTTON_TO_SLOT` memilih slot 92 karena kecocokan pertama. Dibutuhkan papan
dengan spacebar terbelah untuk memastikan slot mana yang benar-benar space
kanan, sehingga tabelnya dibiarkan apa adanya alih-alih dikoreksi berdasarkan
tebakan.

## Tidak dijalankan

- Timer dongle tidak dikirim karena receiver fisik yang diamati memakai PID
  `0603:0352` dan tidak memiliki bentuk feature report `ff03:0001` yang telah
  diverifikasi. Identitas konfigurasi dongle logis `0603:0356` tidak terdeteksi.

  Pada software original pun timer bersifat dongle-only, jadi ini bukan celah
  cakupan. Backend vendor menggerbangi paket tersebut lewat `BaseInfo.StateID`,
  yaitu indeks ke `StateList` dua entri yang isinya hanya
  `[0] = 0603:0351 "USB"` dan `[1] = 0603:0356 "Dongle"`. Fungsi
  `SetLightOffToDevice` dibuka dengan `if (0 == BaseInfo.StateID) return
  callback();`, sehingga identitas kabel dilewati sebelum frame dibentuk; UI
  vendor juga hanya merender kontrol light-off dan sleep di bawah
  `*ngIf="DeviceService.getCurrentDevice().StateID === 1"`, dan handle tulisnya
  sendiri diselesaikan sebagai `hid.FindDevice(0xff03, 0x1,
  StateList[StateID].vid, StateList[StateID].pid)`. Tiga gerbang independen
  menjaga opcode `0x0B` tidak pernah sampai ke `0603:0351`. Membatasi
  `spade65ctl sleep` ke `0603:0356` berarti mereproduksi perilaku itu, bukan
  menambah pembatasan baru. Debounce (`0x09`) dan reset (`0x08`) tidak memiliki
  gerbang serupa pada backend original, sehingga keduanya tetap tersedia lewat
  koneksi kabel.
- Firmware, bootloader, raw flash, dan arbitrary HID tidak tersedia di aplikasi.

Frame timer tetap diuji melalui unit test terhadap format report hasil analisis
backend original. Pengujian timer secara fisik membutuhkan dongle yang
terdeteksi sebagai `0603:0356` dan menyediakan interface konfigurasi
`ff03:0001`; receiver `0352` yang descriptor-nya tidak kompatibel tidak aman
digunakan sebagai pengganti.
