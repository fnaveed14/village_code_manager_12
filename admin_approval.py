import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Village Approvals", layout="wide")

# Load secrets
admin_user = st.secrets["admin"]["username"]
admin_pass = st.secrets["admin"]["password"]

# Authentication
st.title("🔐 Admin Village Approval Panel")
username = st.text_input("Username")
password = st.text_input("Password", type="password")

if username == admin_user and password == admin_pass:
    st.success("✅ Logged in as admin")

    # Load data
    try:
        pending_df = pd.read_excel("pending_villages.xlsx")
    except FileNotFoundError:
        st.warning("No pending_villages.xlsx found.")
        pending_df = pd.DataFrame()

    if pending_df.empty:
        st.info("✅ No villages pending approval.")
    else:
        st.subheader("🕓 Pending Villages")
        selected = st.multiselect("Select Villages to Approve (by index)", pending_df.index.tolist())

        st.dataframe(pending_df)

        if st.button("✅ Approve Selected"):
            if selected:
                approved_rows = pending_df.loc[selected]

                try:
                    master_df = pd.read_excel("data/village_masterlist.xlsx")
                except FileNotFoundError:
                    master_df = pd.DataFrame()

                updated_df = pd.concat([master_df, approved_rows], ignore_index=True)
                updated_df.to_excel("data/village_masterlist.xlsx", index=False)

                pending_df.drop(index=selected, inplace=True)
                pending_df.to_excel("pending_villages.xlsx", index=False)

                st.success(f"✅ Approved and moved {len(selected)} villages to masterlist.")
            else:
                st.warning("⚠️ Please select at least one village.")

        if st.button("🗑️ Reject Selected"):
            if selected:
                pending_df.loc[selected, "remarks"] = f"Rejected on {datetime.today().strftime('%Y-%m-%d')}"
                pending_df.to_excel("pending_villages.xlsx", index=False)
                st.warning(f"❌ Marked {len(selected)} villages as rejected.")
            else:
                st.warning("⚠️ Please select at least one village.")

else:
    if username or password:
        st.error("Invalid credentials.")
