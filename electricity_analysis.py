import pandas as pd
import matplotlib.pyplot as plt
import os

# File paths **Downlaod files from Google Drive folder and
# Copy your own local specific path to the csv files in the file code to the strings below**

PRICE_FOLDER = r"C:\Users\carlo\OneDrive\Desktop\Electricity Price Code\prices"  # Folder containing price CSV files

# File paths
FUEL_PATH = r"C:\Users\carlo\OneDrive\Desktop\Electricity Price Code\fueltypes.csv"
CARBON_PATH = r"C:\Users\carlo\OneDrive\Desktop\Electricity Price Code\carbon_intensity.csv"

# Collect all CSV files in the prices folder
price_files = [
    os.path.join(PRICE_FOLDER, f)
    for f in os.listdir(PRICE_FOLDER)
    if f.endswith(".csv")
]

# Load and combine all price data files
price_list = []
for file in price_files:
    temp_df = pd.read_csv(file)
    price_list.append(temp_df)

price_df = pd.concat(price_list, ignore_index=True)


# Load fuel and carbon data
fuel_df = pd.read_csv(FUEL_PATH)
carbon_df = pd.read_csv(CARBON_PATH)

# Standardize column names
fuel_df.columns = fuel_df.columns.str.strip().str.lower()
price_df.columns = price_df.columns.str.strip().str.lower()
carbon_df.columns = carbon_df.columns.str.strip().str.lower()

# Rename price column for consistency
PRICE_COL = "total_lmp_da"
price_df = price_df.rename(columns={PRICE_COL: "price"})

# Convert datetime columns
TIME_COL = "datetime_beginning_utc"

fuel_df[TIME_COL] = pd.to_datetime(fuel_df[TIME_COL])
price_df[TIME_COL] = pd.to_datetime(
    price_df[TIME_COL],
    format="%m/%d/%Y %I:%M:%S %p",
    errors="coerce"
)

fuel_df = fuel_df.rename(columns={TIME_COL: "datetime"})
price_df = price_df.rename(columns={TIME_COL: "datetime"})

# Prepare carbon data and align daily values to hourly frequency
carbon_df["datetime"] = pd.to_datetime(carbon_df["datetime"], errors="coerce")

# Remove timezone information if present
if carbon_df["datetime"].dt.tz is not None:
    carbon_df["datetime"] = carbon_df["datetime"].dt.tz_localize(None)

# Keep only necessary columns
carbon_df = carbon_df[["datetime", "carbonintensity"]]

# Remove rows with invalid timestamps
carbon_df = carbon_df.dropna(subset=["datetime"])

# Ensure timestamps are unique before resampling
carbon_df = carbon_df.groupby("datetime", as_index=False).mean()

# Convert daily data to hourly using forward fill
carbon_df = carbon_df.set_index("datetime")
carbon_df = carbon_df.resample("h").ffill()
carbon_df = carbon_df.reset_index()

carbon_df = carbon_df[["datetime", "carbonintensity"]]

# Remove timezone info to ensure consistent merging
fuel_df["datetime"] = fuel_df["datetime"].dt.tz_localize(None)
price_df["datetime"] = price_df["datetime"].dt.tz_localize(None)
carbon_df["datetime"] = carbon_df["datetime"].dt.tz_localize(None)

# Pivot fuel data so each fuel type becomes its own column
GENERATION_COL = "mw"

if 'fuel_type' not in fuel_df.columns or GENERATION_COL not in fuel_df.columns:
    raise ValueError(f"Fuel CSV must have 'fuel_type' and '{GENERATION_COL}' columns")

fuel_df = fuel_df.pivot_table(
    index='datetime',
    columns='fuel_type',
    values=GENERATION_COL,
    aggfunc='sum'
).reset_index()

fuel_df.columns = [col.lower() if isinstance(col, str) else col for col in fuel_df.columns]

# Merge fuel, price, and carbon data
df = pd.merge(fuel_df, price_df, on="datetime", how="inner")
df = pd.merge(df, carbon_df, on="datetime", how="inner")

# Identify fuel type columns
GREEN_KEYWORDS = ["wind", "solar", "hydro", "nuclear", "other renewables"]
FOSSIL_KEYWORDS = ["coal", "gas", "oil"]

def find_fuel_columns(df, keywords):
    cols = []
    for col in df.columns:
        col_lower = col.lower()
        for key in keywords:
            if key in col_lower:
                cols.append(col)
    return sorted(set(cols))

GREEN_FUELS = find_fuel_columns(df, GREEN_KEYWORDS)
FOSSIL_FUELS = find_fuel_columns(df, FOSSIL_KEYWORDS)

print("Detected green fuel columns:", GREEN_FUELS)
print("Detected fossil fuel columns:", FOSSIL_FUELS)

# Calculate generation shares
df["green_generation"] = df[GREEN_FUELS].sum(axis=1)
df["fossil_generation"] = df[FOSSIL_FUELS].sum(axis=1)
df["total_generation"] = df["green_generation"] + df["fossil_generation"]

df = df[df["total_generation"] > 0]
df["green_share"] = df["green_generation"] / df["total_generation"]
df["fossil_share"] = df["fossil_generation"] / df["total_generation"]

# Scatter plot: Price vs Green Share
plt.figure(figsize=(10, 6))
plt.scatter(df["green_share"], df["price"], alpha=0.6)
plt.xlabel("Green Energy Share")
plt.ylabel("Electricity Price (USD/MWh)")
plt.title("Electricity Price vs Green Energy Share")
plt.grid(True)
plt.tight_layout()
plt.show()

# Scatter plot: Price vs Fossil Share
plt.figure(figsize=(10, 6))
plt.scatter(df["fossil_share"], df["price"], alpha=0.6, color="orange")
plt.xlabel("Fossil Fuel Share")
plt.ylabel("Electricity Price (USD/MWh)")
plt.title("Electricity Price vs Fossil Fuel Share")
plt.grid(True)
plt.tight_layout()
plt.show()

# Time series: Price and Green Share
fig, ax1 = plt.subplots(figsize=(12, 6))

ax1.plot(df["datetime"], df["price"], color="black", label="Price (USD/MWh)")
ax1.set_ylabel("Price (USD/MWh)")
ax1.set_xlabel("Time")

ax2 = ax1.twinx()
ax2.plot(df["datetime"], df["green_share"], color="green", alpha=0.6, label="Green Share")
ax2.set_ylabel("Green Energy Share")

fig.suptitle("Electricity Prices vs Green Energy Share (Hourly)")
fig.legend(loc="upper right")
plt.tight_layout()
plt.show()

# Scatter plot: Price vs Carbon Intensity
plt.figure(figsize=(10, 6))
plt.scatter(df["carbonintensity"], df["price"], alpha=0.6)
plt.xlabel("Carbon Intensity (gCO₂/kWh)")
plt.ylabel("Electricity Price (USD/MWh)")
plt.title("Electricity Price vs Carbon Intensity")
plt.grid(True)
plt.tight_layout()
plt.show()

# Time series: Price and Carbon Intensity
fig, ax1 = plt.subplots(figsize=(12, 6))

ax1.plot(df["datetime"], df["price"], color="black", label="Price")
ax1.set_ylabel("Price (USD/MWh)")
ax1.set_xlabel("Time")

ax2 = ax1.twinx()
ax2.plot(df["datetime"], df["carbonintensity"], color="red", alpha=0.6, label="Carbon Intensity")
ax2.set_ylabel("Carbon Intensity (gCO₂/kWh)")

fig.suptitle("Electricity Price vs Carbon Intensity Over Time")
fig.legend(loc="upper right")
plt.tight_layout()
plt.show()

# Correlation calculations
green_corr = df["green_share"].corr(df["price"])
fossil_corr = df["fossil_share"].corr(df["price"])
carbon_corr = df["carbonintensity"].corr(df["price"])

print(f"Correlation (Green Share vs Price): {green_corr:.3f}")
print(f"Correlation (Fossil Share vs Price): {fossil_corr:.3f}")
print(f"Correlation (Carbon Intensity vs Price): {carbon_corr:.3f}")