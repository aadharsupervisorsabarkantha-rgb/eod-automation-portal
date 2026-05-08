import streamlit as st
import pyzipper
import io
import re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="EOD Professional Portal",
    layout="wide"
)

# ---------------- OPERATOR DATABASE ----------------
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

# ---------------- CSS ----------------
st.markdown("""
<style>
.main-box{
    padding:20px; border-radius:15px; background:#d32f2f; color:white; text-align:center; margin-bottom:20px;
}
.success-card{
    padding:20px; border-radius:12px; background:#f0fdf4; border:1px solid #16a34a; color:#166534; margin-top:15px;
}
.warning-box{
    padding:15px; border-radius:10px; background:#fef2f2; border:1px solid #dc2626; color:#991b1b; margin-top:10px; font-weight:bold;
}
</style>
<div class="main-box">
<h2>🏦 STATION EOD AUTOMATION SYSTEM</h2>
</div>
""", unsafe_allow_html=True)

# ---------------- UI ----------------
col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox("Date Range", ["01 to 08", "09 to 16", "17 to 24", "25 to 31"])
with col2:
    st.selectbox("Month", ["January","February","March","April","May","June","July","August","September","October","November","December"], index=datetime.now().month - 1)
with col3:
    st.selectbox("Year", [2024, 2025, 2026], index=2)

zip_password = st.text_input("Enter ZIP Password", type="password")
uploaded_files = st.file_uploader("Upload ZIP Reports", type="zip", accept_multiple_files=True)

# ---------------- MAIN PROCESS ----------------
if st.button("🚀 FINAL SUBMIT & PROCESS"):
    if not uploaded_files:
        st.error("❌ ZIP file upload karo")
        st.stop()
    if not zip_password:
        st.error("❌ ZIP password enter karo")
        st.stop()

    try:
        # GSheet Connection
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key("19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU")

        for uploaded_file in uploaded_files:
            st.info(f"📦 Processing: {uploaded_file.name}")
            try:
                with pyzipper.AESZipFile(uploaded_file) as zf:
                    zf.setpassword(zip_password.encode())
                    html_files = [f for f in zf.namelist() if f.lower().endswith(".html")]

                    if not html_files:
                        st.warning(f"⚠️ No HTML file found in {uploaded_file.name}")
                        continue

                    for html_file in html_files:
                        try:
                            with zf.open(html_file) as f:
                                content = f.read().decode("utf-8", errors="ignore")
                            
                            soup = BeautifulSoup(content, "html.parser")
                            station_id, operator_id = None, None
                            all_entries = []
                            summary_table_ui = None

                            # Extract Summary Table for UI
                            try:
                                tables = pd.read_html(io.StringIO(content))
                                for t in tables:
                                    t.columns = [str(c).strip().lower() for c in t.columns]
                                    if "date" in t.columns and "no. of enrolments" in t.columns:
                                        summary_table_ui = t[t['date'].str.contains(r'\d{2}/\d{2}/\d{4}', na=False)]
                            except: pass

                            # Extract Entries
                            for row in soup.find_all("tr"):
                                tds = [td.get_text(strip=True) for td in row.find_all("td")]
                                if len(tds) < 2: continue
                                if "Station ID" in tds[0]: station_id = tds[1].strip()
                                if "Operator" in tds[0]: operator_id = tds[1].strip()

                                eid_found = None
                                for x in tds:
                                    digits = re.sub(r"\D", "", x)
                                    if len(digits) >= 20:
                                        eid_found = digits
                                        break

                                if eid_found:
                                    try:
                                        hidden_date = eid_found[-14:-6]
                                        d_str = datetime.strptime(hidden_date, "%Y%m%d").strftime("%d/%m/%Y")
                                        
                                        txn_type = "E"
                                        for x in tds:
                                            if x.strip().upper() in ["E", "U"]:
                                                txn_type = x.strip().upper()
                                                break
                                        
                                        f_amt = 0.0
                                        for x in reversed(tds):
                                            try:
                                                amt = float(x.replace("Rs.", "").replace("Rs", "").replace(",", "").strip())
                                                if amt > 0: f_amt = amt; break
                                            except: pass
                                        
                                        all_entries.append({"date": d_str, "type": txn_type, "amt": f_amt})
                                    except: continue

                            op_name = OPERATOR_MAP.get(operator_id, "Unknown")

                            if station_id and all_entries:
                                df = pd.DataFrame(all_entries)
                                try: worksheet = spreadsheet.worksheet(str(station_id))
                                except:
                                    worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="8")
                                    worksheet.append_row(["Date", "Station ID", "Operator", "Operator ID", "Enrol", "Update", "Total", "Amount"])

                                existing_data = worksheet.get_all_values()
                                existing_dates = [row[0] for row in existing_data[1:]] if len(existing_data) > 1 else []
                                
                                unique_dates = sorted(list(set(df["date"].tolist())), key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
                                newly_added = []

                                for d in unique_dates:
                                    if d in existing_dates: continue
                                    day_df = df[df["date"] == d]
                                    enrol = len(day_df[day_df["type"] == "E"])
                                    update = len(day_df[day_df["type"] == "U"])
                                    total = len(day_df)
                                    amount = int(day_df["amt"].sum())
                                    
                                    worksheet.append_row([d, station_id, op_name, operator_id, enrol, update, total, amount])
                                    newly_added.append(d)

                                if newly_added:
                                    st.markdown(f"""
                                    <div class="success-card">
                                    <h3>✅ DATA SAVED SUCCESSFULLY</h3>
                                    👤 <b>Operator:</b> {op_name}<br>
                                    📍 <b>Station:</b> {station_id}<br>
                                    📅 <b>Dates Added:</b> {newly_added[0]} to {newly_added[-1]}
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    st.write("### 📅 Date Wise Summary (From Report Table)")
                                    st.table(summary_table_ui)
                                    
                                    avg_val = round(len(df) / len(unique_dates), 2)
                                    if avg_val < 15:
                                        st.toast(f"🚨 Low Average: {avg_val}", icon="⚠️")
                                        st.markdown(f"<div class='warning-box'>⚠️ Warning: Aapka average {avg_val} hai. Minimum 15 chahiye!</div>", unsafe_allow_html=True)
                                    else:
                                        st.balloons()
                                        st.success(f"🔥 Performance: {avg_val} Avg")
                                else:
                                    st.info(f"ℹ️ {station_id}: Sari dates pehle se sheet mein hain.")
                            else:
                                st.error("⚠️ Data nahi mil paya.")
                        except Exception as e:
                            st.error(f"❌ HTML Process Error: {str(e)}")
            except RuntimeError:
                st.error(f"❌ Wrong Password: {uploaded_file.name}")
            except Exception as e:
                st.error(f"❌ ZIP Error: {str(e)}")
    except Exception as e:
        st.error(f"🚨 Main Error: {str(e)}")
