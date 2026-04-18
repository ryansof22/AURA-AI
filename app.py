import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import datetime
import pytz
import time

# --- 1. KONFIGURASI HALAMAN & STYLE (UI WHATSAPP PRO) ---
st.set_page_config(page_title="AURA AI", page_icon="✨", layout="centered")

# URL Raw Foto Profil dari GitHub Ryan
URL_FOTO = "https://raw.githubusercontent.com/ryansof22/AURA-AI/main/profile_aura_1.jpeg"

st.markdown(f"""
    <style>
    .stApp {{ background-color: #0b141a; color: #e9edef; }}
    
    /* Header Statis (Sticky) yang menyesuaikan dengan Sidebar */
    header[data-testid="stHeader"] {{
        background-color: rgba(0,0,0,0) !important;
        z-index: 100;
    }}
    
    .fixed-header {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: 100%;
        background-color: #202c33;
        padding: 10px 15px;
        display: flex;
        align-items: center;
        z-index: 90; /* Di bawah tombol sidebar (z-index 100+) */
        border-bottom: 1px solid #313d45;
        height: 65px;
    }}
    
    .header-img {{
        width: 42px;
        height: 42px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 12px;
        border: 1px solid #313d45;
    }}
    
    .header-name {{ font-weight: bold; font-size: 16px; color: #e9edef; }}
    .header-status {{ font-size: 12px; color: #00a884; }}

    /* Container Chat */
    .chat-container {{ margin-top: 85px; margin-bottom: 100px; }}
    
    .chat-row {{ display: flex; margin: 15px 0; align-items: flex-end; }}
    .user-row {{ justify-content: flex-end; }}
    .aura-row {{ justify-content: flex-start; }}
    
    /* Avatar Bundar AURA di Chat */
    .chat-avatar-aura {{
        width: 35px;
        height: 35px;
        border-radius: 50%;
        margin-right: 10px;
        object-fit: cover;
    }}

    .user-bubble {{
        background-color: #005c4b;
        color: #e9edef;
        padding: 10px 16px;
        border-radius: 15px 15px 0px 15px;
        max-width: 75%;
        box-shadow: 0 1px 1px rgba(0,0,0,0.2);
    }}
    
    .aura-bubble {{
        background-color: #202c33;
        color: #e9edef;
        padding: 10px 16px;
        border-radius: 15px 15px 15px 0px;
        max-width: 75%;
        box-shadow: 0 1px 1px rgba(0,0,0,0.2);
    }}

    /* Sembunyikan elemen Streamlit yang tidak perlu */
    .block-container {{ padding-top: 0rem; }}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)

# --- 2. KONEKSI & SETUP ---
# Tambahkan di bagian atas file app.py
def init_aura():
    try:
        # Tambahkan Scopes untuk Drive dan Docs
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents"
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=scopes
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(st.secrets["spreadsheet_id"])
        
        # Inisialisasi Service untuk Docs dan Drive
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash') # Gunakan versi terbaru
        return sh, model, drive_service, docs_service
    except Exception as e:
        st.error(f"Error Koneksi: {e}")
        return None, None, None, None

def get_now():
    return datetime.datetime.now(pytz.timezone('Asia/Jakarta'))

sh, model = init_aura()

# --- 3. LOGIKA PROAKTIF & JADWAL ---
def process_temporary_notes(sh):
    """Mengecek Catatan_Sementara: Hapus jika lewat, simpan jika belum."""
    try:
        sheet_cs = sh.worksheet("Catatan_Sementara")
        rows = sheet_cs.get_all_values()
        if len(rows) <= 1: return ""
        
        now = get_now()
        reminders = []
        rows_to_delete = []

        for i, row in enumerate(rows[1:], start=2):
            try:
                # Format: A:Tanggal (YYYY-MM-DD), B:Jam (HH:MM), C:Kegiatan
                jadwal_str = f"{row[0]} {row[1]}"
                jadwal_dt = datetime.datetime.strptime(jadwal_str, "%Y-%m-%d %H:%M")
                jadwal_dt = pytz.timezone('Asia/Jakarta').localize(jadwal_dt)

                if now > jadwal_dt:
                    rows_to_delete.append(i)
                elif 0 <= (jadwal_dt - now).total_seconds() <= 1800:
                    reminders.append(f"⚠️ Jadwal: {row[2]} jam {row[1]}")
            except: continue

        for idx in reversed(rows_to_delete):
            sheet_cs.delete_rows(idx)
        return "\n".join(reminders)
    except: return ""

def manage_memory(sheet):
    try:
        all_rows = sheet.get_all_values()
        if len(all_rows) > 100:
            sheet.delete_rows(2, (len(all_rows) - 80 + 1))
    except: pass

# --- 4. TAMPILAN HEADER FIXED ---
st.markdown(f'''
    <div class="fixed-header">
        <img src="{URL_FOTO}" class="header-img">
        <div class="header-info">
            <div class="header-name">AURA</div>
            <div class="header-status">Online</div>
        </div>
    </div>
''', unsafe_allow_html=True)

def run_chal_process(sh, drive_service, docs_service, template_name, replacements):
    try:
        # 1. Cari Template di Sheet CHAL_Template
        sheet_chal = sh.worksheet("CHAL_Template")
        cell = sheet_chal.find(template_name)
        if not cell:
            return "Template tidak ditemukan di database CHAL."
        
        row_data = sheet_chal.row_values(cell.row)
        template_id = row_data[1]  # Kolom B: ID_Template
        folder_id = row_data[2]    # Kolom C: Folder_Output
        
        # 2. Duplikasi Template
        file_metadata = {
            'name': f"Hasil_{template_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}", 
            'parents': [folder_id]
        }
        copy_file = drive_service.files().copy(fileId=template_id, body=file_metadata).execute()
        new_doc_id = copy_file.get('id')
        
        # 3. Pengisian Data Otomatis (Replace [KEY] with VALUE)
        requests = []
        for key, value in replacements.items():
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': f'[{key}]', 'matchCase': True},
                    'replaceText': str(value)
                }
            })
        
        docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': requests}).execute()
        
        # 4. Generate Link PDF (Export)
        return f"✅ Berhasil! Dokumen telah dibuat. Silakan download di sini: https://docs.google.com/document/d/{new_doc_id}/export?format=pdf"
    except Exception as e:
        return f"Terjadi kesalahan pada CHAL: {e}"

# --- 5. LOGIKA PERCAKAPAN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Halo Ryan! Ada jadwal atau rencana strategis yang ingin kita diskusikan? ✨"})

st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f'<div class="chat-row user-row"><div class="user-bubble">{m["content"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'''
            <div class="chat-row aura-row">
                <img src="{URL_FOTO}" class="chat-avatar-aura">
                <div class="aura-bubble">{m["content"]}</div>
            </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Input Chat
if prompt := st.chat_input("Ketik pesan... (Gunakan (CS) untuk jadwal sementara)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Proses Respon
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_input = st.session_state.messages[-1]["content"]
    
    with st.spinner(""):
        sheet_harian = sh.worksheet("Chat_Harian")
        sheet_info = sh.worksheet("Personal_Information")
        sheet_cs = sh.worksheet("Catatan_Sementara")
        
        alert_jadwal = process_temporary_notes(sh)
        
        info_data = sheet_info.get_all_values()
        konteks_pribadi = "\n".join([f"- {r[0]}" for r in info_data[1:]])
        
        raw_chat = sheet_harian.get_all_values()
        konteks_chat = [[str(c).replace('\\n', '\n') for c in r] for r in raw_chat[-30:]]

        waktu_skrg = get_now()
        
        prompt_system = f"""
        Kamu adalah AURA, Personal AI Strategis Ryan.
        Waktu: {waktu_skrg.strftime('%Y-%m-%d %H:%M')} WIB.
        DATA RYAN: {konteks_pribadi}
        INGATAN: {konteks_chat}

        ATURAN:
        1. (CS) Tag: Ekstrak Tanggal (YYYY-MM-DD), Jam (HH:MM), & Kegiatan.
        2. (Detail) Tag: Jawaban mendalam. Tanpa tag: Singkat (1-2 kalimat).
        3. Peringatan Jadwal: {alert_jadwal} (Sampaikan jika tidak kosong).
        4. Respon natural (Aku/Kamu).
        """
        
        try:
            response = model.generate_content([prompt_system, user_input])
            jawaban = response.text.replace('\\n', '\n')
            
            if "(CS)" in user_input:
                extract = model.generate_content(f"Format: TANGGAL|JAM|KEGIATAN. Dari: {user_input}. Hari ini {waktu_skrg.strftime('%Y-%m-%d')}")
                parts = extract.text.strip().split("|")
                if len(parts) == 3: sheet_cs.append_row(parts)

            st.session_state.messages.append({"role": "assistant", "content": jawaban})
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", user_input])
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
            manage_memory(sheet_harian)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal memproses: {e}")

# Di dalam loop percakapan app.py
if "(CHAL)" in user_input:
    # AURA meminta data lewat prompt singkat atau kamu bisa menginputnya langsung
    # Contoh sederhana: CHAL|Nama_Template|KEY1=VAL1,KEY2=VAL2
    try:
        parts = user_input.split("|")
        t_name = parts[1]
        raw_data = parts[2].split(",")
        replacements = {item.split("=")[0]: item.split("=")[1] for item in raw_data}
        
        hasil_chal = run_chal_process(sh, drive_service, docs_service, t_name, replacements)
        st.write(hasil_chal)
    except:
        st.warning("Format CHAL salah. Gunakan: (CHAL)|NamaTemplate|KEY=VALUE")

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("AURA Control")
    if st.button("🗑️ Bersihkan Layar"):
        st.session_state.messages = []
        st.rerun()
    st.info("Status: Connected 🟢")
