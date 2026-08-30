[English](../jenkins.md) · **Bahasa Indonesia**

# Jalur cadangan CI/CD Jenkins

[`Jenkinsfile`](../../Jenkinsfile) di root menyediakan jalur CI/CD kedua ketika
GitHub Actions tidak tersedia atau kuota hosted runner habis. File ini tidak
menyediakan server Jenkins secara otomatis. Controller, tiga agent native,
tool, credential, dan webhook repository tetap harus dikonfigurasi oleh
administrator.

Publish sengaja tetap manual. Build branch atau pull request biasa menjalankan
test di Windows, Linux, dan macOS dengan Python 3.10 serta 3.13, tetapi tidak
membuat paket desktop maupun GitHub Release.

## Komponen Jenkins

Gunakan Jenkins LTS terkini dengan komponen berikut:

- Pipeline dan Pipeline: Declarative;
- Git;
- Credentials Binding;
- GitHub Branch Source untuk Multibranch Pipeline;
- Artifact Manager eksternal, sangat disarankan untuk stash paket native yang
  besar.

Dokumentasi Jenkins menjelaskan
[Multibranch Pipeline](https://www.jenkins.io/doc/book/pipeline/multibranch/)
dan [sintaks Declarative Pipeline](https://www.jenkins.io/doc/book/pipeline/syntax/).
Buat Multibranch Pipeline untuk
`git@github.com:dirhamtriyadi/spade65-non-qmk.git`, pertahankan script path
`Jenkinsfile`, lalu atur webhook GitHub yang biasa dipakai plugin Branch Source.

Jangan izinkan pull request tidak tepercaya mengganti `Jenkinsfile` yang dapat
menggunakan credential controller. Terapkan kebijakan trusted revision atau
trusted author Jenkins sebelum mengaktifkan discovery pull request; lihat
[pengamanan multibranch pipeline](https://www.jenkins.io/doc/book/security/securing-org-folders-and-multibranch-pipelines/).
Pipeline juga menolak publikasi dari job pull request maupun job multibranch
selain `main`, tetapi pemeriksaan saat runtime itu tidak menggantikan konfigurasi
permission dan trust Jenkins.

## Agent native

Pasang label berikut secara persis pada agent. Setiap agent membutuhkan Git,
Node.js, akses HTTPS keluar ke GitHub dan PyPI, serta ruang disk yang cukup untuk
virtual environment terisolasi dan bundle desktop.

| Label | Host dan command yang dibutuhkan |
|---|---|
| `linux` | Ubuntu 22.04 x86_64; `python3.10`, `python3.13`, Bash, `curl`, `sha256sum`, `dpkg-query`; GitHub CLI `gh` untuk job rilis |
| `windows` | Windows x64; Python Launcher `py -3.10` dan `py -3.13`, PowerShell, Node.js, serta Microsoft Edge WebView2 Runtime |
| `macos` | macOS dengan Xcode Command Line Tools; `python3.10`, `python3.13`, `lipo`, `codesign`, `hdiutil`, serta interpreter Python 3.13 universal2 dari Python.org |

Tahap packaging Linux menerapkan baseline Ubuntu 22.04 x86_64 yang sama dengan
GitHub Actions. Pasang paket runtime berikut lebih dahulu:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends --yes \
  libstdc++6 libgcc-s1 libgbm1 libfontconfig1 libfreetype6 \
  libexpat1 libx11-6 libx11-xcb1 libasound2 libegl1 libgl1 \
  libxcb-shape0 libxcb-image0 libxcb-xkb1 libxcb-icccm4 \
  libxkbcommon-x11-0 libxcb-util1 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-render-util0 curl coreutils
```

Tahap paket macOS secara default menggunakan interpreter universal2 di:

```text
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
```

Pasang dan verifikasi interpreter Python.org yang dipin satu kali saat
menyiapkan agent, dengan
[`packaging/prepare_macos_ci.sh`](../../packaging/prepare_macos_ci.sh) sebagai
patokan. Jika lokasinya berbeda, definisikan `SPADE65_MACOS_PYTHON` pada
environment node tersebut. Interpreter Homebrew tipis atau satu arsitektur akan
ditolak karena setiap payload Mach-O dalam rilis harus memiliki slice `x86_64`
dan `arm64`.

## Credential rilis

Buat satu credential Jenkins berjenis **Secret text** dengan ID:

```text
spade65-github-token
```

Gunakan token GitHub fine-grained yang hanya berlaku untuk repository ini dengan
permission minimum untuk membuat dan mengubah Release (`Contents: Read and
write`). Credential hanya diminta oleh dua tahap rilis opt-in; CI biasa dan
package preflight tidak menerimanya. Agent `linux` untuk tahap tersebut harus
memiliki executable `gh` yang kompatibel, tetapi tidak boleh menyimpan login
maintainer lain secara permanen.

## Parameter pipeline

| Parameter | Default | Efek |
|---|---:|---|
| `BUILD_DESKTOP` | `false` | Membuat, menjalankan smoke test, dan mengarsipkan ketiga paket native |
| `RELEASE_TAG` | kosong | Memilih tag `vMAJOR.MINOR.PATCH` yang sudah ada dan membangun commit immutable-nya |
| `PUBLISH_RELEASE` | `false` | Otomatis mengaktifkan semua build native lalu memublikasikan tag setelah verifikasi |

Pola eksekusi yang umum:

- CI branch/PR otomatis: biarkan semua parameter pada default;
- package preflight: atur `BUILD_DESKTOP=true`;
- menguji tag tanpa publish: isi hanya `RELEASE_TAG`;
- rilis dari job `main`: isi `RELEASE_TAG=vX.Y.Z` dan
  `PUBLISH_RELEASE=true`. `BUILD_DESKTOP` boleh tetap false karena publikasi
  otomatis mengaktifkan tahap paket.

Pada scan pertama, Jenkins mungkin memerlukan satu build awal untuk mendaftarkan
parameter; eksekusi selanjutnya tampil sebagai **Build with Parameters**.

## Jaminan publikasi

Untuk rilis opt-in, pipeline:

1. memvalidasi bentuk tag serta mencocokkannya dengan `pyproject.toml` dan
   `spade65/__init__.py`;
2. me-resolve tag annotated maupun lightweight menjadi satu commit dan memaksa
   semua agent membangun commit tersebut;
3. menolak GitHub Release yang sudah dipublikasikan sebelum build mahal dimulai;
4. menjalankan enam sel test dan tiga build paket native;
5. memverifikasi dan mengarsipkan tepat satu ZIP Windows, AppImage Linux, dan
   DMG macOS universal;
6. mengambil ulang tag dan berhenti bila tag telah berpindah;
7. hanya membuat atau memakai ulang draft Release, menolak asset tak terduga,
   mengunggah tiga asset yang diharapkan, memeriksa jumlahnya, lalu publish.

Job memakai `disableConcurrentBuilds()` agar dua publikasi tidak berjalan
bersamaan pada job `main`. Jangan memindahkan tag yang sudah dipublikasikan. Jika
source rilis harus berubah, terbitkan versi patch baru sesuai
[panduan rilis desktop](releasing.md).

## Penyimpanan dan retensi artifact

File native berpindah antar-agent melalui `stash`/`unstash`, kemudian Jenkins
menyimpannya dengan `archiveArtifacts`. Pipeline menyimpan 20 catatan build,
tetapi hanya tiga kumpulan paket terarsip terbaru. Kebijakan ini hanya berlaku
untuk artifact Jenkins dan tidak pernah menghapus asset GitHub Release.

Paket tersebut, terutama AppImage, berukuran besar. Jenkins memperingatkan
bahwa stash besar dapat memakai CPU controller dan bandwidth jaringan yang
tinggi. Konfigurasikan Artifact Manager eksternal seperti
[plugin Artifact Manager on S3](https://plugins.jenkins.io/artifact-manager-s3/)
sebelum build native dijalankan rutin. Lihat
[dokumentasi langkah `stash`](https://www.jenkins.io/doc/pipeline/steps/workflow-basic-steps/#stash-stash-some-files-to-be-used-later-in-the-build)
untuk perilaku penyimpanannya.

Jenkins memvalidasi Declarative Pipeline berdasarkan plugin pada controller yang
sebenarnya. Setelah setup, jalankan CI default terlebih dahulu, lalu package
preflight, sebelum memberikan credential rilis atau mengandalkan pipeline ini
untuk publikasi produksi.
