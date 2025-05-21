# app/code_generator.py

def generate_village_code(df, uc_prefix: str) -> str:
    """
    Generate the next full P-code for a village under the given UC prefix.
    Uses 'village/settlement_code' for numeric suffix increment.
    """
    suffix_col = 'village/settlement_code'

    if suffix_col not in df.columns:
        raise KeyError(f"'{suffix_col}' column not found in DataFrame.")

    matching = df[df['uc_prefix'] == uc_prefix][suffix_col].dropna()

    # Parse valid integer suffixes
    numeric_suffixes = [int(str(x).strip()) for x in matching if str(x).strip().isdigit()]
    next_number = max(numeric_suffixes, default=0) + 1
    suffix = str(next_number).zfill(3)

    return f"{uc_prefix}{suffix}"
# app/code_generator.py (add below existing code)

def generate_tehsil_code(df, district_pcode: str) -> str:
    """
    Generates the next tehsil P-code under a district.
    """
    matching = df[df['district_pcode'] == district_pcode]['tehsil_code'].dropna()
    numeric = [int(str(x).strip()) for x in matching if str(x).strip().isdigit()]
    next_code = str(max(numeric, default=0) + 1).zfill(2)
    return f"{district_pcode}{next_code}"


def generate_uc_code(df, tehsil_pcode: str) -> str:
    """
    Generates the next UC P-code under a tehsil.
    """
    matching = df[df['tehsil_pcode'] == tehsil_pcode]['uc_id'].dropna()
    numeric = [int(str(x).strip()) for x in matching if str(x).strip().isdigit()]
    next_code = str(max(numeric, default=0) + 1).zfill(3)
    return f"{tehsil_pcode}{next_code}"


def generate_other_district_code(df, province_code: str) -> str:
    """
    For 'Other' districts, generate next available district code within the province.
    """
    matching = df[df['province_code'] == province_code]['district_code'].dropna()
    numeric = [int(str(x).strip()) for x in matching if str(x).strip().isdigit()]
    next_code = str(max(numeric, default=0) + 1).zfill(2)
    return f"PK{province_code}{next_code}"
