import pandas as pd
import matplotlib.pyplot as plt
import os

BEFORE_FILE = "data/before_management_results.csv"
AFTER_FILE = "data/after_management_results.csv"

print()
print("==============================================")
print("     NETWORK TRAFFIC MANAGEMENT COMPARISON")
print("==============================================")
print()

# ------------------------------------------------
# LOAD DATA
# ------------------------------------------------

before = pd.read_csv(BEFORE_FILE)
after = pd.read_csv(AFTER_FILE)

# Clean column names
before.columns = [c.strip().lower() for c in before.columns]
after.columns = [c.strip().lower() for c in after.columns]

# Remove TOTAL row if it exists
before = before[
    before["priority"].str.upper() != "TOTAL"
].copy()

after = after[
    after["priority"].str.upper() != "TOTAL"
].copy()

# ------------------------------------------------
# DISPLAY ORIGINAL RESULTS
# ------------------------------------------------

print("BEFORE MANAGEMENT")
print("-----------------")
print(
    before[
        [
            "priority",
            "offered_mbps",
            "received_mbps",
            "packet_loss_percent",
            "jitter_ms"
        ]
    ].to_string(index=False)
)

print()
print("AFTER MANAGEMENT")
print("----------------")
print(
    after[
        [
            "priority",
            "offered_mbps",
            "received_mbps",
            "packet_loss_percent",
            "jitter_ms"
        ]
    ].to_string(index=False)
)

# ------------------------------------------------
# MERGE BEFORE AND AFTER
# ------------------------------------------------

comparison = pd.merge(
    before[
        [
            "priority",
            "received_mbps",
            "packet_loss_percent",
            "jitter_ms"
        ]
    ],
    after[
        [
            "priority",
            "received_mbps",
            "packet_loss_percent",
            "jitter_ms"
        ]
    ],
    on="priority",
    suffixes=("_before", "_after")
)

# ------------------------------------------------
# CALCULATE CHANGES
# ------------------------------------------------

comparison["throughput_change_mbps"] = (
    comparison["received_mbps_after"]
    - comparison["received_mbps_before"]
)

comparison["throughput_change_percent"] = (
    comparison["throughput_change_mbps"]
    / comparison["received_mbps_before"]
) * 100

comparison["jitter_change_ms"] = (
    comparison["jitter_ms_after"]
    - comparison["jitter_ms_before"]
)

# Absolute jitter improvement
comparison["jitter_change_percent"] = (
    comparison["jitter_change_ms"]
    / comparison["jitter_ms_before"]
) * 100

# ------------------------------------------------
# PRINT COMPARISON
# ------------------------------------------------

print()
print("==============================================")
print("          BEFORE vs AFTER RESULTS")
print("==============================================")

for _, row in comparison.iterrows():

    print()
    print("Priority:", row["priority"].upper())

    print(
        f"  Before throughput : "
        f"{row['received_mbps_before']:.2f} Mbps"
    )

    print(
        f"  After throughput  : "
        f"{row['received_mbps_after']:.2f} Mbps"
    )

    print(
        f"  Throughput change : "
        f"{row['throughput_change_mbps']:+.2f} Mbps"
    )

    print(
        f"  Throughput change : "
        f"{row['throughput_change_percent']:+.2f}%"
    )

    print(
        f"  Before packet loss: "
        f"{row['packet_loss_percent_before']:.2f}%"
    )

    print(
        f"  After packet loss : "
        f"{row['packet_loss_percent_after']:.2f}%"
    )

    print(
        f"  Before jitter     : "
        f"{row['jitter_ms_before']:.3f} ms"
    )

    print(
        f"  After jitter      : "
        f"{row['jitter_ms_after']:.3f} ms"
    )

# ------------------------------------------------
# SAVE COMPARISON CSV
# ------------------------------------------------

comparison.to_csv(
    "data/before_after_comparison.csv",
    index=False
)

print()
print("----------------------------------------------")
print("Comparison saved to:")
print("data/before_after_comparison.csv")

# ------------------------------------------------
# GRAPH 1: THROUGHPUT
# ------------------------------------------------

priorities = comparison["priority"].str.upper()

x = list(range(len(priorities)))
width = 0.35

plt.figure(figsize=(9, 6))

plt.bar(
    [i - width / 2 for i in x],
    comparison["received_mbps_before"],
    width,
    label="Before Management"
)

plt.bar(
    [i + width / 2 for i in x],
    comparison["received_mbps_after"],
    width,
    label="After Management"
)

plt.xticks(x, priorities)
plt.xlabel("Traffic Priority")
plt.ylabel("Received Throughput (Mbps)")
plt.title("Throughput Before vs After Traffic Management")
plt.legend()
plt.tight_layout()

plt.savefig(
    "data/throughput_before_after.png",
    dpi=300
)

plt.close()

# ------------------------------------------------
# GRAPH 2: JITTER
# ------------------------------------------------

plt.figure(figsize=(9, 6))

plt.bar(
    [i - width / 2 for i in x],
    comparison["jitter_ms_before"],
    width,
    label="Before Management"
)

plt.bar(
    [i + width / 2 for i in x],
    comparison["jitter_ms_after"],
    width,
    label="After Management"
)

plt.xticks(x, priorities)
plt.xlabel("Traffic Priority")
plt.ylabel("Jitter (ms)")
plt.title("Jitter Before vs After Traffic Management")
plt.legend()
plt.tight_layout()

plt.savefig(
    "data/jitter_before_after.png",
    dpi=300
)

plt.close()

# ------------------------------------------------
# FINAL MESSAGE
# ------------------------------------------------

print()
print("==============================================")
print("          COMPARISON COMPLETE")
print("==============================================")
print()
print("Generated files:")
print("1. data/before_after_comparison.csv")
print("2. data/throughput_before_after.png")
print("3. data/jitter_before_after.png")
print()
