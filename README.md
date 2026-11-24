# SI Surat Tugas Ambulance — RSUD Cut Nyak Dhien Meulaboh

Website untuk membuat **Surat Tugas Ambulance** (rujukan pasien antar rumah sakit)
dengan output PDF persis template resmi RS: kertas **Legal 216 × 356 mm, 1 halaman**.

Dibangun mengikuti metode **Waterfall**: Analisis → Perancangan
(`../docs/Perancangan_Surat_Tugas_Ambulance.md`) → Implementasi (folder ini) →
Pengujian (18 kasus uji otomatis, semua lulus).

## Cara Menjalankan

Butuh Python 3.10+.

```bash
cd app
pip install -r requirements.txt
python3 app.py
```

Buka **http://localhost:5000**

Akun awal (segera ganti password-nya untuk pemakaian nyata):

| Peran | Username | Password |
|-------|----------|----------|
| Admin | `admin` | `admin123` |
| Koordinator | `koordinator` | `koord123` |

Database SQLite (`instance/surat.db`) dibuat & diisi data contoh otomatis
pada jalan pertama. Hapus file itu untuk mengosongkan data.

Di Windows: perintahnya sama (`python app.py`), atau klik dua kali `app.py`
setelah `pip install -r requirements.txt`.

## Fitur (sesuai perancangan)

- **Login 2 peran** — Admin (semua menu) & Koordinator (dashboard, surat, arsip).
- **Dashboard** — statistik bulan berjalan, peringatan surat "Berangkat" yang
  belum dilengkapi kepulangannya, grafik rujukan 7 hari, tujuan terbanyak,
  surat terakhir.
- **Buat Surat Tugas** — form 4 kelompok (Surat, Dasar Rujukan, Petugas,
  Perjalanan). **Nomor surat diisi MANUAL**; sistem menolak nomor kosong dan
  nomor duplikat (ditunjukkan surat pemilik nomor tersebut).
- **Petugas dinamis** — default 2 (Sopir + Perawat/Pendamping), bisa ditambah;
  NIP & pangkat terisi otomatis dari data master dan tersimpan sebagai
  *snapshot* di surat (arsip tidak berubah walau master berubah).
- **Data master** — Pegawai, Kendaraan, RS Tujuan (jarak terisi otomatis),
  Dokter. Data dinonaktifkan, bukan dihapus.
- **Alur status** — Draft → Berangkat → Selesai (+ Dibatalkan dengan alasan).
  Draft bisa diedit; surat terbit terkunci; menutup surat wajib mengisi
  tanggal kembali & waktu terima rujukan.
- **Output PDF** — tombol Cetak/Unduh PDF di dashboard, arsip, dan detail
  surat; layout sama dengan template (kop 2 logo, tabel perjalanan, blok
  waktu terima rujukan, QR tanda tangan penandatangan).
- **Pengaturan** — data penandatangan & upload gambar QR tanda tangan,
  tambah akun pengguna.
- **Jejak audit** — setiap buat/edit/status/cetak tercatat di detail surat.
- **Responsif** — desktop: sidebar; HP (≤860px): topbar + navigasi bawah,
  form 1 kolom, tabel berubah menjadi kartu.

## Struktur

```
app/
├── app.py            # seluruh route & logika (Flask)
├── surat_pdf.py      # generator PDF surat (fpdf2, ukuran Legal)
├── templates/        # halaman (Jinja2)
├── static/style.css  # tampilan responsif
├── assets/           # logo kop, QR contoh, logo BSrE (dari template)
└── instance/surat.db # database SQLite (dibuat otomatis)
```

## Catatan Teknologi

Perancangan menyebut Laravel + MySQL. Implementasi ini memakai
**Flask + SQLite** dengan arsitektur, skema tabel, dan aturan bisnis yang
**sama persis** dengan dokumen perancangan (8 tabel: users, pegawai,
kendaraan, rs_tujuan, dokter, penandatangan, surat_tugas, surat_petugas,
audit_log), karena lingkungan pembangunan di sini tidak memiliki PHP/Composer
dan pengunduhan paket Laravel tidak dapat diselesaikan. Skema di `app.py`
dapat diterjemahkan 1:1 menjadi migration Laravel, dan template PDF di
`surat_pdf.py` menjadi acuan view PDF-nya, bila kelak dipindah ke Laravel.

Untuk produksi: ganti `app.secret_key` di `app.py`, ganti password akun awal,
dan jalankan di balik server WSGI (gunicorn/waitress) — bukan mode bawaan Flask.
