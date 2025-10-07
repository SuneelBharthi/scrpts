import pandas as pd
import numpy as np
import re

# Input & Output paths
INPUT_XLSX  = "Final-3-venders.xlsx"
OUTPUT_XLSX = "Updated-price_2.xlsx"

VENDOR_WHITELIST = {"routerswitch", "serversupply", "etechbuy"}

# Function to normalize text
def norm_text(s):
    return "" if pd.isna(s) else str(s).strip().lower()

# Normalize vendor names
def norm_vendor(v):
    v = norm_text(v)
    v_compact = re.sub(r"[^a-z0-9]", "", v)
    if "routerswitch" in v_compact or ("router" in v and "switch" in v):
        return "routerswitch"
    if "serversupply" in v_compact or ("server" in v and "supply" in v):
        return "serversupply"
    if "etechbuy" in v_compact or ("etech" in v and "buy" in v):
        return "etechbuy"
    return v_compact or v

# Normalize condition names
def norm_condition(c):
    c = norm_text(c)
    c_simple = re.sub(r"[\s\-_/()]+", " ", c).strip()
    if c_simple.startswith(("new", "original new", "new (npen-box)")):
        return "New Factory Sealed"
    if c_simple.startswith("refurb"):
        return "Refurbished"
    return ""

# Convert price to float
def to_price(x):
    if pd.isna(x):
        return np.nan
    s = str(x)
    s = re.sub(r"[^\d\.\-]", "", s)
    try:
        return float(s) if s not in {"", ".", "-"} else np.nan
    except:
        return np.nan

# Vendor priority map
vendor_priority = {"routerswitch": 0, "serversupply": 1, "etechbuy": 2}

# Load data
df = pd.read_excel(INPUT_XLSX, sheet_name="Sheet1", dtype=str)
df.columns = [c.strip() for c in df.columns]

# Normalize columns
df["sku"] = df["SKU"].astype(str).str.strip()
df["vendor_norm"] = df["Vendor"].map(norm_vendor)
df["condition_norm"] = df["Product Condition"].map(norm_condition)
df["list_price_num"] = df["List Price"].map(to_price)
df["current_price_num"] = df["Current Price"].map(to_price)

# Filter to vendors and conditions
df = df[df["vendor_norm"].isin(VENDOR_WHITELIST)]
df = df[df["condition_norm"].isin(["New Factory Sealed", "Refurbished"])]
df = df[df["sku"] != ""]

# Drop exact duplicates
df = df.drop_duplicates(subset=["sku", "vendor_norm", "condition_norm", "list_price_num", "current_price_num"])

# Add priority column
df["vendor_priority"] = df["vendor_norm"].map(vendor_priority)

# --- Intelligent fallback logic per SKU and condition ---
def pick_best_vendor(group):
    # Sort by priority
    group = group.sort_values("vendor_priority")
    # Iterate and pick first row with valid prices
    for idx, row in group.iterrows():
        if not pd.isna(row["list_price_num"]) and not pd.isna(row["current_price_num"]):
            return row
    # If none valid, return empty row
    return pd.Series({
        "sku": group["sku"].iloc[0],
        "condition_norm": group["condition_norm"].iloc[0],
        "list_price_num": np.nan,
        "current_price_num": np.nan
    })

agg_list = []
for (sku, cond), group in df.groupby(["sku", "condition_norm"]):
    best = pick_best_vendor(group)
    agg_list.append(best)

df_best = pd.DataFrame(agg_list)

# Pivot for wide format
wide = df_best.pivot(index="sku", columns="condition_norm", values=["list_price_num", "current_price_num"])
wide.columns = [f"{a}_{b}" for a,b in wide.columns.to_flat_index()]
wide = wide.reset_index()

# Rename columns
rename_map = {
    "list_price_num_New Factory Sealed": "newlistprice",
    "current_price_num_New Factory Sealed": "newcurrentprice",
    "list_price_num_Refurbished": "refurblistprice",
    "current_price_num_Refurbished": "refurbcurrentprice",
}
wide = wide.rename(columns=rename_map)

# Ensure all columns exist
for col in ["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]:
    if col not in wide.columns:
        wide[col] = np.nan

# Round and convert to integer
for col in ["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]:
    wide[col] = wide[col].round().astype("Int64")

# Remove rows where all prices missing
wide = wide.dropna(subset=["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"], how="all")

# Reorder columns
wide = wide[["sku", "newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]].sort_values("sku")

# Save to Excel
wide.to_excel(OUTPUT_XLSX, index=False)

print("Output saved to:", OUTPUT_XLSX)
print("Shape of final dataframe:", wide.shape)





# import pandas as pd
# import numpy as np
# import re

# # Input & Output paths
# INPUT_XLSX  = "Final-3-venders.xlsx"  # your input file path
# OUTPUT_XLSX = "Updated-price_1.xlsx"

# VENDOR_WHITELIST = {"routerswitch", "serversupply", "etechbuy"}

# # Function to normalize the vendor name
# def norm_text(s):
#     return "" if pd.isna(s) else str(s).strip().lower()

# # Normalizing Vendor names
# def norm_vendor(v):
#     v = norm_text(v)
#     v_compact = re.sub(r"[^a-z0-9]", "", v)
#     if "routerswitch" in v_compact or ("router" in v and "switch" in v):
#         return "routerswitch"
#     if "serversupply" in v_compact or ("server" in v and "supply" in v):
#         return "serversupply"
#     if "etechbuy" in v_compact or ("etech" in v and "buy" in v):
#         return "etechbuy"
#     return v_compact or v

# # Normalizing condition names
# def norm_condition(c):
#     c = norm_text(c)
#     c_simple = re.sub(r"[\s\-_/()]+", " ", c).strip()
#     if c_simple.startswith("new" , "original new" , "new (npen-box)"):
#         return "New Factory Sealed"
#     if c_simple.startswith("Refurbished"):
#         return "Refurbished"
#     return ""

# # Converting price values to float, handle errors by setting NaN
# def to_price(x):
#     if pd.isna(x):
#         return np.nan
#     s = str(x)
#     s = re.sub(r"[^\d\.\-]", "", s)
#     try:
#         return float(s) if s not in {"", ".", "-"} else np.nan
#     except:
#         return np.nan

# # Load data
# df = pd.read_excel(INPUT_XLSX, sheet_name="Sheet1", dtype=str)
# df.columns = [c.strip() for c in df.columns]

# # Clean columns and normalize
# df["sku"] = df["SKU"].astype(str).str.strip()
# df["vendor_norm"] = df["Vendor"].map(norm_vendor)
# df["condition_norm"] = df["Product Condition"].map(norm_condition)
# df["list_price_num"] = df["List Price"].map(to_price)
# df["current_price_num"] = df["Current Price"].map(to_price)

# # Filter to the desired vendors and conditions
# df = df[df["vendor_norm"].isin(VENDOR_WHITELIST)]
# df = df[df["condition_norm"].isin(["New Factory Sealed", "Refurbished"])]
# df = df[df["sku"] != ""]

# # Drop exact duplicates based on the important fields
# df = df.drop_duplicates(subset=["sku", "vendor_norm", "condition_norm", "list_price_num", "current_price_num"])

# # Aggregating by SKU and condition to get minimum List Price and Current Price
# agg = (
#     df.groupby(["sku", "condition_norm"], as_index=False)
#       .agg(min_list_price=("list_price_num", "min"),
#            min_current_price=("current_price_num", "min"))
# )

# # Pivot the data for final wide format
# wide = agg.pivot(index="sku", columns="condition_norm", values=["min_list_price", "min_current_price"])
# wide.columns = [f"{a}_{b}" for a,b in wide.columns.to_flat_index()]
# wide = wide.reset_index()

# # Rename columns as per required output
# rename_map = {
#     "min_list_price_New Factory Sealed": "newlistprice",
#     "min_current_price_New Factory Sealed": "newcurrentprice",
#     "min_list_price_Refurbished": "refurblistprice",
#     "min_current_price_Refurbished": "refurbcurrentprice",
# }

# # Apply renaming to columns
# wide = wide.rename(columns=rename_map)

# # Ensure columns exist even if some are missing
# for col in ["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]:
#     if col not in wide.columns:
#         wide[col] = np.nan

# # Handle missing values for List Price and Current Price
# for idx, row in wide.iterrows():
#     if pd.isna(row['newlistprice']) or pd.isna(row['newcurrentprice']):
#         wide.at[idx, 'newlistprice'] = np.nan
#         wide.at[idx, 'newcurrentprice'] = np.nan

#     if pd.isna(row['refurblistprice']) or pd.isna(row['refurbcurrentprice']):
#         wide.at[idx, 'refurblistprice'] = np.nan
#         wide.at[idx, 'refurbcurrentprice'] = np.nan

# # Round prices to 2 decimals and convert them to integers
# for col in ["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]:
#     wide[col] = wide[col].round().astype("Int64")

# # Remove rows where both new and refurbished prices are missing
# wide = wide.dropna(subset=["newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"], how="all")

# # Order and sort the data by SKU
# wide = wide[["sku", "newlistprice", "newcurrentprice", "refurblistprice", "refurbcurrentprice"]].sort_values("sku")

# # Save the final output to an Excel file
# wide.to_excel(OUTPUT_XLSX, index=False)

# OUTPUT_XLSX, wide.shape
