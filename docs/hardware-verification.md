# Verifikasi hardware

Pengujian terakhir dilakukan pada 29 Agustus 2026 menggunakan Spade65 USB
`0603:0351` yang tersedia di mesin pengembangan.

## Berhasil

- Tiga interface `/dev/hidraw3`, `/dev/hidraw4`, dan `/dev/hidraw5` ditemukan.
- Interface konfigurasi mengiklankan feature report `0x07` sepanjang 620 byte,
  feature report `0x08` sepanjang 8 byte, serta output report `0x06` sepanjang
  64 byte.
- Satu frame custom timeline berhasil dikirim melalui perintah background
  service ke `/dev/hidraw4`. Jalur ini hanya mengaktifkan streaming dan mengirim
  lima output RGB; tidak menulis flash, keymap, macro, atau bootloader.
- Pembacaan sysfs menghasilkan USB revision `01.00`. Nilai ini tidak diberi label
  versi firmware.

## Tidak dijalankan

- Keymap dan macro tidak ditulis karena perangkat tidak menyediakan readback
  konfigurasi untuk membuat backup kondisi saat ini. Mengujinya akan menimpa
  tiga layer dan macro pengguna tanpa jalur restore yang terjamin.
- Reset tidak dikirim karena bersifat menghapus konfigurasi.
- Timer dongle tidak dikirim karena PID dongle `0603:0356` tidak terdeteksi.
- Firmware, bootloader, raw flash, dan arbitrary HID tidak tersedia di aplikasi.

Frame keymap, macro, reset, dan timer tetap diuji melalui unit test terhadap
format report hasil analisis backend original. Pengujian fisiknya baru aman
dilakukan setelah tersedia profil backup yang diketahui atau dongle yang sesuai.
