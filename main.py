# main.py

from app.data_loader import load_and_clean_data
from app.code_generator import generate_village_code
from app.updater import add_new_village
import pandas as pd
from datetime import datetime

def main():
    # Step 1: Load and clean dataset
    df = load_and_clean_data()

    # Step 2: Choose a UC prefix
    uc_prefix = "PK60102012"  # Example: Sharai Sadullah
    print(f"\n🔍 Existing suffixes under {uc_prefix}:")
    suffixes = df[df['uc_prefix'] == uc_prefix]['village/settlement_code'].dropna().tolist()
    print(suffixes)

    # Step 3: Generate the next available full P-code
    new_code = generate_village_code(df, uc_prefix)
    print(f"\n🚀 Next village code for {uc_prefix}: {new_code}")

    # Step 4: Add a new village
    village_name = "Example New Village"

    # Add remark with date
    today = datetime.today().strftime("%Y-%m-%d")
    new_row = add_new_village(df, uc_prefix, village_name, new_code)
    new_row["remarks"] = f"newly added on {today}"

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    print(f"✅ Village '{village_name}' added with code {new_code}")

    # Step 5: Overwrite the original masterlist
    output_path = "data/village_masterlist.xlsx"  # Overwrite original
    # NEW:
    df.to_excel(output_path, index=False, sheet_name="Masterlist")

    print(f"💾 Masterlist updated in: {output_path}")

if __name__ == "__main__":
    main()
