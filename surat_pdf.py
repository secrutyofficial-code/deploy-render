"""Generator PDF Surat Tugas Ambulance — Legal 216x356 mm, 1 halaman.
Layout meniru template RSUD Cut Nyak Dhien Meulaboh.
Dipakai route /surat/<id>/pdf pada app.py.
"""
import os
from fpdf import FPDF

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def buat_pdf(d, qr_path=None):
    """d: dict data surat (string siap cetak). Mengembalikan bytes PDF."""
    pdf = FPDF(orientation="P", unit="mm", format=(215.9, 355.6))  # Legal
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_margins(18, 12, 18)
    W = 215.9 - 36

    # ---------- KOP ----------
    pdf.image(os.path.join(ASSETS, "logo-kiri.png"), x=20, y=11, w=23)
    pdf.image(os.path.join(ASSETS, "logo-kanan.png"), x=173, y=11, w=21)
    pdf.set_y(11)
    pdf.set_font("times", "", 13)
    pdf.cell(W, 6, "PEMERINTAH KABUPATEN ACEH BARAT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("times", "B", 11.5)
    pdf.set_x(40)
    pdf.cell(136, 7, "RUMAH SAKIT UMUM DAERAH CUT NYAK DHIEN MEULABOH", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("times", "", 10.5)
    pdf.cell(W, 5, "Jl. Gajah Mada  Telp. (0655) 7551274 - Fax. (0655) 7551274", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(W, 5, "Email : rsucnd@acehbaratkab.go.id     Website : www.rsucnd.acehbaratkab.go.id", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("times", "B", 13)
    pdf.cell(W, 6, "MEULABOH  23617", align="C", new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 1
    pdf.set_line_width(0.7); pdf.line(18, y, 18 + W, y)
    pdf.set_line_width(0.25); pdf.line(18, y + 1.4, 18 + W, y + 1.4)
    pdf.set_y(y + 6)

    # ---------- JUDUL ----------
    pdf.set_font("times", "BU", 14)
    pdf.cell(W, 7, "SURAT  TUGAS", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("times", "", 12)
    pdf.cell(W, 6, f"Nomor : {d['nomor_surat']}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def baris(label, isi, label_w=26):
        pdf.set_font("times", "", 11.5)
        pdf.cell(label_w, 6, label)
        pdf.cell(6, 6, ":")
        pdf.multi_cell(W - label_w - 6, 6, isi)

    # ---------- DASAR ----------
    baris("Dasar", f"Surat dari Rujukan Antar Rumah Sakit tanggal {d['dasar_tanggal']}")
    sub = [("Dokter yang merujuk", d["dokter"]), ("Nama Pasien", d["pasien"]),
           ("No. KP. JKA", d["no_kp_jka"]), ("Sub/ Spesialis", d["sub_spesialis"])]
    for lab, val in sub:
        pdf.set_x(18 + 32)
        pdf.set_font("times", "", 11.5)
        pdf.cell(42, 6, lab); pdf.cell(6, 6, ":"); pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(18); pdf.ln(3)
    pdf.set_font("times", "", 12)
    pdf.cell(W, 6, "MENUGASKAN :", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ---------- KEPADA ----------
    pdf.set_font("times", "", 11.5)
    pdf.cell(26, 6, "Kepada"); pdf.cell(6, 6, ":"); pdf.ln(0.1)
    for i, p in enumerate(d["petugas"], 1):
        pdf.set_x(18 + 32)
        pdf.set_font("times", "", 11.5)
        pdf.cell(8, 6, f"{i}."); pdf.cell(24, 6, "Nama"); pdf.cell(6, 6, ":")
        pdf.cell(0, 6, p["nama"], new_x="LMARGIN", new_y="NEXT")
        for lab, val in [("Nip", p["nip"] or "-"), ("Pangkat/Gol", p["pangkat"] or "-"),
                         ("Jabatan", p["jabatan"])]:
            pdf.set_x(18 + 40)
            pdf.cell(24, 6, lab); pdf.cell(6, 6, ":"); pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    pdf.set_x(18); pdf.ln(1)

    # ---------- UNTUK + TABEL ----------
    baris("Untuk", "Mengantar  pasien  rujukan  dengan  Kenderaan  Khusus  Ambulance RSUD Cut Nyak Dhien Meulaboh Sebagai Berikut :")
    rows = [("1. Jenis Kenderaan", d["jenis_kendaraan"]), ("2. Nomor Polisi", d["nomor_polisi"]),
            ("3. Tujuan Rujukan", d["tujuan"]), ("4. Jarak Tempuh Rujukan", d["jarak"]),
            ("5. Berangkat Pada Tanggal", d["berangkat"]), ("6. Kembali Pada Tanggal", d["kembali"]),
            ("7. Pengambilan O2 di IPSRS", d["o2"])]
    tx, tw1, tw2 = 18 + 32, 62, 6
    tw3 = W - 32 - 68
    pdf.set_fill_color(232, 240, 224)
    for lab, val in rows:
        pdf.set_x(tx)
        pdf.set_font("times", "", 11)
        pdf.cell(tw1, 6.4, " " + lab, border=1)
        pdf.cell(tw2, 6.4, ":", border=1, align="C")
        pdf.cell(tw3, 6.4, " " + val, border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(18); pdf.ln(4)

    # ---------- KRONOLOGI ----------
    pdf.set_font("times", "", 11.5)
    pdf.multi_cell(W, 6, f"* Kronologi Kejadian (bila ada) : {d['kronologi']}")
    for _ in range(3):
        yy = pdf.get_y() + 4.5
        pdf.set_dash_pattern(dash=0.6, gap=1.6)
        pdf.line(18, yy, 18 + W, yy)
        pdf.set_dash_pattern()
        pdf.ln(6)
    pdf.ln(6)

    # ---------- BLOK BAWAH ----------
    y_bottom = pdf.get_y()
    half = W / 2 - 4
    pdf.set_fill_color(242, 242, 242)
    pdf.rect(18, y_bottom, half, 62, style="F")
    pdf.set_xy(20, y_bottom + 4)
    pdf.set_font("times", "", 11.5)
    pdf.cell(half - 4, 6, "Waktu Terima Rujukan :", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(20); pdf.cell(half - 4, 6, f"Tanggal : {d['terima_tanggal']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(20); pdf.cell(half - 4, 6, f"Pukul    : {d['terima_pukul']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(20); pdf.ln(4)
    pdf.set_x(20); pdf.cell(half - 4, 6, f"RS {d['terima_rs']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(20, y_bottom + 52)
    pdf.cell(half - 4, 6, f"( {d['terima_nama']} )")

    rx = 18 + half + 8
    pdf.set_xy(rx, y_bottom + 2)
    pdf.set_font("times", "", 11.5)
    pdf.cell(W - half - 8, 6, f"Meulaboh, {d['tanggal_surat']}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(rx); pdf.cell(W - half - 8, 6, d["jabatan_baris_1"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(rx); pdf.cell(W - half - 8, 6, d["jabatan_baris_2"], align="C", new_x="LMARGIN", new_y="NEXT")
    qr = qr_path if (qr_path and os.path.exists(qr_path)) else os.path.join(ASSETS, "qr-ttd-asli.png")
    pdf.image(qr, x=rx + 26, y=pdf.get_y() + 3, w=30)
    pdf.set_xy(rx, pdf.get_y() + 40)
    pdf.set_font("times", "BU", 11.5)
    pdf.cell(W - half - 8, 6, d["penandatangan"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(rx); pdf.set_font("times", "", 11.5)
    pdf.cell(W - half - 8, 6, f"Nip. {d['penandatangan_nip']}", align="C")

    pdf.image(os.path.join(ASSETS, "logo-bse.png"), x=100, y=340, w=16)
    return bytes(pdf.output())
