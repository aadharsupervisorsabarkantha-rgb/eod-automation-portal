import streamlit as st
import pyzipper
import os, shutil, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

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
    "GJPE_SBR_NS737401": "DABHI BIBIBEN",
    "GJPE_SBK_NS101344": "PARMAR RAVINDRA"
}

# --- STYLING ---
st.markdown("""
    <style>
    .main-box { padding: 20px; border-radius: 12px; background-color: #d32f2f; color: white; text-align: center; margin-bottom: 20px; }
    .success-card { padding: 20px; border-radius: 10px; background-color: #e8f5e9; border-left: 8px solid #2e7d32; margin-top: 15px; color: #1b5e20; }
    .info-tag { background-color: #f1f3f4; padding: 5px 10px; border-radius: 5px; font-size: 14px; border: 1px solid #ccc; color: #555; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# --- UI DROPDOWNS (Only for Professional Show) ---
col1, col2, col3 = st.columns(3)
with col1: st.selectbox("Date Range", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2: st.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=datetime.now().month - 1)
with col3: st.selectbox("Year", [2024, 2025, 2026], index=1)

zip_password = st.text_input("Enter ZIP Password", type="password")
uploaded_files = st.file_uploader("Upload ZIP Reports", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Password aur File zaroori hai!")
    else:
        try:
            # GSheets Connection
            creds_dict = st.secrets["gcp_service_account"]
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")

            for uploaded_file in uploaded_files:
                extract_dir = f"temp_{uploaded_file.name}"
                os.makedirs(extract_dir, exist_ok=True)
                
                with pyzipper.AESZipFile(uploaded_file) as zf:
                    try: zf.extractall(extract_dir, pwd=zip_password.encode())
                    except: 
                        st.error(f"🚨 Password galat hai: {uploaded_file.name}")
                        continue

                # Variables to hold data from FILE
                station_id, file_date_range, operator_id = None, None, None
                date_summary_table = None

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            text = soup.get_text(" ", strip=True)
                            
                            # File se asli Range nikalna
                            d_match = re.search(r"Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text)
                            if d_match: file_date_range = d_match.group(1)
                            
                            for row in soup.find_all("tr"):
                                c = row.find_all("td")
                                if len(c) >= 2:
                                    if "Station ID" in c[0].text: station_id = c[1].text.strip()
                                    if "Operator" in c[0].text: operator_id = c[1].text.strip()
                            
                            all_tabs = pd.read_html(path)
                            for df in all_tabs:
                                df.columns = [str(col).strip().lower() for col in df.columns]
                                if "no. of enrolments" in df.columns and "date" in df.columns:
                                    date_summary_table = df[df['date'].str.contains(r'\d{2}/\d{2}/\d{4}', na=False)]

                op_name = OPERATOR_MAP.get(operator_id, "Unknown")
                
                if station_id and file_date_range:
                    # 1. Auto-create/Get Worksheet
                    try: worksheet = spreadsheet.worksheet(str(station_id))
                    except: 
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator", "ID", "Enrol", "Update", "Total", "Amount", "Avg", "SortKey"])

                    # 2. Day-wise Duplicate Check (Using FILE dates)
                    existing_data = worksheet.get_all_values()
                    file_dates = date_summary_table['date'].tolist()
                    
                    # Agar ek bhi date pehle se sheet mein hai, toh block karein
                    is_dup = any(any(d in row[0] for d in file_dates) for row in existing_data)

                    if is_dup:
                        st.error(f"🛑 Duplicate Alert! File ki dates pehle se sheet mein hain.")
                    else:
                        # 3. Calculations (Purely from FILE)
                        enrol = pd.to_numeric(date_summary_table["no. of enrolments"], errors='coerce').sum()
                        update = pd.to_numeric(date_summary_table["no. of updates"], errors='coerce').sum()
                        total_ent = pd.to_numeric(date_summary_table["total"], errors='coerce').sum()
                        
                        # Total Amount logic (if table exists)
                        total_amt = 0
                        for df in all_tabs:
                            amt_col = next((c for c in df.columns if "total amount charged" in c), None)
                            if amt_col:
                                total_amt += pd.to_numeric(df[amt_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors='coerce').sum()

                        avg_val = round(total_ent / len(date_summary_table), 2)
                        
                        # Sorting logic based on FILE Date
                        start_date_str = file_date_range.split(' to ')[0].strip()
                        temp_dt = datetime.strptime(start_date_str, "%d/%m/%Y")
                        sort_key = temp_dt.strftime("%Y%m%d")

                        # 4. Final Entry
                        worksheet.append_row([
                            file_date_range, station_id, op_name, operator_id, 
                            int(enrol), int(update), int(total_ent), int(total_amt), avg_val, sort_key
                        ])
                        worksheet.sort((10, 'asc'))
                        
                        # --- PROFESSIONAL SUCCESS CARD ---
                        st.markdown(f"""
                        <div class="success-card">
                            <b style="font-size:20px;">✅ SUCCESS: Data Extracted from File</b><br><br>
                            👤 <b>Operator:</b> {op_name} | 📍 <b>Station:</b> {station_id}<br>
                            📅 <b>Actual File Range:</b> <span style="color:#d32f2f;">{file_date_range}</span><br>
                            📈 <b>Average:</b> {avg_val}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if avg_val < 15:
                            st.warning(f"⚠️ Low Average Warning: {avg_val}")

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
