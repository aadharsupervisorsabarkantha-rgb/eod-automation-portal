import streamlit as st
import pyzipper
import os, shutil, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="EOD Professional Portal", layout="centered")

# --- OPERATOR DATABASE ---
OPERATOR_MAP = {
    "GJPE_SBK_NS603205": "RATHOD VIJAY",
    "GJPE_SBK_NS435053": "PATEL VIPUL",
    "GJPE_SBK_NS668733": "CHAUHAN CHANDUJI",
    "GJPE_SBK_NS716164": "DAYANI MADHUBEN",
    "GJPE_SBR_NS851220": "MEMON SAKIL",
    "GJPE_SBK_NS101318": "BHATT SANAM",
    "GJPE_SBK_NS054082": "SOLANKI RAJESH",
    "GJPE_SBK_NS463140": "JADAV SHASHIKANT",
    "GJPE_SBK_NS728611": "RAVAL JAYPAL",
    "GJPE_SBK_NS721374": "ASARI ROHIT",
    "GJPE_SBK_NS776405": "BAROT APURVA",
    "GJPE_SBK_NS829265": "VANKAR TEJALBEN",
    "GJPE_SBK_NS442326": "MANSURI VARISH",
    "GJPE_SBK_NS701346": "DABHI SAGAR",
    "GJPE_SBR_NS737401": "DABHI BIBIBEN",
    "GJPE_SBK_NS101344": "PARMAR RAVINDRA"
}

# --- STYLING ---
st.markdown("""
    <style>
    .strict-penalty-box { padding: 20px; border-radius: 12px; background-color: #d32f2f; color: #ffffff; text-align: center; border: 4px solid #f44336; margin-bottom: 30px; }
    </style>
    <div class="strict-penalty-box">
        <b style="font-size: 22px;">🚫 ATTENTION OPERATOR 🚫</b><br>
        Data upload compulsory hai. <b>Yaad Rakhein: Mismatch par PENALTY lagegi!</b>
    </div>
    """, unsafe_allow_html=True)

st.title("🏦 Station EOD Automation")

# --- INPUTS ---
st.subheader("1️⃣ Details & File")
col1, col2, col3 = st.columns(3)
with col1: ui_date_range = st.selectbox("Expected Date Range", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2: selected_month = st.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=datetime.now().month - 1)
with col3: selected_year = st.selectbox("Year", [2025, 2026], index=0)

zip_password = st.text_input("ZIP File ka Password dalein", type="password")
uploaded_files = st.file_uploader("ZIP Files Upload Karein", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Password aur File check karein!")
    else:
        try:
            # --- AUTHENTICATION ---
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            
            # G-Sheet Client
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")
            
            # Drive Client
            drive_service = build('drive', 'v3', credentials=creds)

            for uploaded_file in uploaded_files:
                # 1. Save ZIP locally temporarily
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 2. Upload ZIP to Google Drive
                file_metadata = {'name': uploaded_file.name}
                media = MediaFileUpload(uploaded_file.name, mimetype='application/zip')
                drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

                # 3. Extraction Logic
                extract_dir = f"temp_{uploaded_file.name}"
                os.makedirs(extract_dir, exist_ok=True)
                
                with pyzipper.AESZipFile(uploaded_file) as zf:
                    try:
                        zf.extractall(extract_dir, pwd=zip_password.encode())
                    except:
                        st.error(f"🚨 GALAT PASSWORD for {uploaded_file.name}!")
                        continue

                station_id, file_date, operator_id, total_sum = None, None, None, 0
                enrol, update, total_ent = 0, 0, 0
                summary_df = None

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            text = soup.get_text(" ", strip=True)
                            
                            # Date & ID Extraction
                            d_match = re.search(r"Report Generated for Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text, re.I)
                            if d_match: file_date = d_match.group(1)
                            
                            for row in soup.find_all("tr"):
                                c = row.find_all("td")
                                if len(c) >= 2:
                                    if "Station ID" in c[0].text: station_id = c[1].text.strip()
                                    if "Operator" in c[0].text: operator_id = c[1].text.strip()

                            # Tables
                            all_tabs = pd.read_html(path)
                            for df in all_tabs:
                                df.columns = [str(col).strip().lower() for col in df.columns]
                                if "total" in df.columns and "no. of enrolments" in df.columns:
                                    summary_df = df
                                    enrol = pd.to_numeric(df["no. of enrolments"], errors='coerce').sum()
                                    update = pd.to_numeric(df["no. of updates"], errors='coerce').sum()
                                    total_ent = pd.to_numeric(df["total"], errors='coerce').sum()
                                
                                amt_col = next((c for c in df.columns if "total amount charged" in c), None)
                                if amt_col:
                                    total_sum += pd.to_numeric(df[amt_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors='coerce').sum()

                # --- FINALIZE ---
                op_name = OPERATOR_MAP.get(operator_id, "Unknown")
                f_date = file_date if file_date else f"{ui_date_range} {selected_month}"

                if station_id:
                    try:
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator Name", "Operator ID", "Enrol", "Update", "Total", "Amount"])
                    
                    worksheet.append_row([f_date, station_id, op_name, operator_id, int(enrol), int(update), int(total_ent), int(total_sum)])
                    
                    st.success(f"✅ Data & ZIP Saved Successfully for {f_date}!")
                    st.markdown(f"👤 **Operator:** {op_name} ({operator_id}) | 📍 **Station:** {station_id}")
                    if summary_df is not None:
                        st.table(summary_df)
                        avg = total_ent / len(summary_df)
                        st.info(f"📊 Total: {int(total_ent)} | Average: {avg:.1f}")
                        if avg < 15: st.warning(f"⚠️ Average entries ({avg:.1f}) kam hain!")
                
                shutil.rmtree(extract_dir)
                if os.path.exists(uploaded_file.name): os.remove(uploaded_file.name)

        except Exception as e:
            st.error(f"Error: {e}")
