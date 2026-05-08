import streamlit as st
import pyzipper
import io, re
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="EOD Professional Portal", layout="wide")

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

# --- CSS ---
st.markdown("""
<style>
.main-box{
    padding:20px;
    border-radius:15px;
    background:#d32f2f;
    color:white;
    text-align:center;
    margin-bottom:20px;
}
.success-card{
    padding:20px;
    border-radius:12px;
    background:#f0fdf4;
    border:1px solid #16a34a;
    color:#166534;
    margin-top:15px;
}
.warning-box{
    padding:15px;
    border-radius:10px;
    background:#fef2f2;
    border:1px solid #dc2626;
    color:#991b1b;
    margin-top:10px;
    font-weight:bold;
}
</style>

<div class="main-box">
<h2>🏦 STATION EOD AUTOMATION SYSTEM</h2>
</div>
""", unsafe_allow_html=True)

# --- UI ---
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
            "January","February","March","April",
            "May","June","July","August",
            "September","October","November","December"
        ],
        index=datetime.now().month - 1
    )

with col3:
    st.selectbox(
        "Year",
        [2024, 2025, 2026],
        index=2
    )

zip_password = st.text_input(
    "Enter ZIP Password",
    type="password"
)

uploaded_files = st.file_uploader(
    "Upload ZIP Reports",
    type="zip",
    accept_multiple_files=True
)

# ---------------- PROCESS ----------------
if st.button("🚀 FINAL SUBMIT & PROCESS"):

    if not uploaded_files or not zip_password:
        st.error("❌ Password aur File zaroori hai!")
        st.stop()

    try:

        # --- GOOGLE SHEET LOGIN ---
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

        # --- FILE LOOP ---
        for uploaded_file in uploaded_files:

            with pyzipper.AESZipFile(uploaded_file) as zf:

                zf.setpassword(zip_password.encode())

                html_files = [
                    f for f in zf.namelist()
                    if f.lower().endswith(".html")
                ]

                for html_file in html_files:

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

                    # --- SUMMARY TABLE ---
                    try:

                        tabs = pd.read_html(
                            io.StringIO(content)
                        )

                        for t in tabs:

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

                    # =====================================================
                    # TABLE ROW PROCESSING
                    # =====================================================

                    rows = soup.find_all("tr")

                    for row in rows:

                        tds = [
                            td.get_text(strip=True)
                            for td in row.find_all("td")
                        ]

                        # Minimum 2 columns required
                        if len(tds) < 2:
                            continue

                        # ---------------- STATION ID ----------------
                        if "Station ID" in tds[0]:
                            station_id = tds[1].strip()

                        # ---------------- OPERATOR ID ----------------
                        if "Operator" in tds[0]:
                            operator_id = tds[1].strip()

                        # Transaction rows only
                        if len(tds) < 10:
                            continue

                        # ---------------- EID FIND ----------------
                        eid_val = None

                        for x in tds:

                            digits = re.sub(r"\D", "", x)

                            if len(digits) >= 20:
                                eid_val = digits
                                break

                        # ---------------- DATE EXTRACTION ----------------
                        if eid_val:

                            try:

                                # Hidden date before last 6 digits
                                hidden_date = eid_val[-14:-6]

                                h_date = datetime.strptime(
                                    hidden_date,
                                    "%Y%m%d"
                                ).strftime("%d/%m/%Y")

                                # ---------------- TYPE ----------------
                                txn_type = "E"

                                for x in tds:

                                    val = x.strip().upper()

                                    if val in ["E", "U"]:
                                        txn_type = val
                                        break

                                # ---------------- AMOUNT ----------------
                                last_col_val = (
                                    tds[-1]
                                    .replace("Rs.", "")
                                    .replace("Rs", "")
                                    .replace(",", "")
                                    .strip()
                                )

                                if last_col_val.replace('.', '', 1).isdigit():
                                    f_amt = float(last_col_val)
                                else:
                                    f_amt = 0.0

                                # Safety
                                if f_amt > 1000000:
                                    f_amt = 0.0

                                # ---------------- SAVE ENTRY ----------------
                                all_entries.append({
                                    "date": h_date,
                                    "type": txn_type,
                                    "amt": f_amt
                                })

                            except:
                                continue

                    # =====================================================

                    op_name = OPERATOR_MAP.get(
                        operator_id,
                        "Unknown"
                    )

                    # --- MAIN DATAFRAME ---
                    if station_id and all_entries:

                        df = pd.DataFrame(all_entries)

                        # --- WORKSHEET ---
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
                                "Operator ID",
                                "Enrol",
                                "Update",
                                "Total",
                                "Amount"
                            ])

                        # --- EXISTING DATES ---
                        existing_data = worksheet.get_all_values()

                        existing_dates = [
                            r[0]
                            for r in existing_data
                            if len(r) > 0
                        ]

                        # --- UNIQUE DATES ---
                        unique_dates_in_file = sorted(
                            list(set(df["date"].tolist())),
                            key=lambda x: datetime.strptime(
                                x,
                                "%d/%m/%Y"
                            )
                        )

                        newly_added = []

                        # --- DATE LOOP ---
                        for d in unique_dates_in_file:

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

                            amount = int(
                                day_df["amt"].sum()
                            )

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

                        # --- SUCCESS UI ---
                        if newly_added:

                            st.markdown(f"""
                            <div class="success-card">
                            <h3>
                            ✅ SAVED: {len(newly_added)} New Dates
                            </h3>

                            👤 {op_name}
                            |
                            📍 {station_id}

                            <br>

                            📅 {newly_added[0]} to {newly_added[-1]}

                            </div>
                            """, unsafe_allow_html=True)

                            avg_val = round(
                                len(df) / len(unique_dates_in_file),
                                2
                            )

                            st.write(
                                f"### 📊 Report Stats: {avg_val} Avg"
                            )

                            if summary_table_ui is not None:
                                st.table(summary_table_ui)

                            # --- DATE WISE SUMMARY ---
                            st.write("## 📅 Date Wise Summary")

                            daily_summary = (
                                df.groupby("date")
                                .agg(
                                    Enrol=(
                                        "type",
                                        lambda x: (x == "E").sum()
                                    ),
                                    Update=(
                                        "type",
                                        lambda x: (x == "U").sum()
                                    ),
                                    Total=("type", "count"),
                                    Amount=("amt", "sum")
                                )
                                .reset_index()
                            )

                            st.dataframe(
                                daily_summary,
                                use_container_width=True
                            )

                            # --- PERFORMANCE ---
                            if avg_val < 15:

                                st.toast(
                                    f"🚨 Low Average Alert: {avg_val}",
                                    icon="⚠️"
                                )

                                st.markdown(f"""
                                <div class='warning-box'>
                                ⚠️ Warning:
                                Aapka average {avg_val} kam hai!
                                </div>
                                """, unsafe_allow_html=True)

                            else:
                                st.balloons()

                        else:

                            st.warning(
                                f"ℹ️ {station_id}: "
                                f"Data pehle se sheet mein hai."
                            )

                    else:

                        st.error(
                            "⚠️ Station ID ya transaction data nahi mila"
                        )

    except Exception as e:

        st.error(f"🚨 Error: {str(e)}")
