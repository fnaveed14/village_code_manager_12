import streamlit as st
import pandas as pd
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


from app.data_loader import load_and_clean_data
from app.code_generator import (
    generate_village_code,
    generate_uc_code,
    generate_tehsil_code,
    generate_other_district_code
)
from app.updater import add_new_village, mark_village_for_deletion
from data.admin_codes import PROVINCES, DISTRICTS

st.set_page_config(page_title="Admin Code Manager", layout="wide")

# Format all code columns consistently with leading zeros
def format_code_columns(df: pd.DataFrame) -> pd.DataFrame:
    def safe_format(x, width):
        if pd.notnull(x) and str(x).strip() != "":
            try:
                return str(int(float(x))).zfill(width)
            except:
                return str(x).zfill(width)  # fallback
        return ""

    if "district_code" in df.columns:
        df["district_code"] = df["district_code"].apply(lambda x: safe_format(x, 2))
    if "tehsil_code" in df.columns:
        df["tehsil_code"] = df["tehsil_code"].apply(lambda x: safe_format(x, 2))
    if "uc_id" in df.columns:
        df["uc_id"] = df["uc_id"].apply(lambda x: safe_format(x, 3))
    if "village/settlement_code" in df.columns:
        df["village/settlement_code"] = df["village/settlement_code"].apply(lambda x: safe_format(x, 3))
    return df



def load_data():
    return load_and_clean_data()

df = format_code_columns(load_data())

st.title("📍 Village and Admin Code Manager")

tab1, tab2, tab3, tab4, tab5,tab6 = st.tabs([
    "➕ Add Village",
    "➕ Add UC / Tehsil / District",
    "🛑 Mark Deletion",
    "📄 View Data",
    "📥 Bulk Import",
    "🔐 Approve Pending Villages"
])

def generate_next_uc_id(df, tehsil_pcode: str) -> str:
    uc_ids = (
        df[df["tehsil_pcode"] == tehsil_pcode]["uc_id"]
        .dropna()
        .astype(str)
        .apply(lambda x: x.zfill(3))
    )
    numeric_ids = [int(uid) for uid in uc_ids if uid.isdigit()]
    next_id = max(numeric_ids, default=0) + 1
    return str(next_id).zfill(3)

with tab1:
    st.header("➕ Add New Village(s)")
    province = st.selectbox("Province", list(PROVINCES.keys()))
    province_code = PROVINCES[province].replace("PK", "")

    districts = {k: v for k, v in DISTRICTS.items() if v.startswith(f"PK{province_code}")}
    district = st.selectbox("District", list(districts.keys()))
    district_pcode = districts[district]

    tehsils = df[df["district_pcode"] == district_pcode]["tehsil"].dropna().unique().tolist()
    tehsil = st.selectbox("Tehsil", tehsils)

    ucs = df[(df["district_pcode"] == district_pcode) & (df["tehsil"] == tehsil)]["uc"].dropna().unique().tolist()
    uc = st.selectbox("UC", ucs)

    uc_df = df[(df["tehsil"] == tehsil) & (df["uc"] == uc)]
    uc_prefix = uc_df["uc_prefix"].iloc[0] if not uc_df.empty else None

    village_names_input = st.text_area("Enter Village Name(s) (comma or newline separated)")
    lat_input = st.text_area("Latitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 23 and 37 with 6 decimals.")
    lon_input = st.text_area("Longitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 60 and 77 with 6 decimals.")

    village_names = [v.strip() for v in village_names_input.replace(",", "\n").split("\n") if v.strip()]
    lat_values = [v.strip() for v in lat_input.replace(",", "\n").split("\n") if v.strip()]
    lon_values = [v.strip() for v in lon_input.replace(",", "\n").split("\n") if v.strip()]

    if st.button("Submit for Approval"):
        if not uc_prefix or not village_names:
            st.error("UC prefix or village names missing.")
        elif (lat_values or lon_values) and (len(lat_values) != len(village_names) or len(lon_values) != len(village_names)):
            st.error("Lat/Lon counts must match number of villages.")
        else:
            new_rows = []
            valid = True
            for idx, name in enumerate(village_names):
                lat = lat_values[idx] if idx < len(lat_values) else ""
                lon = lon_values[idx] if idx < len(lon_values) else ""

                if lat and lon:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        if not (23 <= lat_f <= 37) or not (60 <= lon_f <= 77):
                            st.error(f"❌ Invalid coordinates for '{name}'")
                            valid = False
                            break
                        if len(lat.split(".")[-1]) < 6 or len(lon.split(".")[-1]) < 6:
                            st.error(f"❌ Coordinates for '{name}' must have at least 6 digits after decimal.")
                            valid = False
                            break
                    except:
                        st.error(f"❌ Coordinates for '{name}' are not valid float values.")
                        valid = False
                        break

                new_code = generate_village_code(df, uc_prefix)
                new_row = add_new_village(df, uc_prefix, name, new_code)
                new_row["latitude"] = lat
                new_row["longitude"] = lon
                new_row["remarks"] = f"pending approval from tab 1 on {datetime.today().date()}"
                new_rows.append(new_row)

            if valid:
                try:
                    pending_df = pd.read_excel("data/pending_approvals.xlsx")
                except:
                    pending_df = pd.DataFrame()

                pending_df = pd.concat([pending_df, pd.DataFrame(new_rows)], ignore_index=True)
                pending_df = format_code_columns(pending_df)
                pending_df.to_excel("data/pending_approvals.xlsx", index=False)
                st.success("✅ Submitted for approval.")

with tab2:
    st.header("➕ Add New UC / Tehsil / District (with village)")

    level = st.radio("Select Level to Add", ["UC", "Tehsil", "District"])
    province = st.selectbox("Province", list(PROVINCES.keys()), key="admin_prov")
    province_code = PROVINCES[province].replace("PK", "")

    district = None
    tehsil = None
    tehsil_pcode = None
    district_pcode = None

    if level in ["Tehsil", "UC"]:
        district = st.selectbox("District", [k for k, v in DISTRICTS.items() if v.startswith(f"PK{province_code}")], key="admin_district")
        district_pcode = DISTRICTS[district]
        district_code = district_pcode[-2:]

    if level == "UC":
        tehsils = df[df["district_pcode"] == district_pcode]["tehsil"].dropna().unique().tolist()
        tehsil = st.selectbox("Tehsil", tehsils, key="admin_tehsil")
        filtered_tehsil = df[(df["district_pcode"] == district_pcode) & (df["tehsil"] == tehsil)]
        if not filtered_tehsil.empty:
            tehsil_pcode = filtered_tehsil["tehsil_pcode"].iloc[0]
            tehsil_code = tehsil_pcode[-2:]

    new_district = st.text_input("New District Name") if level == "District" else None
    new_tehsil = st.text_input("New Tehsil Name") if level in ["Tehsil", "District"] else None
    new_uc = st.text_input("New UC Name") if level in ["UC", "Tehsil", "District"] else None

    village_input = st.text_area("Village Names (comma or newline separated)")
    lat_input = st.text_area("Latitude(s) (Optional, match order)")
    lon_input = st.text_area("Longitude(s) (Optional, match order)")

    village_list = [v.strip() for v in village_input.replace(",", "\n").split("\n") if v.strip()]
    lat_values = [v.strip() for v in lat_input.replace(",", "\n").split("\n") if v.strip()]
    lon_values = [v.strip() for v in lon_input.replace(",", "\n").split("\n") if v.strip()]

    if st.button("Submit Admin Unit with Villages"):
        if not village_list:
            st.error("You must add at least one village.")
        else:
            new_rows = []
            valid = True

            if level == "District":
                existing_codes = [int(v[-2:]) for v in DISTRICTS.values() if v.startswith(f"PK{province_code}")]
                district_code = str(max(existing_codes, default=0) + 1).zfill(2)
                district_pcode = f"PK{province_code}{district_code}"
                district = new_district

            if level in ["District", "Tehsil"]:
                existing_tehsils = df[df["district_pcode"] == district_pcode]["tehsil_code"].dropna().astype(str)
                next_teh = max([int(t) for t in existing_tehsils if t.isdigit()] + [0]) + 1
                tehsil_code = str(next_teh).zfill(2)
                tehsil_pcode = f"{district_pcode}{tehsil_code}"
                tehsil = new_tehsil

            if level in ["District", "Tehsil", "UC"]:
                uc_ids = df[df["tehsil_pcode"] == tehsil_pcode]["uc_id"].dropna().astype(str).str.zfill(3)
                uc_id = str(max([int(uid) for uid in uc_ids if uid.isdigit()] + [0]) + 1).zfill(3)
                uc_prefix = f"{tehsil_pcode}{uc_id}"

                existing_suffixes = df[df["uc_prefix"] == uc_prefix]["village/settlement_code"].dropna().astype(int).tolist()
                start_suffix = max(existing_suffixes, default=0)

                for i, v in enumerate(village_list):
                    lat = lat_values[i] if i < len(lat_values) else ""
                    lon = lon_values[i] if i < len(lon_values) else ""

                    if lat and lon:
                        try:
                            lat_f = float(lat)
                            lon_f = float(lon)
                            if not (23 <= lat_f <= 37) or not (60 <= lon_f <= 77):
                                st.error(f"Invalid coords for {v}")
                                valid = False
                                break
                            if len(lat.split(".")[-1]) < 6 or len(lon.split(".")[-1]) < 6:
                                st.error(f"{v} coordinates must have at least 6 decimals")
                                valid = False
                                break
                        except:
                            st.error(f"Invalid lat/lon for {v}")
                            valid = False
                            break

                    next_suffix = start_suffix + i + 1
                    village_code = str(next_suffix).zfill(3)
                    village_pcode = f"{uc_prefix}{village_code}"

                    new_row = {
                        "province": province,
                        "province_code": province_code,
                        "province_pcode": f"PK{province_code}",
                        "district": district,
                        "district_code": district_code,
                        "district_pcode": district_pcode,
                        "tehsil": tehsil,
                        "tehsil_code": tehsil_code,
                        "tehsil_pcode": tehsil_pcode,
                        "uc": new_uc,
                        "uc_id": uc_id,
                        "uc/vc/nc_pcode": uc_prefix,
                        "uc_prefix": uc_prefix,
                        "village_name": v,
                        "village/settlement_code": village_code,
                        "village_pcode_new": village_pcode,
                        "latitude": lat,
                        "longitude": lon,
                        "remarks": f"pending approval from tab 2 on {datetime.today().date()}"
                    }
                    new_rows.append(new_row)

            if valid:
                try:
                    pending_df = pd.read_excel("data/pending_approvals.xlsx")
                except:
                    pending_df = pd.DataFrame()

                pending_df = pd.concat([pending_df, pd.DataFrame(new_rows)], ignore_index=True)
                pending_df = format_code_columns(pending_df)
                pending_df.to_excel("data/pending_approvals.xlsx", index=False)
                st.success(f"✅ {len(new_rows)} record(s) submitted for approval.")

# TAB 3: Mark Deletion
with tab3:
    st.header("🛑 Mark Village for Deletion")

    sub_tab = st.radio("Choose Deletion Method", ["By Location", "By Village P-code", "Bulk P-code Upload"])

    if sub_tab == "By Location":
        province = st.selectbox("Province (Delete)", list(PROVINCES.keys()), key="del_prov")
        province_code = PROVINCES[province].replace("PK", "")

        districts = {k: v for k, v in DISTRICTS.items() if v.startswith(f"PK{province_code}")}
        district = st.selectbox("District", list(districts.keys()), key="del_dist")
        district_pcode = districts[district]

        tehsils = df[df["district_pcode"] == district_pcode]["tehsil"].dropna().unique().tolist()
        tehsil = st.selectbox("Tehsil", tehsils, key="del_tehsil")

        ucs = df[(df["district_pcode"] == district_pcode) & (df["tehsil"] == tehsil)]["uc"].dropna().unique().tolist()
        uc = st.selectbox("UC", ucs, key="del_uc")

        uc_df = df[(df["tehsil"] == tehsil) & (df["uc"] == uc)]
        villages = uc_df["village_name"].dropna().unique().tolist()
        village = st.selectbox("Select Village", villages)

        selected_row = uc_df[uc_df["village_name"] == village]
        code_to_mark = selected_row["village_pcode_new"].iloc[0] if not selected_row.empty else None

        justification = st.text_area("Justification for deletion")

        if st.button("Mark as Deleted"):
            if code_to_mark and justification:
                if mark_village_for_deletion(df, code_to_mark):
                    idx = df[df["village_pcode_new"] == code_to_mark].index[0]
                    df.loc[idx, "remarks"] = f"to be deleted: {justification or 'no reason'} on {datetime.today().strftime('%Y-%m-%d')}"
                    df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                    st.success(f"🛑 Village '{village}' marked for deletion.")
                else:
                    st.warning("Village code not found.")
            else:
                st.error("Please select a village and provide justification.")

    elif sub_tab == "By Village P-code":
        pcode = st.text_input("Enter Village P-code", key="pcode_single")
        justification = st.text_area("Justification", key="just_single")

        if st.button("Delete by P-code"):
            if pcode and pcode in df["village_pcode_new"].values:
                idx = df[df["village_pcode_new"] == pcode].index[0]
                df.loc[idx, "remarks"] = f"to be deleted: {justification or 'no reason'} on {datetime.today().strftime('%Y-%m-%d')}"
                df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                st.success(f"✅ Village with code {pcode} marked for deletion.")
            else:
                st.error("P-code not found.")

    elif sub_tab == "Bulk P-code Upload":
        st.markdown("📥 Paste multiple P-codes (comma or newline separated):")
        pcode_bulk = st.text_area("Bulk Village P-codes", key="bulk_codes")
        justification = st.text_area("Justification for bulk deletion", key="bulk_reason")

        if st.button("Apply Bulk Deletion"):
            raw_codes = [x.strip() for x in pcode_bulk.replace(",", "\n").split("\n") if x.strip()]
            valid_codes = [c for c in raw_codes if c in df["village_pcode_new"].values]
            missing = [c for c in raw_codes if c not in df["village_pcode_new"].values]

            if valid_codes:
                df.loc[df["village_pcode_new"].isin(valid_codes), "remarks"] = f"to be deleted: {justification or 'no reason'} on {datetime.today().strftime('%Y-%m-%d')}"
                df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                st.success(f"✅ {len(valid_codes)} villages marked for deletion.")
                if missing:
                    st.warning(f"⚠️ The following codes were not found: {', '.join(missing)}")
            else:
                st.error("No valid village P-codes provided.")
# TAB 4: View Data
with tab4:
    st.header("📄 Filter & View Dataset")
    col1, col2, col3 = st.columns(3)
    with col1:
        enum_filter = st.selectbox("Enumerator", ["All"] + sorted(df["enumerator"].dropna().unique().tolist()), key="f1")
        prov_filter = st.selectbox("Province", ["All"] + sorted(df["province"].dropna().unique().tolist()), key="f2")
        dist_filter = st.selectbox("District", ["All"] + sorted(df["district"].dropna().unique().tolist()), key="f3")
    with col2:
        tehsil_filter = st.selectbox("Tehsil", ["All"] + sorted(df["tehsil"].dropna().unique().tolist()), key="f4")
        uc_filter = st.selectbox("UC", ["All"] + sorted(df["uc"].dropna().unique().tolist()), key="f5")
        remarks_options = ["All"] + sorted(df["remarks"].dropna().unique().tolist())
        remarks_filter = st.selectbox("Remarks", remarks_options, key="f8")

    with col3:
        village_filter = st.text_input("Village Name", key="f6")
        code_filter = st.text_input("Village Code", key="f7")

    filtered_df = df.copy()
    if enum_filter != "All":
        filtered_df = filtered_df[filtered_df["enumerator"] == enum_filter]
    if prov_filter != "All":
        filtered_df = filtered_df[filtered_df["province"] == prov_filter]
    if dist_filter != "All":
        filtered_df = filtered_df[filtered_df["district"] == dist_filter]
    if tehsil_filter != "All":
        filtered_df = filtered_df[filtered_df["tehsil"] == tehsil_filter]
    if uc_filter != "All":
        filtered_df = filtered_df[filtered_df["uc"] == uc_filter]
    if village_filter:
        filtered_df = filtered_df[filtered_df["village_name"].str.contains(village_filter, case=False, na=False)]
    if code_filter:
        filtered_df = filtered_df[filtered_df["village_pcode_new"].str.contains(code_filter, case=False, na=False)]
    if remarks_filter != "All":
        filtered_df = filtered_df[filtered_df["remarks"] == remarks_filter]
    st.dataframe(filtered_df)

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export Filtered Data", data=csv, file_name="filtered_villages.csv", mime="text/csv")

    # Button to export district-wise Excel files with selected columns only
    if st.button("📁 Export District-wise Excel Files"):
        import os

        export_dir = "exports"
        os.makedirs(export_dir, exist_ok=True)

        export_columns = [
            "enumerator", "province", "district", "tehsil", "uc",
            "village_name", "village_pcode_new","latitude", "longitude"
        ]

        grouped = df.groupby(["province", "district"])

        for (province_name, district_name), group in grouped:
            province_folder = os.path.join(export_dir, province_name)
            os.makedirs(province_folder, exist_ok=True)

            filename = f"{district_name}.xlsx".replace("/", "-")
            filepath = os.path.join(province_folder, filename)

            # Only include specified columns (ignore missing)
            columns_to_export = [col for col in export_columns if col in group.columns]
            group[columns_to_export].to_excel(filepath, index=False)

        st.success(f"✅ District-wise Excel files exported to '{export_dir}' folder.")

with tab5:
    st.header("📥 Bulk Import Villages")

    # Downloadable Template
    import io
    template_df = pd.DataFrame(columns=["province", "district", "tehsil", "uc", "village_name", "latitude", "longitude"])
    excel_buf = io.BytesIO()
    template_df.to_excel(excel_buf, index=False, engine='openpyxl')
    excel_buf.seek(0)
    st.download_button(
        "⬇️ Download Template",
        data=excel_buf,
        file_name="bulk_import_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    uploaded_file = st.file_uploader("Upload Filled Template (.xlsx or .csv)", type=["xlsx", "csv"])

    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            import_df = pd.read_csv(uploaded_file)
        else:
            import_df = pd.read_excel(uploaded_file)

        import_df = import_df.fillna("").astype(str)
        st.subheader("📋 Preview Uploaded Data")
        st.dataframe(import_df.head(20), use_container_width=True)

        new_rows = []

        for idx, row in import_df.iterrows():
            prov = row.get("province", "").strip()
            dist = row.get("district", "").strip()
            teh = row.get("tehsil", "").strip()
            uc = row.get("uc", "").strip()
            vill = row.get("village_name", "").strip()
            lat = row.get("latitude", "").strip()
            lon = row.get("longitude", "").strip()

            if not all([prov, dist, teh, uc, vill]):
                st.warning(f"⚠️ Row {idx+2}: Required fields missing.")
                continue

            if prov not in PROVINCES:
                st.warning(f"⚠️ Row {idx+2}: Province '{prov}' not found.")
                continue

            # Latitude/Longitude validation
            if lat and lon:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    if not (23 <= lat_f <= 37) or not (60 <= lon_f <= 77):
                        st.warning(f"⚠️ Row {idx+2}: Latitude or Longitude out of Pakistan bounds.")
                        continue
                    if len(lat.split(".")[-1]) < 6 or len(lon.split(".")[-1]) < 6:
                        st.warning(f"⚠️ Row {idx+2}: Coordinates must have at least 6 decimal digits.")
                        continue
                except:
                    st.warning(f"⚠️ Row {idx+2}: Invalid format for latitude/longitude.")
                    continue
            else:
                lat = lon = ""

            prov_code = PROVINCES[prov].replace("PK", "")
            prov_pcode = f"PK{prov_code}"

            # District
            dist_rows = df[(df["province"] == prov) & (df["district"] == dist)]
            if not dist_rows.empty:
                dist_pcode = dist_rows["district_pcode"].iloc[0]
                dist_code = dist_pcode[-2:]
            else:
                existing_pcodes = [v for v in DISTRICTS.values() if v.startswith(prov_pcode)]
                codes = [int(v[-2:]) for v in existing_pcodes if v[-2:].isdigit()]
                dist_code = str(max(codes, default=0) + 1).zfill(2)
                dist_pcode = f"{prov_pcode}{dist_code}"
                df = pd.concat([df, pd.DataFrame([{
                    "province": prov,
                    "province_code": prov_code,
                    "province_pcode": prov_pcode,
                    "district": dist,
                    "district_code": dist_code,
                    "district_pcode": dist_pcode
                }])], ignore_index=True)

            # Tehsil
            teh_rows = df[(df["district_pcode"] == dist_pcode) & (df["tehsil"] == teh)]
            if not teh_rows.empty:
                teh_pcode = teh_rows["tehsil_pcode"].iloc[0]
                teh_code = teh_pcode[-2:]
            else:
                existing_tehsils = df[df["district_pcode"] == dist_pcode]["tehsil_code"].dropna().astype(str)
                next_teh = max([int(t) for t in existing_tehsils if t.isdigit()] + [0]) + 1
                teh_code = str(next_teh).zfill(2)
                teh_pcode = f"{dist_pcode}{teh_code}"

            # UC
            uc_rows = df[(df["tehsil_pcode"] == teh_pcode) & (df["uc"] == uc)]
            if not uc_rows.empty:
                uc_id = uc_rows["uc_id"].iloc[0]
                uc_prefix = uc_rows["uc_prefix"].iloc[0]
            else:
                uc_ids = df[df["tehsil_pcode"] == teh_pcode]["uc_id"].dropna().astype(str).str.zfill(3)
                uc_id = str(max([int(uid) for uid in uc_ids if uid.isdigit()] + [0]) + 1).zfill(3)
                uc_prefix = f"{teh_pcode}{uc_id}"

            # Village Code
            suffixes = df[df["uc_prefix"] == uc_prefix]["village/settlement_code"].dropna().astype(int).tolist()
            next_suffix = max(suffixes, default=0) + 1
            village_code = str(next_suffix).zfill(3)
            village_pcode = f"{uc_prefix}{village_code}"

            new_row = {
                "province": prov,
                "province_code": prov_code,
                "province_pcode": prov_pcode,
                "district": dist,
                "district_code": dist_code,
                "district_pcode": dist_pcode,
                "tehsil": teh,
                "tehsil_code": teh_code,
                "tehsil_pcode": teh_pcode,
                "uc": uc,
                "uc_id": uc_id,
                "uc/vc/nc_pcode": uc_prefix,
                "uc_prefix": uc_prefix,
                "village_name": vill,
                "village/settlement_code": village_code,
                "village_pcode_new": village_pcode,
                "latitude": lat,
                "longitude": lon,
                "remarks": f"bulk imported pending approval from tab 5 on {datetime.today().date()}"
            }

            new_rows.append(new_row)

        if new_rows:
            try:
                pending_df = pd.read_excel("data/pending_approvals.xlsx")
            except:
                pending_df = pd.DataFrame()

            pending_df = pd.concat([pending_df, pd.DataFrame(new_rows)], ignore_index=True)
            pending_df = format_code_columns(pending_df)
            pending_df.to_excel("data/pending_approvals.xlsx", index=False)
            st.success(f"✅ {len(new_rows)} villages submitted for approval.")
        else:
            st.info("ℹ️ No valid rows to submit.")
# TAB 6: Admin Approval Panel
with tab6:
    if not st.session_state.get("logged_in", False):
        st.markdown("🔐 **Admin Login**")
        username = st.text_input("Username", type="default")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")

        admin_user = st.secrets["admin"]["username"]
        admin_pass = st.secrets["admin"]["password"]

        if login_button:
            if username == admin_user and password == admin_pass:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")
    else:
        st.title("✅ Admin Approval Panel")

        try:
            pending_df = pd.read_excel("data/pending_approvals.xlsx")
        except FileNotFoundError:
            pending_df = pd.DataFrame()

        if pending_df.empty:
            st.info("✅ No villages pending approval.")
        else:
            st.subheader("📋 Villages Awaiting Approval")

            display_columns = [
                "province", "district", "tehsil", "uc",
                "village_name", "village_pcode_new", "latitude", "longitude"
            ]
            display_df = pending_df[display_columns].copy()

            gb = GridOptionsBuilder.from_dataframe(display_df)
            gb.configure_selection(selection_mode="multiple", use_checkbox=True)
            gb.configure_pagination(paginationAutoPageSize=True)
            grid_options = gb.build()

            # Add select all checkbox
            select_all = st.checkbox("☑️ Select All Rows", key="admin_select_all")

            grid_response = AgGrid(
                display_df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                enable_enterprise_modules=False,
                height=450
            )

            selected_rows_df = pd.DataFrame(grid_response["selected_rows"])

            # Select all logic
            if select_all:
                selected_rows_df = display_df.copy()

            if not selected_rows_df.empty:
                action = st.radio("Select Action", ["Approve", "Reject"], key="approval_action")

                if st.button("✅ Apply Action"):
                    # Match selected rows back to pending_df by village code
                    selected_codes = selected_rows_df["village_pcode_new"].tolist()
                    selected_full_rows = pending_df[pending_df["village_pcode_new"].isin(selected_codes)]

                    pending_df = pending_df[~pending_df["village_pcode_new"].isin(selected_codes)].reset_index(drop=True)

                    if action == "Approve":
                        selected_full_rows["remarks"] = f"approved on {datetime.today().strftime('%Y-%m-%d')}"
                        try:
                            master_df = pd.read_excel("data/village_masterlist.xlsx", sheet_name="Masterlist")
                        except:
                            master_df = pd.DataFrame()

                        updated_master = pd.concat([master_df, selected_full_rows], ignore_index=True)
                        updated_master = format_code_columns(updated_master)
                        updated_master.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                        st.success(f"✅ Approved {len(selected_full_rows)} villages.")

                    elif action == "Reject":
                        selected_full_rows["rejected_on"] = str(datetime.today().date())
                        try:
                            rejected_df = pd.read_excel("data/rejected_villages.xlsx")
                        except:
                            rejected_df = pd.DataFrame()

                        updated_rejected = pd.concat([rejected_df, selected_full_rows], ignore_index=True)
                        updated_rejected.to_excel("data/rejected_villages.xlsx", index=False)
                        st.warning(f"❌ Rejected {len(selected_full_rows)} villages.")

                    pending_df.to_excel("data/pending_approvals.xlsx", index=False)
                    st.rerun()
            else:
                st.info("ℹ️ Select rows using checkboxes or enable 'Select All Rows'.")
