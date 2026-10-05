import pandas as pd
from pathlib import Path

INPUT_FILE = Path("data/live_features.csv")
OUTPUT_FILE = Path("data/live_labeled.csv")

df = pd.read_csv(INPUT_FILE)

# Start with all samples as NORMAL
df["congestion_state"] = "NORMAL"

# WARNING conditions
warning = (
    (df["latency_ms"] >= 20) |
    (df["jitter_ms"] >= 10) |
    (df["packet_loss_percent"] >= 1)
)

df.loc[warning, "congestion_state"] = "WARNING"

# CONGESTED conditions
congested = (
    (df["latency_ms"] >= 40) |
    (df["jitter_ms"] >= 20) |
    (df["packet_loss_percent"] >= 5)
)

df.loc[congested, "congestion_state"] = "CONGESTED"

# If latency/jitter is unavailable because the probe failed,
# do not automatically call it congestion.
missing_quality = (
    df["latency_ms"].isna() &
    df["jitter_ms"].isna()
)

df.loc[missing_quality, "congestion_state"] = "UNKNOWN"

# Save
df.to_csv(OUTPUT_FILE, index=False)

print("=" * 60)
print("LIVE CONGESTION LABEL GENERATION")
print("=" * 60)

print(f"Input samples : {len(df)}")
print(f"Output file   : {OUTPUT_FILE}")

print("\nSTATE COUNTS:")
print(df["congestion_state"].value_counts(dropna=False))

print("\nSAMPLE:")
print(
    df[
        [
            "timestamp",
            "latency_ms",
            "packet_loss_percent",
            "jitter_ms",
            "signal_percent",
            "congestion_state",
        ]
    ].tail(10).to_string(index=False)
)

print("\nLive labels created successfully.")
