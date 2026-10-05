import subprocess
import csv
import os
import time
from datetime import datetime

# ============================================================
# NETWORK PRIORITY TRAFFIC TEST
# ============================================================

TARGET = "192.168.16.1"
DURATION = 10

# Traffic classes
TRAFFIC = [
    {
        "name": "HIGH",
        "port": 5201,
        "offered_mbps": 20
    },
    {
        "name": "MEDIUM",
        "port": 5202,
        "offered_mbps": 20
    },
    {
        "name": "LOW",
        "port": 5203,
        "offered_mbps": 20
    }
]

OUTPUT_FILE = "data/priority_test_results.csv"


# ============================================================
# RUN IPERF3 TEST
# ============================================================

def run_test(name, port, offered_mbps):

    print("\n" + "=" * 55)
    print(f"Testing {name} PRIORITY traffic")
    print(f"Destination : {TARGET}")
    print(f"Port        : {port}")
    print(f"Offered     : {offered_mbps} Mbps")
    print("=" * 55)

    command = [
        "iperf3",
        "-c", TARGET,
        "-u",
        "-b", f"{offered_mbps}M",
        "-t", str(DURATION),
        "-p", str(port),
        "-J"
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=DURATION + 20
        )

        if result.returncode != 0:
            print("\nERROR: iPerf3 failed.")
            print(result.stderr)
            return None

        data = __import__("json").loads(result.stdout)

        end = data.get("end", {})

        # UDP results
        udp = end.get("sum", {})

        received_bps = udp.get("bits_per_second", 0)
        jitter_ms = udp.get("jitter_ms", 0)
        lost_packets = udp.get("lost_packets", 0)
        total_packets = udp.get("packets", 0)

        received_mbps = received_bps / 1_000_000

        if total_packets > 0:
            packet_loss = (lost_packets / total_packets) * 100
        else:
            packet_loss = 0

        print(f"\nRESULT: {name}")
        print(f"Received Throughput : {received_mbps:.2f} Mbps")
        print(f"Packet Loss         : {packet_loss:.2f}%")
        print(f"Jitter              : {jitter_ms:.3f} ms")

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "priority": name,
            "port": port,
            "offered_mbps": offered_mbps,
            "received_mbps": round(received_mbps, 2),
            "packet_loss_percent": round(packet_loss, 2),
            "jitter_ms": round(jitter_ms, 3)
        }

    except subprocess.TimeoutExpired:
        print("ERROR: Test timed out.")
        return None

    except Exception as e:
        print(f"ERROR: {e}")
        return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 60)
    print("      NETWORK PRIORITY TRAFFIC MANAGEMENT TEST")
    print("=" * 60)

    print("\nTraffic Management Configuration:")
    print("HIGH   : 12 Mbps")
    print("MEDIUM :  5 Mbps")
    print("LOW    :  3 Mbps")

    print("\nEach class will attempt to send 20 Mbps.")
    print("The traffic manager should enforce the configured limits.")

    input("\nPress ENTER to start the experiment...")

    results = []

    # --------------------------------------------------------
    # Run each priority class
    # --------------------------------------------------------

    for traffic in TRAFFIC:

        result = run_test(
            traffic["name"],
            traffic["port"],
            traffic["offered_mbps"]
        )

        if result is not None:
            results.append(result)

        time.sleep(2)

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

    if not results:
        print("\nNo results were collected.")
        print("Check whether the iPerf3 servers are running.")
        return

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

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print("\n")
    print("=" * 60)
    print("             EXPERIMENT SUMMARY")
    print("=" * 60)

    print(
        f"{'Priority':<12}"
        f"{'Offered':<12}"
        f"{'Received':<12}"
        f"{'Loss':<12}"
        f"{'Jitter':<12}"
    )

    print("-" * 60)

    for r in results:

        print(
            f"{r['priority']:<12}"
            f"{r['offered_mbps']:<12.2f}"
            f"{r['received_mbps']:<12.2f}"
            f"{r['packet_loss_percent']:<12.2f}"
            f"{r['jitter_ms']:<12.3f}"
        )

    print("=" * 60)

    print(f"\nResults saved to:")
    print(OUTPUT_FILE)

    print("\nExperiment completed successfully.")


if __name__ == "__main__":
    main()
