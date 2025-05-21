import pandas as pd

# Load your current Excel file
file_path = "data/village_masterlist.xlsx"
df = pd.read_excel(file_path)

# Fix formatting for specific columns
code_columns = {
    "district_code": 2,
    "tehsil_code": 2,
    "uc_id": 3,
    "village/settlement_code": 3,
}

for col, width in code_columns.items():
    if col in df.columns:
        df[col] = df[col].apply(lambda x: str(int(float(x))).zfill(width) if pd.notnull(x) else "")



# Save back with corrected formatting
df.to_excel(file_path, index=False, sheet_name="Masterlist")
print("✅ Excel formatting restored for code columns.")
