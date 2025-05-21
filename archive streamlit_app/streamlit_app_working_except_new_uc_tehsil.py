
import streamlit as st
import pandas as pd
from datetime import datetime

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


def load_data():
    return load_and_clean_data()

df = load_data()

st.title("📍 Village and Admin Code Manager")

tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Add Village",
    "➕ Add UC / Tehsil / District",
    "🛑 Mark Deletion",
    "📄 View Data"
])

# TAB 1: Add Village
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
    village_names = [v.strip() for v in village_names_input.replace(",", "\n").split("\n") if v.strip()]

    if st.button("Add Villages"):
        if uc_prefix and village_names:
            new_rows = []
            for name in village_names:
                new_code = generate_village_code(df, uc_prefix)
                new_row = add_new_village(df, uc_prefix, name, new_code)
                new_row["remarks"] = f"newly added on {datetime.today().strftime('%Y-%m-%d')}"
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                new_rows.append((name, new_code))

            df.to_excel("data/village_masterlist.xlsx", index=False, sheet_name="Masterlist")
            st.success(f"✅ Added {len(new_rows)} villages.")
            for vname, vcode in new_rows:
                st.write(f"🟢 {vname} → {vcode}")
        else:
            st.error("UC prefix or village names missing.")


# TAB 2: Add Admin Levels
with tab2:
    st.header("➕ Add New UC / Tehsil / District")
    level = st.radio("Select Level", ["UC", "Tehsil", "District"])
    province = st.selectbox("Province (Admin Add)", list(PROVINCES.keys()), key="admin_prov")
    province_code = PROVINCES[province].replace("PK", "")

    if level == "District":
        new_district = st.text_input("New District Name")
        if st.button("Add District") and new_district:
            new_code = generate_other_district_code(df, province_code)
            st.success(f"✅ District '{new_district}' assigned code {new_code}")

    elif level == "Tehsil":
        district = st.selectbox("District", [k for k, v in DISTRICTS.items() if v.startswith(f"PK{province_code}")])
        district_pcode = DISTRICTS[district]
        new_tehsil = st.text_input("New Tehsil Name")
        if st.button("Add Tehsil") and new_tehsil:
            new_code = generate_tehsil_code(df, district_pcode)
            st.success(f"✅ Tehsil '{new_tehsil}' assigned code {new_code}")

    elif level == "UC":
        district = st.selectbox("District", [k for k, v in DISTRICTS.items() if v.startswith(f"PK{province_code}")], key="admin_uc_dist")
        district_pcode = DISTRICTS[district]
        tehsils = df[df["district_pcode"] == district_pcode]["tehsil"].dropna().unique().tolist()
        tehsil = st.selectbox("Tehsil", tehsils, key="admin_uc_tehsil")

        filtered_tehsil = df[(df["district_pcode"] == district_pcode) & (df["tehsil"] == tehsil)]
        new_uc = st.text_input("New UC Name")
        if not filtered_tehsil.empty:
            tehsil_pcode = filtered_tehsil["tehsil_pcode"].iloc[0]
            if st.button("Add UC") and new_uc:
                new_code = generate_uc_code(df, tehsil_pcode)
                st.success(f"✅ UC '{new_uc}' assigned code {new_code}")
        else:
            st.warning("⚠️ Selected tehsil not found in the dataset.")


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

# TAB 4: View Data with Filters
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

    st.dataframe(filtered_df)

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export Filtered Data", data=csv, file_name="filtered_villages.csv", mime="text/csv")
