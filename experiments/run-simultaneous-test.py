import subprocess
import json
import csv
import os
from datetime import datetime

TARGET = "192.168.16.1"
DURATION = 10
OFFERED_RATE = 20

TRAFFIC = [
    ("HIGH", 5201),
    ("MEDIUM", 5202),
    ("LOW", 5203),
]

OUTPUT_FILE = "data/simultaneous_priority_results.csv"


def run_all_tests():

    print("\n" + "=" * 65)
    print("       SIMULTANEOUS PRIORITY TRAFFIC EXPERIMENT")
    print("=" * 65)

    print("\nTraffic-management limits:")
    print("HIGH   = 12 Mbps")
    print("MEDIUM =  5 Mbps")
    print("LOW    =  3 Mbps")
    print("TOTAL  = 20 Mbps")

    print("\nEach traffic class will attempt 20 Mbps.")
    print("All three flows will run simultaneously.")

    input("\nPress ENTER to start...")

    processes = []

    # --------------------------------------------------------
    # Start all three UDP flows at the same time
    # --------------------------------------------------------

    for name, port in TRAFFIC:

        command = [
            "iperf3",
            "-c", TARGET,
            "-u",
            "-b", f"{OFFERED_RATE}M",
            "-t", str(DURATION),
            "-p", str(port),
            "-J"
        ]

        print(f"\nStarting {name} traffic on UDP port {port}...")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        processes.append((name, port, process))

    print("\nAll three flows are running...")
    print("Please wait approximately 10 seconds.\n")

    results = []

    # --------------------------------------------------------
    # Wait for all tests and collect results
    # --------------------------------------------------------

    for name, port, process in processes:

        try:
            stdout, stderr = process.communicate(
                timeout=DURATION + 20
            )

            if process.returncode != 0:
                print(f"{name}: ERROR")
                print(stderr)
                continue

            data = json.loads(stdout)

            end = data.get("end", {})
            udp = end.get("sum", {})

            bits_per_second = udp.get(
                "bits_per_second", 0
            )

            jitter_ms = udp.get(
                "jitter_ms", 0
            )

            lost_packets = udp.get(
                "lost_packets", 0
            )

            total_packets = udp.get(
                "packets", 0
            )

            received_mbps = bits_per_second / 1_000_000

            if total_packets > 0:
                packet_loss = (
                    lost_packets / total_packets
                ) * 100
            else:
                packet_loss = 0

            results.append({
                "timestamp":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                "priority": name,
                "port": port,
                "offered_mbps": OFFERED_RATE,
                "received_mbps":
                    round(received_mbps, 2),
                "packet_loss_percent":
                    round(packet_loss, 2),
                "jitter_ms":
                    round(jitter_ms, 3)
            })

        except subprocess.TimeoutExpired:

            process.kill()

            print(
                f"{name}: TIMEOUT"
            )

        except Exception as e:

            print(
                f"{name}: ERROR - {e}"
            )

    # --------------------------------------------------------
    # Display results
    # --------------------------------------------------------

    print("\n")
    print("=" * 65)
    print("                 EXPERIMENT RESULTS")
    print("=" * 65)

    print(
        f"{'Priority':<12}"
        f"{'Offered':<12}"
        f"{'Received':<12}"
        f"{'Loss':<12}"
        f"{'Jitter':<12}"
    )

    print("-" * 65)

    for result in results:

        print(
            f"{result['priority']:<12}"
            f"{result['offered_mbps']:<12.2f}"
            f"{result['received_mbps']:<12.2f}"
            f"{result['packet_loss_percent']:<12.2f}"
            f"{result['jitter_ms']:<12.3f}"
        )

    print("-" * 65)

    total_received = sum(
        r["received_mbps"]
        for r in results
    )

    print(
        f"{'TOTAL':<12}"
        f"{'60.00':<12}"
        f"{total_received:<12.2f}"
    )

    # --------------------------------------------------------
    # Save CSV
    # --------------------------------------------------------

    os.makedirs("data", exist_ok=True)

    with open(
        OUTPUT_FILE,
        "w",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp",
                "priority",
                "port",
                "offered_mbps",
                "received_mbps",
                "packet_loss_percent",
                "jitter_ms"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nResults saved to:")
    print(OUTPUT_FILE)

    print("\n" + "=" * 65)
    print("SIMULTANEOUS EXPERIMENT COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    run_all_tests()
