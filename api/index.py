import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta
import telebot
from fpdf import FPDF
import requests
from flask import Flask, request

# --- KONFIGURASI ---
TOKEN = os.getenv("BOT_TOKEN", "7614899277:AAGhUBOI3atXqRb2IyHmO45CxC0elgDK16M")
WA_LAUNDRY = os.getenv("WA_LAUNDRY", "085641344448")
BOS_ID = int(os.getenv("BOS_ID", "1705785645"))
WEB_OFFICIAL = os.getenv("WEB_OFFICIAL", "hanifalaundry.my.id")
GAS_URL = "https://script.google.com/macros/s/AKfycbybGRFNIHrJ2u_uleBjNl-4b6VAKI6x1Ey5JjoS-Yr3Et4eow1AJvAmwVxYFTfSwv2rBQ/exec"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- FUNGSI API & UTILS ---
def send_gas(action, data=None):
    payload = {"action": action}
    if data: payload.update(data)
    try:
        res = requests.post(GAS_URL, json=payload, timeout=20)
        return res.json()
    except Exception as e:
        print(f"Error GAS: {e}")
        return None

def get_all_sheets():
    res = send_gas("get_all_data")
    if res and isinstance(res, dict) and "layanan" in res:
        return res.get("layanan", []), res.get("transaksi", []), res.get("pelanggan", [])
    return [], [], []

def is_bos(m): return m.from_user.id == BOS_ID
def clean_latin(text): return re.sub(r'[^\x00-\x7F]+', '', str(text)) if text else ""

def menu_utama():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📝 Nota Baru', '📊 Riwayat Nota')
    markup.row('💰 Cek Omset', '⚙️ Tambah Layanan')
    markup.row('👥 Edit Pelanggan', '🛠️ Edit Layanan')
    return markup

# --- FUNGSI PDF THERMAL ---
def create_pdf_thermal(data):
    try:
        fname = f"/tmp/nota_{data['inv']}.pdf"
        qr_file = f"/tmp/temp_qr_{data['inv']}.png"
        tinggi = 145 if data.get('catatan') else 135
        pdf = FPDF(format=(58, tinggi))
        pdf.add_page()
        pdf.set_margins(2, 2, 2)
        pdf.set_auto_page_break(False)

        def draw_dashed_line():
            pdf.set_font("Arial", '', 7)
            pdf.set_x(0)
            pdf.cell(58, 2, "- - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", ln=1, align='C')

        # Header
        pdf.set_font("Arial", 'B', 11)
        pdf.set_x(0)
        pdf.cell(58, 5, "HANIFA LAUNDRY", ln=1, align='C')
        pdf.set_font("Arial", '', 6)
        pdf.set_x(0)
        pdf.cell(58, 3, "Genting Raya, Kalibagor, Banyumas", ln=1, align='C')
        pdf.set_font("Arial", 'I', 6)
        pdf.set_x(0)
        pdf.cell(58, 3, clean_latin(WEB_OFFICIAL), ln=1, align='C')
        pdf.set_font("Arial", '', 6)
        pdf.set_x(0)
        pdf.cell(58, 3, f"WA: {WA_LAUNDRY}", ln=1, align='C')
        pdf.ln(1)
        draw_dashed_line()

        # Info Nota
        pdf.set_font("Arial", '', 7)
        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(14, 3.5, "No. Nota", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 3.5, f": {clean_latin(data['inv'])}", ln=1)

        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(14, 3.5, "Pelanggan", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 3.5, f": {clean_latin(data['nama'])}", ln=1)

        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(14, 3.5, "Tgl Masuk", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 3.5, f": {data['tgl_m']}", ln=1)

        if data.get('catatan') and str(data['catatan']).strip():
            pdf.ln(1)
            pdf.set_x(3)
            pdf.set_font("Arial", 'B', 6)
            catatan_txt = clean_latin(data['catatan'])[:38]
            pdf.cell(0, 3.5, f"*Catatan: {catatan_txt}", ln=1, align='L')

        pdf.ln(1)
        draw_dashed_line()

        # Tabel Rincian
        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(22, 4, "Layanan", 0)
        pdf.cell(14, 4, "Qty", 0, align='C')
        pdf.cell(16, 4, "Total", 0, align='R', ln=1)
        draw_dashed_line()

        pdf.set_x(3)
        pdf.set_font("Arial", '', 7)
        layanan_txt = clean_latin(data['layanan'])[:16]
        subtotal_num = int("".join(filter(str.isdigit, str(data['subtotal'])))) if str(data['subtotal']).isdigit() else data['subtotal']
        pdf.cell(22, 4, layanan_txt, 0)
        pdf.cell(14, 4, f"{data['qty']} {clean_latin(data['unit'])}", 0, align='C')
        pdf.cell(16, 4, f"Rp {subtotal_num:,}", 0, align='R', ln=1)

        if data.get('ongkir', 0) > 0:
            pdf.set_x(3)
            ongkir_num = int(data['ongkir'])
            pdf.cell(22, 4, "Ongkir", 0)
            pdf.cell(14, 4, "-", 0, align='C')
            pdf.cell(16, 4, f"Rp {ongkir_num:,}", 0, align='R', ln=1)

        draw_dashed_line()

        total_num = int("".join(filter(str.isdigit, str(data['total'])))) if str(data['total']).isdigit() else data['total']
        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(26, 5, "TOTAL BAYAR", 0)
        pdf.cell(26, 5, f"Rp {total_num:,}", 0, align='R', ln=1)
        draw_dashed_line()

        # Footer & QR
        pdf.set_font("Arial", 'I', 6)
        pdf.set_x(0)
        pdf.cell(58, 3, "Harap simpan nota ini.", ln=1, align='C')
        pdf.set_x(0)
        pdf.cell(58, 3, "Cucian diambil max 3 hari setelah selesai.", ln=1, align='C')

        bot_un = bot.get_me().username
        link_qr = f"https://t.me/{bot_un}?start={data['inv']}"
        api_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=90x90&data={urllib.parse.quote(link_qr)}"

        qr_inserted = False
        try:
            r = requests.get(api_qr, timeout=8)
            if r.status_code == 200:
                with open(qr_file, 'wb') as f: f.write(r.content)
                y_sebelum_qr = pdf.get_y() + 1
                pdf.image(qr_file, x=18, y=y_sebelum_qr, w=22)
                pdf.set_y(y_sebelum_qr + 23)
                qr_inserted = True
        except: pass

        pdf.set_font("Arial", '', 6)
        if qr_inserted:
            pdf.set_x(0)
            pdf.cell(58, 3, "Scan QR untuk Cek Status Cucian", ln=1, align='C')

        pdf.ln(0.5)
        pdf.set_font("Arial", 'B', 7)
        pdf.set_x(0)
        pdf.cell(58, 4, "=== TERIMA KASIH ===", ln=1, align='C')

        pdf.output(fname)
        if os.path.exists(qr_file): os.remove(qr_file)
        return fname
    except Exception as e:
        print(f"Error PDF: {e}")
        return None

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    args = message.text.split()
    if len(args) > 1:
        nota_id = str(args[1]).strip().upper()
        _, all_trans, _ = get_all_sheets()
        found = next((row for row in all_trans[1:] if len(row) > 1 and str(row[1]).strip().upper() == nota_id), None)
        if found:
            status_txt = found[6] if len(found) > 6 else "Proses"
            icon = "⏳" if status_txt == "Proses" else "✅" if status_txt == "Selesai" else "🧺"
            unit_txt = found[7] if len(found) > 7 else "Kg"
            qty_info = f"{found[4]} {unit_txt}" if len(found) > 4 else ""
            balasan = (f"📋 DETAIL NOTA HANIFA\n---------------------------\n"
                      f"👤 Pelanggan: {found[2]}\n🎫 Nota: {found[1]}\n"
                      f"🧺 Layanan: {found[3]}\n📦 Jumlah: {qty_info}\n"
                      f"💰 Total: Rp {found[5]}\n---------------------------\n"
                      f"📌 Status: {icon} {status_txt}\n---------------------------\n"
                      f"🌐 {WEB_OFFICIAL}\nTerima kasih!")
            bot.send_message(message.chat.id, balasan)
        else:
            bot.send_message(message.chat.id, f"❌ Nota {nota_id} tidak ditemukan.")
        return

    if is_bos(message):
        bot.send_message(message.chat.id, "Hanifa Laundry Aktif!", reply_markup=menu_utama())
    else:
        bot.send_message(message.chat.id, f"⚠️ Akses Ditolak.\nID Anda: `{message.from_user.id}` tidak cocok dengan BOS_ID.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text_bos(message):
    if not is_bos(message):
        bot.send_message(message.chat.id, f"⚠️ Akses Ditolak. ID Anda: `{message.from_user.id}`", parse_mode="Markdown")
        return

    txt = message.text.strip()

    if txt == '📊 Riwayat Nota':
        show_history(message, 1)
    elif txt == '💰 Cek Omset':
        m = telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("Harian", callback_data="oms_hari"),
            telebot.types.InlineKeyboardButton("Bulanan", callback_data="oms_bulan"),
            telebot.types.InlineKeyboardButton("Tahunan", callback_data="oms_tahun"))
        bot.send_message(message.chat.id, "💰 Pilih laporan omset:", reply_markup=m)
    elif txt == '👥 Edit Pelanggan':
        _, _, list_p = get_all_sheets()
        m = telebot.types.InlineKeyboardMarkup()
        for i, r in enumerate(list_p[1:]):
            if r and len(r) > 0 and str(r[0]).strip():
                m.add(telebot.types.InlineKeyboardButton(f"{r[0]}", callback_data=f"editpel_{i+2}"))
        bot.send_message(message.chat.id, "Pilih pelanggan yang ingin diedit:", reply_markup=m)
    elif txt == '🛠️ Edit Layanan':
        data_l, _, _ = get_all_sheets()
        m = telebot.types.InlineKeyboardMarkup()
        for i, r in enumerate(data_l[1:]):
            if r and len(r) > 0 and str(r[0]).strip():
                m.add(telebot.types.InlineKeyboardButton(f"{r[0]}", callback_data=f"editlay_{i+2}"))
        bot.send_message(message.chat.id, "Pilih layanan yang ingin diedit:", reply_markup=m)
    elif txt == '📝 Nota Baru':
        bot.send_message(message.chat.id, "Format Nota Cepat (Ketik dalam 1 pesan):\n\n`NAMA | HP | ALAMAT | NAMA_LAYANAN | QTY | ONGKIR | CATATAN`\n\nContoh:\n`Rina | 08123456789 | Kalibagor | Cuci Komplit | 5 | 0 | Jangan pakai pewangi`", parse_mode="Markdown")
    elif "|" in txt:
        proses_nota_otomatis(message, txt)
    else:
        bot.send_message(message.chat.id, "Hanifa Laundry Aktif!", reply_markup=menu_utama())

def proses_nota_otomatis(m, txt):
    parts = [p.strip() for p in txt.split("|")]
    if len(parts) < 5:
        bot.send_message(m.chat.id, "⚠️ Format salah. Minimal masukkan 5 data:\n`NAMA | HP | ALAMAT | LAYANAN | QTY`", parse_mode="Markdown")
        return

    nama, phone, alamat, layanan_nama, qty_str = parts[:5]
    ongkir_str = parts[5] if len(parts) > 5 else "0"
    catatan = parts[6] if len(parts) > 6 else ""

    data_l, _, list_p = get_all_sheets()

    # Cek & Tambah Pelanggan
    pel_exist = next((p for p in list_p[1:] if len(p) > 0 and str(p[0]).lower() == nama.lower()), None)
    if not pel_exist:
        phone_fmt = '62' + phone[1:] if phone.startswith('0') else phone
        send_gas("add_pelanggan", {"row": [nama, phone_fmt, alamat]})

    # Cek Layanan
    srv = next((l for l in data_l[1:] if len(l) > 0 and str(l[0]).lower() == layanan_nama.lower()), None)
    harga = int(str(srv[1]).replace('.', '')) if srv else 7000
    hari = srv[2] if srv else "2"
    unit = srv[3] if srv and len(srv) > 3 else "Kg"

    qty = float(qty_str.replace(',', '.'))
    subtotal = int(qty * harga)
    ongkir = int(ongkir_str.replace('.', '')) if ongkir_str.isdigit() else 0
    total = subtotal + ongkir

    inv = f"HNF-{datetime.now().strftime('%d%m%y%H%M')}"
    tgl_m = datetime.now().strftime("%d/%m/%Y %H:%M")
    tgl_s = (datetime.now() + timedelta(days=int(hari))).strftime("%d/%m/%Y")

    send_gas("add_transaksi", {"row": [tgl_m, inv, nama, layanan_nama, qty, total, "Proses", unit, tgl_s, "", catatan]})

    pdf_data = {
        'nama': nama, 'inv': inv, 'tgl_m': tgl_m, 'layanan': layanan_nama,
        'qty': qty, 'unit': unit, 'subtotal': subtotal, 'ongkir': ongkir,
        'total': total, 'catatan': catatan
    }
    pdf = create_pdf_thermal(pdf_data)

    if pdf:
        ongkir_txt = f"\nOngkir: Rp {ongkir:,}" if ongkir > 0 else ""
        catatan_txt = f"\n📝 Catatan: {catatan}" if catatan else ""
        wa_text = (f"HANIFA LAUNDRY\n---------------------------\n"
                  f"Pelanggan: {nama}\nNo. Nota: {inv}\n"
                  f"Layanan: {layanan_nama}\n📦 Jumlah: {qty} {unit}\n"
                  f"Subtotal: Rp {subtotal:,}{ongkir_txt}\nTotal: Rp {total:,}{catatan_txt}\n---------------------------\n"
                  f"🌐 {WEB_OFFICIAL}\nTerima Kasih!")

        phone_target = '62' + phone[1:] if phone.startswith('0') else phone
        url_wa = f"https://api.whatsapp.com/send?phone={phone_target}&text={urllib.parse.quote(wa_text)}"
        markup = telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("📲 Kirim WA", url=url_wa))

        with open(pdf, "rb") as f:
            bot.send_document(m.chat.id, f, caption="✅ Nota Berhasil Dibuat!", reply_markup=markup)
        os.remove(pdf)

def show_history(m, page):
    _, data, _ = get_all_sheets()
    if len(data) <= 1:
        bot.send_message(m.chat.id, "Belum ada transaksi.")
        return
    rows = data[1:]
    rows.reverse()
    curr = rows[(page-1)*10 : page*10]
    markup = telebot.types.InlineKeyboardMarkup()
    for i, r in enumerate(curr):
        idx = len(data) - ((page-1)*10 + i)
        icon = "⏳" if len(r) > 6 and r[6] == "Proses" else "✅" if len(r) > 6 and r[6] == "Selesai" else "🧺"
        markup.add(telebot.types.InlineKeyboardButton(f"{icon} {r[2]} | {r[1]}", callback_data=f"view_{idx}"))
    if len(rows) > 10:
        nav = []
        if page > 1: nav.append(telebot.types.InlineKeyboardButton("⬅️ Prev", callback_data=f"p_{page-1}"))
        if page*10 < len(rows): nav.append(telebot.types.InlineKeyboardButton("Next ➡️", callback_data=f"p_{page+1}"))
        markup.row(*nav)
    bot.send_message(m.chat.id, f"📊 Riwayat Nota - Halaman {page}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    try:
        if call.data.startswith('p_'):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_history(call.message, int(call.data.split('_')[1]))
        elif call.data.startswith('view_'):
            idx = int(call.data.split('_')[1])
            _, all_trans, _ = get_all_sheets()
            if idx <= len(all_trans):
                r = all_trans[idx - 1]
                st = r[6] if len(r) > 6 else "Proses"
                icon = "⏳" if st == "Proses" else "✅" if st == "Selesai" else "🧺"
                txt = (f"📋 DETAIL NOTA\n---------------------------\n👤 {r[2]}\n🎫 {r[1]}\n🧺 {r[3]}\n💰 Rp {r[5]}\n{icon} Status: {st}")
                m = telebot.types.InlineKeyboardMarkup()
                m.add(telebot.types.InlineKeyboardButton("⏳ Proses", callback_data=f"u_{idx}_Proses"),
                      telebot.types.InlineKeyboardButton("✅ Selesai", callback_data=f"u_{idx}_Selesai"))
                m.add(telebot.types.InlineKeyboardButton("🧺 Diambil", callback_data=f"u_{idx}_Diambil"))
                m.row(telebot.types.InlineKeyboardButton("🖨️ Print Ulang", callback_data=f"pr_{idx}"),
                      telebot.types.InlineKeyboardButton("📲 Kirim WA", callback_data=f"rw_{idx}"))
                bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=m)
        elif call.data.startswith('u_'):
            _, idx, st = call.data.split('_')
            idx = int(idx)
            send_gas("update_cell", {"sheet_name": "transaksi", "row": idx, "col": 7, "value": st})
            if st == "Diambil":
                send_gas("update_cell", {"sheet_name": "transaksi", "row": idx, "col": 10, "value": datetime.now().strftime("%d/%m/%Y %H:%M")})
            bot.answer_callback_query(call.id, f"Status: {st}")
            bot.send_message(call.message.chat.id, f"✅ Nota diupdate ke: {st}", reply_markup=menu_utama())
        elif call.data.startswith('pr_'):
            idx = int(call.data.split('_')[1])
            _, all_trans, _ = get_all_sheets()
            if idx <= len(all_trans):
                r = all_trans[idx - 1]
                d_p = {
                    'inv': r[1], 'nama': r[2], 'tgl_m': r[0], 'layanan': r[3],
                    'qty': r[4], 'total': r[5], 'subtotal': r[5], 'ongkir': 0,
                    'unit': r[7] if len(r) > 7 else 'Kg', 'catatan': r[10] if len(r) > 10 else ''
                }
                pdf = create_pdf_thermal(d_p)
                if pdf:
                    with open(pdf, "rb") as f: bot.send_document(call.message.chat.id, f)
                    os.remove(pdf)
        elif call.data.startswith('oms_'):
            tipe = call.data.split('_')[1]
            _, data, _ = get_all_sheets()
            total = 0
            now = datetime.now()
            tgl_skrg = now.strftime("%d/%m/%Y")
            bln_skrg = now.strftime("%m/%Y")
            thn_skrg = now.strftime("%Y")
            for r in data[1:]:
                try:
                    if len(r) > 9 and r[6] == "Diambil" and str(r[9]).strip() != "":
                        tgl_ambil_full = str(r[9]).split()[0]
                        cocok = False
                        if tipe == "hari" and tgl_ambil_full == tgl_skrg: cocok = True
                        elif tipe == "bulan" and bln_skrg in tgl_ambil_full: cocok = True
                        elif tipe == "tahun" and thn_skrg in tgl_skrg: cocok = True
                        if cocok:
                            angka = "".join(filter(str.isdigit, str(r[5])))
                            if angka: total += int(angka)
                except: continue
            bot.edit_message_text(f"💰 OMSET {tipe.upper()}: Rp {total:,}", call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Callback Error: {e}")

# --- ROUTE VERCEL WEBHOOK ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Unauthorized', 403

@app.route('/', methods=['GET'])
def index():
    return "Hanifa Laundry Bot Serverless is Ready!"
