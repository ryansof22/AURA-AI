import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import datetime
import pytz
import time

# --- 1. KONFIGURASI HALAMAN & STYLE (STABIL) ---
st.set_page_config(page_title="AURA AI", page_icon="✨", layout="centered")

URL_FOTO = "https://raw.githubusercontent.com/ryansof22/AURA-AI/main/profile_aura_1.jpeg"

st.markdown(f"""
    <style>
    .stApp {{ background-color: #0b141a; color: #e9edef; }}
    header[data-testid="stHeader"] {{ background-color: rgba(0,0,0,0) !important; z-index: 100; }}
    .fixed-header {{
        position: fixed; top: 0; left: 0; right: 0; width: 100%;
        background-color: #202c33; padding: 10px 15px; display: flex;
        align-items: center; z-index: 90; border-bottom: 1px solid #313d45; height: 65px;
    }}
    .header-img {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; margin-right: 12px; border: 1px solid #313d45; }}
    .header-name {{ font-weight: bold; font-size: 16px; color: #e9edef; }}
    .header-status {{ font-size: 12px; color: #00a884; }}
    .chat-container {{ margin-top: 85px; margin-bottom: 100px; }}
    .chat-row {{ display: flex; margin: 15px 0; align-items: flex-end; }}
    .user-row {{ justify-content: flex-end; }}
    .aura-row {{ justify-content: flex-start; }}
    .chat-avatar-aura {{ width: 35px; height: 35px; border-radius: 50%; margin-right: 10px; object-fit: cover; }}
    .user-bubble {{ background-color: #005c4b; color: #e9edef; padding: 10px 16px; border-radius: 15px 15px 0px 15px; max-width: 75%; box-shadow: 0 1px 1px rgba(0,0,0,0.2); }}
    .aura-bubble {{ background-color: #202c33; color: #e9edef; padding: 10px 16px; border-radius: 15px 15px 15px 0px; max-width: 75%; box-shadow: 0 1px 1px rgba(0,0,0,0.2); }}
    </style>
""", unsafe_allow_html=True)

# --- 2. KONEKSI & SETUP ---
def init_aura():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents"
        ]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(st.secrets["spreadsheet_id"])
        
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        return sh, model, drive_service, docs_service
    except Exception as e:
        st.error(f"Error Koneksi: {e}")
        return None, None, None, None

def get_now():
    return datetime.datetime.now(pytz.timezone('Asia/Jakarta'))

def manage_memory(sheet):
    try:
        all_rows = sheet.get_all_values()
        if len(all_rows) > 100: sheet.delete_rows(2, (len(all_rows) - 80 + 1))
    except: pass

sh, model, drive_service, docs_service = init_aura()

# --- 3. LOGIKA MESIN CHAL ---
def run_chal_process(drive_service, docs_service, template_data, replacements):
    try:
        file_metadata = {
            'name': f"Hasil_{template_data['name']}_{get_now().strftime('%Y%m%d_%H%M')}", 
            'parents': [template_data['folder']]
        }
        copy_file = drive_service.files().copy(fileId=template_data['id'], body=file_metadata).execute()
        new_doc_id = copy_file.get('id')
        
        requests = []
        for key, value in replacements.items():
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': f'[{key}]', 'matchCase': True},
                    'replaceText': str(value)
                }
            })
        docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': requests}).execute()
        drive_service.permissions().create(fileId=new_doc_id, body={'type': 'anyone', 'role': 'viewer'}).execute()
        
        url = f"https://docs.google.com/document/d/{new_doc_id}/export?format=pdf"
        return url, new_doc_id
    except Exception as e:
        return None, str(e)

# --- 4. TAMPILAN HEADER ---
st.markdown(f'''<div class="fixed-header"><img src="{URL_FOTO}" class="header-img"><div class="header-info"><div class="header-name">AURA</div><div class="header-status">Online</div></div></div>''', unsafe_allow_html=True)

# --- 5. INITIALIZE SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Halo Ryan! Ada jadwal atau dokumen (CHAL) yang bisa kubantu? ✨"})

if "chal_step" not in st.session_state: st.session_state.chal_step = None
if "active_template" not in st.session_state: st.session_state.active_template = None
if "last_file_id" not in st.session_state: st.session_state.last_file_id = None

# Tampilkan Pesan
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for m in st.session_state.messages:
    role_class = "user-row" if m["role"] == "user" else "aura-row"
    bubble_class = "user-bubble" if m["role"] == "user" else "aura-bubble"
    avatar = "" if m["role"] == "user" else f'<img src="{URL_FOTO}" class="chat-avatar-aura">'
    st.markdown(f'<div class="chat-row {role_class}">{avatar}<div class="{bubble_class}">{m["content"]}</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- 6. LOGIKA INPUT & RESPONS ---
if prompt := st.chat_input("Ketik pesan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.spinner(""):
        sheet_harian = sh.worksheet("Chat_Harian")
        sheet_chal = sh.worksheet("CHAL_Template")
        waktu_skrg = get_now()
        jawaban = ""

        # --- A. LOGIKA CHAL_FIX (PENGHAPUSAN) ---
        if "(CHAL_Fix)" in prompt:
            if st.session_state.last_file_id:
                try:
                    drive_service.files().delete(fileId=st.session_state.last_file_id).execute()
                    jawaban = "Sama-sama Ryan! File telah dihapus dari cloud. Sesi CHAL selesai. ✨"
                except:
                    jawaban = "Sesi CHAL ditutup (file mungkin sudah tidak ada)."
                st.session_state.last_file_id = None
            else:
                jawaban = "Tidak ada file aktif untuk dihapus, Ryan."
            st.session_state.chal_step = None

        # --- B. LOGIKA CHAL INTERAKTIF ---
        elif "(CHAL)" in prompt or st.session_state.chal_step is not None:
            # Tahap 1: Pilih Template
            if st.session_state.chal_step is None:
                all_t = sheet_chal.get_all_values()[1:]
                options = "\n".join([f"- {t[0]}" for t in all_t[:7]])
                jawaban = f"Baiklah Ryan, silakan pilih nama template surat yang ingin dibuat:\n\n{options}"
                st.session_state.chal_step = "PILIH"
            
            # Tahap 2: Minta Data
            elif st.session_state.chal_step == "PILIH":
                try:
                    cell = sheet_chal.find(prompt)
                    row = sheet_chal.row_values(cell.row)
                    st.session_state.active_template = {'name': row[0], 'id': row[1], 'folder': row[2], 'placeholders': row[3]}
                    jawaban = f"Siap! Untuk **{row[0]}**, mohon isi data berikut:\n\n`{row[3]}`\n\nFormat: `KUNCI=ISI, KUNCI2=ISI2`"
                    st.session_state.chal_step = "DATA"
                except:
                    jawaban = "Template tidak ditemukan. Mohon ketik nama yang sesuai daftar ya."

            # Tahap 3: Proses & Link
            elif st.session_state.chal_step == "DATA":
                try:
                    pairs = prompt.split(",")
                    replacements = {p.split("=")[0].strip(): p.split("=")[1].strip() for p in pairs}
                    url, f_id = run_chal_process(drive_service, docs_service, st.session_state.active_template, replacements)
                    if url:
                        jawaban = f"✨ **Berhasil!** [Download PDF Di Sini]({url})\n\nKetik **(CHAL_Fix)** jika sudah selesai agar file segera dihapus."
                        st.session_state.last_file_id = f_id
                        st.session_state.chal_step = "FINISH"
                    else:
                        jawaban = f"Gagal: {f_id}"
                except:
                    jawaban = "Format salah. Gunakan `KUNCI=ISI` (contoh: `Nama=Ryan`)."

        # --- C. LOGIKA CHAT BIASA & (CS) ---
        else:
            # Ambil data personal & harian untuk konteks
            info_data = sh.worksheet("Personal_Information").get_all_values()
            konteks_pribadi = "\n".join([f"- {r[0]}" for r in info_data[1:]])
            
            prompt_system = f"""
            Kamu adalah AURA, asisten cerdas Ryan.
            Waktu: {waktu_skrg.strftime('%Y-%m-%d %H:%M')} WIB.
            DATA RYAN: {konteks_pribadi}
            ATURAN:
            1. (CS) Tag: Catat jadwal (TANGGAL|JAM|KEGIATAN).
            2. (CHAL) Tag: Fitur buat dokumen otomatis.
            3. Responlah dengan anggun dan cerdas.
            """
            
            try:
                response = model.generate_content([prompt_system, prompt])
                jawaban = response.text
                
                if "(CS)" in prompt:
                    extract = model.generate_content(f"Format: TANGGAL|JAM|KEGIATAN. Dari: {prompt}. Hari ini {waktu_skrg.strftime('%Y-%m-%d')}")
                    parts = extract.text.strip().split("|")
                    if len(parts) == 3: sh.worksheet("Catatan_Sementara").append_row(parts)
            except Exception as e:
                jawaban = f"AURA mengalami gangguan: {e}"

        # Simpan & Refresh
        st.session_state.messages.append({"role": "assistant", "content": jawaban})
        sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "User", prompt])
        sheet_harian.append_row([waktu_skrg.strftime("%H:%M:%S"), "AURA", jawaban])
        manage_memory(sheet_harian)
        st.rerun()

# --- 7. SIDEBAR ---
with st.sidebar:
    st.title("AURA Control")
    if st.button("🗑️ Bersihkan Layar"):
        st.session_state.messages = []
        st.rerun()
