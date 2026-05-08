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
    .warning-card { padding: 15px; border-radius: 10px; background-color: #fff3e0; border-left: 8px solid #ef6c00; color: #e65100; margin-top: 10px; font-weight: bold; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# UI Inputs
zip_password = st.text_input("Enter ZIP Password", type="password")
uploaded_files = st.file_uploader("Upload ZIP Reports", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Password aur File zaroori hai!")
    else:
        try:
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

                station_id, file_date, operator_id = None, None, None
                enrol, update, total_ent, total_sum = 0, 0, 0, 0
                date_summary_table = None

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            text = soup.get_text(" ", strip=True)
                            
                            d_match = re.search(r"Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text)
                            if d_match: file_date = d_match.group(1)
                            
                            for row in soup.find_all("tr"):
                                c = row.find_all("td")
                                if len(c) >= 2:
                                    if "Station ID" in c[0].text: station_id = c[1].text.strip()
                                    if "Operator" in c[0].text: operator_id = c[1].text.strip()
                            
                            all_tabs = pd.read_html(path)
                            for df in all_tabs:
                                df.columns = [str(col).strip().lower() for col in df.columns]
                                if "no. of enrolments" in df.columns and "date" in df.columns:
                                    df = df[df['date'].str.contains(r'\d{2}/\d{2}/\d{4}', na=False)]
                                    date_summary_table = df
                                    enrol = pd.to_numeric(df["no. of enrolments"], errors='coerce').sum()
                                    update = pd.to_numeric(df["no. of updates"], errors='coerce').sum()
                                    total_ent = pd.to_numeric(df["total"], errors='coerce').sum()

                            for df in all_tabs:
                                amt_col = next((c for c in df.columns if "total amount charged" in c), None)
                                if amt_col:
                                    total_sum += pd.to_numeric(df[amt_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors='coerce').sum()

                op_name = OPERATOR_MAP.get(operator_id, "Unknown")
                
                if station_id:
                    try: 
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except gspread.exceptions.WorksheetNotFound:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator", "ID", "Enrol", "Update", "Total", "Amount", "Avg", "SortKey"])
                        st.info(f"✨ New Station `{station_id}` created.")

                    existing_data = worksheet.get_all_values()
                    
                    # --- NEW SMART DUPLICATE CHECK (Day-wise) ---
                    file_dates_list = date_summary_table['date'].tolist() if date_summary_table is not None else []
                    is_duplicate = False
                    duplicate_dates = []

                    # Sheet mein Column A mein jo ranges hain, unhe check karna
                    for row in existing_data:
                        existing_range = row[0]
                        for f_date in file_dates_list:
                            if f_date in existing_range:
                                is_duplicate = True
                                duplicate_dates.append(f_date)
                    
                    if is_duplicate:
                        st.error(f"🛑 Duplicate Data Found! Is file mein dates {', '.join(list(set(duplicate_dates)))} pehle se sheet mein maujood hain.")
                    else:
                        # Process entry
                        days_worked = len(date_summary_table) if date_summary_table is not None else 1
                        avg_val = round(total_ent / days_worked, 2)
                        
                        start_date_str = file_date.split(' to ')[0].strip()
                        temp_dt = datetime.strptime(start_date_str, "%d/%m/%Y")
                        sort_key = temp_dt.strftime("%Y%m%d")
                        
                        worksheet.append_row([file_date, station_id, op_name, operator_id, int(enrol), int(update), int(total_ent), int(total_sum), avg_val, sort_key])
                        worksheet.sort((10, 'asc'))
                        
                        st.markdown(f"""
                        <div class="success-card">
                            <b style="font-size:20px;">✅ SUCCESS: Report Saved!</b><br><br>
                            👤 <b>Operator:</b> {op_name} | 📍 <b>Station:</b> {station_id}<br>
                            📅 <b>Range:</b> {file_date}<br>
                            📈 <b>Daily Average:</b> {avg_val}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if avg_val < 15:
                            st.markdown(f"""<div class="warning-card">⚠️ Aapki average kam hai ({avg_val}). Entry badhayein!</div>""", unsafe_allow_html=True)

                        if date_summary_table is not None:
                            st.table(date_summary_table[['date', 'no. of enrolments', 'no. of updates', 'total']])

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
