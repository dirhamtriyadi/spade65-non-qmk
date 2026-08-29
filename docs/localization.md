# Lokalisasi GUI

GUI memakai katalog JSON yang dibundel bersama aplikasi. English (`en`) adalah
bahasa canonical sekaligus default, dan Bahasa Indonesia (`id`) tersedia sejak
versi `0.6.0`. Pilihan pada sidebar disimpan di `localStorage` dengan key
`spade65-language`, sehingga tetap digunakan saat GUI dibuka kembali pada origin
localhost yang sama. Backup library juga menyimpan code bahasa dan restore akan
menerapkannya kembali bila locale tersebut masih didukung. Bahasa browser tidak
dideteksi otomatis.

Jika manifest atau locale terpilih gagal dimuat, GUI kembali ke English. Teks
English yang tertanam di HTML juga menjadi fallback paling awal agar halaman
tetap dapat digunakan ketika katalog gagal dilayani.

## Struktur file

```text
spade65/web/
├── index.html
├── app.js
└── locales/
    ├── index.json
    ├── en.json
    └── id.json
```

`locales/index.json` adalah manifest bahasa:

```json
{
  "default": "en",
  "languages": [
    {"code": "en", "name": "English"},
    {"code": "id", "name": "Bahasa Indonesia"}
  ]
}
```

Nama file harus sama dengan `code`, hanya memakai huruf, angka, `_`, atau `-`,
dan berakhiran `.json`. Server hanya melayani pola nama aman tersebut. File
locale ikut dimasukkan melalui package data setuptools dan data collection
PyInstaller, jadi perubahan katalog berlaku pada instalasi source maupun paket
desktop.

## Konvensi string

Semua locale harus memiliki key yang sama dengan `en.json`. Gunakan key stabil
berdasarkan area dan makna, misalnya `nav.device`, `action.applyProfile`, atau
`profile.savedLocal`; jangan memakai kalimat English sebagai key.

Untuk teks statis di HTML, pilih atribut sesuai target:

```html
<h3 data-i18n="safety.title">Safety status</h3>
<input data-i18n-placeholder="keymap.usagePlaceholder"
       placeholder="a, play-pause, mouse-left, or 0x04">
<button data-i18n-title="action.remove" title="Remove">×</button>
<select data-i18n-aria-label="device.select" aria-label="Device"></select>
```

- `data-i18n` mengganti `textContent`;
- `data-i18n-placeholder` mengganti `placeholder`;
- `data-i18n-title` mengganti `title`;
- `data-i18n-aria-label` mengganti `aria-label`.

Pertahankan fallback English yang bermakna pada markup. Jangan memasang
`data-i18n` pada elemen yang berisi child node yang harus dipertahankan, karena
penggantian `textContent` akan menghapus child tersebut.

String yang dibuat dinamis di `app.js` harus memakai helper `t()`:

```javascript
toast(t('profile.savedLocal', {name}));
```

Interpolation memakai placeholder bernama berbentuk `{name}`. Nama placeholder
dan jumlahnya harus identik di setiap bahasa. Jangan merangkai beberapa fragmen
terjemahan untuk membentuk satu kalimat; sediakan satu key lengkap agar urutan
kata dapat berubah antarbahasa. Setelah bahasa berubah, renderer dinamis yang
relevan harus dipanggil dari `renderLocalizedDynamic()` agar daftar atau status
yang sudah tampil ikut diperbarui.

Teks dari backend, nama perangkat, path, keycode HID, token konfirmasi literal
seperti `RESET SPADE65`/`APPLY PROFILE`, dan isi JSON diagnostics tidak perlu
diterjemahkan. Untuk pesan UI yang membungkus error backend, terjemahkan bagian
UI-nya dan sisipkan detail error sebagai placeholder.

## Menambahkan bahasa

Contoh menambahkan bahasa Jepang dengan code `ja`:

1. Salin `spade65/web/locales/en.json` ke
   `spade65/web/locales/ja.json`.
2. Terjemahkan seluruh value tanpa mengubah key atau placeholder `{...}`.
3. Tambahkan `{"code": "ja", "name": "日本語"}` ke array `languages` dalam
   `locales/index.json`. Nama ini adalah nama bahasa yang tampil pada selector.
4. Jalankan test dan pemeriksaan katalog di bawah.
5. Buka GUI, ganti bahasa, muat ulang halaman, lalu periksa semua page, dialog,
   toast, placeholder, title, serta label aksesibilitas.

Tidak perlu mengubah backend, daftar route, `pyproject.toml`, atau spec
PyInstaller untuk setiap bahasa baru selama file memakai pola nama di atas.
English harus tetap menjadi `default`, canonical key set, dan fallback.

## Validasi

Jalankan seluruh test, syntax check JavaScript, lalu pemeriksaan konsistensi
katalog di bawah:

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py packaging tests
node --check spade65/web/app.js
```

Untuk pemeriksaan cepat bahwa katalog dapat dibaca dan key-nya identik:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path("spade65/web/locales")
manifest = json.loads((root / "index.json").read_text(encoding="utf-8"))
catalogs = {
    item["code"]: json.loads(
        (root / f'{item["code"]}.json').read_text(encoding="utf-8")
    )
    for item in manifest["languages"]
}
english = set(catalogs["en"])
for code, catalog in catalogs.items():
    assert set(catalog) == english, (code, english ^ set(catalog))
print(f"{len(catalogs)} locales, {len(english)} keys: OK")
PY
```

Selain key parity, review manusia tetap diperlukan untuk terminology, panjang
label pada layout sempit, plural/context, dan kesesuaian placeholder.
