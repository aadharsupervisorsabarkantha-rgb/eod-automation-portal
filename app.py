if station_id:
                    try: 
                        worksheet = spreadsheet.worksheet(str(station_id))
                        existing_data = worksheet.get_all_values()
                        
                        if any(file_date == row[0] for row in existing_data):
                            st.error(f"⚠️ Duplicate Entry: {file_date} pehle se record mein hai!")
                        else:
                            # 1. Background Calculations (Sheet mein nahi jayega)
                            days_worked = len(date_summary_table) if date_summary_table is not None else 1
                            avg_val = round(total_ent / days_worked, 2)
                            
                            month_num = str(datetime.strptime(selected_month, '%B').month).zfill(2)
                            sort_key = f"{selected_year}{month_num}{ui_date_range[:2]}"
                            
                            # 2. Append ONLY required data (Column A se H tak)
                            # Humne Avg aur SortKey ko list se hata diya hai
                            worksheet.append_row([
                                file_date, station_id, op_name, operator_id, 
                                int(enrol), int(update), int(total_ent), int(total_sum)
                            ])
                            
                            # Note: Agar aapko sorting chahiye toh Sheet mein date column hona zaroori hai.
                            # Hum Column A (Date Range) ke basis par sort kar sakte hain:
                            worksheet.sort((1, 'asc'))
                            
                            # 3. SUCCESS CARD (Yahan sab kuch dikhega)
                            st.markdown(f"""
                            <div class="success-card">
                                <b style="font-size:20px;">✅ SUCCESS: Data Saved!</b><br><br>
                                👤 <b>Operator:</b> {op_name} | 📍 <b>Station:</b> {station_id}<br>
                                🗓️ <b>Range:</b> {ui_date_range} {selected_month} {selected_year}<br>
                                📊 <b>Total Enrolment:</b> {int(total_ent)} | 📈 <b>Daily Average:</b> {avg_val}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Average Warning
                            if avg_val < 15:
                                st.markdown(f"""
                                <div class="warning-card">
                                    ⚠️ Aapki average kam hai ({avg_val}). Kripya entry jyada karein!
                                </div>
                                """, unsafe_allow_html=True)

                            # Table Display
                            if date_summary_table is not None:
                                st.subheader("📊 Date-wise Performance Table")
                                st.table(date_summary_table[['date', 'no. of enrolments', 'no. of updates', 'total']])

                    except gspread.exceptions.WorksheetNotFound:
                        # New Sheet Header (Sirf Amount tak)
                        worksheet = spreadsheet.add_worksheet(title=str(station_id), rows="1000", cols="8")
                        worksheet.append_row(["Date Range", "Station ID", "Operator", "ID", "Enrol", "Update", "Total", "Amount"])
                        st.info(f"New Station Sheet `{station_id}` created. Please re-upload.")
