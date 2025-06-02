import streamlit as st
import pandas as pd
from datetime import datetime
import pydeck as pdk
import pydeck as pdk
import geopandas as gpd
import os
from io import BytesIO



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
df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
st.title("📍 Village and Admin Code Manager")

tab1, tab2, tab3, tab4, tab5,tab6, tab7 = st.tabs([
    "➕ Add Village",
    "➕ Add UC / Tehsil / District",
    "🛑 Mark Deletion",
    "📄 View Data",
    "📥 Bulk Import",
    "🗺️ View on a Map",
    "📂 KML Upload & Merge"
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

# TAB 1: Add Village
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

    village_names_input = st.text_area("Enter Village Name(s) (For multiple villages use comma or newline separated)")
    lat_input = st.text_area("Latitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 23 and 37 with 6 decimals.")
    lon_input = st.text_area("Longitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 60 and 77 with 6 decimals.")

    village_names = [v.strip() for v in village_names_input.replace(",", "\n").split("\n") if v.strip()]
    lat_values = [v.strip() for v in lat_input.replace(",", "\n").split("\n") if v.strip()]
    lon_values = [v.strip() for v in lon_input.replace(",", "\n").split("\n") if v.strip()]

    if st.button("Add Villages"):
        if not uc_prefix or not village_names:
            st.error("UC prefix or village names missing.")
        elif (lat_values or lon_values) and (len(lat_values) != len(village_names) or len(lon_values) != len(village_names)):
            st.error("Number of latitudes/longitudes must match the number of villages.")
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
                            st.error(f"❌ Invalid coordinates for '{name}': Latitude must be 23-37 and Longitude 60-77")
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
                else:
                    lat = lon = None

                new_code = generate_village_code(df, uc_prefix)
                new_row = add_new_village(df, uc_prefix, name, new_code)
                new_row["latitude"] = lat
                new_row["longitude"] = lon
                new_row["remarks"] = f"newly added on {datetime.today().strftime('%Y-%m-%d')}"
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                new_rows.append((name, new_code))

            if valid:
                df = format_code_columns(df)
                df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                st.success(f"✅ Added {len(new_rows)} villages.")
                for vname, vcode in new_rows:
                    st.write(f"🟢 {vname} → {vcode}")

# TAB 2: Add Admin Levels
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

    st.markdown("📥 Enter at least one village name to register:")
    village_input = st.text_area("Village Names (comma or newline separated)")

    lat_input = st.text_area("Latitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 23 and 37 with at least 6 decimals.")
    lon_input = st.text_area("Longitude(s) (Optional, match village order)", help="Comma or newline-separated. Must be between 60 and 77 with at least 6 decimals.")

    village_list = [v.strip() for v in village_input.replace(",", "\n").split("\n") if v.strip()]
    lat_values = [v.strip() for v in lat_input.replace(",", "\n").split("\n") if v.strip()]
    lon_values = [v.strip() for v in lon_input.replace(",", "\n").split("\n") if v.strip()]

    if st.button("➕ Add Admin Unit with Village(s)"):
        if not village_list:
            st.error("⚠️ You must add at least one village.")
        else:
            new_rows = []
            valid = True

            if level == "District":
                existing_districts = [v for v in DISTRICTS.values() if v.startswith(f"PK{province_code}")]
                existing_codes = [int(v[-2:]) for v in existing_districts if v[-2:].isdigit()]
                next_code = max(existing_codes, default=0) + 1
                district_code = str(next_code).zfill(2)
                district_pcode = f"PK{province_code}{district_code}"
                district = new_district
                st.success(f"✅ District '{district}' assigned code {district_pcode}")

            if level in ["District", "Tehsil"]:
                existing_tehsils = df[df["district_pcode"] == district_pcode]["tehsil_code"].dropna().astype(str).tolist()
                numeric_tehsils = [int(t) for t in existing_tehsils if t.isdigit()]
                next_tehsil = max(numeric_tehsils, default=0) + 1
                tehsil_code = str(next_tehsil).zfill(2)
                tehsil_pcode = f"{district_pcode}{tehsil_code}"
                tehsil = new_tehsil
                st.success(f"✅ Tehsil '{tehsil}' assigned code {tehsil_pcode}")

            if level in ["District", "Tehsil", "UC"]:
                uc_id = generate_next_uc_id(df, tehsil_pcode)
                uc_prefix = f"{tehsil_pcode}{uc_id}"
                st.info(f"🔢 UC Prefix assigned: {uc_prefix}")

                existing_suffixes = df[df["uc_prefix"] == uc_prefix]["village/settlement_code"].dropna().astype(int).tolist()
                start_suffix = max(existing_suffixes, default=0)

                for i, v in enumerate(village_list):
                    next_suffix = start_suffix + i + 1
                    village_settlement_code = str(next_suffix).zfill(3)
                    village_pcode = f"{uc_prefix}{village_settlement_code}"

                    # Latitude and Longitude validation
                    lat = lat_values[i] if i < len(lat_values) else ""
                    lon = lon_values[i] if i < len(lon_values) else ""

                    if lat and lon:
                        try:
                            lat_f = float(lat)
                            lon_f = float(lon)
                            if not (23 <= lat_f <= 37) or not (60 <= lon_f <= 77):
                                st.error(f"❌ Invalid coordinates for '{v}': Latitude must be 23-37 and Longitude 60-77")
                                valid = False
                                break
                            if len(lat.split(".")[-1]) < 6 or len(lon.split(".")[-1]) < 6:
                                st.error(f"❌ Coordinates for '{v}' must have at least 6 digits after decimal.")
                                valid = False
                                break
                        except:
                            st.error(f"❌ Coordinates for '{v}' are not valid float values.")
                            valid = False
                            break
                    else:
                        lat = lon = None

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
                        "village/settlement_code": village_settlement_code,
                        "village_pcode_new": village_pcode,
                        "latitude": lat,
                        "longitude": lon,
                        "remarks": f"newly added with {level.lower()} on {datetime.today().strftime('%Y-%m-%d')}"
                    }

                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    new_rows.append((v, village_pcode))

                if valid:
                    df = format_code_columns(df)
                    df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
                    st.success(f"✅ {level} and {len(new_rows)} village(s) saved.")
                    for vname, vcode in new_rows:
                        st.write(f"🟢 {vname} → {vcode}")

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

   # TAB 5: Bulk Import
with tab5:
    st.header("📦 Bulk Import Villages")

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
            lat = row.get("latitude", None).strip()
            lon = row.get("longitude", None).strip()

            if not all([prov, dist, teh, uc, vill]):
                continue

            if prov not in PROVINCES:
                st.warning(f"⚠️ Province '{prov}' not found (Row {idx+2})")
                continue

            # Validate lat/lon if present
            if lat and lon:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    if not (23 <= lat_f <= 37) or not (60 <= lon_f <= 77):
                        st.warning(f"⚠️ Invalid coordinates for '{vill}' in row {idx+2}")
                        continue
                    if len(lat.split(".")[-1]) < 6 or len(lon.split(".")[-1]) < 6:
                        st.warning(f"⚠️ Coordinates in row {idx+2} must have at least 6 decimal places.")
                        continue
                except:
                    st.warning(f"⚠️ Invalid lat/lon format in row {idx+2}")
                    continue
            else:
                lat = lon = None

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
                next_code = max(codes, default=0) + 1
                dist_code = str(next_code).zfill(2)
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
                next_uc = max([int(uid) for uid in uc_ids if uid.isdigit()] + [0]) + 1
                uc_id = str(next_uc).zfill(3)
                uc_prefix = f"{teh_pcode}{uc_id}"

            # Village
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
                "remarks": f"bulk imported on {datetime.today().strftime('%Y-%m-%d')}"
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            new_rows.append((vill, village_pcode))

        if new_rows:
            df = format_code_columns(df)
            df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
            st.success(f"✅ Imported {len(new_rows)} villages.")
            for name, pcode in new_rows:
                st.write(f"🟢 {name} → {pcode}")
        else:
            st.info("ℹ️ No valid villages were imported.")

import pydeck as pdk
import pandas as pd
import geopandas as gpd
import json
import re
#tab 6 code
import pandas as pd
from io import BytesIO
import streamlit as st
import pydeck as pdk
import geopandas as gpd
import json
import re

# Assuming df is already loaded earlier in your main Streamlit app.
# Begin Tab 6 logic
with tab6:
    st.header("🗺️ Villages Map Viewer")
    pdk.settings.mapbox_api_key = st.secrets["mapbox"]["token"]

    # Clean coordinates
    def clean_coordinate_strict(val):
        try:
            val = str(val).strip()
            val = re.sub(r"[^\d\.\-]+", "", val)
            return float(val)
        except:
            return None

    df["latitude"] = df["latitude"].apply(clean_coordinate_strict)
    df["longitude"] = df["longitude"].apply(clean_coordinate_strict)

    geo_df = df.dropna(subset=["latitude", "longitude"])
    geo_df = geo_df[
        (geo_df["latitude"].between(23, 37)) &
        (geo_df["longitude"].between(60, 77))
    ]

    # Session state for filters
    if "tab6_province" not in st.session_state:
        st.session_state["tab6_province"] = "All"
    if "tab6_district" not in st.session_state:
        st.session_state["tab6_district"] = "All"

    # UI Filters
    col1, col2, col3 = st.columns([3, 3, 2])
    with col1:
        prov_list = ["All"] + sorted(geo_df["province"].dropna().unique())
        selected_prov = st.selectbox("Select Province", prov_list,
                                     index=prov_list.index(st.session_state["tab6_province"]))
    with col2:
        if selected_prov != "All":
            dist_list = ["All"] + sorted(geo_df[geo_df["province"] == selected_prov]["district"].dropna().unique())
        else:
            dist_list = ["All"] + sorted(geo_df["district"].dropna().unique())
        selected_dist = st.selectbox("Select District", dist_list,
                                     index=dist_list.index(st.session_state["tab6_district"]))
    with col3:
        show_village_labels = st.checkbox("📝 Show Village Names", value=False)
        show_district_labels = st.checkbox("🏷️ Show District Names", value=False)

    # Reset button
    if st.button("🔄 Reset Filters"):
        st.session_state["tab6_province"] = "All"
        st.session_state["tab6_district"] = "All"
        selected_prov = "All"
        selected_dist = "All"

    st.session_state["tab6_province"] = selected_prov
    st.session_state["tab6_district"] = selected_dist

    # Apply filters
    filtered_df = geo_df.copy()
    if selected_prov != "All":
        filtered_df = filtered_df[filtered_df["province"] == selected_prov]
    if selected_dist != "All":
        filtered_df = filtered_df[filtered_df["district"] == selected_dist]

    # Legend & Count
    colA, colB = st.columns([1.5, 5])
    with colA:
        st.markdown(f"✅ **Villages with Coordinates:** `{geo_df.shape[0]}`")
        st.markdown(f"📍 **After Filter:** `{filtered_df.shape[0]}`")
    with colB:
        st.markdown("### 🧭 Legend")
        st.markdown("""
        - 🔴 Red Dots: Villages  
        - <span style='color:blue;'>───</span> Province Boundaries  
        - <span style='color:green;'>───</span> District Boundaries  
        """, unsafe_allow_html=True)

    # Set view state dynamically
    if not filtered_df.empty:
        center_lat = filtered_df["latitude"].mean()
        center_lon = filtered_df["longitude"].mean()
        zoom = 7 if selected_dist != "All" else 5.5 if selected_prov != "All" else 5
    else:
        center_lat, center_lon, zoom = 30.3753, 69.3451, 5

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=0
    )

    # Map style
    style_options = {
        "Light": "mapbox://styles/mapbox/light-v9",
        "Dark": "mapbox://styles/mapbox/dark-v9",
        "Satellite": "mapbox://styles/mapbox/satellite-v9",
        "Streets": "mapbox://styles/mapbox/streets-v11",
        "Outdoors": "mapbox://styles/mapbox/outdoors-v11"
    }
    selected_style = st.selectbox("🗺️ Select Map Style", list(style_options.keys()))
    map_style = style_options[selected_style]

    # Map layers
    layers = []

    # Red Dots Layer for Villages
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=filtered_df,
            get_position='[longitude, latitude]',
            get_fill_color=[255, 0, 0],
            pickable=True,
            radius_scale=10,
            radius_min_pixels=4,
            radius_max_pixels=12,
            get_radius=100
        )
    )

    if show_village_labels:
        layers.append(
            pdk.Layer(
                "TextLayer",
                data=filtered_df,
                get_position='[longitude, latitude]',
                get_text="village_name",
                get_size=14,
                get_color=[0, 0, 0],
                get_alignment_baseline="'bottom'"
            )
        )

    # Province boundaries
    try:
        with open("data/geoBoundaries-PAK-province.geojson", "r", encoding="utf-8") as f:
            province_geojson = json.load(f)
        province_gdf = gpd.GeoDataFrame.from_features(province_geojson["features"])
        province_gdf["geometry"] = province_gdf["geometry"].buffer(0)

        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=province_gdf.__geo_interface__,
                stroked=True,
                filled=False,
                get_line_color=[0, 128, 255],
                get_line_width=30,
                line_width_min_pixels=1.5
            )
        )
    except Exception as e:
        st.warning(f"⚠️ Province boundary error: {e}")

    # District boundaries
    try:
        with open("data/geoBoundaries-PAK-ADM2 (1)district.geojson", "r", encoding="utf-8") as f:
            district_geojson = json.load(f)

        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=district_geojson,
                stroked=True,
                filled=False,
                get_line_color=[0, 255, 0],
                get_line_width=2,
                line_width_min_pixels=1
            )
        )

        if show_district_labels:
            district_gdf = gpd.GeoDataFrame.from_features(district_geojson["features"])
            district_gdf["lon"] = district_gdf.geometry.centroid.x
            district_gdf["lat"] = district_gdf.geometry.centroid.y
            district_gdf["name"] = district_gdf["shapeName"] if "shapeName" in district_gdf.columns else district_gdf.iloc[:, 0]

            layers.append(
                pdk.Layer(
                    "TextLayer",
                    data=district_gdf,
                    get_position='[lon, lat]',
                    get_text="name",
                    get_size=12,
                    get_color=[0, 100, 0],
                    get_alignment_baseline="'top'"
                )
            )
    except Exception as e:
        st.warning(f"⚠️ District boundary error: {e}")

    # Render map
    st.pydeck_chart(pdk.Deck(
        map_style=map_style,
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "Village: {village_name}\nDistrict: {district}"}
    ), use_container_width=True, height=750)

    # --- DUPLICATE COORDINATES CHECK ---
    st.subheader("📌 Duplicate Village Points")
    duplicate_points = geo_df[geo_df.duplicated(subset=["latitude", "longitude"], keep=False)]
    duplicate_count = duplicate_points.groupby(["latitude", "longitude"]).ngroups

    st.markdown(f"**🔁 Duplicate Locations Found:** `{duplicate_count}`")
    if duplicate_count > 0:
        st.dataframe(duplicate_points.reset_index(drop=True))

        output = BytesIO()
        duplicate_points.to_excel(output, index=False, engine="xlsxwriter")
        st.download_button(
            label="📥 Download Duplicates as Excel",
            data=output.getvalue(),
            file_name="duplicate_village_coordinates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No exact duplicate coordinates found.")


#TAB 7 CODE HERE
with tab7:
    import io
    import re
    import os
    import zipfile
    import tempfile
    from xml.dom import minidom

    st.header("📂 KML Upload & Merge")
    uploaded_kmls = st.file_uploader("Upload KML files", type=["kml"], accept_multiple_files=True)

    def extract_text_from_description(desc_html):
        """Extract Province, District, Tehsil, UC names from HTML description."""
        fields = {"Province": "", "District": "", "Tehsil": "", "UC": ""}
        rows = re.findall(r'<td[^>]*>(.*?)</td>', desc_html)
        for i in range(len(rows) - 1):
            label = rows[i].strip().lower()
            value = rows[i + 1].strip()
            if value.isdigit():  # Skip numeric codes
                continue
            if "province" in label:
                fields["Province"] = value
            elif "district" in label:
                fields["District"] = value
            elif "tehsil" in label:
                fields["Tehsil"] = value
            elif "uc" in label or "union council" in label:
                fields["UC"] = value
        return fields

    def parse_kml_file(file):
        village_data = []
        boundary_data = []
        try:
            xmldoc = minidom.parse(file)
            placemarks = xmldoc.getElementsByTagName("Placemark")
            fallback_admin = None

            for placemark in placemarks:
                name_node = placemark.getElementsByTagName("name")
                coords_node = placemark.getElementsByTagName("coordinates")
                desc_node = placemark.getElementsByTagName("description")

                if not name_node or not coords_node or not coords_node[0].firstChild:
                    continue

                name = name_node[0].firstChild.nodeValue.strip()
                coords_text = coords_node[0].firstChild.nodeValue.strip()
                coords_split = coords_text.split()

                if desc_node and desc_node[0].firstChild:
                    desc_html = desc_node[0].firstChild.nodeValue
                    admin_fields = extract_text_from_description(desc_html)
                    if not fallback_admin and all(admin_fields.values()):
                        fallback_admin = admin_fields
                else:
                    admin_fields = fallback_admin or {"Province": "", "District": "", "Tehsil": "", "UC": ""}

                if len(coords_split) == 1:
                    lon, lat, *_ = coords_split[0].split(',')
                    village_data.append({
                        "File": file.name,
                        "Country": "Pakistan",
                        "Province": admin_fields.get("Province", ""),
                        "District": admin_fields.get("District", ""),
                        "Tehsil": admin_fields.get("Tehsil", ""),
                        "UC": admin_fields.get("UC", ""),
                        "Village Name": name,
                        "Latitude": float(lat),
                        "Longitude": float(lon)
                    })
                else:
                    boundary_data.append({
                        "Name": name,
                        "Description": desc_node[0].firstChild.nodeValue if desc_node and desc_node[0].firstChild else "",
                        "Coordinates": coords_split
                    })

        except Exception as e:
            st.error(f"Failed to parse {file.name}: {e}")
        return village_data, boundary_data

    def write_combined_kml(villages, boundaries):
        kml_buffer = io.StringIO()
        kml_buffer.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        kml_buffer.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        kml_buffer.write('  <Document>\n')
        kml_buffer.write('    <name>All UCs and Villages</name>\n')

        for b in boundaries:
            kml_buffer.write('    <Placemark>\n')
            kml_buffer.write(f'      <name>{b["Name"]}</name>\n')
            kml_buffer.write('      <Polygon>\n')
            kml_buffer.write('        <outerBoundaryIs><LinearRing><coordinates>\n')
            for coord in b["Coordinates"]:
                kml_buffer.write(f'          {coord}\n')
            kml_buffer.write('        </coordinates></LinearRing></outerBoundaryIs>\n')
            kml_buffer.write('      </Polygon>\n')
            kml_buffer.write('    </Placemark>\n')

        for v in villages:
            kml_buffer.write('    <Placemark>\n')
            kml_buffer.write(f'      <name>{v["Village Name"]}</name>\n')
            kml_buffer.write('      <description><![CDATA[\n')
            kml_buffer.write(f'Province: {v["Province"]}<br>\nDistrict: {v["District"]}<br>Tehsil: {v["Tehsil"]}<br>UC: {v["UC"]}<br>File: {v["File"]}\n')
            kml_buffer.write('      ]]></description>\n')
            kml_buffer.write('      <Point>\n')
            kml_buffer.write(f'        <coordinates>{v["Longitude"]},{v["Latitude"]},0</coordinates>\n')
            kml_buffer.write('      </Point>\n')
            kml_buffer.write('    </Placemark>\n')

        kml_buffer.write('  </Document>\n')
        kml_buffer.write('</kml>\n')
        return kml_buffer.getvalue()

    if uploaded_kmls and st.button("📥 Process Files"):
        all_villages = []
        all_boundaries = []
        csv_outputs = {}

        for file in uploaded_kmls:
            villages, boundaries = parse_kml_file(file)
            if villages:
                import pandas as pd
                df_v = pd.DataFrame(villages)
                csv_outputs[file.name.replace(".kml", "_villages.csv")] = df_v.to_csv(index=False).encode("utf-8")
                all_villages.extend(villages)
            all_boundaries.extend(boundaries)

        if all_villages:
            import pandas as pd
            st.success(f"Processed {len(uploaded_kmls)} KML files.")

            st.subheader("⬇️ Download Outputs")

            # Merged CSV
            merged_csv_bytes = pd.DataFrame(all_villages).to_csv(index=False).encode("utf-8")
            st.download_button("Download Merged CSV", merged_csv_bytes, "all_villages_merged.csv", mime="text/csv")

            # Merged KML
            combined_kml_text = write_combined_kml(all_villages, all_boundaries)
            st.download_button("Download Combined KML", combined_kml_text, "all_villages_and_boundaries.kml", mime="application/vnd.google-earth.kml+xml")

            # Individual CSVs
            st.markdown("### Individual File Exports:")
            for filename, data in csv_outputs.items():
                st.download_button(f"{filename}", data, file_name=filename, mime="text/csv")

            # ZIP Download
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "all_outputs.zip")
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    # Merged CSV
                    merged_csv_path = os.path.join(tmpdir, "all_villages_merged.csv")
                    with open(merged_csv_path, "wb") as f:
                        f.write(merged_csv_bytes)
                    zipf.write(merged_csv_path, "all_villages_merged.csv")

                    # Merged KML
                    merged_kml_path = os.path.join(tmpdir, "all_villages_and_boundaries.kml")
                    with open(merged_kml_path, "w", encoding="utf-8") as f:
                        f.write(combined_kml_text)
                    zipf.write(merged_kml_path, "all_villages_and_boundaries.kml")

                    # Individual CSVs
                    for filename, data in csv_outputs.items():
                        file_path = os.path.join(tmpdir, filename)
                        with open(file_path, "wb") as f:
                            f.write(data)
                        zipf.write(file_path, filename)

                with open(zip_path, "rb") as zip_file:
                    st.download_button(
                        label="📦 Download All as ZIP",
                        data=zip_file.read(),
                        file_name="all_kml_outputs.zip",
                        mime="application/zip"
                    )
