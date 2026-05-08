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

# --- UI STYLING ---
st.markdown("""
    <style>
    .main-box { padding: 20px; border-radius: 12px; background-color: #d32f2f; color: white; text-align: center; margin-bottom: 20px; }
    .success-card { padding: 20px; border-radius: 10px; background-color: #e8f5e9; border-left: 8px solid #2e7d32; margin-top: 15px; color: #1b5e20; }
    .dup-info { padding: 15px; border-radius: 10px; background-color: #fff3e0; border-left: 8px solid #ef6c00; color: #e65100; margin-bottom: 10px; font-weight: bold; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# Dropdowns
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

                # Extraction logic
                station_id, operator_id = None, None
                master_data = [] # Saari entries isme aayengi

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            
                            # Station & Operator ID find karna
                            rows = soup.find_all("tr")
                            for row in rows:
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    txt = cols[0].text.strip()
                                    if "Station ID" in txt: station_id = cols[1].text.strip()
                                    if "Operator" in txt: operator_id = cols[1].text.strip()
                            
                            # Data rows find karna (Regex se)
                            for row in rows:
                                tds = [td.text.strip() for td in row.find_all("td")]
                                if len(tds) > 5 and re.search(r'\d{14,}', tds[1]): # EID mil gaya
                                    eid = tds[1]
                                    # EID format: ...YYYY/MM/DD... ya ...YYYYMMDD...
                                    # Date nikalne ka robust tarika (2024/12/23 ya 20241223)
                                    match = re.search(r'(\d{4})/?(\d{2})/?(\d{2})', eid)
                                    if match:
                                        found_date = f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
                                        # Amount last se pehle wala column hota hai aksar
                                        amt_str = tds[-2].replace("Rs.", "").strip()
                                        amt = float(amt_str) if amt_str.replace('.', '').isdigit() else 0
                                        
                                        # Entry type (Enrolment ya Update)
                                        is_update = "Update" in str(tds)
                                        master_data.append({"date": found_date, "amount": amt, "is_update": is_update})

                if station_id and master_data:
                    df_all = pd.DataFrame(master_data)
                    try: worksheet = spreadsheet.worksheet(str(station_id))
                    except: worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")

                    existing_data = worksheet.get_all_values()
                    flat_existing = " ".join([r[0] for r in existing_data])

                    # 1. Duplicate Filtering
                    all_dates = df_all['date'].unique().tolist()
                    new_dates = [d for d in all_dates if d not in flat_existing]
                    dup_dates = [d for d in all_dates if d in flat_existing]

                    if not new_dates:
                        st.error(f"🛑 Duplicate Alert! File ki dates pehle se sheet mein hain.")
                    else:
                        # 2. Filter only New Data
                        df_new = df_all[df_all['date'].isin(new_dates)]
                        
                        total_amt = int(df_new['amount'].sum())
                        total_ent = len(df_new)
                        updates = len(df_new[df_new['is_update'] == True])
                        enrols = total_ent - updates
                        
                        avg_val = round(total_ent / len(new_dates), 2)
                        new_range_str = f"{new_dates[0]} to {new_dates[-1]}"
                        
                        # Sort Key
                        sort_key = datetime.strptime(new_dates[0], "%d/%m/%Y").strftime("%Y%m%d")

                        # 3. Final Append
                        worksheet.append_row([new_range_str, station_id, OPERATOR_MAP.get(operator_id, "Unknown"), operator_id, enrols, updates, total_ent, total_amt, avg_val, sort_key])
                        worksheet.sort((10, 'asc'))

                        # 4. Success UI
                        if dup_dates:
                            st.markdown(f"<div class='dup-info'>ℹ️ Note: {len(dup_dates)} purani dates skip kar di gayi hain. Baki {len(new_dates)} nayi dates save ho gayi!</div>", unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="success-card">
                            ✅ <b>SUCCESS: Data Processed!</b><br>
                            📅 Range: {new_range_str} | 💰 Amount: ₹{total_amt}<br>
                            📊 Total Enrolment: {total_ent} | 📈 Average: {avg_val}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Display Table for verification
                        summary_df = df_new.groupby('date').size().reset_index(name='Total')
                        st.table(summary_df)

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Technical Error: {e}")
