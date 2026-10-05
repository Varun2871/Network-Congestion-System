import os
import time
import subprocess
import pandas as pd
from datetime import datetime, timezone


OUTPUT_FILE = "data/controlled_experiments.csv"

SAMPLE_INTERVAL = 2

PING_TARGET = "1.1.1.1"

COLUMNS = [
    "timestamp",
    "label",
    "latency_ms",
    "packet_loss_percent",
    "jitter_ms",
    "rx_mbps",
    "tx_mbps",
    "total_traffic_mbps",
]


def ping_target():

    try:

        result = subprocess.run(
            [
                "ping",
                "-c",
                "4",
                "-W",
                "1",
                PING_TARGET
            ],
            capture_output=True,
            text=True,
            timeout=8
        )

        output = result.stdout

        latency = None
        packet_loss = None

        for line in output.splitlines():

            if "packet loss" in line:

                try:
                    packet_loss = float(
                        line.split("%")[0]
                        .split()[-1]
                    )
                except Exception:
                    pass

            if "min/avg" in line:

                try:

                    values = line.split("=")[1]
                    values = values.strip()
                    values = values.split("/")

                    latency = float(
                        values[1]
                    )

                except Exception:
                    pass

        return latency, packet_loss

    except Exception:

        return None, None


def get_interface_stats():

    try:

        result = subprocess.run(
            ["cat", "/proc/net/dev"],
            capture_output=True,
            text=True
        )

        for line in result.stdout.splitlines():

            if "eth0:" in line:

                parts = line.split()

                rx_bytes = int(parts[1])
                tx_bytes = int(parts[9])

                return rx_bytes, tx_bytes

    except Exception:
        pass

    return None, None


def calculate_rate(
    previous,
    current,
    seconds
):

    if (
        previous is None
        or current is None
        or seconds <= 0
    ):
        return 0.0

    difference = current - previous

    if difference < 0:
        return 0.0

    return (
        difference * 8
        / seconds
        / 1_000_000
    )


def save_sample(sample):

    os.makedirs(
        "data",
        exist_ok=True
    )

    if os.path.exists(OUTPUT_FILE):

        df = pd.read_csv(
            OUTPUT_FILE
        )

    else:

        df = pd.DataFrame(
            columns=COLUMNS
        )

    df = pd.concat(
        [
            df,
            pd.DataFrame([sample])
        ],
        ignore_index=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )


def collect_condition(
    label,
    duration
):

    print()
    print("=" * 60)
    print(f"COLLECTING: {label}")
    print("=" * 60)
    print(f"Duration: {duration} seconds")
    print()

    start_time = time.time()

    previous_rx = None
    previous_tx = None
    previous_time = None

    previous_latency = None

    while (
        time.time() - start_time
        < duration
    ):

        current_time = time.time()

        rx_bytes, tx_bytes = (
            get_interface_stats()
        )

        latency, packet_loss = (
            ping_target()
        )

        if (
            latency is not None
            and previous_latency is not None
        ):

            jitter = abs(
                latency -
                previous_latency
            )

        else:

            jitter = None

        if previous_time is not None:

            elapsed = (
                current_time -
                previous_time
            )

            rx_mbps = calculate_rate(
                previous_rx,
                rx_bytes,
                elapsed
            )

            tx_mbps = calculate_rate(
                previous_tx,
                tx_bytes,
                elapsed
            )

        else:

            rx_mbps = 0.0
            tx_mbps = 0.0

        total_traffic_mbps = (
            rx_mbps +
            tx_mbps
        )

        sample = {

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "label":
                label,

            "latency_ms":
                latency,

            "packet_loss_percent":
                packet_loss,

            "jitter_ms":
                jitter,

            "rx_mbps":
                rx_mbps,

            "tx_mbps":
                tx_mbps,

            "total_traffic_mbps":
                total_traffic_mbps,
        }

        save_sample(sample)

        print(
            f"{sample['timestamp']} | "
            f"{label:<10} | "
            f"Latency={latency} ms | "
            f"Loss={packet_loss}% | "
            f"Jitter={jitter} ms | "
            f"Traffic={total_traffic_mbps:.3f} Mbps"
        )

        if latency is not None:
            previous_latency = latency

        previous_rx = rx_bytes
        previous_tx = tx_bytes
        previous_time = current_time

        time.sleep(
            SAMPLE_INTERVAL
        )


def main():

    print("=" * 60)
    print("CONTROLLED NETWORK DATASET COLLECTOR")
    print("=" * 60)

    print()
    print("Ping target:", PING_TARGET)
    print("Output:", OUTPUT_FILE)

    print()
    print(
        "This collector is used for controlled"
    )
    print(
        "NORMAL / WARNING / CONGESTED experiments."
    )

    print()

    input(
        "Press ENTER to start CONGESTED collection..."
    )

    collect_condition(
        "CONGESTED",
        60
    )

    print()
    print("=" * 60)
    print("NORMAL COLLECTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
