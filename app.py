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

# Penalty Warning UI
st.markdown("""
    <style>
    .penalty-box {
        padding: 15px; border-radius: 10px; background-color: #ff4b4b; color: white;
        font-weight: bold; text-align: center; margin-bottom: 25px; border: 2px solid white;
    }
    </style>
    <div class="penalty-box">
        ⚠️ ATTENTION OPERATOR: Data upload compulsory hai. Mismatch par PENALTY lagu hogi!
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

                station_id, total_sum, file_date, operator_id = None, 0, None, None
                
                for file in os.listdir(extract_dir):
                    if file.endswith(".html"):
                        path = os.path.join(extract_dir, file)
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            html_content = f.read()
                            soup = BeautifulSoup(html_content, "html.parser")
                            text_data = soup.get_text(" ", strip=True)

                            # --- 1. STRICT DATE EXTRACTION ---
                            date_match = re.search(r"Report Generated for Date:\s*(\d{2}/\d{2}/\d{4}\s*to\s*\d{2}/\d{2}/\d{4})", text_data, re.IGNORECASE)
                            if date_match:
                                file_date = date_match.group(1)

                            # --- 2. STATION & OPERATOR EXTRACTION ---
                            for row in soup.find_all("tr"):
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    label = cols[0].get_text(strip=True)
                                    val = cols[1].get_text(strip=True)
                                    if "Station ID" in label: station_id = val
                                    if "Operator" in label: operator_id = val
                            
                            # --- 3. AMOUNT ---
                            tables = pd.read_html(path)
                            for df in tables:
                                df.columns = [str(c).strip().lower() for c in df.columns]
                                col = next((c for c in df.columns if "total amount charged" in c), None)
                                if col:
                                    cleaned = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
                                    total_sum += pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()

                # Map Operator ID to Name
                operator_name = OPERATOR_MAP.get(operator_id, "Unknown Operator")
                final_date = file_date if file_date else f"{ui_date_range} {selected_month} {selected_year}"

                if station_id:
                    try:
                        worksheet = spreadsheet.worksheet(str(station_id))
                    except:
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="10")
                        worksheet.append_row(["Date Range", "Station ID", "Operator Name", "Operator ID", "Total Amount"])
                    
                    # Save to Sheet
                    worksheet.append_row([final_date, station_id, operator_name, operator_id, int(total_sum)])
                    
                    # --- DYNAMIC SUCCESS MESSAGE ---
                    st.balloons()
                    st.success(f"✅ Report Save Success for {final_date}")
                    st.markdown(f"""
                        **📋 Report Summary:**
                        * **Station ID:** {station_id}
                        * **Operator Name:** {operator_name}
                        * **Operator ID:** {operator_id}
                    """)
                    st.toast(f"🔔 Yaad rakhein {operator_name}, agli file bhi upload karni hai!", icon='📅')
                
                shutil.rmtree(extract_dir)

        except Exception as e:
            st.error(f"System Error: {e}")
