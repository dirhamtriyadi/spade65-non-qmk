[English](../hardware-verification.md) · **Bahasa Indonesia**

# Verifikasi hardware

Pengujian kabel dilakukan pada 29–31 Agustus 2026 menggunakan Spade65 USB
`0603:0351`. Pada 31 Agustus, receiver fisik 2,4 GHz milik keyboard yang sama
juga diperiksa dan terdeteksi sebagai `0603:0352`.

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
mungkin: tidak ada feature report yang bisa dituju paket konfigurasi. Seluruh
perintah write dicoba terhadap receiver yang terhubung dan semuanya menolak
sebelum mengirim apa pun — `rgb`, `debounce`, `sleep`, `reset` (semuanya `no
matching HID interface for usage ff02:0001` / `ff03:0001`), `stream-rgb`, dan
`profile apply`. `probe` dan `info` tetap berfungsi dan melaporkan
`unsupported-read-only`. `0603:0356` sampai kini belum pernah muncul pada
hardware ini. Tiga koleksi HID yang diamati menyediakan report keyboard biasa,
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
menyediakan interface konfigurasi `0603:0356` terverifikasi; receiver `0352`
yang descriptor-nya tidak kompatibel tidak aman digunakan sebagai pengganti.
