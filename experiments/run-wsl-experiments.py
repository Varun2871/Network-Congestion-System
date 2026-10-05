import csv
import json
import subprocess
import time
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

INTERFACE = "eth0"

# iPerf3 server running on the other side of the WSL network
SERVER = "192.168.16.1"

# Duration of each experiment in seconds
DURATION = 10

# Number of times each test is repeated
REPEATS = 3

# Output dataset
OUTPUT_FILE = "data/congestion_experiments.csv"


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================
#
# Each tuple is:
#
#     (bottleneck_capacity_mbps, offered_udp_load_mbps)
#
# Example:
#
#     (10, 15)
#
# means:
#     Network capacity = 10 Mbps
#     Offered traffic  = 15 Mbps
#
# This should create congestion because:
#
#     Offered load > network capacity
#
# ============================================================

TESTS = [
    # 10 Mbps bottleneck
    (10, 2.5),
    (10, 5),
    (10, 7.5),
    (10, 10),
    (10, 12.5),
    (10, 15),

    # 20 Mbps bottleneck
    (20, 5),
    (20, 10),
    (20, 15),
    (20, 20),
    (20, 25),
    (20, 30),

    # 30 Mbps bottleneck
    (30, 7.5),
    (30, 10),
    (30, 15),
    (30, 20),
    (30, 25),
    (30, 30),
    (30, 40),
    (30, 45),

    # 40 Mbps bottleneck
    (40, 10),
    (40, 15),
    (40, 20),
    (40, 30),
    (40, 35),
    (40, 40),
    (40, 50),
    (40, 60),

    # 50 Mbps bottleneck
    (50, 10),
    (50, 15),
    (50, 20),
    (50, 25),
    (50, 30),
    (50, 40),
    (50, 50),
    (50, 60),
    (50, 75),
]


# ============================================================
# APPLY NETWORK BOTTLENECK
# ============================================================

def apply_limit(capacity):
    """
    Apply a TBF (Token Bucket Filter) bandwidth limit
    to the WSL network interface.
    """

    command = [
        "sudo",
        "tc",
        "qdisc",
        "replace",
        "dev",
        INTERFACE,
        "root",
        "tbf",
        "rate",
        f"{capacity}mbit",
        "burst",
        "32kbit",
        "latency",
        "50ms",
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


# ============================================================
# REMOVE NETWORK BOTTLENECK
# ============================================================

def remove_limit():
    """
    Remove the traffic control rule.
    """

    subprocess.run(
        [
            "sudo",
            "tc",
            "qdisc",
            "del",
            "dev",
            INTERFACE,
            "root",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ============================================================
# RUN iPERF3 UDP TEST
# ============================================================

def run_iperf(offered_rate):
    """
    Run an iPerf3 UDP experiment and return JSON results.
    """

    command = [
        "iperf3",
        "-c",
        SERVER,
        "-u",
        "-b",
        f"{offered_rate}M",
        "-t",
        str(DURATION),
        "-J",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(result.stdout)


# ============================================================
# EXTRACT RESULTS
# ============================================================

def extract_results(data):
    """
    Extract throughput, jitter and packet-loss information
    from iPerf3 JSON output.
    """

    end = data.get("end", {})

    # iPerf3 normally provides UDP summary information here.
    receiver = end.get("sum", {})

    # Some versions provide the information through streams.
    if not receiver:
        streams = end.get("streams", [])

        if streams:
            receiver = streams[0].get("udp", {})

    throughput = receiver.get("bits_per_second", 0) / 1_000_000

    jitter = receiver.get("jitter_ms", 0)

    lost = receiver.get("lost_packets", 0)

    total = receiver.get("packets", 0)

    loss = receiver.get("lost_percent", 0)

    return (
        throughput,
        jitter,
        loss,
        lost,
        total,
    )


# ============================================================
# MAIN EXPERIMENT
# ============================================================

def main():

    print()
    print("==============================================")
    print(" NETWORK CONGESTION DATASET GENERATOR")
    print("==============================================")
    print()
    print(f"Server       : {SERVER}")
    print(f"Interface    : {INTERFACE}")
    print(f"Duration     : {DURATION} seconds")
    print(f"Repetitions  : {REPEATS}")
    print(f"Test cases   : {len(TESTS)}")
    print(f"Total samples: {len(TESTS) * REPEATS}")
    print()
    print(f"Output file  : {OUTPUT_FILE}")
    print()

    # Create/overwrite dataset
    with open(
        OUTPUT_FILE,
        "w",
        newline=""
    ) as file:

        writer = csv.writer(file)

        # CSV header
        writer.writerow([
            "timestamp",
            "capacity_mbps",
            "offered_load_mbps",
            "received_throughput_mbps",
            "jitter_ms",
            "packet_loss_percent",
            "lost_datagrams",
            "total_datagrams",
            "congested",
        ])

        sample_number = 0

        try:

            # Loop through all capacity/load combinations
            for capacity, offered in TESTS:

                for repeat in range(1, REPEATS + 1):

                    sample_number += 1

                    print("----------------------------------------------")
                    print(
                        f"Sample {sample_number}/{len(TESTS) * REPEATS}"
                    )
                    print(
                        f"Capacity = {capacity} Mbps | "
                        f"Offered = {offered} Mbps | "
                        f"Repeat = {repeat}/{REPEATS}"
                    )

                    # Apply bottleneck
                    apply_limit(capacity)

                    # Small pause so the qdisc is fully active
                    time.sleep(1)

                    # Run iPerf3
                    data = run_iperf(offered)

                    # Extract measurements
                    (
                        throughput,
                        jitter,
                        loss,
                        lost,
                        total,
                    ) = extract_results(data)

                    # Determine congestion label
                    #
                    # Congestion is marked when:
                    #
                    # 1. Offered traffic exceeds capacity
                    # OR
                    # 2. Packet loss exceeds 1%
                    #
                    congested = int(
                        offered > capacity or loss > 1
                    )

                    # Save row
                    writer.writerow([
                        datetime.now().isoformat(timespec="seconds"),
                        capacity,
                        offered,
                        round(throughput, 3),
                        round(jitter, 3),
                        round(loss, 3),
                        lost,
                        total,
                        congested,
                    ])

                    file.flush()

                    # Display result
                    print(
                        f"Received   : {throughput:.2f} Mbps"
                    )

                    print(
                        f"Packet loss: {loss:.2f}%"
                    )

                    print(
                        f"Jitter     : {jitter:.3f} ms"
                    )

                    print(
                        f"Congested  : {congested}"
                    )

                    print()

                    # Small pause before next experiment
                    time.sleep(1)

        finally:

            # Always remove the traffic limit
            remove_limit()

    print("==============================================")
    print("ALL EXPERIMENTS COMPLETED")
    print("==============================================")
    print()
    print(f"Dataset saved to: {OUTPUT_FILE}")
    print()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
