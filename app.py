import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz
import time
import requests

# --- 1. KONFIGURASI HALAMAN & STYLE (WhatsApp Dark Mode) ---
st.set_page_config(page_title="AURA AI", page_icon="✨", layout="centered")

st.markdown("""
    <style>
    /* Background Dinamis */
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    /* Container Chat */
    .chat-row { display: flex; margin: 10px 0; }
    .user-row { justify-content: flex-end; }
    .aura-row { justify-content: flex-start; }
    
    /* Balon Chat User (Kanan - Hijau) */
    .user-bubble {
        background-color: #056162;
        padding: 12px 18px;
        border-radius: 15px 15px 0px 15px;
        max-width: 70%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    
    /* Balon Chat AURA (Kiri - Abu) */
    .aura-bubble {
        background-color: #262d31;
        padding: 12px 18px;
        border-radius: 15px 15px 15px 0px;
        max-width: 70%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    /* Ikon Profil */
    .avatar { font-size: 25px; margin: 0 10px; align-self: flex-end; }
    </style>
""", unsafe_allow_html=True)

# --- 2. KONEKSI & SETUP ---
def init_aura():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(st.secrets["spreadsheet_id"])
        
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Menggunakan model flash terbaru sesuai kode rujukanmu
        model = genai.GenerativeModel('gemini-2.5-flash')
        return sh, model
    except Exception as e:
        st.error(f"Error Koneksi: {e}")
        return None, None

def get_now():
    return datetime.datetime.now(pytz.timezone('Asia/Jakarta'))

# Fungsi Notifikasi Telegram (Eksternal)
def send_telegram_notification(message):
    try:
        token = st.secrets["TELEGRAM_BOT_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, json=payload)
    except Exception as e:
        pass # Notifikasi gagal tidak menghentikan proses utama chat

sh, model = init_aura()

# --- 3. FUNGSI LOGIKA PERILAKU AURA ---
def get_aura_emoji(text):
    text = text.lower()
    if any(word in text for word in ["maaf", "sedih", "sayang sekali"]): return "😔"
    if any(word in text for word in ["pikir", "analisis", "riset", "strategi", "detail"]): return "🤔"
    if any(word in text for word in ["hebat", "semangat", "bagus", "siap"]): return "🔥"
    if any(word in text for word in ["halo", "hai", "pagi", "siang", "malam"]): return "😊"
    return "✨"

def aura_initial_greet():
    jam = get_now().hour
    if 5 <= jam < 11: return "Selamat pagi, Ryan! Sudah siap cek Coursera atau lanjut SQL hari ini? ☕"
    elif 19 <= jam < 22: return "Sudah jam belajar Jepang-mu nih, Ryan. Ada kanji baru yang mau kita bahas? 🇯🇵"
    return "Halo Ryan! ✨"

def manage_memory(sheet):
    """Menjaga baris Spreadsheet agar tidak overload (Batas 100 baris)"""
    try:
        all_rows = sheet.get_all_values()
        total_baris = len(all_rows)
        if total_baris > 100:
            jumlah_hapus = total_baris - 80
            sheet.delete_rows(2, jumlah_hapus + 1)
    except Exception as e:
        pass

# --- 4. LOGIKA PERCAKAPAN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    greet = aura_initial_greet()
    st.session_state.messages.append({"role": "assistant", "content": greet, "emoji": "😊"})

# Header Tetap
col1, col2 = st.columns([1, 6])
with col1:
    st.image("profile_aura.jpeg", width=70) 
with col2:
    st.subheader("AURA")
    st.caption("Online | Inisiatif AI Strategic Assistant")

# Tampilkan Riwayat Chat
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f'''<div class="chat-row user-row"><div class="user-bubble">{m["content"]}</div><div class="avatar">👤</div></div>''', unsafe_allow_html=True)
    else:
        st.markdown(f'''<div class="chat-row aura-row"><div class="avatar">{m.get("emoji", "✨")}</div><div class="aura-bubble">{m["content"]}</div></div>''', unsafe_allow_html=True)

# Input Chat
if prompt := st.chat_input("Ketik pesan... (Gunakan tag '(Detail)' untuk jawaban lengkap)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Proses Respon
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_input = st.session_state.messages[-1]["content"]
    
    with st.spinner("AURA sedang berpikir..."):
        sheet_harian = sh.worksheet("Chat_Harian")
        sheet_info = sh.worksheet("Personal_Information")
        
        info_data = sheet_info.get_all_values()
        konteks_personal = "\n".join([f"- {r[0]}" for r in info_data[1:]])
        
        # PERBAIKAN: Membaca memori dengan pembersih karakter \n mentah
        chat_data = sheet_harian.get_all_values()
        konteks_chat = []
        for row in chat_data[-50:]:
            # Membersihkan string mentah agar kembali menjadi enter nyata 
            cleaned_row = [str(cell).replace('\\n', '\n') for cell in row]
            konteks_chat.append(cleaned_row)

        waktu_skrg = get_now()
        
        # PROMPT SYSTEM DENGAN LOGIKA LABELING (DETAIL)
        prompt_system = f"""
        Kamu adalah AURA, Personal AI Strategis milik Ryan.
        Waktu: {waktu_skrg.strftime('%A, %d %B %Y %H:%M')} WIB.
        
        PANDUAN RYAN: {konteks_personal}
        KONTEKS CHAT (Ingatan): {konteks_chat}

        ATURAN RESPONS:
        1. Jika Ryan menggunakan tag '(Detail)', berikan penjelasan yang sangat mendalam, teknis, dan komprehensif.
        2. Jika Ryan bertanya biasa (Tanpa Tag), jawablah dengan SINGKAT (1-2 kalimat), santai, dan to-the-point seperti chat WhatsApp.
        3. Jika bertanya jadwal, segera cek PANDUAN RYAN di atas.
        4. Respon natural (Gunakan 'Aku/Kamu'), cerdas, dan jangan bertele-tele jika tidak diminta detail.
        """
        
        try:
            response = model.generate_content([prompt_system, user_input])
            # PERBAIKAN: Membersihkan output Gemini dari karakter \n literal
            jawaban = response.text.replace('\\n', '\n')
            emoji_aura = get_aura_emoji(jawaban)

            time.sleep(1)
            
            # TRIGGER NOTIFIKASI TELEGRAM
            # Kirim notif otomatis jika membahas jadwal atau hal penting lainnya
            if any(key in user_input.lower() for key in ["jadwal", "penting", "ingat"]):
                send_telegram_notification(f"🔔 NOTIFIKASI AURA:\n{jawaban}")

            # Update UI
            st.session_state.messages.append({"role": "assistant", "content": jawaban, "emoji": emoji_aura})
            
            # Simpan ke Spreadsheet
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", user_input])
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
            
            manage_memory(sheet_harian)
            st.rerun()
        except Exception as e:
            st.error(f"Maaf Ryan, terjadi kendala teknis: {e}")

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("AURA Control")
    st.write("Status: Connected 🟢")
    st.divider()
    if st.button("🗑️ Bersihkan Layar"):
        st.session_state.messages = []
        st.rerun()
    st.toggle("🔇 Mute Notifications", value=True)
    st.divider()
    st.info("AURA menggunakan memori Hybrid dari Google Sheets untuk tetap mengenalmu.")
