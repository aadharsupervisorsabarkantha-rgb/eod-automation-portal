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
    "GJPE_SBK_NS603205": "RATHOD VIJAY", "GJPE_SBK_NS435053": "PATEL VIPUL",
    "GJPE_SBK_NS668733": "CHAUHAN CHANDUJI", "GJPE_SBK_NS716164": "DAYANI MADHUBEN",
    "GJPE_SBR_NS851220": "MEMON SAKIL", "GJPE_SBK_NS101318": "BHATT SANAM",
    "GJPE_SBK_NS054082": "SOLANKI RAJESH", "GJPE_SBK_NS463140": "JADAV SHASHIKANT",
    "GJPE_SBK_NS728611": "RAVAL JAYPAL", "GJPE_SBK_NS721374": "ASARI ROHIT",
    "GJPE_SBK_NS776405": "BAROT APURVA", "GJPE_SBK_NS829265": "VANKAR TEJALBEN",
    "GJPE_SBK_NS442326": "MANSURI VARISH", "GJPE_SBR_NS737401": "DABHI BIBIBEN",
    "GJPE_SBK_NS101344": "PARMAR RAVINDRA"
}

# --- STYLING ---
st.markdown("""
    <style>
    .main-box { padding: 20px; border-radius: 12px; background-color: #d32f2f; color: white; text-align: center; margin-bottom: 20px; }
    .success-card { padding: 20px; border-radius: 10px; background-color: #e8f5e9; border-left: 8px solid #2e7d32; margin-top: 15px; color: #1b5e20; }
    .dup-info { padding: 15px; border-radius: 10px; background-color: #fff3e0; border-left: 8px solid #ef6c00; color: #e65100; margin-bottom: 10px; font-weight: bold; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# Dropdowns (For Professional Look Only)
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
                    except: st.error("🚨 Password Galat Hai!"); continue

                station_id, file_range, operator_id = None, None, None
                date_summary_table, details_table = None, None

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        all_tabs = pd.read_html(path)
                        with open(path, "r", encoding="utf-8") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            text = soup.get_text(" ", strip=True)
                            d_match = re.search(r"Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text)
                            if d_match: file_range = d_match.group(1)
                            for row in soup.find_all("tr"):
                                c = row.find_all("td")
                                if len(c) >= 2:
                                    if "Station ID" in c[0].text: station_id = c[1].text.strip()
                                    if "Operator" in c[0].text: operator_id = c[1].text.strip()

                        for df in all_tabs:
                            df.columns = [str(col).strip().lower() for col in df.columns]
                            if "no. of enrolments" in df.columns:
                                date_summary_table = df[df['date'].str.contains(r'\d{2}/\d{2}/\d{4}', na=False)]
                            if "enrolment no. and date" in df.columns:
                                details_table = df

                op_name = OPERATOR_MAP.get(operator_id, "Unknown")
                if station_id and date_summary_table is not None:
                    try: worksheet = spreadsheet.worksheet(str(station_id))
                    except: worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")

                    existing_data = worksheet.get_all_values()
                    flat_existing = " ".join([r[0] for r in existing_data])

                    # Smart Filtering
                    new_dates_df = date_summary_table[~date_summary_table['date'].apply(lambda x: x in flat_existing)]
                    dup_dates = date_summary_table[date_summary_table['date'].apply(lambda x: x in flat_existing)]['date'].tolist()

                    if len(new_dates_df) == 0:
                        st.error(f"🛑 Duplicate Alert! Range {file_range} pehle se sheet mein hai. Aage ki entry karein.")
                    else:
                        # Calculation from Nayi Dates
                        new_dates_list = new_dates_df['date'].tolist()
                        enrol = pd.to_numeric(new_dates_df["no. of enrolments"], errors='coerce').sum()
                        update = pd.to_numeric(new_dates_df["no. of updates"], errors='coerce').sum()
                        total_ent = pd.to_numeric(new_dates_df["total"], errors='coerce').sum()
                        
                        # Amount from Application No. Date Matching
                        total_amt = 0
                        if details_table is not None:
                            for index, row in details_table.iterrows():
                                eid = str(row['enrolment no. and date'])
                                # EID se date nikalna (2024/12/23 -> 23/12/2024)
                                if len(eid) >= 22:
                                    # UIDAI format: ...YYYYMMDD...
                                    e_date = f"{eid[19:21]}/{eid[17:19]}/{eid[13:17]}" 
                                    if e_date in new_dates_list:
                                        amt = str(row.iloc[-2]).replace("Rs.", "").strip()
                                        total_amt += pd.to_numeric(amt, errors='coerce')

                        avg_val = round(total_ent / len(new_dates_df), 2)
                        new_range_str = f"{new_dates_df['date'].iloc[-1]} to {new_dates_df['date'].iloc[0]}"
                        sort_key = datetime.strptime(new_dates_df['date'].iloc[-1], "%d/%m/%Y").strftime("%Y%m%d")

                        # FINAL APPEND
                        worksheet.append_row([new_range_str, station_id, op_name, operator_id, int(enrol), int(update), int(total_ent), int(total_amt), avg_val, sort_key])
                        worksheet.sort((10, 'asc'))

                        # SHOW PURPOSE MESSAGE FOR OPERATOR
                        if dup_dates:
                            st.markdown(f"""
                            <div class="dup-info">
                                ℹ️ Note: Aapki file mein se {min(dup_dates)} se {max(dup_dates)} tak ki entry duplicate thi jo pehle se ho chuki thi.<br>
                                Par aap tension na lein, system ne baki bachi dates ({new_range_str}) ki nayi entry kar di hai!
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="success-card">
                            <b style="font-size:20px;">✅ SUCCESS: Nayi Report Save Ho Gayi!</b><br><br>
                            👤 <b>Operator:</b> {op_name}<br>
                            📅 <b>Saved Dates:</b> {new_range_str}<br>
                            💰 <b>Total Amount:</b> ₹{int(total_amt)}
                        </div>
                        """, unsafe_allow_html=True)

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
