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
    .success-card { padding: 20px; border-radius: 10px; background-color: #f0fdf4; border: 1px solid #16a34a; margin-top: 15px; color: #166534; }
    .warning-box { padding: 15px; background-color: #fef2f2; border: 1px solid #dc2626; color: #991b1b; border-radius: 10px; margin-top: 10px; font-weight: bold; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# --- UI DROPDOWNS (Professional Purpose Only) ---
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

                station_id, operator_id = None, None
                all_entries = []
                summary_table_ui = None

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        
                        # UI Table nikalna
                        tabs = pd.read_html(path)
                        for t in tabs:
                            t.columns = [str(c).lower() for c in t.columns]
                            if "no. of enrolments" in t.columns:
                                summary_table_ui = t[t['date'].str.contains(r'\d{2}/\d{2}/\d{4}', na=False)]

                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            rows = soup.find_all("tr")
                            for row in rows:
                                tds = [td.get_text(strip=True) for td in row.find_all("td")]
                                if len(tds) < 2: continue
                                if "Station ID" in tds[0]: station_id = tds[1]
                                if "Operator" in tds[0]: operator_id = tds[1]
                                if len(tds) > 10 and "/" in tds[1]:
                                    date_match = re.search(r'(\d{4})/(\d{2})/(\d{2})', tds[1])
                                    if date_match:
                                        d_str = f"{date_match.group(3)}/{date_match.group(2)}/{date_match.group(1)}"
                                        f_amt = float(tds[-2].replace("Rs.", "").strip()) if tds[-2].replace('.','').isdigit() else 0.0
                                        all_entries.append({"date": d_str, "type": tds[3].upper(), "amt": f_amt})

                op_name = OPERATOR_MAP.get(operator_id, "Unknown")

                if station_id and all_entries:
                    df = pd.DataFrame(all_entries)
                    try: worksheet = spreadsheet.worksheet(str(station_id))
                    except: 
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="8")
                        worksheet.append_row(["Date", "Station ID", "Operator", "ID", "Enrol", "Update", "Total", "Amount"])

                    existing_data = worksheet.get_all_values()
                    flat_existing = " ".join([r[0] for r in existing_data])
                    
                    unique_dates = sorted(list(set(df['date'].tolist())), key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
                    newly_added = []

                    for d in unique_dates:
                        if d in flat_existing: continue
                        day_df = df[df['date'] == d]
                        enrol = len(day_df[day_df['type'] == 'E'])
                        update = len(day_df[day_df['type'] == 'U'])
                        total = len(day_df)
                        amount = int(day_df['amt'].sum())
                        worksheet.append_row([d, station_id, op_name, operator_id, enrol, update, total, amount])
                        newly_added.append(d)

                    if newly_added:
                        st.markdown(f"""
                        <div class="success-card">
                            <b style="font-size:18px;">✅ DATA SAVED SUCCESSFULLY!</b><br><br>
                            👤 <b>Operator:</b> {op_name}<br>
                            📍 <b>Station:</b> {station_id}<br>
                            📅 <b>Dates Processed:</b> {newly_added[0]} to {newly_added[-1]}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.write("### 📊 Summary of Uploaded Report")
                        st.table(summary_table_ui)
                        
                        avg_val = round(len(df) / len(unique_dates), 2)
                        if avg_val < 15:
                            st.toast(f"🚨 Low Average Alert: {avg_val}", icon="⚠️")
                            st.markdown(f"<div class='warning-box'>⚠️ Warning: Average {avg_val} hai. 15 se kam hai!</div>", unsafe_allow_html=True)
                        else:
                            st.balloons()
                            st.success(f"🔥 Performance: {avg_val} Avg")
                    else:
                        st.info("ℹ️ Sari dates pehle se sheet mein hain.")

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
