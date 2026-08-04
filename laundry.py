import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import requests

# --- KONFIGURASI (Membaca dari Environment Variables) ---
TOKEN = os.getenv("BOT_TOKEN", "7614899277:AAGhUBOI3atXqRb2IyHmO45CxC0elgDK16M")
WA_LAUNDRY = os.getenv("WA_LAUNDRY", "085641344448")
BOS_ID = int(os.getenv("BOS_ID", "1705785645"))
WEB_OFFICIAL = os.getenv("WEB_OFFICIAL", "hanifalaundry.my.id")

bot = telebot.TeleBot(TOKEN)

# --- KONEKSI GOOGLE SHEETS ---
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Prioritas membaca kredensial dari Environment Variable
    google_creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_env:
        creds_dict = json.loads(google_creds_env)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Fallback file lokal
        creds = ServiceAccountCredentials.from_json_keyfile_name("kunci.json", scope)

    client = gspread.authorize(creds)
    sheet = client.open("Database Hanifa Laundry")
    ws_layanan = sheet.get_worksheet(0)
    ws_transaksi = sheet.get_worksheet(1)
    ws_pelanggan = sheet.get_worksheet(2)
except Exception as e:
    print(f"Gagal koneksi ke Google Sheets: {e}")

# --- FUNGSI KEAMANAN & HELPER ---
def is_bos(m):
    return m.from_user.id == BOS_ID

def clean_latin(text):
    """Menghapus karakter non-ASCII/Emoji agar FPDF tidak error"""
    if not text:
        return ""
    return re.sub(r'[^\x00-\x7F]+', '', str(text))

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

# --- FUNGSI PDF PROFESIONAL ---
def create_pdf_thermal(data):
    try:
        fname = f"nota_{data['inv']}.pdf"
        qr_file = f"temp_qr_{data['inv']}.png"

        tinggi = 170 if data.get('catatan') else 160
        pdf = FPDF(format=(58, tinggi))
        pdf.add_page()
        pdf.set_margins(3, 2, 3)
        pdf.set_auto_page_break(False)

        # HEADER
        pdf.set_font("Arial", 'B', 12)
        pdf.set_x(0)
        pdf.cell(0, 6, "HANIFA LAUNDRY", ln=1, align='C')

        pdf.set_font("Arial", '', 6)
        pdf.cell(0, 3, "Genting Raya, Kalibagor, Banyumas", ln=1, align='C')

        pdf.set_font("Arial", 'I', 6)
        pdf.cell(0, 3, clean_latin(WEB_OFFICIAL), ln=1, align='C')

        pdf.set_font("Arial", '', 6)
        pdf.cell(0, 3, f"WA: {WA_LAUNDRY}", ln=1, align='C')

        pdf.set_draw_color(0, 0, 0)
        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(2)

        # DATA NOTA
        pdf.set_font("Arial", '', 8)
        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(12, 4, "Nota", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 4, f": {clean_latin(data['inv'])}", ln=1)

        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(12, 4, "Nama", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 4, f": {clean_latin(data['nama'])}", ln=1)

        pdf.set_x(3)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(12, 4, "Masuk", 0)
        pdf.set_font("Arial", '', 7)
        pdf.cell(0, 4, f": {data['tgl_m']}", ln=1)

        if data.get('catatan') and str(data['catatan']).strip():
            pdf.set_x(3)
            pdf.set_font("Arial", 'B', 7)
            pdf.cell(12, 4, "Catatan", 0)
            pdf.set_font("Arial", 'I', 6)
            catatan_text = clean_latin(data['catatan'])[:35]
            pdf.cell(0, 4, f": {catatan_text}", ln=1)

        pdf.ln(1)
        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(2)

        # TABLE
        pdf.set_font("Arial", 'B', 7)
        pdf.set_x(3)
        pdf.cell(24, 5, "Layanan", 0)
        pdf.cell(15, 5, "Qty", 0, align='C')
        pdf.cell(13, 5, "Total", 0, align='R', ln=1)

        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(1)

        pdf.set_font("Arial", '', 7)
        pdf.set_x(3)
        layanan_txt = clean_latin(data['layanan'])[:18]
        pdf.cell(24, 5, layanan_txt, 0)
        pdf.cell(15, 5, f"{data['qty']} {clean_latin(data['unit'])}", 0, align='C')
        pdf.cell(13, 5, f"{data['subtotal']}", 0, align='R', ln=1)

        if data.get('ongkir', 0) > 0:
            pdf.set_x(3)
            pdf.cell(24, 5, "Ongkir", 0)
            pdf.cell(15, 5, "", 0)
            pdf.cell(13, 5, f"{data['ongkir']}", 0, align='R', ln=1)

        pdf.ln(1)
        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(2)

        # TOTAL
        pdf.set_font("Arial", 'B', 10)
        pdf.set_x(3)
        pdf.cell(40, 6, "TOTAL", 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(12, 6, f"Rp {data['total']}", 0, ln=1, align='R')

        pdf.ln(1)
        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("Arial", 'I', 5)
        pdf.cell(0, 3, "Cucian diambil max 3 hari", ln=1, align='C')

        pdf.ln(1)
        pdf.line(3, pdf.get_y(), 55, pdf.get_y())
        pdf.ln(2)

        # QR CODE
        bot_un = bot.get_me().username
        link_qr = f"https://t.me/{bot_un}?start={data['inv']}"
        api_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=90x90&data={urllib.parse.quote(link_qr)}"

        qr_inserted = False
        try:
            r = requests.get(api_qr, timeout=8)
            if r.status_code == 200:
                with open(qr_file, 'wb') as f:
                    f.write(r.content)
                pdf.ln(2)
                pdf.image(qr_file, x=17, w=22)
                pdf.ln(18)
                qr_inserted = True
        except:
            pass

        pdf.set_font("Arial", '', 6)
        if qr_inserted:
            pdf.cell(0, 3, "Scan untuk cek status", ln=1, align='C')
            pdf.ln(1)

        pdf.set_font("Arial", 'B', 7)
        pdf.cell(0, 4, "*** TERIMA KASIH ***", ln=1, align='C')

        pdf.output(fname)

        if os.path.exists(qr_file):
            os.remove(qr_file)
        return fname
    except Exception as e:
        print(f"Error PDF: {e}")
        return None

# --- HANDLER START ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    args = message.text.split()
    if len(args) > 1:
        nota_id = str(args[1]).strip().upper()
        try:
            all_trans = ws_transaksi.get_all_values()
            found = None
            for row in all_trans[1:]:
                if len(row) > 1 and str(row[1]).strip().upper() == nota_id:
                    found = row
                    break
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
        except Exception as e:
            bot.send_message(message.chat.id, "❌ Gagal membaca database.")
        return

    if is_bos(message):
        bot.send_message(message.chat.id, "Hanifa Laundry Aktif!", reply_markup=menu_utama())
    else:
        bot.send_message(message.chat.id, "Selamat datang! Scan QR di nota Anda.")

# --- CALLBACK QUERY ROUTER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    if call.data.startswith('p_'):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_history(call.message, int(call.data.split('_')[1]))

    elif call.data.startswith('selpel_'):
        # Ringkas callback data untuk mencegah batas 64 byte
        idx = int(call.data.split('_')[1])
        list_p = ws_pelanggan.get_all_records()
        if idx < len(list_p):
            p = list_p[idx]
            bot.delete_message(call.message.chat.id, call.message.message_id)
            show_service_menu(call.message, {'nama': p['Nama'], 'phone': str(p['No HP']), 'alamat': p['Alamat']})

    elif call.data.startswith('view_'):
        idx = int(call.data.split('_')[1])
        r = ws_transaksi.row_values(idx)
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
        ws_transaksi.update_cell(idx, 7, st) # Update Kolom 7 (Status)
        if st == "Diambil":
            # Update Kolom 10 (Tanggal Ambil)
            ws_transaksi.update_cell(idx, 10, datetime.now().strftime("%d/%m/%Y %H:%M"))
        bot.answer_callback_query(call.id, f"Status: {st}")
        bot.send_message(call.message.chat.id, f"✅ Nota diupdate ke: {st}", reply_markup=menu_utama())

    elif call.data.startswith('pr_'):
        idx = int(call.data.split('_')[1])
        r = ws_transaksi.row_values(idx)
        d_p = {
            'inv': r[1],
            'nama': r[2],
            'tgl_m': r[0],
            'layanan': r[3],
            'qty': r[4],
            'total': r[5],
            'subtotal': r[5],
            'ongkir': 0,
            'unit': r[7] if len(r) > 7 else 'Kg',
            'catatan': r[10] if len(r) > 10 else ''
        }
        pdf = create_pdf_thermal(d_p)
        if pdf:
            with open(pdf, "rb") as f:
                bot.send_document(call.message.chat.id, f)
            os.remove(pdf)

    elif call.data.startswith('rw_'):
        idx = int(call.data.split('_')[1])
        r = ws_transaksi.row_values(idx)
        list_p = ws_pelanggan.get_all_records()
        pel = next((p for p in list_p if str(p['Nama']).lower() == str(r[2]).lower()), None)
        if pel:
            qty_info = f"{r[4]} {r[7]}" if len(r) > 7 else r[4]
            catatan_txt = f"\n📝 Catatan: {r[10]}" if len(r) > 10 and r[10] else ""
            wa_t = (f"HANIFA LAUNDRY\n---------------------------\n"
                   f"Pelanggan: {r[2]}\nNo. Nota: {r[1]}\n"
                   f"Layanan: {r[3]}\n📦 Jumlah: {qty_info}\n"
                   f"Subtotal: Rp {r[5]}\n"
                   f"Total: Rp {r[5]}{catatan_txt}\n---------------------------\n"
                   f"🌐 {WEB_OFFICIAL}\nTerima Kasih!")
            url = f"https://api.whatsapp.com/send?phone={pel['No HP']}&text={urllib.parse.quote(wa_t)}"
            bot.send_message(call.message.chat.id, "📲 Link WA:", reply_markup=telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("Kirim WA", url=url)))

    elif call.data.startswith('oms_'):
        tipe = call.data.split('_')[1]
        data = ws_transaksi.get_all_values()
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
                    if tipe == "hari" and tgl_ambil_full == tgl_skrg:
                        cocok = True
                    elif tipe == "bulan" and bln_skrg in tgl_ambil_full:
                        cocok = True
                    elif tipe == "tahun" and thn_skrg in tgl_ambil_full:
                        cocok = True
                    if cocok:
                        angka = "".join(filter(str.isdigit, str(r[5])))
                        if angka:
                            total += int(angka)
            except:
                continue
        bot.edit_message_text(f"💰 OMSET {tipe.upper()}: Rp {total:,}", call.message.chat.id, call.message.message_id)

    elif call.data.startswith('editpel_'):
        idx = int(call.data.split('_')[1])
        m = telebot.types.InlineKeyboardMarkup()
        m.add(telebot.types.InlineKeyboardButton("Nama", callback_data=f"upel_{idx}_1"),
              telebot.types.InlineKeyboardButton("No HP", callback_data=f"upel_{idx}_2"),
              telebot.types.InlineKeyboardButton("Alamat", callback_data=f"upel_{idx}_3"))
        bot.edit_message_text("Pilih kolom pelanggan yang akan diedit:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif call.data.startswith('upel_'):
        _, idx, col = call.data.split('_')
        msg = bot.send_message(call.message.chat.id, "Masukkan data baru:", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, lambda m: proses_edit_cell(m, ws_pelanggan, int(idx), int(col)))

    elif call.data.startswith('editlay_'):
        idx = int(call.data.split('_')[1])
        m = telebot.types.InlineKeyboardMarkup()
        m.add(telebot.types.InlineKeyboardButton("Nama Layanan", callback_data=f"ulay_{idx}_1"),
              telebot.types.InlineKeyboardButton("Harga", callback_data=f"ulay_{idx}_2"),
              telebot.types.InlineKeyboardButton("Hari", callback_data=f"ulay_{idx}_3"))
        bot.edit_message_text("Pilih kolom layanan yang akan diedit:", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif call.data.startswith('ulay_'):
        _, idx, col = call.data.split('_')
        msg = bot.send_message(call.message.chat.id, "Masukkan data baru:", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, lambda m: proses_edit_cell(m, ws_layanan, int(idx), int(col)))

def proses_edit_cell(m, ws, row, col):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    try:
        ws.update_cell(row, col, m.text)
        bot.send_message(m.chat.id, "✅ Data berhasil diperbarui!", reply_markup=menu_utama())
    except:
        bot.send_message(m.chat.id, "❌ Gagal memperbarui data.", reply_markup=menu_utama())

# --- HANDLER TEKS UTAMA ---
@bot.message_handler(func=lambda m: True)
def handle_text_bos(message):
    if not is_bos(message):
        return
    if message.text == '❌ BATAL':
        bot.send_message(message.chat.id, "Pesanan dibatalkan.", reply_markup=menu_utama())
        return
    if message.text == '📝 Nota Baru':
        start_nota(message)
    elif message.text == '📊 Riwayat Nota':
        show_history(message, 1)
    elif message.text == '💰 Cek Omset':
        m = telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("Harian", callback_data="oms_hari"),
            telebot.types.InlineKeyboardButton("Bulanan", callback_data="oms_bulan"),
            telebot.types.InlineKeyboardButton("Tahunan", callback_data="oms_tahun"))
        bot.send_message(message.chat.id, "💰 Pilih laporan:", reply_markup=m)
    elif message.text == '⚙️ Tambah Layanan':
        start_tambah_layanan(message)
    elif message.text == '👥 Edit Pelanggan':
        data = ws_pelanggan.get_all_values()
        m = telebot.types.InlineKeyboardMarkup()
        blacklist = ['📝 Nota Baru', '📊 Riwayat Nota', '💰 Cek Omset', '⚙️ Tambah Layanan', '👥 Edit Pelanggan', '🛠️ Edit Layanan']
        for i, r in enumerate(data[1:]):
            nama_p = str(r[0]).strip()
            if nama_p and nama_p not in blacklist:
                m.add(telebot.types.InlineKeyboardButton(f"{nama_p}", callback_data=f"editpel_{i+2}"))
        bot.send_message(message.chat.id, "Pilih pelanggan yang ingin diedit:", reply_markup=m)
    elif message.text == '🛠️ Edit Layanan':
        data = ws_layanan.get_all_values()
        m = telebot.types.InlineKeyboardMarkup()
        for i, r in enumerate(data[1:]):
            m.add(telebot.types.InlineKeyboardButton(f"{r[0]}", callback_data=f"editlay_{i+2}"))
        bot.send_message(message.chat.id, "Pilih layanan yang ingin diedit:", reply_markup=m)

# --- ALUR NOTA BARU ---
def start_nota(m):
    msg = bot.send_message(m.chat.id, "Nama Pelanggan:", reply_markup=tombol_batal())
    bot.register_next_step_handler(msg, search_pelanggan)

def search_pelanggan(m):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    nama_in = m.text
    list_p = ws_pelanggan.get_all_records()
    matches = [(i, p) for i, p in enumerate(list_p) if nama_in.lower() in str(p['Nama']).lower()]
    
    if not matches:
        ud = {'nama': nama_in}
        msg = bot.send_message(m.chat.id, f"👤 {nama_in} baru. No HP:", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, lambda ms: get_hp_p(ms, ud))
    elif len(matches) == 1:
        p = matches[0][1]
        show_service_menu(m, {'nama': p['Nama'], 'phone': str(p['No HP']), 'alamat': p['Alamat']})
    else:
        markup = telebot.types.InlineKeyboardMarkup()
        for orig_idx, p in matches:
            markup.add(telebot.types.InlineKeyboardButton(f"{p['Nama']} | {str(p['No HP'])[-4:]}", callback_data=f"selpel_{orig_idx}"))
        bot.send_message(m.chat.id, "Pilih Pelanggan:", reply_markup=markup)

def get_hp_p(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    p = m.text
    ud['phone'] = '62' + p[1:] if p.startswith('0') else p
    msg = bot.send_message(m.chat.id, "Alamat:", reply_markup=tombol_batal())
    bot.register_next_step_handler(msg, lambda ms: save_p_new(ms, ud))

def save_p_new(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    ud['alamat'] = m.text
    ws_pelanggan.append_row([ud['nama'], ud['phone'], ud['alamat']])
    show_service_menu(m, ud)

def show_service_menu(m, ud):
    data_l = ws_layanan.get_all_records()
    ud['list_l'] = data_l
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for i, l in enumerate(data_l):
        markup.add(f"{i+1}. {l['Nama Layanan']}")
    markup.add('❌ BATAL')
    msg = bot.send_message(m.chat.id, f"Layanan {ud['nama']}:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_service, ud)

def process_service(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    try:
        idx = int(m.text.split(".")[0]) - 1
        srv = ud['list_l'][idx]
        ud.update({
            'layanan': srv['Nama Layanan'],
            'harga': int(str(srv['Harga']).replace('.', '')),
            'hari': srv['Hari Selesai'],
            'unit': srv.get('Satuan/Kilo', 'Kg')
        })
        msg = bot.send_message(m.chat.id, f"Jumlah ({ud['unit']}):", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, process_qty, ud)
    except:
        bot.send_message(m.chat.id, "Salah pilih.", reply_markup=menu_utama())

def process_qty(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    try:
        qty = float(m.text.replace(',', '.'))
        ud['qty'] = qty
        ud['subtotal'] = int(qty * ud['harga'])
        msg = bot.send_message(m.chat.id, "Masukkan Ongkir (isi 0 jika tidak ada):", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, process_ongkir, ud)
    except:
        bot.send_message(m.chat.id, "Input jumlah salah.", reply_markup=menu_utama())

def process_ongkir(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    try:
        ongkir = int(m.text.replace('.', ''))
        ud['ongkir'] = ongkir
        msg = bot.send_message(m.chat.id, "📝 Catatan (opsional):\nKetik 'skip' jika tidak ada:", reply_markup=tombol_batal())
        bot.register_next_step_handler(msg, process_catatan, ud)
    except:
        bot.send_message(m.chat.id, "Input ongkir salah.", reply_markup=menu_utama())

def process_catatan(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return

    catatan = m.text.strip()
    if catatan.lower() == 'skip':
        catatan = ""

    ud['catatan'] = catatan

    total = ud['subtotal'] + ud['ongkir']
    inv = f"HNF-{datetime.now().strftime('%d%m%y%H%M')}"
    tgl_m = datetime.now().strftime("%d/%m/%Y %H:%M")
    tgl_s = (datetime.now() + timedelta(days=int(ud['hari']))).strftime("%d/%m/%Y")

    ws_transaksi.append_row([tgl_m, inv, ud['nama'], ud['layanan'], ud['qty'], total, "Proses", ud['unit'], tgl_s, "", catatan])

    pdf_data = {
        'nama': ud['nama'],
        'inv': inv,
        'tgl_m': tgl_m,
        'layanan': ud['layanan'],
        'qty': ud['qty'],
        'unit': ud['unit'],
        'subtotal': ud['subtotal'],
        'ongkir': ud['ongkir'],
        'total': total,
        'catatan': catatan
    }
    pdf = create_pdf_thermal(pdf_data)

    if pdf:
        ongkir_txt = f"\nOngkir: Rp {ud['ongkir']:,}" if ud['ongkir'] > 0 else ""
        catatan_txt = f"\n📝 Catatan: {catatan}" if catatan else ""

        wa_text = (f"HANIFA LAUNDRY\n---------------------------\n"
                  f"Pelanggan: {ud['nama']}\nNo. Nota: {inv}\n"
                  f"Layanan: {ud['layanan']}\n"
                  f"📦 Jumlah: {ud['qty']} {ud['unit']}\n"
                  f"Subtotal: Rp {ud['subtotal']:,}{ongkir_txt}\n"
                  f"Total: Rp {total:,}{catatan_txt}\n---------------------------\n"
                  f"🌐 {WEB_OFFICIAL}\nTerima Kasih!")

        url = f"https://api.whatsapp.com/send?phone={ud['phone']}&text={urllib.parse.quote(wa_text)}"
        markup = telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("📲 Kirim WA", url=url))

        with open(pdf, "rb") as f:
            bot.send_document(m.chat.id, f, caption="✅ Berhasil!", reply_markup=markup)
        os.remove(pdf)

    bot.send_message(m.chat.id, "Siap!", reply_markup=menu_utama())

# --- TAMBAH LAYANAN ---
def start_tambah_layanan(m):
    msg = bot.send_message(m.chat.id, "Nama layanan baru:", reply_markup=tombol_batal())
    bot.register_next_step_handler(msg, save_l_n)

def save_l_n(m):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    ud = {'nama': m.text}
    msg = bot.send_message(m.chat.id, "Harga:", reply_markup=tombol_batal())
    bot.register_next_step_handler(msg, lambda ms: save_l_h(ms, ud))

def save_l_h(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    ud['harga'] = m.text
    msg = bot.send_message(m.chat.id, "Hari selesai (contoh: 2):", reply_markup=tombol_batal())
    bot.register_next_step_handler(msg, lambda ms: save_l_u(ms, ud))

def save_l_u(m, ud):
    if m.text == '❌ BATAL':
        handle_text_bos(m)
        return
    ws_layanan.append_row([ud['nama'], ud['harga'], m.text, "Kg"])
    bot.send_message(m.chat.id, "✅ Layanan berhasil ditambahkan!", reply_markup=menu_utama())

# --- RIWAYAT ---
def show_history(m, page):
    data = ws_transaksi.get_all_values()
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
        if page > 1:
            nav.append(telebot.types.InlineKeyboardButton("⬅️ Prev", callback_data=f"p_{page-1}"))
        if page*10 < len(rows):
            nav.append(telebot.types.InlineKeyboardButton("Next ➡️", callback_data=f"p_{page+1}"))
        markup.row(*nav)
    bot.send_message(m.chat.id, f"📊 Riwayat Nota - Halaman {page}", reply_markup=markup)

print("Bot sedang berjalan...")
bot.infinity_polling()
