
import subprocess
import sys

INTERFACE = "eth0"

# Total available bandwidth during the experiment
TOTAL_BANDWIDTH = "20mbit"

# Bandwidth allocation
HIGH_BANDWIDTH = "12mbit"
MEDIUM_BANDWIDTH = "5mbit"
LOW_BANDWIDTH = "3mbit"


def run_command(command, allow_failure=False):
    print("\n$ " + " ".join(command))

    result = subprocess.run(
        command,
        text=True,
        capture_output=True
    )

    if result.stdout:
        print(result.stdout.strip())

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip())

        if not allow_failure:
            raise RuntimeError("Command failed.")

    return result


def remove_existing_qdisc():
    """
    Remove an existing root qdisc if one exists.

    tc may return an error when the interface is already using its
    default/root configuration. That situation is harmless here.
    """

    result = subprocess.run(
        [
            "sudo", "tc", "qdisc", "del",
            "dev", INTERFACE,
            "root"
        ],
        text=True,
        capture_output=True
    )

    if result.returncode == 0:
        print("Existing root qdisc removed.")
    else:
        print("No removable custom root qdisc found. Continuing.")


def setup_priority_queue():
    print("\n==========================================")
    print(" NETWORK TRAFFIC MANAGEMENT SYSTEM")
    print("==========================================")
    print(f"Interface        : {INTERFACE}")
    print(f"Total bandwidth  : {TOTAL_BANDWIDTH}")
    print("------------------------------------------")
    print(f"HIGH priority    : {HIGH_BANDWIDTH}")
    print(f"MEDIUM priority  : {MEDIUM_BANDWIDTH}")
    print(f"LOW priority     : {LOW_BANDWIDTH}")
    print("------------------------------------------")

    # ---------------------------------------------------------
    # 1. Remove any previous custom configuration
    # ---------------------------------------------------------
    remove_existing_qdisc()

    # ---------------------------------------------------------
    # 2. Create HTB root qdisc
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "qdisc", "add",
        "dev", INTERFACE,
        "root",
        "handle", "1:",
        "htb",
        "default", "30"
    ])

    # ---------------------------------------------------------
    # 3. Root class: 20 Mbps
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "class", "add",
        "dev", INTERFACE,
        "parent", "1:",
        "classid", "1:1",
        "htb",
        "rate", TOTAL_BANDWIDTH,
        "ceil", TOTAL_BANDWIDTH
    ])

    # ---------------------------------------------------------
    # 4. HIGH class: 12 Mbps
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "class", "add",
        "dev", INTERFACE,
        "parent", "1:1",
        "classid", "1:10",
        "htb",
        "rate", HIGH_BANDWIDTH,
        "ceil", TOTAL_BANDWIDTH,
        "prio", "1"
    ])

    # ---------------------------------------------------------
    # 5. MEDIUM class: 5 Mbps
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "class", "add",
        "dev", INTERFACE,
        "parent", "1:1",
        "classid", "1:20",
        "htb",
        "rate", MEDIUM_BANDWIDTH,
        "ceil", TOTAL_BANDWIDTH,
        "prio", "2"
    ])

    # ---------------------------------------------------------
    # 6. LOW class: 3 Mbps
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "class", "add",
        "dev", INTERFACE,
        "parent", "1:1",
        "classid", "1:30",
        "htb",
        "rate", LOW_BANDWIDTH,
        "ceil", TOTAL_BANDWIDTH,
        "prio", "3"
    ])

    # ---------------------------------------------------------
    # 7. Queue discipline for each class
    # ---------------------------------------------------------
    for class_id, handle in [
        ("1:10", "110"),
        ("1:20", "120"),
        ("1:30", "130")
    ]:
        run_command([
            "sudo", "tc", "qdisc", "add",
            "dev", INTERFACE,
            "parent", class_id,
            "handle", handle,
            "sfq"
        ])

    # ---------------------------------------------------------
    # 8. UDP destination port 5201 -> HIGH
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "filter", "add",
        "dev", INTERFACE,
        "protocol", "ip",
        "parent", "1:",
        "prio", "1",
        "u32",
        "match", "ip", "protocol", "17", "0xff",
        "match", "ip", "dport", "5201", "0xffff",
        "flowid", "1:10"
    ])

    # ---------------------------------------------------------
    # 9. UDP destination port 5202 -> MEDIUM
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "filter", "add",
        "dev", INTERFACE,
        "protocol", "ip",
        "parent", "1:",
        "prio", "2",
        "u32",
        "match", "ip", "protocol", "17", "0xff",
        "match", "ip", "dport", "5202", "0xffff",
        "flowid", "1:20"
    ])

    # ---------------------------------------------------------
    # 10. UDP destination port 5203 -> LOW
    # ---------------------------------------------------------
    run_command([
        "sudo", "tc", "filter", "add",
        "dev", INTERFACE,
        "protocol", "ip",
        "parent", "1:",
        "prio", "3",
        "u32",
        "match", "ip", "protocol", "17", "0xff",
        "match", "ip", "dport", "5203", "0xffff",
        "flowid", "1:30"
    ])

    print("\n==========================================")
    print(" TRAFFIC MANAGEMENT CONFIGURED")
    print("==========================================")
    print("HIGH   -> UDP port 5201 -> 12 Mbps")
    print("MEDIUM -> UDP port 5202 ->  5 Mbps")
    print("LOW    -> UDP port 5203 ->  3 Mbps")
    print("==========================================\n")


def show_configuration():
    print("\n==========================================")
    print(" CURRENT TRAFFIC MANAGEMENT")
    print("==========================================")

    print("\n--- Qdiscs ---")

    run_command([
        "sudo", "tc", "qdisc", "show",
        "dev", INTERFACE
    ])

    print("\n--- Classes ---")

    run_command([
        "sudo", "tc", "class", "show",
        "dev", INTERFACE
    ])

    print("\n--- Class Statistics ---")

    run_command([
        "sudo", "tc", "-s", "class", "show",
        "dev", INTERFACE
    ])

    print("\n--- Filters ---")

    run_command([
        "sudo", "tc", "filter", "show",
        "dev", INTERFACE,
        "parent", "1:"
    ])


def remove_management():
    print("\nRemoving traffic-management configuration...")

    result = subprocess.run(
        [
            "sudo", "tc", "qdisc", "del",
            "dev", INTERFACE,
            "root"
        ],
        text=True,
        capture_output=True
    )

    if result.returncode == 0:
        print("Traffic management removed successfully.")
    else:
        print("No custom traffic-management configuration found.")


def main():
    if len(sys.argv) < 2:
        print("""
Network Traffic Management System

Usage:

  python traffic_management/traffic_manager.py setup
  python traffic_management/traffic_manager.py show
  python traffic_management/traffic_manager.py remove

Commands:

  setup   Configure HIGH / MEDIUM / LOW traffic classes
  show    Display qdiscs, classes, counters and filters
  remove  Remove the custom traffic-management configuration
""")
        return

    command = sys.argv[1].lower()

    if command == "setup":
        setup_priority_queue()

    elif command == "show":
        show_configuration()

    elif command == "remove":
        remove_management()

    else:
        print("Unknown command.")
        print("Use: setup, show, or remove")


if __name__ == "__main__":
    main()
