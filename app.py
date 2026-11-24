#!/usr/bin/env python3
"""SI Surat Tugas Ambulance — RSUD Cut Nyak Dhien Meulaboh.

Implementasi tahap Implementation (Waterfall) dari dokumen perancangan
docs/Perancangan_Surat_Tugas_Ambulance.md.

Stack: Flask + SQLite (arsitektur & skema sama dengan rancangan;
mudah dipindah ke Laravel + MySQL — lihat README).
Jalankan:  python3 app.py   lalu buka http://localhost:5000
Login awal: admin / admin123  dan  koordinator / koord123
"""
import os
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import io

from surat_pdf import buat_pdf

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "instance", "surat.db")
UPLOAD_DIR = os.path.join(BASE, "static", "uploads")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "ganti-kunci-ini-di-produksi"

BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
STATUS_LABEL = {"draft": "Draft", "berangkat": "Berangkat",
                "selesai": "Selesai", "dibatalkan": "Dibatalkan"}


# ---------------------------------------------------------------- DB
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def _close(_exc):
    con = g.pop("db", None)
    if con:
        con.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, username TEXT UNIQUE,
  password_hash TEXT, role TEXT CHECK(role IN ('admin','koordinator')),
  is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS pegawai(
  id INTEGER PRIMARY KEY, nama TEXT, nip TEXT, pangkat_gol TEXT,
  jabatan_default TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS kendaraan(
  id INTEGER PRIMARY KEY, jenis TEXT, nomor_polisi TEXT UNIQUE,
  is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS rs_tujuan(
  id INTEGER PRIMARY KEY, nama_rs TEXT, kota TEXT, jarak_km REAL,
  is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS dokter(
  id INTEGER PRIMARY KEY, nama TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS penandatangan(
  id INTEGER PRIMARY KEY, nama TEXT, nip TEXT, jabatan_baris_1 TEXT,
  jabatan_baris_2 TEXT, qr_ttd_path TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS surat_tugas(
  id INTEGER PRIMARY KEY,
  nomor_surat TEXT UNIQUE NOT NULL,
  tanggal_surat TEXT, dasar_tanggal_rujukan TEXT,
  dokter_id INTEGER REFERENCES dokter(id),
  dokter_nama TEXT,
  nama_pasien TEXT, no_kp_jka TEXT,
  sub_spesialis TEXT DEFAULT 'Instalasi Gawat Darurat (IGD)',
  kendaraan_id INTEGER REFERENCES kendaraan(id),
  kendaraan_jenis TEXT, kendaraan_nopol TEXT,
  rs_tujuan_id INTEGER REFERENCES rs_tujuan(id),
  rs_nama TEXT, jarak_km REAL,
  berangkat_tanggal TEXT, berangkat_pukul TEXT,
  kembali_tanggal TEXT, kembali_pukul TEXT,
  pengambilan_o2 TEXT, kronologi TEXT,
  terima_tanggal TEXT, terima_pukul TEXT, terima_rs TEXT, terima_nama TEXT,
  penandatangan_id INTEGER REFERENCES penandatangan(id),
  status TEXT DEFAULT 'draft' CHECK(status IN ('draft','berangkat','selesai','dibatalkan')),
  alasan_batal TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT DEFAULT (datetime('now','localtime')),
  updated_at TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS surat_petugas(
  id INTEGER PRIMARY KEY,
  surat_id INTEGER REFERENCES surat_tugas(id) ON DELETE CASCADE,
  pegawai_id INTEGER REFERENCES pegawai(id),
  nama TEXT, nip TEXT, pangkat_gol TEXT, jabatan_di_surat TEXT,
  urutan INTEGER);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, user_id INTEGER, surat_id INTEGER,
  aksi TEXT, keterangan TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')));
"""


def seed():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO users(name,username,password_hash,role) VALUES(?,?,?,?)",
            [("Administrator", "admin", generate_password_hash("admin123"), "admin"),
             ("Koordinator Ambulance", "koordinator", generate_password_hash("koord123"), "koordinator")])
        con.executemany("INSERT INTO pegawai(nama,nip,pangkat_gol,jabatan_default) VALUES(?,?,?,?)",
                        [("Budi Santoso", "19900101 201501 1 001", "Pengatur / II.c", "Sopir Ambulance"),
                         ("Siti Rahma, Amd. Kep", "19930512 201903 2 002", "Penata Muda / III.a", "Perawat / Pendamping Pasien"),
                         ("Rahmad Hidayat", "19970720 202001 1 003", "Pengatur Muda / II.a", "Sopir Ambulance")])
        con.executemany("INSERT INTO kendaraan(jenis,nomor_polisi) VALUES(?,?)",
                        [("Toyota Hiace", "BL 7045 C"), ("Toyota Innova", "BL 7021 A")])
        con.executemany("INSERT INTO rs_tujuan(nama_rs,kota,jarak_km) VALUES(?,?,?)",
                        [("RSUD Meuraxa", "Banda Aceh", 237.3),
                         ("RSUD Teuku Umar", "Calang", 98.4),
                         ("RSUD Datu Beru", "Takengon", 152.7)])
        con.executemany("INSERT INTO dokter(nama) VALUES(?)",
                        [("dr. Andi Saputra",), ("dr. Ratna Dewi",), ("dr. Hendra Wijaya",)])
        con.execute("INSERT INTO penandatangan(nama,nip,jabatan_baris_1,jabatan_baris_2) VALUES(?,?,?,?)",
                    ("Janatah, Amd. Kep", "19821016 200801 1002",
                     "a.n. Kepala Bagian Umum", "Koordinator Ambulance"))
        # Surat contoh (data dummy untuk demo dashboard)
        contoh = [
            ("000.1.2/040", "2026-11-21", "Abdullah Syafii", 1, "berangkat", "2026-11-21"),
            ("000.1.2/041", "2026-11-22", "Cut Nyak Meutia", 3, "draft", "2026-11-22"),
            ("000.1.2/042", "2026-11-23", "Teuku Umar Said", 1, "selesai", "2026-11-23"),
            ("000.1.2/043", "2026-11-23", "Fatimah Zahra", 2, "selesai", "2026-11-23"),
            ("000.1.2/044", "2026-11-24", "Muhammad Ali", 1, "berangkat", "2026-11-24"),
        ]
        for nomor, tgl, pasien, rs_id, status, brg in contoh:
            rs = con.execute("SELECT * FROM rs_tujuan WHERE id=?", (rs_id,)).fetchone()
            cur = con.execute(
                """INSERT INTO surat_tugas(nomor_surat,tanggal_surat,dasar_tanggal_rujukan,
                   dokter_id,dokter_nama,nama_pasien,no_kp_jka,kendaraan_id,kendaraan_jenis,
                   kendaraan_nopol,rs_tujuan_id,rs_nama,jarak_km,berangkat_tanggal,berangkat_pukul,
                   kembali_tanggal,kembali_pukul,pengambilan_o2,kronologi,penandatangan_id,status,created_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (nomor, tgl, tgl, 1, "dr. Andi Saputra", pasien, "1112012345678901",
                 1, "Toyota Hiace", "BL 7045 C", rs_id, rs[1], rs[3], brg, "08:00",
                 brg if status == "selesai" else None, "16:30" if status == "selesai" else None,
                 "6 M3 / Tabung", "hati-hati dalam perjalanan utamakan keselamatan", 1, status, 1))
            sid = cur.lastrowid
            for urutan, (peg_id, jabatan) in enumerate(
                    [(1, "Sopir Ambulance"), (2, "Perawat / Pendamping Pasien")], 1):
                p = con.execute("SELECT * FROM pegawai WHERE id=?", (peg_id,)).fetchone()
                con.execute("INSERT INTO surat_petugas(surat_id,pegawai_id,nama,nip,pangkat_gol,jabatan_di_surat,urutan) VALUES(?,?,?,?,?,?,?)",
                            (sid, peg_id, p[1], p[2], p[3], jabatan, urutan))
    con.commit()
    con.close()


# ---------------------------------------------------------------- helpers
def tgl_indo(iso):
    if not iso:
        return "......."
    try:
        y, m, d = str(iso)[:10].split("-")
        return f"{int(d)} {BULAN[int(m)]} {y}"
    except Exception:
        return str(iso)


def jarak_str(km):
    if km is None:
        return "-"
    return ("%g" % float(km)).replace(".", ",") + " Km"


app.jinja_env.filters["tgl_indo"] = tgl_indo
app.jinja_env.filters["jarak"] = jarak_str
app.jinja_env.globals["STATUS_LABEL"] = STATUS_LABEL


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return w


def admin_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        if u["role"] != "admin":
            flash("Halaman ini hanya untuk Admin.", "error")
            return redirect(url_for("dashboard"))
        return fn(*a, **kw)
    return w


@app.context_processor
def inject_user():
    return {"user": current_user()}


def audit(surat_id, aksi, keterangan=""):
    db().execute("INSERT INTO audit_log(user_id,surat_id,aksi,keterangan) VALUES(?,?,?,?)",
                 (session.get("user_id"), surat_id, aksi, keterangan))
    db().commit()


def get_surat(sid):
    s = db().execute("SELECT * FROM surat_tugas WHERE id=?", (sid,)).fetchone()
    if not s:
        abort(404)
    return s


def get_petugas(sid):
    return db().execute("SELECT * FROM surat_petugas WHERE surat_id=? ORDER BY urutan", (sid,)).fetchall()


# ---------------------------------------------------------------- auth
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE username=? AND is_active=1",
                         (request.form.get("username", "").strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session["user_id"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    con = db()
    today = date.today()
    ym = today.strftime("%Y-%m")
    stats = {
        "total": con.execute("SELECT COUNT(*) c FROM surat_tugas WHERE strftime('%Y-%m',tanggal_surat)=?", (ym,)).fetchone()["c"],
        "berangkat": con.execute("SELECT COUNT(*) c FROM surat_tugas WHERE status='berangkat'").fetchone()["c"],
        "selesai": con.execute("SELECT COUNT(*) c FROM surat_tugas WHERE status='selesai' AND strftime('%Y-%m',tanggal_surat)=?", (ym,)).fetchone()["c"],
        "draft": con.execute("SELECT COUNT(*) c FROM surat_tugas WHERE status='draft'").fetchone()["c"],
    }
    belum_lengkap = con.execute(
        "SELECT * FROM surat_tugas WHERE status='berangkat' AND (kembali_tanggal IS NULL OR terima_tanggal IS NULL) ORDER BY berangkat_tanggal").fetchall()
    hari = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        c = con.execute("SELECT COUNT(*) c FROM surat_tugas WHERE berangkat_tanggal=?",
                        (d.isoformat(),)).fetchone()["c"]
        hari.append({"label": ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][d.weekday()],
                     "count": c})
    maks = max([h["count"] for h in hari] + [1])
    for h in hari:
        h["pct"] = max(6, round(h["count"] / maks * 92))
    tujuan = con.execute(
        """SELECT rs_nama, COUNT(*) c FROM surat_tugas
           WHERE strftime('%Y-%m',tanggal_surat)=? GROUP BY rs_nama ORDER BY c DESC LIMIT 4""",
        (ym,)).fetchall()
    terakhir = con.execute("SELECT * FROM surat_tugas ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, belum_lengkap=belum_lengkap,
                           hari=hari, tujuan=tujuan, terakhir=terakhir,
                           tanggal_hari_ini=tgl_indo(today.isoformat()))


# ---------------------------------------------------------------- surat
@app.route("/surat")
@login_required
def surat_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    sql = "SELECT * FROM surat_tugas WHERE 1=1"
    args = []
    if q:
        sql += " AND (nomor_surat LIKE ? OR nama_pasien LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY id DESC"
    rows = db().execute(sql, args).fetchall()
    petugas = {}
    for r in rows:
        petugas[r["id"]] = get_petugas(r["id"])
    return render_template("surat_list.html", rows=rows, petugas=petugas, q=q, status=status)


def form_masters():
    con = db()
    return {
        "pegawai": con.execute("SELECT * FROM pegawai WHERE is_active=1 ORDER BY nama").fetchall(),
        "kendaraan": con.execute("SELECT * FROM kendaraan WHERE is_active=1 ORDER BY jenis").fetchall(),
        "rs": con.execute("SELECT * FROM rs_tujuan WHERE is_active=1 ORDER BY nama_rs").fetchall(),
        "dokter": con.execute("SELECT * FROM dokter WHERE is_active=1 ORDER BY nama").fetchall(),
        "penandatangan": con.execute("SELECT * FROM penandatangan WHERE is_active=1 ORDER BY id").fetchall(),
    }


def validasi_surat(form, surat_id=None):
    """Mengembalikan (errors, data). Nomor surat MANUAL: wajib + unik."""
    errors = []
    nomor = form.get("nomor_surat", "").strip()
    if not nomor:
        errors.append("Nomor surat wajib diisi (diisi manual).")
    else:
        sql = "SELECT * FROM surat_tugas WHERE nomor_surat=?"
        args = [nomor]
        if surat_id:
            sql += " AND id<>?"
            args.append(surat_id)
        dup = db().execute(sql, args).fetchone()
        if dup:
            errors.append(f"Nomor surat {nomor} sudah dipakai surat tanggal "
                          f"{tgl_indo(dup['tanggal_surat'])} — pasien a.n. {dup['nama_pasien']}.")
    if not form.get("nama_pasien", "").strip():
        errors.append("Nama pasien wajib diisi.")
    if not form.getlist("pegawai_id"):
        errors.append("Minimal 1 petugas harus dipilih.")
    brg, kmb = form.get("berangkat_tanggal"), form.get("kembali_tanggal")
    if brg and kmb and kmb < brg:
        errors.append("Tanggal kembali tidak boleh lebih awal dari tanggal berangkat.")
    return errors


def simpan_surat(form, surat_id=None):
    con = db()
    kend = con.execute("SELECT * FROM kendaraan WHERE id=?", (form.get("kendaraan_id"),)).fetchone()
    rs = con.execute("SELECT * FROM rs_tujuan WHERE id=?", (form.get("rs_tujuan_id"),)).fetchone()
    dok = con.execute("SELECT * FROM dokter WHERE id=?", (form.get("dokter_id"),)).fetchone()
    try:
        jarak = float(str(form.get("jarak_km", "")).replace(",", "."))
    except ValueError:
        jarak = rs["jarak_km"] if rs else None
    vals = (
        form.get("nomor_surat", "").strip(), form.get("tanggal_surat") or None,
        form.get("dasar_tanggal_rujukan") or None,
        form.get("dokter_id") or None, dok["nama"] if dok else None,
        form.get("nama_pasien", "").strip(), form.get("no_kp_jka", "").strip(),
        form.get("sub_spesialis", "").strip() or "Instalasi Gawat Darurat (IGD)",
        form.get("kendaraan_id") or None,
        kend["jenis"] if kend else None, kend["nomor_polisi"] if kend else None,
        form.get("rs_tujuan_id") or None, rs["nama_rs"] if rs else None, jarak,
        form.get("berangkat_tanggal") or None, form.get("berangkat_pukul") or None,
        form.get("kembali_tanggal") or None, form.get("kembali_pukul") or None,
        form.get("pengambilan_o2", "").strip(),
        form.get("kronologi", "").strip(),
        form.get("penandatangan_id") or None,
    )
    cols = """nomor_surat,tanggal_surat,dasar_tanggal_rujukan,dokter_id,dokter_nama,
              nama_pasien,no_kp_jka,sub_spesialis,kendaraan_id,kendaraan_jenis,kendaraan_nopol,
              rs_tujuan_id,rs_nama,jarak_km,berangkat_tanggal,berangkat_pukul,kembali_tanggal,
              kembali_pukul,pengambilan_o2,kronologi,penandatangan_id"""
    if surat_id:
        set_sql = ",".join(f"{c.strip()}=?" for c in cols.split(","))
        con.execute(f"UPDATE surat_tugas SET {set_sql}, updated_at=datetime('now','localtime') WHERE id=?",
                    vals + (surat_id,))
        con.execute("DELETE FROM surat_petugas WHERE surat_id=?", (surat_id,))
        sid = surat_id
    else:
        cur = con.execute(f"INSERT INTO surat_tugas({cols},created_by) VALUES({','.join('?'*len(vals))},?)",
                          vals + (session["user_id"],))
        sid = cur.lastrowid
    for urutan, (peg_id, jabatan) in enumerate(
            zip(form.getlist("pegawai_id"), form.getlist("jabatan_di_surat")), 1):
        p = con.execute("SELECT * FROM pegawai WHERE id=?", (peg_id,)).fetchone()
        if p:
            con.execute(
                "INSERT INTO surat_petugas(surat_id,pegawai_id,nama,nip,pangkat_gol,jabatan_di_surat,urutan) VALUES(?,?,?,?,?,?,?)",
                (sid, peg_id, p["nama"], p["nip"], p["pangkat_gol"],
                 jabatan or p["jabatan_default"], urutan))
    con.commit()
    return sid


@app.route("/surat/baru", methods=["GET", "POST"])
@login_required
def surat_baru():
    if request.method == "POST":
        errors = validasi_surat(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            sid = simpan_surat(request.form)
            audit(sid, "buat", f"Surat {request.form.get('nomor_surat')} dibuat (draft)")
            flash("Surat tersimpan sebagai Draft.", "ok")
            return redirect(url_for("surat_detail", sid=sid))
    return render_template("surat_form.html", surat=None, petugas=[], **form_masters())


@app.route("/surat/<int:sid>")
@login_required
def surat_detail(sid):
    s = get_surat(sid)
    logs = db().execute(
        """SELECT a.*, u.name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
           WHERE a.surat_id=? ORDER BY a.id DESC""", (sid,)).fetchall()
    return render_template("surat_detail.html", surat=s, petugas=get_petugas(sid), logs=logs)


@app.route("/surat/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def surat_edit(sid):
    s = get_surat(sid)
    if s["status"] != "draft":
        flash("Hanya surat berstatus Draft yang bisa diedit. Surat yang sudah terbit dikunci.", "error")
        return redirect(url_for("surat_detail", sid=sid))
    if request.method == "POST":
        errors = validasi_surat(request.form, surat_id=sid)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            simpan_surat(request.form, surat_id=sid)
            audit(sid, "edit", "Draft diubah")
            flash("Perubahan draft tersimpan.", "ok")
            return redirect(url_for("surat_detail", sid=sid))
    return render_template("surat_form.html", surat=s, petugas=get_petugas(sid), **form_masters())


@app.route("/surat/<int:sid>/terbitkan", methods=["POST"])
@login_required
def surat_terbitkan(sid):
    s = get_surat(sid)
    if s["status"] == "draft":
        db().execute("UPDATE surat_tugas SET status='berangkat', updated_at=datetime('now','localtime') WHERE id=?", (sid,))
        db().commit()
        audit(sid, "status", "Draft → Berangkat (diterbitkan)")
        flash("Surat diterbitkan — status sekarang Berangkat.", "ok")
    return redirect(url_for("surat_detail", sid=sid))


@app.route("/surat/<int:sid>/selesaikan", methods=["POST"])
@login_required
def surat_selesaikan(sid):
    s = get_surat(sid)
    f = request.form
    if not f.get("kembali_tanggal") or not f.get("terima_tanggal"):
        flash("Tanggal kembali dan tanggal terima rujukan wajib diisi untuk menutup surat.", "error")
        return redirect(url_for("surat_detail", sid=sid))
    if f.get("kembali_tanggal") < (s["berangkat_tanggal"] or ""):
        flash("Tanggal kembali tidak boleh lebih awal dari tanggal berangkat.", "error")
        return redirect(url_for("surat_detail", sid=sid))
    db().execute(
        """UPDATE surat_tugas SET kembali_tanggal=?, kembali_pukul=?, terima_tanggal=?,
           terima_pukul=?, terima_rs=?, terima_nama=?, status='selesai',
           updated_at=datetime('now','localtime') WHERE id=?""",
        (f.get("kembali_tanggal"), f.get("kembali_pukul") or None, f.get("terima_tanggal"),
         f.get("terima_pukul") or None, f.get("terima_rs") or s["rs_nama"],
         f.get("terima_nama") or "Petugas Penerima RS Tujuan", sid))
    db().commit()
    audit(sid, "status", "Berangkat → Selesai")
    flash("Surat ditutup — status Selesai.", "ok")
    return redirect(url_for("surat_detail", sid=sid))


@app.route("/surat/<int:sid>/batalkan", methods=["POST"])
@login_required
def surat_batalkan(sid):
    alasan = request.form.get("alasan_batal", "").strip()
    if not alasan:
        flash("Alasan pembatalan wajib diisi.", "error")
        return redirect(url_for("surat_detail", sid=sid))
    db().execute("UPDATE surat_tugas SET status='dibatalkan', alasan_batal=?, updated_at=datetime('now','localtime') WHERE id=?",
                 (alasan, sid))
    db().commit()
    audit(sid, "batal", alasan)
    flash("Surat dibatalkan.", "ok")
    return redirect(url_for("surat_detail", sid=sid))


# ---------------------------------------------------------------- PDF
@app.route("/surat/<int:sid>/pdf")
@login_required
def surat_pdf(sid):
    s = get_surat(sid)
    if s["status"] == "dibatalkan":
        flash("Surat yang dibatalkan tidak dicetak.", "error")
        return redirect(url_for("surat_detail", sid=sid))
    ptd = db().execute("SELECT * FROM penandatangan WHERE id=?", (s["penandatangan_id"],)).fetchone()
    if not ptd:
        ptd = db().execute("SELECT * FROM penandatangan WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()

    def jam(t):
        return (t or "..")[:5].replace(":", ".")

    def _nama_rs_pendek(nama):
        # Blok kiri surat berformat "RS <nama>" — hindari "RS RSUD ..."
        for awalan in ("RSUD ", "RS "):
            if nama.startswith(awalan):
                return nama[len(awalan):]
        return nama

    d = {
        "nomor_surat": s["nomor_surat"],
        "dasar_tanggal": tgl_indo(s["dasar_tanggal_rujukan"]),
        "dokter": s["dokter_nama"] or "-",
        "pasien": s["nama_pasien"],
        "no_kp_jka": s["no_kp_jka"] or "-",
        "sub_spesialis": s["sub_spesialis"] or "-",
        "petugas": [{"nama": p["nama"], "nip": p["nip"], "pangkat": p["pangkat_gol"],
                     "jabatan": p["jabatan_di_surat"]} for p in get_petugas(sid)],
        "jenis_kendaraan": s["kendaraan_jenis"] or "-",
        "nomor_polisi": s["kendaraan_nopol"] or "-",
        "tujuan": s["rs_nama"] or "-",
        "jarak": jarak_str(s["jarak_km"]),
        "berangkat": f"{tgl_indo(s['berangkat_tanggal'])}  Pukul {jam(s['berangkat_pukul'])} WIB",
        "kembali": (f"{tgl_indo(s['kembali_tanggal'])}  Pukul {jam(s['kembali_pukul'])} WIB"
                    if s["kembali_tanggal"] else ".......  Pukul ... WIB"),
        "o2": s["pengambilan_o2"] or "-",
        "kronologi": s["kronologi"] or "",
        "terima_tanggal": tgl_indo(s["terima_tanggal"]) if s["terima_tanggal"] else "..........",
        "terima_pukul": (jam(s["terima_pukul"]) + " WIB") if s["terima_pukul"] else "....WIB",
        "terima_rs": _nama_rs_pendek(s["terima_rs"] or s["rs_nama"] or ".........."),
        "terima_nama": s["terima_nama"] or "..............",
        "tanggal_surat": tgl_indo(s["tanggal_surat"]),
        "jabatan_baris_1": ptd["jabatan_baris_1"] if ptd else "a.n. Kepala Bagian Umum",
        "jabatan_baris_2": ptd["jabatan_baris_2"] if ptd else "Koordinator Ambulance",
        "penandatangan": ptd["nama"] if ptd else "-",
        "penandatangan_nip": ptd["nip"] if ptd else "-",
    }
    qr_path = None
    if ptd and ptd["qr_ttd_path"]:
        qr_path = os.path.join(BASE, "static", ptd["qr_ttd_path"])
    pdf_bytes = buat_pdf(d, qr_path=qr_path)
    audit(sid, "cetak", "PDF diunduh/dicetak")
    nama_file = "Surat_Tugas_" + s["nomor_surat"].replace("/", "-") + ".pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                     as_attachment=False, download_name=nama_file)


# ---------------------------------------------------------------- master data
MASTER = {
    "pegawai": {"judul": "Pegawai", "tabel": "pegawai",
                "kolom": [("nama", "Nama"), ("nip", "NIP"), ("pangkat_gol", "Pangkat/Gol"),
                          ("jabatan_default", "Jabatan Default")]},
    "kendaraan": {"judul": "Kendaraan", "tabel": "kendaraan",
                  "kolom": [("jenis", "Jenis Kendaraan"), ("nomor_polisi", "Nomor Polisi")]},
    "rs": {"judul": "RS Tujuan", "tabel": "rs_tujuan",
           "kolom": [("nama_rs", "Nama RS"), ("kota", "Kota"), ("jarak_km", "Jarak (Km)")]},
    "dokter": {"judul": "Dokter Perujuk", "tabel": "dokter",
               "kolom": [("nama", "Nama Dokter")]},
}


@app.route("/master/<jenis>", methods=["GET", "POST"])
@admin_required
def master(jenis):
    if jenis not in MASTER:
        abort(404)
    cfg = MASTER[jenis]
    con = db()
    if request.method == "POST":
        kolom = [k for k, _ in cfg["kolom"]]
        vals = [request.form.get(k, "").strip() for k in kolom]
        if not vals[0]:
            flash(f"{cfg['kolom'][0][1]} wajib diisi.", "error")
        else:
            try:
                con.execute(f"INSERT INTO {cfg['tabel']}({','.join(kolom)}) VALUES({','.join('?'*len(kolom))})", vals)
                con.commit()
                flash(f"{cfg['judul']} baru ditambahkan.", "ok")
            except sqlite3.IntegrityError:
                flash("Data duplikat — sudah ada di master.", "error")
        return redirect(url_for("master", jenis=jenis))
    rows = con.execute(f"SELECT * FROM {cfg['tabel']} ORDER BY id").fetchall()
    return render_template("master.html", cfg=cfg, jenis=jenis, rows=rows)


@app.route("/master/<jenis>/<int:mid>/toggle", methods=["POST"])
@admin_required
def master_toggle(jenis, mid):
    if jenis not in MASTER:
        abort(404)
    con = db()
    cur = con.execute(f"SELECT is_active FROM {MASTER[jenis]['tabel']} WHERE id=?", (mid,)).fetchone()
    if cur:
        new_st = 0 if cur["is_active"] else 1
        con.execute(f"UPDATE {MASTER[jenis]['tabel']} SET is_active=? WHERE id=?", (new_st, mid))
        con.commit()
        flash("Status data master diubah.", "ok")
    return redirect(url_for("master", jenis=jenis))


# ---------------------------------------------------------------- pengaturan
@app.route("/pengaturan", methods=["GET", "POST"])
@admin_required
def pengaturan():
    con = db()
    ptd = con.execute("SELECT * FROM penandatangan WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
    if request.method == "POST":
        if request.form.get("aksi") == "penandatangan":
            qr_rel = ptd["qr_ttd_path"]
            f = request.files.get("qr_ttd")
            if f and f.filename:
                nama = "qr_ttd_" + secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_DIR, nama))
                qr_rel = "uploads/" + nama
            con.execute("UPDATE penandatangan SET nama=?, nip=?, jabatan_baris_1=?, jabatan_baris_2=?, qr_ttd_path=? WHERE id=?",
                        (request.form.get("nama"), request.form.get("nip"),
                         request.form.get("jabatan_baris_1"), request.form.get("jabatan_baris_2"),
                         qr_rel, ptd["id"]))
            con.commit()
            flash("Data penandatangan tersimpan.", "ok")
        elif request.form.get("aksi") == "user_baru":
            username = request.form.get("username", "").strip()
            if not username or not request.form.get("password"):
                flash("Username dan password wajib diisi.", "error")
            else:
                try:
                    con.execute("INSERT INTO users(name,username,password_hash,role) VALUES(?,?,?,?)",
                                (request.form.get("name"), username,
                                 generate_password_hash(request.form.get("password")),
                                 request.form.get("role", "koordinator")))
                    con.commit()
                    flash("Pengguna baru ditambahkan.", "ok")
                except sqlite3.IntegrityError:
                    flash("Username sudah dipakai.", "error")
        return redirect(url_for("pengaturan"))
    users = con.execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("pengaturan.html", ptd=ptd, users=users)


if __name__ == "__main__":
    seed()
    app.run(host="0.0.0.0", port=5000, debug=False)
else:
    seed()
