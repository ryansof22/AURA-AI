import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz
import time

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
        model = genai.GenerativeModel('gemini-2.5-flash')
        return sh, model
    except Exception as e:
        st.error(f"Error Koneksi: {e}")
        return None, None

def get_now():
    return datetime.datetime.now(pytz.timezone('Asia/Jakarta'))

sh, model = init_aura()

# --- 3. FUNGSI EMOSI & INISIATIF ---
def get_aura_emoji(text):
    text = text.lower()
    if any(word in text for word in ["maaf", "sedih", "sayang sekali"]): return "😔"
    if any(word in text for word in ["pikir", "analisis", "riset", "strategi"]): return "🤔"
    if any(word in text for word in ["hebat", "semangat", "bagus", "siap"]): return "🔥"
    if any(word in text for word in ["halo", "hai", "pagi", "siang", "malam"]): return "😊"
    return "✨"

def aura_initial_greet():
    jam = get_now().hour
    if 5 <= jam < 11: return "Selamat pagi, Ryan! Sudah siap cek Coursera atau lanjut SQL hari ini? ☕"
    elif 19 <= jam < 22: return "Sudah jam belajar Jepang-mu nih, Ryan. Ada kanji baru yang mau kita bahas? 🇯🇵"
    return "Halo Ryan! Ada proyek menarik apa yang ingin kita diskusikan sekarang? ✨"

# --- 4. LOGIKA PERCAKAPAN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Jalankan Inisiatif AI pertama kali
    greet = aura_initial_greet()
    st.session_state.messages.append({"role": "assistant", "content": greet, "emoji": "😊"})

# Header Tetap (Foto Profil & Nama)
col1, col2 = st.columns([1, 6])
with col1:
    st.image("profile_aura.jpeg", width=70) # Pastikan file ini ada di GitHub
with col2:
    st.subheader("AURA")
    st.caption("Online | Inisiatif AI Strategic Assistant")

# Tampilkan Riwayat Chat dengan Style WA
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f'''<div class="chat-row user-row"><div class="user-bubble">{m["content"]}</div><div class="avatar">👤</div></div>''', unsafe_allow_html=True)
    else:
        st.markdown(f'''<div class="chat-row aura-row"><div class="avatar">{m.get("emoji", "✨")}</div><div class="aura-bubble">{m["content"]}</div></div>''', unsafe_allow_html=True)

# Input Chat
if prompt := st.chat_input("Ketik pesan..."):
    # Tampilkan Pesan User
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Proses Respon (Jika pesan terakhir dari User)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_input = st.session_state.messages[-1]["content"]
    
    with st.spinner("AURA sedang berpikir..."):
        # Ambil Memori (Sheet)
        sheet_harian = sh.worksheet("Chat_Harian")
        sheet_info = sh.worksheet("Personal_Information")
        
        info_data = sheet_info.get_all_values()
        konteks_personal = "\n".join([f"- {r[0]}" for r in info_data[1:]])
        
        chat_data = sheet_harian.get_all_values()
        konteks_chat = chat_data[-50:] # Ambil 50 baris terakhir

        waktu_skrg = get_now()
        prompt_system = f"""
        Kamu adalah AURA, Personal AI Strategis milik Ryan.
        Waktu: {waktu_skrg.strftime('%A, %d %B %Y %H:%M')} WIB.
        
        PANDUAN RYAN: {konteks_personal}
        KONTEKS CHAT: {konteks_chat}

        Tugas:
        1. Respon natural (Gunakan 'Aku/Kamu'), tidak kaku.
        2. Jika tanya tren/riset: gunakan perspektif 'Think with Google'.
        3. Jika tanya ide: buat format Mind Map poin-poin.
        4. Jika Bahasa Jepang: sertakan Romaji & arti.
        """
        
        response = model.generate_content([prompt_system, user_input])
        jawaban = response.text
        emoji_aura = get_aura_emoji(jawaban)

        # Animasi Ketik Sederhana
        time.sleep(1)
        
        # --- LOGIKA PENYIMPANAN CERDAS (AUTO-CLEANUP) ---
        # 1. Tambahkan baris baru (User & AURA)
        sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", user_input])
        sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
        
        # 2. Cek jumlah baris saat ini
        all_rows = sheet_harian.get_all_values()
        total_baris = len(all_rows)
        
        # 3. Jika lebih dari 100 baris, hapus baris paling lama (baris ke-2, karena baris 1 adalah Header)
        # Kita hapus 2 baris sekaligus (1 pasang chat) agar efisien
        if total_baris > 100:
            # Menghapus baris ke-2 dan ke-3 (data tertua setelah header)
            sheet_harian.delete_rows(2, 3)

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
