[English](../parity.md) · **Bahasa Indonesia**

# Audit paritas software original Spade65

Audit ini memakai hasil ekstraksi statis `Spade65_SETUP_20240403.exe`, terutama
`app.component.js`, `APModeModule.js`, `SupportData.js`, `KeyBoardStyle.js`, dan
backend perangkat `JupengSeries.deobfuscated.js`. Istilah **lengkap** di bawah
berarti seluruh fungsi konfigurasi Spade65 yang aktif dan dapat direplikasi
dengan protokol yang sudah terverifikasi, bukan seluruh kode generik yang ikut
dibundel dalam aplikasi vendor.

## Halaman aktif perangkat

`setPageData` software original hanya mengaktifkan empat area untuk perangkat:

| Area original | Implementasi proyek |
|---|---|
| Keyboard settings | Editor Normal/FN1/FN2, empat layout fisik, assignment, shortcut, macro binding, disable group, Win Lock, pertukaran WASD/panah, profil lokal dan import/export |
| Lighting setting / AP mode | Sepuluh mode, maksimal sepuluh layer, show/hide layer, rentang tombol, palet, opacity, speed, bandwidth, angle, number, gap, fire, effect center, direction, bump, bidirectional, gradient dan audio reactive |
| Built-in effects | Seluruh 20 effect ID firmware, brightness, speed, palette index, multicolor, dan custom per-key color |
| Macro settings | Maksimal sepuluh macro perangkat, 84 event per macro, delay, key-down/up, repeat, rename, rekam dari keyboard, hapus dan bind ke tombol |

Daftar assignment vendor berisi 132 entri (130 usage unik). Proyek mengekspos
seluruh usage unik tersebut ditambah `disabled`: keyboard, numpad, media,
browser/system, mouse, profile next/previous, FN/FN2, copy/paste, dan shortcut
bermodifier.

Profil software original adalah penyimpanan host. Backend memilih satu profil,
lalu menulis frame keymap yang sama ke perangkat; nomor profil tidak diserialisasi
ke report keymap. Karena itu saved profiles + import/export proyek ini setara,
tanpa mengarang opcode profile baru.

## Kode bundle yang bukan fitur aktif Spade65

Beberapa komponen ada di bundle generik tetapi bukan halaman aktif perangkat:

- `RELATEDPROGRAM` adalah integrasi host Windows. Proyek sekarang menyediakan
  ekuivalen lintas platform opt-in melalui background service untuk Linux,
  Windows, dan macOS, tanpa menyalin integrasi executable vendor.
- `Custom Effect` timeline tidak terdapat di daftar halaman aktif Spade65, tetapi
  ekuivalen aman berbasis streaming lokal sekarang tersedia hingga 200 frame.
- UI polling rate dikomentari dan `reportRateIndex` tidak pernah diserialisasi
  oleh backend Jupeng.
- Model UI menyimpan long/instant press, tetapi `KeyAssigntoData` Jupeng hanya
  membaca assignment normal (`keyAssignType[2]`). Menampilkan kontrol itu akan
  menyesatkan karena perangkat tidak pernah menerimanya.
- Login, telemetry, updater aplikasi, dan pemeriksaan update bukan fungsi
  konfigurasi keyboard.

## Batas keselamatan

Firmware updater, bootloader, raw flash, dan arbitrary HID packet sengaja tidak
memiliki endpoint atau packet builder. Reset memerlukan teks konfirmasi; overwrite
keymap memerlukan dua konfirmasi; semua feature write harus cocok dengan ukuran
report descriptor. Pengecualian ini adalah keputusan keselamatan, bukan fitur
yang belum selesai.

## Status pengujian hardware

Deteksi descriptor, built-in RGB, per-key RGB, streaming/AP mode, custom timeline,
background service, dan debounce sudah divalidasi melalui USB pada `0603:0351`.
Keymap/macro, timer dongle, dan reset sudah cocok dengan frame backend original
dan memiliki pengujian offline, tetapi belum dieksekusi pada hardware: keymap dan
reset tidak memiliki readback untuk membuat backup kondisi sekarang, sedangkan
dongle `0603:0356` tidak terhubung pada pengujian terakhir.
