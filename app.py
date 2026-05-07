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
    "GJPE_SBK_NS701346": "DABHI SAGAR",
    "GJPE_SBR_NS737401": "DABHI BIBIBEN",
    "GJPE_SBK_NS101344": "PARMAR RAVINDRA"
}

# --- RED PENALTY WARNING BOX ---
st.markdown("""
    <style>
    .strict-penalty-box {
        padding: 20px; border-radius: 12px; background-color: #d32f2f; color: #ffffff;
        font-family: sans-serif; font-size: 18px; text-align: center;
        border: 4px solid #f44336; box-shadow: 0px 4px 15px rgba(0,0,0,0.3); margin-bottom: 30px;
    }
    </style>
    <div class="strict-penalty-box">
        <b style="font-size: 22px;">🚫 ATTENTION OPERATOR 🚫</b><br>
        Data upload compulsory hai. <br>
        <b>Yaad Rakhein: Mismatch par PENALTY lagegi!</b>
    </div>
    """, unsafe_allow_html=True)

st.title("🏦 Station EOD Automation")

# --- STEP 1: DROPDOWN ---
st.subheader("1️⃣ Details Select Karein")
col1, col2, col3 = st.columns(3)
with col1:
    ui_date_range = st.selectbox("Expected Date Range", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2:
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    selected_month = st.selectbox("Month", months, index=datetime.now().month - 1)
with col3:
    selected_year = st.selectbox("Year", [2025, 2026], index=0)

# --- STEP 2: PASSWORD & UPLOAD ---
st.subheader("2️⃣ Security & File")
zip_password = st.text_input("ZIP File ka Password dalein", type="password")
uploaded_files = st.file_uploader("ZIP Files Upload Karein", type="zip", accept_multiple_files=True)

if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files or not zip_password:
        st.error("❌ Kripya Password aur File dono check karein!")
    else:
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")

            for uploaded_file in uploaded_files:
                extract_dir = f"temp_{uploaded_file.name}"
                if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
                os.makedirs(extract_dir)

                with pyzipper.AESZipFile(uploaded_file) as zf:
                    try:
                        zf.extractall(extract_dir, pwd=zip_password.encode())
                    except:
                        st.error(f"🚨 GALAT PASSWORD for {uploaded_file.name}!")
                        continue 

                station_id, total_sum, file_date, operator_id, total_entries = None, 0, None, None, 0
                
                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            html_content = f.read()
                            soup = BeautifulSoup(html_content, "html.parser")
                            text_data = soup.get_text(" ", strip=True)

                            # 1. Date Extraction
                            date_match = re.search(r"Report Generated for Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text_data, re.IGNORECASE)
                            if date_match: file_date = date_match.group(1)

                            # 2. Station & Operator
                            for row in soup.find_all("tr"):
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    label = cols[0].get_text(strip=True)
                                    val = cols[1].get_text(strip=True)
                                    if "Station ID" in label: station_id = val
                                    if "Operator" in label: operator_id = val
                            
                            # 3. Entries (S.No) & Amount
                            tables = pd.read_html(path)
                            for df in tables:
                                df.columns = [str(c).strip().lower() for c in df.columns]
                                if "s.no" in df.columns:
                                    # Count total rows for S.No
                                    total_entries = len(df)
                                col = next((c for c in df.columns if "total amount charged" in c), None)
                                if col:
                                    cleaned = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                                    total_sum += pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()

                # --- AVERAGE CALCULATOR ---
                avg_entries = total_entries / 8 # Dividing by 8 days
                operator_name = OPERATOR_MAP.get(operator_id, "Unknown Operator")
                final_date = file_date if file_date else f"{ui_date_range} {selected_month} {selected_year}"

                if station_id:
                    try:
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator Name", "Total Entries", "Total Amount"])
                    
                    worksheet.append_row([final_date, station_id, operator_name, total_entries, int(total_sum)])
                    
                    # --- DYNAMIC SUCCESS & WARNING MESSAGES ---
                    st.balloons()
                    st.success(f"✅ Report Save Success for {final_date}")
                    st.markdown(f"📍 **Station:** {station_id} | 👤 **Operator:** {operator_name} ({operator_id})")
                    st.info(f"📊 **Total Entries:** {total_entries} | **Daily Average:** {avg_entries:.1f}")

                    if avg_entries < 15:
                        st.warning(f"⚠️ **Warning:** Aapki din ki average entries ({avg_entries:.1f}) kam hain, kripya usse jyada entries karein!")
                    
                    st.toast(f"🔔 Agli file yaad se upload karein!", icon='📅')
                
                shutil.rmtree(extract_dir)

        except Exception as e:
            st.error(f"System Error: {e}")
