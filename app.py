import streamlit as st
import pyzipper
import os, shutil, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="EOD Professional Portal", layout="centered")

# Penalty Warning UI
st.markdown("""
    <style>
    .penalty-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        text-align: center;
        margin-bottom: 25px;
        border: 2px solid white;
    }
    </style>
    <div class="penalty-box">
        ⚠️ ATTENTION OPERATOR: Har mahine data upload karna compulsory hai.<br>
        DATA MISMATCH ya DELAY hone par Seedhi PENALTY lagu hogi!
    </div>
    """, unsafe_allow_html=True)

st.title("🏦 Station EOD Automation")

# --- STEP 1: DROPDOWN (Wapas Add Kar Diya) ---
st.subheader("1️⃣ Details Select Karein")
col1, col2, col3 = st.columns(3)
with col1:
    ui_date_range = st.selectbox("Expected Date Range", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2:
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    selected_month = st.selectbox("Month", months, index=datetime.now().month - 1)
with col3:
    selected_year = st.selectbox("Year", [datetime.now().year, datetime.now().year-1], index=0)

# --- STEP 2: PASSWORD & UPLOAD ---
st.subheader("2️⃣ Security & File")
# Flexible Password: Jo operator likhega wahi use hoga
zip_password = st.text_input("ZIP File ka Password dalein", type="password", help="File ko protect karne wala password yahan likhein")
uploaded_files = st.file_uploader("ZIP Files Upload Karein", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Kripya Password aur File dono check karein!")
    else:
        try:
            # Google Sheet Auth
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")

            for uploaded_file in uploaded_files:
                extract_dir = f"temp_{uploaded_file.name}"
                if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
                os.makedirs(extract_dir)

                # --- FLEXIBLE PASSWORD CHECK ---
                with pyzipper.AESZipFile(uploaded_file) as zf:
                    try:
                        zf.extractall(extract_dir, pwd=zip_password.encode())
                    except:
                        st.error(f"🚨 GALAT PASSWORD! File '{uploaded_file.name}' nahi khul saki. Sahi password likhein.")
                        continue 

                station_id, total_sum, file_date = None, 0, None
                
                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f, "html.parser")
                            
                            # ACTUAL DATE EXTRACTION FROM FILE
                            text_data = soup.get_text(" ")
                            date_matches = re.findall(r'\d{2}[\s/\-]\d{2}[\s/\-]\d{4}', text_data)
                            if len(date_matches) >= 2:
                                file_date = f"{date_matches[0]} to {date_matches[1]}"

                            # Station & Amount Logic
                            for row in soup.find_all("tr"):
                                cols = row.find_all("td")
                                if len(cols) >= 2 and "Station ID" in cols[0].get_text():
                                    station_id = cols[1].get_text(strip=True)
                            
                            tables = pd.read_html(path)
                            for df in tables:
                                df.columns = [str(c).strip().lower() for c in df.columns]
                                col = next((c for c in df.columns if "total amount charged" in c), None)
                                if col:
                                    cleaned = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                                    total_sum += pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()

                # Final Date Decision (Priority: File > Dropdown)
                final_date_to_sheet = file_date if file_date else f"{ui_date_range} {selected_month} {selected_year}"

                if station_id:
                    try:
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Total Amount"])
                    
                    worksheet.append_row([final_date_to_sheet, station_id, int(total_sum)])
                    
                    # --- SUCCESS POPUP & TOAST REMINDER ---
                    st.balloons()
                    st.success(f"✅ SUCCESS! Station {station_id} ka data save ho gaya.")
                    st.toast("🔔 YAAD RAKHEIN: Agli date range ki file bhi yaad se upload karein!", icon='📅')
                    st.info(f"Recorded Date: {final_date_to_sheet}")
                
                shutil.rmtree(extract_dir)

        except Exception as e:
            st.error(f"System Error: {e}")
