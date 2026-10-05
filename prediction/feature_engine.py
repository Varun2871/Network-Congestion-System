import os
import time
import pandas as pd
import numpy as np


INPUT_FILE = "data/live_network_metrics.csv"
OUTPUT_FILE = "data/live_features.csv"

INTERVAL_SECONDS = 3
WINDOW_SIZE = 5


FEATURE_COLUMNS = [
    "rx_mbps",
    "tx_mbps",
    "total_traffic_mbps",
    "latency_ms",
    "packet_loss_percent",
    "jitter_ms",
    "rx_errors",
    "tx_errors",
    "rx_dropped",
    "tx_dropped",
    "receive_rate_mbps",
    "transmit_rate_mbps",
    "signal_percent",
    "rssi_dbm",
    "link_activity_percent",
    "total_traffic_mbps_mean_5",
    "total_traffic_mbps_std_5",
    "total_traffic_mbps_max_5",
    "latency_ms_mean_5",
    "latency_ms_std_5",
    "latency_ms_max_5",
    "packet_loss_percent_mean_5",
    "packet_loss_percent_std_5",
    "packet_loss_percent_max_5",
    "jitter_ms_mean_5",
    "jitter_ms_std_5",
    "jitter_ms_max_5",
    "signal_percent_mean_5",
    "signal_percent_std_5",
    "signal_percent_max_5",
    "link_activity_percent_mean_5",
    "link_activity_percent_std_5",
    "link_activity_percent_max_5",
    "latency_change",
    "jitter_change",
    "packet_loss_change",
    "traffic_change",
]


def calculate_features(df):
    df = df.copy()

    numeric_columns = [
        "rx_mbps",
        "tx_mbps",
        "latency_ms",
        "packet_loss_percent",
        "jitter_ms",
        "rx_errors",
        "tx_errors",
        "rx_dropped",
        "tx_dropped",
        "receive_rate_mbps",
        "transmit_rate_mbps",
        "signal_percent",
        "rssi_dbm",
    ]

    for column in numeric_columns:

        if column not in df.columns:
            df[column] = np.nan

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # ---------------------------------------------------------
    # Basic traffic features
    # ---------------------------------------------------------

    df["rx_mbps"] = df["rx_mbps"].fillna(0)
    df["tx_mbps"] = df["tx_mbps"].fillna(0)

    df["total_traffic_mbps"] = (
        df["rx_mbps"] +
        df["tx_mbps"]
    )

    # ---------------------------------------------------------
    # Link activity
    # ---------------------------------------------------------

    receive_rate = df["receive_rate_mbps"].replace(
        0,
        np.nan
    )

    transmit_rate = df["transmit_rate_mbps"].replace(
        0,
        np.nan
    )

    rx_activity = (
        df["rx_mbps"] /
        receive_rate *
        100
    )

    tx_activity = (
        df["tx_mbps"] /
        transmit_rate *
        100
    )

    rx_activity = rx_activity.replace(
        [np.inf, -np.inf],
        np.nan
    )

    tx_activity = tx_activity.replace(
        [np.inf, -np.inf],
        np.nan
    )

    df["link_activity_percent"] = (
        rx_activity.fillna(0) +
        tx_activity.fillna(0)
    )

    # ---------------------------------------------------------
    # Rolling statistics
    # ---------------------------------------------------------

    rolling_columns = [
        "total_traffic_mbps",
        "latency_ms",
        "packet_loss_percent",
        "jitter_ms",
        "signal_percent",
        "link_activity_percent",
    ]

    for column in rolling_columns:

        rolling = (
            df[column]
            .rolling(
                WINDOW_SIZE,
                min_periods=1
            )
        )

        df[f"{column}_mean_5"] = (
            rolling.mean()
        )

        df[f"{column}_std_5"] = (
            rolling.std()
            .fillna(0)
        )

        df[f"{column}_max_5"] = (
            rolling.max()
        )

    # ---------------------------------------------------------
    # Short-term changes
    # ---------------------------------------------------------

    df["latency_change"] = (
        df["latency_ms"]
        .diff()
        .fillna(0)
    )

    df["jitter_change"] = (
        df["jitter_ms"]
        .diff()
        .fillna(0)
    )

    df["packet_loss_change"] = (
        df["packet_loss_percent"]
        .diff()
        .fillna(0)
    )

    df["traffic_change"] = (
        df["total_traffic_mbps"]
        .diff()
        .fillna(0)
    )

    # ---------------------------------------------------------
    # Clean infinite values
    # ---------------------------------------------------------

    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    return df


def update_features():

    if not os.path.exists(INPUT_FILE):
        print("Waiting for live network metrics...")
        return False

    try:
        df = pd.read_csv(INPUT_FILE)

    except Exception as e:
        print(
            f"Could not read metrics file: {e}"
        )
        return False

    if df.empty:
        print("Metrics file is empty.")
        return False

    features = calculate_features(df)

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    features.to_csv(
        OUTPUT_FILE,
        index=False
    )

    return True


def main():

    print("=" * 70)
    print("CONTINUOUS LIVE FEATURE ENGINE")
    print("=" * 70)

    print()
    print(
        f"Input  : {INPUT_FILE}"
    )

    print(
        f"Output : {OUTPUT_FILE}"
    )

    print(
        f"Update : every {INTERVAL_SECONDS} seconds"
    )

    print()
    print("Starting...")
    print()

    last_row_count = 0

    while True:

        try:

            success = update_features()

            if success:

                try:
                    df = pd.read_csv(
                        OUTPUT_FILE
                    )

                    row_count = len(df)

                    if row_count != last_row_count:

                        print(
                            f"[FEATURE ENGINE] "
                            f"Rows: {row_count}"
                        )

                        last_row_count = row_count

                except Exception:
                    pass

            time.sleep(
                INTERVAL_SECONDS
            )

        except KeyboardInterrupt:

            print()
            print(
                "Feature engine stopped."
            )

            break

        except Exception as e:

            print()
            print(
                f"ERROR: {e}"
            )

            print(
                "Retrying..."
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
