
import csv
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone

import psutil

try:
    from .wifi_monitor import get_wifi_info
except ImportError:
    from wifi_monitor import get_wifi_info


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

CSV_FILE = os.path.join(
    DATA_DIR,
    "live_network_metrics.csv"
)

JSON_FILE = os.path.join(
    DATA_DIR,
    "latest_metrics.json"
)

SAMPLE_INTERVAL = 1.0
PING_COUNT = 2


def get_default_interface_and_gateway():

    try:

        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )

        line = result.stdout.strip()

        if not line:
            return None, None

        parts = line.split()

        gateway = None
        interface = None

        if "via" in parts:
            gateway = parts[
                parts.index("via") + 1
            ]

        if "dev" in parts:
            interface = parts[
                parts.index("dev") + 1
            ]

        return interface, gateway

    except Exception:
        return None, None


def get_interface_ip(interface):

    if not interface:
        return None

    try:

        addresses = psutil.net_if_addrs().get(
            interface,
            []
        )

        for address in addresses:

            if address.family == socket.AF_INET:
                return address.address

    except Exception:
        pass

    return None


def get_interface_stats(interface):

    if not interface:
        return None

    counters = psutil.net_io_counters(
        pernic=True
    )

    return counters.get(interface)


def calculate_rate(
    previous,
    current,
    elapsed_seconds
):

    if (
        previous is None
        or current is None
        or elapsed_seconds <= 0
    ):
        return 0.0

    byte_delta = current - previous

    if byte_delta < 0:
        return 0.0

    return (
        byte_delta * 8
    ) / elapsed_seconds / 1_000_000


def ping_gateway(gateway):
    """
    Measure latency, packet loss and jitter.

    The gateway is tried first because it directly measures
    the local network path. External targets are used as
    fallback.

    A failed measurement is recorded as None, not 100% loss,
    because failure to obtain a measurement is not the same
    as confirmed packet loss.
    """

    # Prefer a reachable external target first.
    # The WSL gateway may not respond to ICMP and can add avoidable delay.
    targets = ["1.1.1.1", "8.8.8.8", gateway]

    for target in targets:
        try:
            result = subprocess.run(
                [
                    "ping",
                    "-c",
                    str(PING_COUNT),
                    "-W",
                    "1",
                    target,
                ],
                capture_output=True,
                text=True,
                timeout=8,
            )

            output = result.stdout

            latency = None
            packet_loss = None
            jitter = None

            for line in output.splitlines():

                # Example:
                # 0% packet loss
                if "packet loss" in line:
                    try:
                        loss_part = line.split("%")[0]
                        packet_loss = float(loss_part.split()[-1])
                    except Exception:
                        pass

                # Example:
                # rtt min/avg/max/mdev = 8.554/9.552/10.876/0.837 ms
                if "min/avg/max" in line and "=" in line:
                    try:
                        values = line.split("=")[1].strip()
                        values = values.split()[0]

                        min_rtt, avg_rtt, max_rtt, mdev = [
                            float(x) for x in values.split("/")
                        ]

                        latency = avg_rtt
                        jitter = mdev
                    except Exception:
                        pass

            # Accept only a genuinely parsed measurement.
            if latency is not None and packet_loss is not None:
                return {
                    "latency_ms": latency,
                    "packet_loss_percent": packet_loss,
                    "jitter_ms": jitter,
                }

        except Exception:
            continue

    # Measurement failed.
    # IMPORTANT: None means "not measured", not 100% packet loss.
    return {
        "latency_ms": None,
        "packet_loss_percent": None,
        "jitter_ms": None,
    }


def collect_metrics(
    previous_stats=None,
    previous_time=None
):

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    interface, gateway = (
        get_default_interface_and_gateway()
    )

    local_ip = get_interface_ip(
        interface
    )

    current_stats = get_interface_stats(
        interface
    )

    now = time.monotonic()

    elapsed = None

    if previous_time is not None:
        elapsed = now - previous_time

    rx_mbps = 0.0
    tx_mbps = 0.0

    if (
        previous_stats
        and current_stats
        and elapsed
    ):

        rx_mbps = calculate_rate(
            previous_stats.bytes_recv,
            current_stats.bytes_recv,
            elapsed,
        )

        tx_mbps = calculate_rate(
            previous_stats.bytes_sent,
            current_stats.bytes_sent,
            elapsed,
        )

    ping_data = ping_gateway(
        gateway
    )

    wifi_data = get_wifi_info()

    metrics = {

        "timestamp": timestamp,

        "network": {

            "interface": interface,

            "local_ip": local_ip,

            "gateway": gateway,

            "rx_mbps": round(
                rx_mbps,
                3
            ),

            "tx_mbps": round(
                tx_mbps,
                3
            ),

            "rx_bytes": (
                current_stats.bytes_recv
                if current_stats
                else None
            ),

            "tx_bytes": (
                current_stats.bytes_sent
                if current_stats
                else None
            ),

            "rx_packets": (
                current_stats.packets_recv
                if current_stats
                else None
            ),

            "tx_packets": (
                current_stats.packets_sent
                if current_stats
                else None
            ),

            "rx_errors": (
                current_stats.errin
                if current_stats
                else None
            ),

            "tx_errors": (
                current_stats.errout
                if current_stats
                else None
            ),

            "rx_dropped": (
                current_stats.dropin
                if current_stats
                else None
            ),

            "tx_dropped": (
                current_stats.dropout
                if current_stats
                else None
            ),
        },

        "quality": {

            "latency_ms":
                ping_data[
                    "latency_ms"
                ],

            "packet_loss_percent":
                ping_data[
                    "packet_loss_percent"
                ],

            "jitter_ms":
                ping_data[
                    "jitter_ms"
                ],
        },

        "wifi": wifi_data,
    }

    return (
        metrics,
        current_stats,
        now
    )


def initialize_csv():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    if os.path.exists(CSV_FILE):
        return

    fieldnames = [

        "timestamp",

        "interface",
        "local_ip",
        "gateway",

        "rx_mbps",
        "tx_mbps",

        "rx_bytes",
        "tx_bytes",

        "rx_packets",
        "tx_packets",

        "rx_errors",
        "tx_errors",

        "rx_dropped",
        "tx_dropped",

        "latency_ms",
        "packet_loss_percent",
        "jitter_ms",

        "wifi_interface",
        "wifi_state",
        "ssid",
        "band",
        "radio_type",
        "channel",

        "receive_rate_mbps",
        "transmit_rate_mbps",

        "signal_percent",
        "rssi_dbm",
    ]

    with open(
        CSV_FILE,
        "w",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()


def flatten_metrics(metrics):

    network = metrics["network"]
    quality = metrics["quality"]
    wifi = metrics["wifi"]

    return {

        "timestamp":
            metrics["timestamp"],

        "interface":
            network["interface"],

        "local_ip":
            network["local_ip"],

        "gateway":
            network["gateway"],

        "rx_mbps":
            network["rx_mbps"],

        "tx_mbps":
            network["tx_mbps"],

        "rx_bytes":
            network["rx_bytes"],

        "tx_bytes":
            network["tx_bytes"],

        "rx_packets":
            network["rx_packets"],

        "tx_packets":
            network["tx_packets"],

        "rx_errors":
            network["rx_errors"],

        "tx_errors":
            network["tx_errors"],

        "rx_dropped":
            network["rx_dropped"],

        "tx_dropped":
            network["tx_dropped"],

        "latency_ms":
            quality["latency_ms"],

        "packet_loss_percent":
            quality[
                "packet_loss_percent"
            ],

        "jitter_ms":
            quality["jitter_ms"],

        "wifi_interface":
            wifi.get("interface"),

        "wifi_state":
            wifi.get("state"),

        "ssid":
            wifi.get("ssid"),

        "band":
            wifi.get("band"),

        "radio_type":
            wifi.get("radio_type"),

        "channel":
            wifi.get("channel"),

        "receive_rate_mbps":
            wifi.get(
                "receive_rate_mbps"
            ),

        "transmit_rate_mbps":
            wifi.get(
                "transmit_rate_mbps"
            ),

        "signal_percent":
            wifi.get(
                "signal_percent"
            ),

        "rssi_dbm":
            wifi.get(
                "rssi_dbm"
            ),
    }


def save_metrics(metrics):

    flat = flatten_metrics(
        metrics
    )

    with open(
        CSV_FILE,
        "a",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=flat.keys()
        )

        writer.writerow(flat)

    temporary_file = (
        JSON_FILE + ".tmp"
    )

    with open(
        temporary_file,
        "w"
    ) as file:

        json.dump(
            metrics,
            file,
            indent=2
        )

    os.replace(
        temporary_file,
        JSON_FILE
    )


def print_metrics(metrics):

    network = metrics["network"]
    quality = metrics["quality"]
    wifi = metrics["wifi"]

    print()
    print("=" * 70)
    print("             LIVE NETWORK TELEMETRY")
    print("=" * 70)

    print(
        f"Timestamp       : "
        f"{metrics['timestamp']}"
    )

    print(
        f"Interface       : "
        f"{network['interface']}"
    )

    print(
        f"Local IP        : "
        f"{network['local_ip']}"
    )

    print(
        f"Gateway         : "
        f"{network['gateway']}"
    )

    print("-" * 70)
    print("NETWORK TRAFFIC")
    print("-" * 70)

    print(
        f"RX Throughput   : "
        f"{network['rx_mbps']} Mbps"
    )

    print(
        f"TX Throughput   : "
        f"{network['tx_mbps']} Mbps"
    )

    print(
        f"RX Packets      : "
        f"{network['rx_packets']}"
    )

    print(
        f"TX Packets      : "
        f"{network['tx_packets']}"
    )

    print("-" * 70)
    print("NETWORK QUALITY")
    print("-" * 70)

    print(
        f"Latency         : "
        f"{quality['latency_ms']} ms"
    )

    print(
        f"Packet Loss     : "
        f"{quality['packet_loss_percent']} %"
    )

    print(
        f"Jitter          : "
        f"{quality['jitter_ms']} ms"
    )

    print("-" * 70)
    print("WI-FI")
    print("-" * 70)

    print(
        f"Adapter         : "
        f"{wifi.get('interface')}"
    )

    print(
        f"State           : "
        f"{wifi.get('state')}"
    )

    print(
        f"SSID            : "
        f"{wifi.get('ssid')}"
    )

    print(
        f"Band            : "
        f"{wifi.get('band')}"
    )

    print(
        f"Radio           : "
        f"{wifi.get('radio_type')}"
    )

    print(
        f"Channel         : "
        f"{wifi.get('channel')}"
    )

    print(
        f"Signal          : "
        f"{wifi.get('signal_percent')} %"
    )

    print(
        f"RSSI            : "
        f"{wifi.get('rssi_dbm')} dBm"
    )

    print(
        f"RX Link Rate    : "
        f"{wifi.get('receive_rate_mbps')} Mbps"
    )

    print(
        f"TX Link Rate    : "
        f"{wifi.get('transmit_rate_mbps')} Mbps"
    )

    print("=" * 70)


def main():

    print("=" * 70)
    print("       INTELLIGENT NETWORK TELEMETRY COLLECTOR")
    print("=" * 70)

    print()
    print(
        "Sampling interval:",
        SAMPLE_INTERVAL,
        "seconds"
    )

    print("Press CTRL+C to stop.")
    print()

    initialize_csv()

    previous_stats = None
    previous_time = None

    try:

        while True:

            (
                metrics,
                current_stats,
                current_time
            ) = collect_metrics(
                previous_stats,
                previous_time
            )

            print_metrics(
                metrics
            )

            save_metrics(
                metrics
            )

            previous_stats = (
                current_stats
            )

            previous_time = (
                current_time
            )

            time.sleep(
                SAMPLE_INTERVAL
            )

    except KeyboardInterrupt:

        print()
        print(
            "Telemetry collector stopped."
        )


if __name__ == "__main__":
    main()