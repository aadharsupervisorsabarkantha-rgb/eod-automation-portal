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
    .dup-card { padding: 15px; border-radius: 10px; background-color: #fff3e0; border-left: 8px solid #ef6c00; color: #e65100; margin-top: 10px; font-weight: bold; }
    </style>
    <div class="main-box"><b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b></div>
    """, unsafe_allow_html=True)

# Dropdowns (Professional Purpose)
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

                station_id, operator_id, file_date_range = None, None, None
                master_list = []

                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            soup = BeautifulSoup(f.read(), "html.parser")
                            
                            # Info nikalna
                            text = soup.get_text(" ", strip=True)
                            d_match = re.search(r"Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text)
                            if d_match: file_date_range = d_match.group(1)
                            
                            for row in soup.find_all("tr"):
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    if "Station ID" in cols[0].text: station_id = cols[1].text.strip()
                                    if "Operator" in cols[0].text: operator_id = cols[1].text.strip()
                                
                                # Row analysis for data
                                tds = [td.get_text(strip=True) for td in cols]
                                if len(tds) > 10 and tds[1].isdigit() and len(tds[1]) >= 28:
                                    eid = tds[1]
                                    # EID format se date nikalna (YYYYMMDD part)
                                    e_date = f"{eid[19:21]}/{eid[17:19]}/{eid[13:17]}"
                                    charge = float(tds[-1]) if tds[-1].replace('.','').isdigit() else 0.0
                                    master_list.append({"date": e_date, "type": tds[3], "amt": charge})

                if station_id and master_list:
                    df = pd.DataFrame(master_list)
                    try: worksheet = spreadsheet.worksheet(str(station_id))
                    except: 
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator", "ID", "Enrol", "Update", "Total", "Amount", "Avg", "SortKey"])

                    existing_data = worksheet.get_all_values()
                    flat_existing = " ".join([r[0] for r in existing_data])

                    # Logic for Duplicate Filtering
                    all_file_dates = sorted(list(set(df['date'].tolist())), key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
                    new_dates = [d for d in all_file_dates if d not in flat_existing]
                    dup_dates = [d for d in all_file_dates if d in flat_existing]

                    if not new_dates:
                        st.error(f"🛑 Duplicate Alert! Is file ki Date Range ({file_date_range}) ki entry pehle se sheet mein ho chuki hai. Kripya aage ki ya baki dates ki entry karein.")
                    else:
                        df_new = df[df['date'].isin(new_dates)]
                        enrol = len(df_new[df_new['type'] == 'E'])
                        update = len(df_new[df_new['type'] == 'U'])
                        total = len(df_new)
                        amount = int(df_new['amt'].sum())
                        avg = round(total / len(new_dates), 2)
                        
                        final_range = f"{new_dates[0]} to {new_dates[-1]}"
                        sort_key = datetime.strptime(new_dates[0], "%d/%m/%Y").strftime("%Y%m%d")

                        # Sheet Entry
                        worksheet.append_row([final_range, station_id, OPERATOR_MAP.get(operator_id, "Unknown"), operator_id, enrol, update, total, amount, avg, sort_key])
                        worksheet.sort((10, 'asc'))

                        # Operator Show Purpose Alert
                        if dup_dates:
                            st.markdown(f"""
                            <div class="dup-card">
                                ℹ️ Note: Aapki file mein se {dup_dates[0]} se {dup_dates[-1]} tak ki entry duplicate thi jo pehle se ho chuki thi.<br>
                                Par aap tension na lein, system ne baki bachi dates ({final_range}) ki entry kar di hai!
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="success-card">
                            ✅ <b>SUCCESS: Data Processed!</b><br>
                            📅 Range: {final_range} | 💰 Amount: ₹{amount}<br>
                            📊 Total Enrolment: {total} | 📈 Avg: {avg}
                        </div>
                        """, unsafe_allow_html=True)

                shutil.rmtree(extract_dir)
        except Exception as e:
            st.error(f"Error: {e}")
