import streamlit as st
import pyzipper
import io
import re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="EOD Professional Portal", layout="centered")

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

# ---------------- STYLING ----------------
st.markdown("""
<style>
.main-box {
    padding: 20px;
    border-radius: 12px;
    background-color: #d32f2f;
    color: white;
    text-align: center;
    margin-bottom: 20px;
}
.success-card {
    padding: 20px;
    border-radius: 10px;
    background-color: #f0fdf4;
    border: 1px solid #16a34a;
    margin-top: 15px;
    color: #166534;
}
.warning-box {
    padding: 15px;
    background-color: #fef2f2;
    border: 1px solid #dc2626;
    color: #991b1b;
    border-radius: 10px;
    margin-top: 10px;
    font-weight: bold;
}
</style>

<div class="main-box">
<b style="font-size: 22px;">🏦 STATION EOD AUTOMATION SYSTEM</b>
</div>
""", unsafe_allow_html=True)

# ---------------- UI ----------------
col1, col2, col3 = st.columns(3)

with col1:
    st.selectbox(
        "Date Range",
        ["01 to 08", "09 to 16", "17 to 24", "25 to 31"]
    )

with col2:
    st.selectbox(
        "Month",
        [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December"
        ],
        index=datetime.now().month - 1
    )

with col3:
    st.selectbox(
        "Year",
        [2024, 2025, 2026],
        index=2
    )

zip_password = st.text_input("Enter ZIP Password", type="password")

uploaded_files = st.file_uploader(
    "Upload ZIP Reports",
    type="zip",
    accept_multiple_files=True
)

# ---------------- MAIN PROCESS ----------------
if st.button("🚀 FINAL SUBMIT & PROCESS"):

    if not uploaded_files:
        st.error("❌ ZIP file upload karo")
        st.stop()

    if not zip_password:
        st.error("❌ ZIP password enter karo")
        st.stop()

    try:

        # ---------------- GOOGLE SHEETS LOGIN ----------------
        creds_dict = st.secrets["gcp_service_account"]

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict,
            scope
        )

        client = gspread.authorize(creds)

        spreadsheet = client.open_by_key(
            "19mlf7dpNJyyvnKYZpoJtjyQY6RkTaze4FsC7xCKnMrU"
        )

        # ---------------- FILE LOOP ----------------
        for uploaded_file in uploaded_files:

            st.info(f"📦 Processing: {uploaded_file.name}")

            try:

                with pyzipper.AESZipFile(uploaded_file) as zf:

                    zf.setpassword(zip_password.encode())

                    html_files = [
                        f for f in zf.namelist()
                        if f.lower().endswith(".html")
                    ]

                    if not html_files:
                        st.warning(f"⚠️ No HTML files found in {uploaded_file.name}")
                        continue

                    # ---------------- HTML LOOP ----------------
                    for html_file in html_files:

                        st.write(f"📄 Reading: {html_file}")

                        try:

                            with zf.open(html_file) as f:

                                content = f.read().decode(
                                    "utf-8",
                                    errors="ignore"
                                )

                            soup = BeautifulSoup(content, "html.parser")

                            station_id = None
                            operator_id = None
                            all_entries = []
                            summary_table_ui = None

                            # ---------------- TABLE EXTRACTION ----------------
                            try:
                                tabs = pd.read_html(io.StringIO(content))
                            except:
                                tabs = []

                            for t in tabs:

                                try:
                                    t.columns = [
                                        str(c).strip().lower()
                                        for c in t.columns
                                    ]

                                    if (
                                        "date" in t.columns
                                        and "no. of enrolments" in t.columns
                                    ):

                                        summary_table_ui = t[
                                            t["date"].astype(str).str.contains(
                                                r'\d{2}/\d{2}/\d{4}',
                                                na=False
                                            )
                                        ]

                                except:
                                    pass

                            # ---------------- ROW LOOP ----------------
                            for row in soup.find_all("tr"):

                                tds = [
                                    td.get_text(strip=True)
                                    for td in row.find_all("td")
                                ]

                                if len(tds) < 2:
                                    continue

                                # DEBUG
                                # st.write(tds)

                                # Station ID
                                if "Station ID" in tds[0]:
                                    station_id = tds[1]

                                # Operator
                                if "Operator" in tds[0]:
                                    operator_id = tds[1]

                                # ---------------- DATE ENTRY ----------------
                                joined = " ".join(tds)

                                date_match = re.search(
                                    r'(\d{4})/(\d{2})/(\d{2})',
                                    joined
                                )

                                if date_match:

                                    try:

                                        d_str = (
                                            f"{date_match.group(3)}/"
                                            f"{date_match.group(2)}/"
                                            f"{date_match.group(1)}"
                                        )

                                        # Type Logic
                                        txn_type = ""

                                        for x in tds:
                                            if x.strip().upper() in ["E", "U"]:
                                                txn_type = x.strip().upper()
                                                break

                                        if txn_type == "":
                                            txn_type = "E"

                                        # Amount Logic
                                        f_amt = 0.0

                                        for x in reversed(tds):

                                            try:
                                                amt_text = (
                                                    x.replace("Rs.", "")
                                                     .replace("Rs", "")
                                                     .replace(",", "")
                                                     .strip()
                                                )

                                                amt = float(amt_text)

                                                if amt > 0:
                                                    f_amt = amt
                                                    break

                                            except:
                                                pass

                                        all_entries.append({
                                            "date": d_str,
                                            "type": txn_type,
                                            "amt": f_amt
                                        })

                                    except Exception as e:
                                        st.warning(f"Row parse error: {e}")

                            # ---------------- OPERATOR NAME ----------------
                            op_name = OPERATOR_MAP.get(
                                operator_id,
                                "Unknown"
                            )

                            # ---------------- DATAFRAME ----------------
                            if station_id and len(all_entries) > 0:

                                df = pd.DataFrame(all_entries)

                                # ---------------- WORKSHEET ----------------
                                try:
                                    worksheet = spreadsheet.worksheet(
                                        str(station_id)
                                    )

                                except:

                                    worksheet = spreadsheet.add_worksheet(
                                        title=str(station_id),
                                        rows="1000",
                                        cols="8"
                                    )

                                    worksheet.append_row([
                                        "Date",
                                        "Station ID",
                                        "Operator",
                                        "ID",
                                        "Enrol",
                                        "Update",
                                        "Total",
                                        "Amount"
                                    ])

                                # ---------------- EXISTING DATA ----------------
                                existing_data = worksheet.get_all_values()

                                existing_dates = []

                                if len(existing_data) > 1:
                                    existing_dates = [
                                        r[0]
                                        for r in existing_data[1:]
                                        if len(r) > 0
                                    ]

                                # ---------------- UNIQUE DATES ----------------
                                unique_dates = sorted(
                                    list(set(df["date"].tolist())),
                                    key=lambda x: datetime.strptime(
                                        x,
                                        "%d/%m/%Y"
                                    )
                                )

                                newly_added = []

                                # ---------------- DATE LOOP ----------------
                                for d in unique_dates:

                                    if d in existing_dates:
                                        continue

                                    day_df = df[df["date"] == d]

                                    enrol = len(
                                        day_df[
                                            day_df["type"] == "E"
                                        ]
                                    )

                                    update = len(
                                        day_df[
                                            day_df["type"] == "U"
                                        ]
                                    )

                                    total = len(day_df)

                                    amount = int(day_df["amt"].sum())

                                    worksheet.append_row([
                                        d,
                                        station_id,
                                        op_name,
                                        operator_id,
                                        enrol,
                                        update,
                                        total,
                                        amount
                                    ])

                                    newly_added.append(d)

                                # ---------------- SUCCESS ----------------
                                if newly_added:

                                    st.markdown(f"""
                                    <div class="success-card">
                                    <b style="font-size:18px;">
                                    ✅ DATA SAVED SUCCESSFULLY!
                                    </b><br><br>

                                    👤 <b>Operator:</b> {op_name}<br>

                                    📍 <b>Station:</b> {station_id}<br>

                                    📅 <b>Dates Added:</b>
                                    {newly_added[0]} to {newly_added[-1]}
                                    </div>
                                    """, unsafe_allow_html=True)

                                    # ---------------- SUMMARY TABLE ----------------
                                    if summary_table_ui is not None:
                                        st.write("### 📊 Report Summary")
                                        st.table(summary_table_ui)

                                    # ---------------- AVERAGE ----------------
                                    avg_val = round(
                                        len(df) / len(unique_dates),
                                        2
                                    )

                                    if avg_val < 15:

                                        st.toast(
                                            f"🚨 Low Average: {avg_val}",
                                            icon="⚠️"
                                        )

                                        st.markdown(f"""
                                        <div class='warning-box'>
                                        ⚠️ Warning:
                                        Aapka average {avg_val} hai.
                                        Minimum 15 chahiye!
                                        </div>
                                        """, unsafe_allow_html=True)

                                    else:

                                        st.balloons()

                                        st.success(
                                            f"🔥 Performance: {avg_val} Avg"
                                        )

                                else:

                                    st.info(
                                        f"ℹ️ {station_id}: "
                                        f"Sari dates already available hain."
                                    )

                            else:

                                st.warning(
                                    f"⚠️ Station data nahi mila in {html_file}"
                                )

                        except Exception as e:
                            st.error(
                                f"❌ HTML Process Error ({html_file}) : {str(e)}"
                            )

            except RuntimeError:
                st.error(
                    f"❌ Wrong ZIP Password: {uploaded_file.name}"
                )

            except Exception as e:
                st.error(
                    f"❌ ZIP Error ({uploaded_file.name}) : {str(e)}"
                )

    except Exception as e:
        st.error(f"🚨 Main Error: {str(e)}")
