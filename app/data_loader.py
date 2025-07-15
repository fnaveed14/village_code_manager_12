import pandas as pd
import re

def clean_coordinate_strict(val):
    """
    Clean coordinates that may contain Excel formatting, stray characters, or non-numeric input.
    """
    try:
        val = str(val).strip()
        val = re.sub(r"[^\d\.\-]+", "", val)  # Keep digits, dot, dash only
        return float(val)
    except:
        return None

def load_and_clean_data(file_path="data/village_masterlist.xlsx"):
    """
    Loads the masterlist, normalizes columns, and strictly cleans coordinate values.
    Ensures latitude/longitude are numeric and compatible with pyarrow serialization.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Excel file not found at: {file_path}")
    # Step 1: Load with all strings to avoid Excel typing issues
    df = pd.read_excel(file_path, sheet_name="Masterlist", dtype=str)

    # Step 2: Normalize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # Step 3: Rename columns with special characters
    df.rename(columns={
        'village/settlement_pcode_(new)': 'village_pcode_new',
        'village/settlement_pcode_(old)': 'village_pcode_old',
        'names_of_villages_/wards_under_this_uc/vc/nc:': 'village_name'
    }, inplace=True)

    # Step 4: Strip whitespace from all string columns
    text_columns = df.select_dtypes(include='object').columns
    df[text_columns] = df[text_columns].apply(lambda col: col.str.strip())

    # Step 5: Generate uc_prefix
    if "uc/vc/nc_pcode" in df.columns:
        df["uc_prefix"] = df["uc/vc/nc_pcode"].astype(str).str.strip()

    # Step 6: Strictly clean and convert lat/lon to float
    df["latitude"] = df["latitude"].apply(clean_coordinate_strict)
    df["longitude"] = df["longitude"].apply(clean_coordinate_strict)

    # Step 7: Ensure final dtypes are float for compatibility
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    return df
