import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build # Library tambahan untuk CHAL
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
    /* ... (Gunakan style CSS yang sudah kamu punya sebelumnya) ... */
    </style>
    <div class="fixed-header">
        <img src="{URL_FOTO}" class="profile-pic">
        <div class="header-text">
            <div class="header-name">AURA AI</div>
            <div class="header-status">Online</div>
        </div>
    </div>
    <div style="margin-top: 80px;"></div>
""", unsafe_allow_html=True)

# --- 2. FUNGSI INISIALISASI (Google Sheets, Docs, Drive & Gemini) ---
def init_aura():
    try:
        # Tambahkan Scopes untuk Drive dan Docs agar CHAL bisa bekerja
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
        
        # Inisialisasi Service untuk CHAL (Docs dan Drive API)
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash') # Versi stabil
        return sh, model, drive_service, docs_service
    except Exception as e:
        st.error(f"Error Koneksi: {e}")
        return None, None, None, None

# --- 3. FUNGSI LOGIKA CHAL (Otomasi Dokumen) ---
def run_chal_process(sh, drive_service, docs_service, template_name, replacements):
    try:
        # 1. Cari data template di Sheet "CHAL_Template"
        sheet_chal = sh.worksheet("CHAL_Template")
        cell = sheet_chal.find(template_name)
        if not cell:
            return "❌ Maaf, template tersebut tidak ditemukan di database CHAL_Template."
        
        row_data = sheet_chal.row_values(cell.row)
        template_id = row_data[1]  # Kolom B: ID_Template
        folder_id = row_data[2]    # Kolom C: Folder_Output
        
        # 2. Duplikasi file template agar Master tetap aman
        file_metadata = {
            'name': f"Hasil_{template_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}", 
            'parents': [folder_id]
        }
        copy_file = drive_service.files().copy(fileId=template_id, body=file_metadata).execute()
        new_doc_id = copy_file.get('id')
        
        # 3. Pengisian data otomatis menggunakan batchUpdate
        requests = []
        for key, value in replacements.items():
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': f'[{key}]', 'matchCase': True},
                    'replaceText': str(value)
                }
            })
        
        docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': requests}).execute()
        
        # 4. Berikan akses viewer agar Ryan bisa mendownloadnya
        drive_service.permissions().create(
            fileId=new_doc_id,
            body={'type': 'anyone', 'role': 'viewer'}
        ).execute()

        # 5. Return link download PDF
        download_url = f"https://docs.google.com/document/d/{new_doc_id}/export?format=pdf"
        return f"✨ **CHAL Berhasil!** Dokumen telah dibuat. [Klik di sini untuk Download PDF]({download_url})"
    except Exception as e:
        return f"❌ Kesalahan Sistem CHAL: {e}"

# --- 4. SISTEM MEMORI ---
def get_context(sheet):
    data = sheet.get_all_values()
    return "\\n".join([f"{row[0]} - {row[1]}: {row[2]}" for row in data[-10:]])

def manage_memory(sheet, max_rows=50):
    data = sheet.get_all_values()
    if len(data) > max_rows:
        sheet.delete_rows(2, len(data) - max_rows)

# --- 5. LOGIKA UTAMA AURA ---
sh, model, drive_service, docs_service = init_aura()

if sh:
    sheet_harian = sh.worksheet("Harian")
    sheet_pribadi = sh.worksheet("Pribadi")
    sheet_cs = sh.worksheet("CS")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Tampilkan Chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Ketik pesan...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        tz = pytz.timezone('Asia/Jakarta')
        waktu_skrg = datetime.datetime.now(tz)
        
        konteks_pribadi = "\\n".join([f"{r[0]}: {r[1]}" for r in sheet_pribadi.get_all_values()])
        konteks_chat = get_context(sheet_harian)
        
        # Logika Alert Jadwal
        jadwal_data = sheet_cs.get_all_values()
        alert_jadwal = ""
        hari_ini = waktu_skrg.strftime('%Y-%m-%d')
        for row in jadwal_data[1:]:
            if row[0] == hari_ini:
                alert_jadwal += f"- {row[1]}: {row[2]}\\n"

        prompt_system = f"""
        Kamu adalah AURA AI, asisten pribadi Ryan.
        Waktu: {waktu_skrg.strftime('%Y-%m-%d %H:%M')} WIB.
        DATA RYAN: {konteks_pribadi}
        INGATAN: {konteks_chat}
        ATURAN:
        1. (CS) Tag: Catat jadwal Ryan.
        2. (CHAL) Tag: Jika Ryan minta buat dokumen/surat, berikan panduan format: (CHAL)|NamaTemplate|DATA1=ISI1,DATA2=ISI2.
        3. Berperanlah sebagai teman yang anggun dan cerdas.
        """
        
        with st.chat_message("assistant"):
            # 1. CEK APAKAH USER MENGGUNAKAN TAG (CHAL)
            if "(CHAL)" in user_input:
                with st.spinner("Sedang menyusun dokumen CHAL..."):
                    try:
                        # Format: (CHAL)|Undangan_Rapat|NAMA=Ryan,NOMOR=123
                        parts = user_input.split("|")
                        template_name = parts[1].strip()
                        data_pairs = parts[2].split(",")
                        replacements = {p.split("=")[0].strip(): p.split("=")[1].strip() for p in data_pairs}
                        
                        jawaban = run_chal_process(sh, drive_service, docs_service, template_name, replacements)
                    except:
                        jawaban = "⚠️ Format CHAL salah. Gunakan: `(CHAL)|NamaTemplate|KEY=VALUE,KEY2=VALUE2`"
                st.markdown(jawaban)
            
            # 2. JIKA CHAT BIASA (TERMASUK CS)
            else:
                response = model.generate_content([prompt_system, user_input])
                jawaban = response.text
                
                if "(CS)" in user_input:
                    extract = model.generate_content(f"Format: TANGGAL|JAM|KEGIATAN. Dari: {user_input}. Hari ini {hari_ini}")
                    p = extract.text.strip().split("|")
                    if len(p) == 3: sheet_cs.append_row(p)
                
                st.markdown(jawaban)

            st.session_state.messages.append({"role": "assistant", "content": jawaban})
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", user_input])
            sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
            manage_memory(sheet_harian)
