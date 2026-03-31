import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz
import time

# --- 1. KONFIGURASI HALAMAN & STYLE (UI WHATSAPP PRO) ---
st.set_page_config(page_title="AURA AI", page_icon="✨", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0b141a; color: #e9edef; }
    
    /* Header Statis (Sticky) */
    .fixed-header {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        background-color: #202c33;
        padding: 10px 20px;
        display: flex;
        align-items: center;
        z-index: 1000;
        border-bottom: 1px solid #313d45;
    }
    .header-img {
        width: 45px;
        height: 45px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 15px;
    }
    .header-info { line-height: 1.2; }
    .header-name { font-weight: bold; font-size: 16px; color: #e9edef; }
    .header-status { font-size: 12px; color: #00a884; }

    /* Container Chat */
    .chat-container { margin-top: 80px; margin-bottom: 100px; }
    
    .chat-row { display: flex; margin: 15px 0; align-items: flex-end; }
    .user-row { justify-content: flex-end; }
    .aura-row { justify-content: flex-start; }
    
    /* Avatar Bundar AURA */
    .chat-avatar-aura {
        width: 35px;
        height: 35px;
        border-radius: 50%;
        margin-right: 10px;
        object-fit: cover;
    }

    .user-bubble {
        background-color: #005c4b;
        color: #e9edef;
        padding: 12px 16px;
        border-radius: 15px 15px 0px 15px;
        max-width: 75%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    
    .aura-bubble {
        background-color: #202c33;
        color: #e9edef;
        padding: 12px 16px;
        border-radius: 15px 15px 15px 0px;
        max-width: 75%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }

    /* Penyesuaian Layout Streamlit */
    .block-container { padding-top: 0rem; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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

# --- 3. LOGIKA JADWAL & MEMORY ---
def process_temporary_notes(sh):
    """Memeriksa jadwal per baris: hapus jika lewat, ingatkan jika dekat"""
    try:
        sheet_cs = sh.worksheet("Catatan_Sementara")
        rows = sheet_cs.get_all_values()
        if len(rows) <= 1: return ""
        
        now = get_now()
        reminders = []
        rows_to_delete = []

        # Cek setiap baris (mulai dari baris ke-2)
        for i, row in enumerate(rows[1:], start=2):
            try:
                # Format: A:Tanggal (YYYY-MM-DD), B:Jam (HH:MM), C:Kegiatan
                jadwal_str = f"{row[0]} {row[1]}"
                jadwal_dt = datetime.datetime.strptime(jadwal_str, "%Y-%m-%d %H:%M")
                jadwal_dt = pytz.timezone('Asia/Jakarta').localize(jadwal_dt)

                if now > jadwal_dt:
                    rows_to_delete.append(i)
                elif 0 <= (jadwal_dt - now).total_seconds() <= 1800: # Rentang 30 menit
                    reminders.append(f"⚠️ Jadwal terdekat: {row[2]} pukul {row[1]}")
            except: continue

        # Hapus baris yang sudah lewat (dari bawah ke atas agar index tidak geser)
        for idx in reversed(rows_to_delete):
            sheet_cs.delete_rows(idx)
            
        return "\n".join(reminders)
    except: return ""

def manage_memory(sheet):
    try:
        all_rows = sheet.get_all_values()
        if len(all_rows) > 100:
            jumlah_hapus = len(all_rows) - 80
            sheet.delete_rows(2, jumlah_hapus + 1)
    except: pass

# --- 4. TAMPILAN HEADER (FIXED) ---
st.markdown(f'''
    <div class="fixed-header">
        <img src="https://raw.githubusercontent.com/RyanSofiyulloh/AURA-AI/main/profile_aura.jpeg" class="header-img">
        <div class="header-info">
            <div class="header-name">AURA</div>
            <div class="header-status">Online</div>
        </div>
    </div>
''', unsafe_allow_html=True)

# --- 5. LOGIKA PERCAKAPAN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Halo Ryan! Ada jadwal atau rencana strategis yang ingin kita bahas hari ini? ✨"})

# Container Chat
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f'<div class="chat-row user-row"><div class="user-bubble">{m["content"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'''
            <div class="chat-row aura-row">
                <img src="https://raw.githubusercontent.com/RyanSofiyulloh/AURA-AI/main/profile_aura.jpeg" class="chat-avatar-aura">
                <div class="aura-bubble">{m["content"]}</div>
            </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Input Chat
if prompt := st.chat_input("Ketik pesan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Proses Respon
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_input = st.session_state.messages[-1]["content"]
    
    with st.spinner(""):
        sheet_harian = sh.worksheet("Chat_Harian")
        sheet_info = sh.worksheet("Personal_Information")
        sheet_cs = sh.worksheet("Catatan_Sementara")
        
        # Jalankan Logika Proaktif
        alert_jadwal = process_temporary_notes(sh)
        
        # Ambil Data
        info_data = sheet_info.get_all_values()
        konteks_personal = "\n".join([f"- {r[0]}" for r in info_data[1:]])
        
        cs_data = sheet_cs.get_all_values()
        konteks_cs = "\n".join([f"- {r[0]} {r[1]}: {r[2]}" for r in cs_data[1:]])
        
        # Bersihkan Memori \n
        raw_chat = sheet_harian.get_all_values()
        konteks_chat = [[str(c).replace('\\n', '\n') for c in r] for r in raw_chat[-30:]]

        waktu_skrg = get_now()
        
        prompt_system = f"""
        Kamu adalah AURA, Personal AI Strategis Ryan.
        Waktu Sekarang: {waktu_skrg.strftime('%A, %d %B %Y %H:%M')} WIB.
        
        DATA TETAP: {konteks_personal}
        JADWAL SEMENTARA: {konteks_cs}
        INGATAN CHAT: {konteks_chat}

        ATURAN RESPONS:
        1. Jika Ryan menggunakan tag '(CS)', kamu wajib mengekstrak Tanggal (YYYY-MM-DD), Jam (HH:MM), dan Kegiatan untuk disimpan.
        2. Jika Ryan menggunakan tag '(Detail)', berikan penjelasan mendalam. Jika TANPA tag, jawab SINGKAT (1-2 kalimat) dan natural.
        3. Gunakan 'Aku/Kamu'. Sertakan Romaji jika berbahasa Jepang.
        4. INFO PROAKTIF: {alert_jadwal} (Gunakan ini untuk menyapa atau mengingatkan Ryan jika tidak kosong).
        """
        
        try:
            response = model.generate_content([prompt_system, user_input])
            jawaban = response.text.replace('\\n', '\n')
            
            # Logika Ekstraksi (CS)
            if "(CS)" in user_input:
                extractor = model.generate_content(f"Ekstrak format: TANGGAL|JAM|KEGIATAN. Dari teks: '{user_input}'. Hari ini {waktu_skrg.strftime('%Y-%m-%d')}")
                parts = extractor.text.strip().split("|")
                if len(parts) == 3:
                    sheet_cs.append_row(parts)

            st.session_state.messages.append({"role": "assistant", "content": jawaban})
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", user_input])
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
            
            manage_memory(sheet_harian)
            st.rerun()
        except Exception as e:
            st.error(f"Maaf Ryan, terjadi kendala teknis: {e}")

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("AURA Control")
    if st.button("🗑️ Bersihkan Layar"):
        st.session_state.messages = []
        st.rerun()
    st.info("Status: Connected 🟢")
