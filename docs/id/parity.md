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
| Lighting setting / AP mode | Sepuluh mode, maksimal sepuluh layer, show/hide layer, rentang tombol, palet, opasitas lapisan, kecerahan utama akhir, speed, bandwidth, angle, number, gap, fire, effect center, direction, bump, bidirectional, gradient, dan reaksi audio dari output sistem atau mikrofon |
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

Operasi `SetKeyMatrix` aplikasi original juga direproduksi sebagai satu transaksi
berurutan: keymap, macro yang direferensikan, lighting saat ini dari cache host,
dan debounce profil, dengan jeda hasil analisis 100/200/100/50/10 ms. Descriptor
collection utama dan companion pendek diselesaikan sebelum write pertama, dan
jalur kabel melewati timer dongle seperti backend original. Profil Spade65 lama
memakai default 5 ms bila data debounce tidak ada demi kompatibilitas; nilai
profil baru aplikasi original adalah 1 ms.

Implementasi AP mode original menangkap output sistem Windows dan tidak
bergantung pada mikrofon. Paket proyek memetakan perilaku tersebut ke WASAPI
loopback pada Windows, monitor PipeWire/PulseAudio melalui SoundCard pada Linux,
dan CoreAudio tap melalui `pysysaudio` pada macOS 14.2 atau lebih baru. Selector
sumber juga menyediakan fallback mikrofon eksplisit. Lapisan yang memakai audio
dapat merespons posisi spektrum, bass, atau keras-lembut keseluruhan, dengan
rentang sensitivitas hasil analisis 200–8000 (default 1000), noise gate, dan
smoothing. Opasitas lapisan memengaruhi satu lapisan sebelum komposisi;
kecerahan utama memengaruhi frame akhir.

Ini adalah ekuivalen streaming host, bukan efek firmware baru. GUI dan
Pratinjau langsung harus tetap aktif melalui USB berkabel `0603:0351`; efek
tidak disimpan di memori keyboard atau diserahkan kepada background service.
Hanya nilai tingkat dan pita frekuensi yang ringkas yang melewati bridge
desktop; PCM mentah tidak disimpan atau diekspos ke antarmuka web lokal.

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
keymap memerlukan satu konfirmasi eksplisit; semua feature write harus cocok dengan ukuran
report descriptor. Pengecualian ini adalah keputusan keselamatan, bukan fitur
yang belum selesai.

## Status pengujian hardware

Deteksi descriptor, seluruh 20 efek built-in RGB, per-key RGB, streaming/AP mode,
custom timeline, background service, debounce, keymap/macro, dan reset sudah
divalidasi melalui USB pada `0603:0351`; pengujian keymap dan macro diterapkan,
dikonfirmasi melalui input fisik, lalu dipulihkan, dan keyboard kembali terdeteksi
dengan benar setelah reset. Transaksi gabungan lengkap sudah diimplementasikan
dan diuji urutannya, tetapi pemeliharaan lighting aktif melalui jalur baru itu
belum mendapat konfirmasi visual pada hardware. Hanya timer dongle yang belum dieksekusi pada
hardware, dan alasannya diketahui, bukan kebetulan: backend original langsung
kembali dari `SetLightOffToDevice` ketika `BaseInfo.StateID` adalah identitas
kabel dan menyelesaikan handle tulis dari `StateList[1]`, sehingga frame tersebut
hanya pernah ditujukan ke `0603:0356`. Identitas itu sampai kini belum pernah
muncul pada hardware ini. Receiver fisik 2,4 GHz terdeteksi sebagai `0603:0352`,
dan report descriptor-nya tidak mengiklankan feature report sama sekali, sehingga
konfigurasi lewat receiver bukan sekadar ditolak, melainkan tidak mungkin.

Penangkapan dan analisis audio native memiliki cakupan otomatis. Penangkapan
monitor Linux juga diuji secara fisik pada 2026-09-02 memakai nada sistem 125 Hz
dan memilih pita dominan yang benar. Penangkapan Windows serta macOS masih belum
diverifikasi secara fisik; transport RGB yang tervalidasi pada hardware bukan
validasi bagi kedua jalur penangkapan OS tersebut.
