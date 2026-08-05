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

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- FUNGSI BOT (KODE UTAMA LAUNDRY) ---
def send_gas(action, data=None):
    payload = {"action": action}
    if data: payload.update(data)
    try:
        res = requests.post(GAS_URL, json=payload, timeout=25)
        return res.json()
    except: return None

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
def tombol_batal():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add('❌ BATAL')
    return markup

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
    if message.text == '❌ BATAL':
        bot.send_message(message.chat.id, "Pesanan dibatalkan.", reply_markup=menu_utama())
        return
    if message.text == '📝 Nota Baru':
        bot.send_message(message.chat.id, "Fitur Nota Baru siap diproses.")

# --- ENDPOINT VERCEL WEBHOOK ---
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
    return "Hanifa Laundry Bot is Live on Vercel!"
        
