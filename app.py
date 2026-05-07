import streamlit as st
import pyzipper
import os, shutil, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="EOD Professional Portal", layout="centered")

# Custom Styling for Warning/Penalty
st.markdown("""
    <style>
    .penalty-box {
        padding: 10px;
        border-radius: 5px;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
    <div class="penalty-box">⚠️ WARNING: Har mahine data upload anivarya hai. Mismatch hone par PENALTY lagu hogi.</div>
    """, unsafe_allow_html=True)

st.title("🏦 Station EOD Automation")

# --- INPUT SECTION ---
zip_password = st.text_input("ZIP File ka Password dalein", type="password", help="Jo password aapne ZIP banate waqt rakha hai wahi dalein")
uploaded_files = st.file_uploader("ZIP Files Upload Karein", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Kripya File aur Password dono bharein!")
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

                # --- PASSWORD CHECK ---
                with pyzipper.AESZipFile(uploaded_file) as zf:
                    try:
                        zf.extractall(extract_dir, pwd=zip_password.encode())
                    except:
                        st.error(f"🚨 GALAT PASSWORD for {uploaded_file.name}! Kripya sahi password dalein.")
                        continue 

                # --- DATA EXTRACTION (From Inside HTML) ---
                station_id, total_sum, actual_date_range = None, 0, "Not Found"
                
                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f, "html.parser")
                            
                            # 1. Actual Date Range Extraction
                            text_content = soup.get_text(" ")
                            date_pattern = r'\d{2}[\s/\-]\d{2}[\s/\-]\d{4}'
                            range_pattern = rf"({date_pattern})\s*(?:to|thi|TO)\s*({date_pattern})"
                            match = re.search(range_pattern, text_content)
                            if match:
                                actual_date_range = f"{match.group(1)} to {match.group(2)}"

                            # 2. Station ID
                            for row in soup.find_all("tr"):
                                cols = row.find_all("td")
                                if len(cols) >= 2 and "Station ID" in cols[0].get_text():
                                    station_id = cols[1].get_text(strip=True)

                            # 3. Total Amount
                            tables = pd.read_html(path)
                            for df in tables:
                                df.columns = [str(c).strip().lower() for c in df.columns]
                                col = next((c for c in df.columns if "total amount charged" in c), None)
                                if col:
                                    cleaned = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                                    total_sum += pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()

                # --- UPLOAD TO SHEET ---
                if station_id:
                    try:
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Total Amount"])
                    
                    worksheet.append_row([actual_date_range, station_id, int(total_sum)])
                    
                    # --- SUCCESS POPUP & REMINDER ---
                    st.success(f"✅ Data Saved! File Date: {actual_date_range} | Station: {station_id}")
                    st.toast(f"🔔 YAAD RAKHEIN: Agli date range ki file bhi yaad se upload karein!", icon='📅')
                    st.balloons()
                
                shutil.rmtree(extract_dir)

        except Exception as e:
            st.error(f"System Error: {e}")
