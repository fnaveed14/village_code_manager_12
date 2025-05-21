# app/updater.py

def add_new_village(df, uc_prefix: str, village_name: str, generated_code: str) -> dict:
    """
    Creates a dictionary for a new village row under the specified UC.
    """
    filtered = df[df['uc_prefix'] == uc_prefix]

    if filtered.empty:
        raise ValueError(f"UC prefix '{uc_prefix}' not found in dataset.")

    uc_row = filtered.iloc[0]
    suffix = generated_code[-3:]

    return {
        "enumerator": "",
        "country_pcode": "PK",
        "province": uc_row["province"],
        "province_code": uc_row["province_code"],
        "province_pcode": uc_row["province_pcode"],
        "district": uc_row["district"],
        "district_code": uc_row["district_code"],
        "district_pcode": uc_row["district_pcode"],
        "tehsil": uc_row["tehsil"],
        "tehsil_code": uc_row["tehsil_code"],
        "tehsil_pcode": uc_row["tehsil_pcode"],
        "uc": uc_row["uc"],
        "uc_id": uc_row["uc_id"],
        "uc/vc/nc_pcode": uc_row["uc/vc/nc_pcode"],
        "village_name": village_name,
        "latitude": "",
        "longitude": "",
        "village/settlement_code": suffix,
        "village_pcode_new": generated_code,
        "village_pcode_old": "",
        "remarks": "",
        "covered_in_r3_(yes/no)": "",
        "uc_prefix": uc_prefix
    }


def mark_village_for_deletion(df, village_code: str) -> bool:
    """
    Marks a village with the given P-code as 'to be deleted'.
    """
    match = df['village_pcode_new'] == village_code
    if match.any():
        df.loc[match, 'remarks'] = 'to be deleted'
        return True
    return False
