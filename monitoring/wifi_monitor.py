import json
import re
import subprocess


def get_wifi_info():
    """
    Collect physical Wi-Fi information from the Windows host.

    WSL sees a virtual network interface, so we query the
    Windows Wi-Fi adapter using netsh.
    """

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-Command",
                "netsh wlan show interfaces",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        output = result.stdout

        if not output.strip():
            return {
                "wifi_available": False,
                "error": "No Wi-Fi information returned",
            }

        info = {
            "wifi_available": True,
            "interface": None,
            "description": None,
            "state": None,
            "ssid": None,
            "band": None,
            "radio_type": None,
            "channel": None,
            "receive_rate_mbps": None,
            "transmit_rate_mbps": None,
            "signal_percent": None,
            "rssi_dbm": None,
        }

        patterns = {
            "interface": r"^\s*Name\s*:\s*(.+)$",
            "description": r"^\s*Description\s*:\s*(.+)$",
            "state": r"^\s*State\s*:\s*(.+)$",
            "ssid": r"^\s*SSID\s*:\s*(.+)$",
            "band": r"^\s*Band\s*:\s*(.+)$",
            "radio_type": r"^\s*Radio type\s*:\s*(.+)$",
            "channel": r"^\s*Channel\s*:\s*(\d+)",
            "receive_rate_mbps": (
                r"^\s*Receive rate \(Mbps\)\s*:\s*([\d.]+)"
            ),
            "transmit_rate_mbps": (
                r"^\s*Transmit rate \(Mbps\)\s*:\s*([\d.]+)"
            ),
            "signal_percent": r"^\s*Signal\s*:\s*(\d+)%",
            "rssi_dbm": r"^\s*Rssi\s*:\s*(-?\d+)",
        }

        for line in output.splitlines():
            for key, pattern in patterns.items():

                match = re.search(
                    pattern,
                    line,
                    re.IGNORECASE,
                )

                if not match:
                    continue

                value = match.group(1).strip()

                if key in {
                    "channel",
                    "receive_rate_mbps",
                    "transmit_rate_mbps",
                    "signal_percent",
                    "rssi_dbm",
                }:
                    try:
                        value = float(value)

                        if key == "channel":
                            value = int(value)

                    except ValueError:
                        pass

                info[key] = value

        return info

    except FileNotFoundError:
        return {
            "wifi_available": False,
            "error": "powershell.exe not available",
        }

    except subprocess.TimeoutExpired:
        return {
            "wifi_available": False,
            "error": "Wi-Fi query timed out",
        }

    except Exception as exc:
        return {
            "wifi_available": False,
            "error": str(exc),
        }


if __name__ == "__main__":
    result = get_wifi_info()

    print(json.dumps(result, indent=2))
