import csv
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FEATURE_FILE = PROJECT_ROOT / "data" / "live_features.csv"
MODEL_FILE = PROJECT_ROOT / "prediction" / "controlled_congestion_model.pkl"

STATE_FILE = PROJECT_ROOT / "data" / "controller_state.json"
EVENT_FILE = PROJECT_ROOT / "data" / "controller_events.jsonl"

INTERFACE = "eth0"
ROOT_CAPACITY_MBPS = 20.0

CHECK_INTERVAL = 3.0

# Traffic-class ports
HIGH_PORT = 5201
MEDIUM_PORT = 5202
LOW_PORT = 5203


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return default

        return value
    except Exception:
        return default


def atomic_json_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(path.suffix + ".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    os.replace(temp_path, path)


def append_event(event):
    EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(EVENT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def run_command(command, sudo=False):
    if sudo:
        command = ["sudo"] + command

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.returncode, result.stdout.strip(), result.stderr.strip()

    except Exception as exc:
        return 1, "", str(exc)


# ---------------------------------------------------------------------
# Live data
# ---------------------------------------------------------------------

def read_latest_feature():
    if not FEATURE_FILE.exists():
        return None

    try:
        with open(FEATURE_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            return None

        return rows[-1]

    except Exception:
        return None


# ---------------------------------------------------------------------
# ML model
# ---------------------------------------------------------------------

def load_model():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_FILE}"
        )

    bundle = joblib.load(MODEL_FILE)

    if isinstance(bundle, dict):
        model = bundle["model"]
        features = bundle.get("features", [])
        labels = bundle.get("labels", [])

    else:
        model = bundle
        features = [
            "latency_ms",
            "packet_loss_percent",
            "jitter_ms",
            "rx_mbps",
            "tx_mbps",
            "total_traffic_mbps",
        ]
        labels = list(model.classes_)

    return model, features, labels


MODEL, MODEL_FEATURES, MODEL_LABELS = load_model()


def build_model_input(row):
    values = []

    for feature in MODEL_FEATURES:
        values.append(
            safe_float(row.get(feature), 0.0)
        )

    return [values]


def predict(row):
    try:
        X = build_model_input(row)

        prediction = MODEL.predict(X)[0]

        probabilities = MODEL.predict_proba(X)[0]

        classes = list(MODEL.classes_)

        probability_map = {
            str(label): round(float(prob), 6)
            for label, prob in zip(classes, probabilities)
        }

        confidence = max(probability_map.values()) if probability_map else 0.0

        return (
            str(prediction),
            confidence,
            probability_map
        )

    except Exception as exc:
        return (
            "UNKNOWN",
            0.0,
            {
                "NORMAL": 0.0,
                "WARNING": 0.0,
                "CONGESTED": 0.0,
            }
        )


# ---------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------

def safety_validation(row, ml_prediction):
    traffic = safe_float(row.get("total_traffic_mbps"))
    latency = safe_float(row.get("latency_ms"))
    jitter = safe_float(row.get("jitter_ms"))
    packet_loss = safe_float(row.get("packet_loss_percent"))

    severe_conditions = []

    if traffic >= 20:
        severe_conditions.append(
            f"traffic {traffic:.2f} Mbps >= 20 Mbps"
        )

    if latency >= 40:
        severe_conditions.append(
            f"latency {latency:.2f} ms >= 40 ms"
        )

    if jitter >= 20:
        severe_conditions.append(
            f"jitter {jitter:.2f} ms >= 20 ms"
        )

    if packet_loss >= 5:
        severe_conditions.append(
            f"packet loss {packet_loss:.2f}% >= 5%"
        )

    warning_conditions = []

    if traffic >= 10:
        warning_conditions.append(
            f"traffic {traffic:.2f} Mbps >= 10 Mbps"
        )

    if latency >= 20:
        warning_conditions.append(
            f"latency {latency:.2f} ms >= 20 ms"
        )

    if jitter >= 10:
        warning_conditions.append(
            f"jitter {jitter:.2f} ms >= 10 ms"
        )

    if packet_loss >= 1:
        warning_conditions.append(
            f"packet loss {packet_loss:.2f}% >= 1%"
        )

    if severe_conditions:
        decision = "CONGESTED"
        reason = "Severe live network condition: " + "; ".join(
            severe_conditions
        )

    elif ml_prediction == "CONGESTED" and warning_conditions:
        decision = "WARNING"
        reason = (
            "ML predicted CONGESTED, but live measurements "
            "only satisfy warning-level conditions."
        )

    elif ml_prediction == "CONGESTED":
        decision = "NORMAL"
        reason = (
            "ML predicted CONGESTED but live measurements "
            "do not support degradation."
        )

    elif ml_prediction == "WARNING" and warning_conditions:
        decision = "WARNING"
        reason = "Live warning conditions confirmed."

    elif ml_prediction == "WARNING":
        decision = "NORMAL"
        reason = (
            "ML predicted WARNING but live measurements "
            "do not support degradation."
        )

    elif ml_prediction == "NORMAL":
        decision = "NORMAL"
        reason = "Live measurements support NORMAL operation."

    else:
        decision = "NORMAL"
        reason = "Unknown prediction; safe fallback applied."

    return decision, reason


# ---------------------------------------------------------------------
# Live congestion severity
# ---------------------------------------------------------------------

def calculate_congestion_score(row):
    traffic = safe_float(row.get("total_traffic_mbps"))
    latency = safe_float(row.get("latency_ms"))
    jitter = safe_float(row.get("jitter_ms"))
    packet_loss = safe_float(row.get("packet_loss_percent"))

    traffic_score = min(traffic / ROOT_CAPACITY_MBPS, 1.0)
    latency_score = min(latency / 50.0, 1.0)
    jitter_score = min(jitter / 25.0, 1.0)
    loss_score = min(packet_loss / 5.0, 1.0)

    score = (
        traffic_score * 0.45
        + latency_score * 0.25
        + jitter_score * 0.20
        + loss_score * 0.10
    )

    return max(0.0, min(score, 1.0))


# ---------------------------------------------------------------------
# Dynamic adaptive policy
# ---------------------------------------------------------------------

def calculate_policy(status, congestion_score):
    """
    Returns live adaptive guaranteed rates.

    The total guaranteed allocation always remains 20 Mbps.
    """

    score = max(0.0, min(congestion_score, 1.0))

    if status == "NORMAL":
        # Gradually moves toward more balanced operation.
        high = 8.0 + (score * 1.0)
        medium = 7.0 - (score * 0.5)
        low = ROOT_CAPACITY_MBPS - high - medium

    elif status == "WARNING":
        # More capacity moves toward high-priority traffic.
        high = 9.0 + (score * 2.0)
        medium = 6.0 - (score * 1.0)
        low = ROOT_CAPACITY_MBPS - high - medium

    elif status == "CONGESTED":
        # Strong preference toward high-priority traffic.
        high = 11.0 + (score * 1.0)
        medium = 5.0
        low = ROOT_CAPACITY_MBPS - high - medium

    else:
        high = 8.0
        medium = 7.0
        low = 5.0

    # Safety bounds.
    high = max(6.0, min(high, 12.0))
    medium = max(4.0, min(medium, 7.0))
    low = max(2.0, min(low, 6.0))

    # Normalize exactly to root capacity.
    total = high + medium + low

    if abs(total - ROOT_CAPACITY_MBPS) > 0.001:
        low += ROOT_CAPACITY_MBPS - total

    return {
        "high": round(high, 2),
        "medium": round(medium, 2),
        "low": round(low, 2),
    }


# ---------------------------------------------------------------------
# Linux tc
# ---------------------------------------------------------------------

def tc_command(args):
    return run_command(
        ["tc"] + args,
        sudo=True
    )


def remove_tc():
    code, out, err = tc_command(
        ["qdisc", "del", "dev", INTERFACE, "root"]
    )

    # Absence of root qdisc is not an error for our controller.
    return True


def apply_policy(policy):
    high = policy["high"]
    medium = policy["medium"]
    low = policy["low"]

    remove_tc()

    commands = [
        [
            "qdisc",
            "replace",
            "dev",
            INTERFACE,
            "root",
            "handle",
            "1:",
            "htb",
            "default",
            "30",
        ],
        [
            "class",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:",
            "classid",
            "1:1",
            "htb",
            "rate",
            f"{ROOT_CAPACITY_MBPS:.0f}mbit",
        ],
        [
            "class",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:1",
            "classid",
            "1:10",
            "htb",
            "rate",
            f"{high:.2f}mbit",
            "ceil",
            f"{ROOT_CAPACITY_MBPS:.0f}mbit",
            "prio",
            "1",
        ],
        [
            "class",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:1",
            "classid",
            "1:20",
            "htb",
            "rate",
            f"{medium:.2f}mbit",
            "ceil",
            f"{ROOT_CAPACITY_MBPS:.0f}mbit",
            "prio",
            "2",
        ],
        [
            "class",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:1",
            "classid",
            "1:30",
            "htb",
            "rate",
            f"{low:.2f}mbit",
            "ceil",
            f"{ROOT_CAPACITY_MBPS:.0f}mbit",
            "prio",
            "3",
        ],

        [
            "qdisc",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:10",
            "handle",
            "110:",
            "sfq",
        ],
        [
            "qdisc",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:20",
            "handle",
            "120:",
            "sfq",
        ],
        [
            "qdisc",
            "replace",
            "dev",
            INTERFACE,
            "parent",
            "1:30",
            "handle",
            "130:",
            "sfq",
        ],

        [
            "filter",
            "replace",
            "dev",
            INTERFACE,
            "protocol",
            "ip",
            "parent",
            "1:",
            "prio",
            "1",
            "u32",
            "match",
            "ip",
            "protocol",
            "17",
            "0xff",
            "flowid",
            "1:30",
        ],

        [
            "filter",
            "replace",
            "dev",
            INTERFACE,
            "protocol",
            "ip",
            "parent",
            "1:",
            "prio",
            "1",
            "u32",
            "match",
            "ip",
            "dport",
            str(HIGH_PORT),
            "0xffff",
            "flowid",
            "1:10",
        ],

        [
            "filter",
            "replace",
            "dev",
            INTERFACE,
            "protocol",
            "ip",
            "parent",
            "1:",
            "prio",
            "2",
            "u32",
            "match",
            "ip",
            "dport",
            str(MEDIUM_PORT),
            "0xffff",
            "flowid",
            "1:20",
        ],

        [
            "filter",
            "replace",
            "dev",
            INTERFACE,
            "protocol",
            "ip",
            "parent",
            "1:",
            "prio",
            "3",
            "u32",
            "match",
            "ip",
            "dport",
            str(LOW_PORT),
            "0xffff",
            "flowid",
            "1:30",
        ],
    ]

    errors = []

    for command in commands:
        code, out, err = tc_command(command)

        if code != 0:
            errors.append({
                "command": "tc " + " ".join(command),
                "error": err
            })

    return len(errors) == 0, errors


# ---------------------------------------------------------------------
# tc observation
# ---------------------------------------------------------------------

def get_tc_snapshot():
    commands = {
        "qdisc": ["qdisc", "show", "dev", INTERFACE],
        "classes": ["class", "show", "dev", INTERFACE],
        "class_stats": ["-s", "class", "show", "dev", INTERFACE],
        "filters": ["filter", "show", "dev", INTERFACE],
    }

    snapshot = {}

    for name, command in commands.items():
        code, out, err = tc_command(command)

        snapshot[name] = {
            "available": code == 0,
            "output": out if code == 0 else err
        }

    return snapshot


# ---------------------------------------------------------------------
# State publication
# ---------------------------------------------------------------------

def publish_state(
    row,
    prediction,
    confidence,
    probabilities,
    decision,
    reason,
    score,
    policy,
    applied,
    tc_snapshot,
    cycle,
):
    state = {
        "timestamp": now_iso(),
        "controller_cycle": cycle,
        "interface": INTERFACE,

        "telemetry": {
            "rx_mbps": safe_float(row.get("rx_mbps")),
            "tx_mbps": safe_float(row.get("tx_mbps")),
            "total_traffic_mbps": safe_float(
                row.get("total_traffic_mbps")
            ),
            "latency_ms": safe_float(row.get("latency_ms")),
            "jitter_ms": safe_float(row.get("jitter_ms")),
            "packet_loss_percent": safe_float(
                row.get("packet_loss_percent")
            ),
            "signal_percent": safe_float(
                row.get("signal_percent")
            ),
            "rssi_dbm": safe_float(
                row.get("rssi_dbm")
            ),
        },

        "ml": {
            "prediction": prediction,
            "confidence": round(confidence, 6),
            "probabilities": probabilities,
            "model": "Random Forest",
            "model_source": "controlled_congestion_model.pkl",
        },

        "decision": {
            "status": decision,
            "reason": reason,
            "congestion_score": round(score, 6),
        },

        "policy": {
            "high_mbps": policy["high"],
            "medium_mbps": policy["medium"],
            "low_mbps": policy["low"],
            "root_mbps": ROOT_CAPACITY_MBPS,
            "applied": applied,
            "type": "adaptive",
        },

        "tc": tc_snapshot,

        "runtime": {
            "interval_seconds": CHECK_INTERVAL,
            "running": True,
        },
    }

    atomic_json_write(STATE_FILE, state)

    return state


# ---------------------------------------------------------------------
# Controller cycle
# ---------------------------------------------------------------------

def controller_cycle(previous_decision, previous_policy, cycle):
    row = read_latest_feature()

    if row is None:
        return previous_decision, previous_policy, cycle

    prediction, confidence, probabilities = predict(row)

    decision, reason = safety_validation(
        row,
        prediction
    )

    score = calculate_congestion_score(row)

    policy = calculate_policy(
        decision,
        score
    )

    policy_changed = (
        previous_policy is None
        or any(
            abs(
                policy[key] - previous_policy[key]
            ) > 0.01
            for key in ["high", "medium", "low"]
        )
        or decision != previous_decision
    )

    applied = False

    if policy_changed:
        success, errors = apply_policy(policy)

        applied = success

        append_event({
            "timestamp": now_iso(),
            "cycle": cycle,
            "type": "ADAPT",
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "decision": decision,
            "reason": reason,
            "policy": policy,
            "success": success,
            "errors": errors,
        })

    tc_snapshot = get_tc_snapshot()

    state = publish_state(
        row=row,
        prediction=prediction,
        confidence=confidence,
        probabilities=probabilities,
        decision=decision,
        reason=reason,
        score=score,
        policy=policy,
        applied=applied,
        tc_snapshot=tc_snapshot,
        cycle=cycle,
    )

    # Always record the measurement/prediction cycle.
    append_event({
        "timestamp": now_iso(),
        "cycle": cycle,
        "type": "CYCLE",
        "telemetry": state["telemetry"],
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "decision": decision,
        "reason": reason,
        "congestion_score": round(score, 4),
        "policy": policy,
        "policy_changed": policy_changed,
    })

    return decision, policy, cycle + 1


# ---------------------------------------------------------------------
# Main runtime
# ---------------------------------------------------------------------

def main():
    print()
    print("=" * 72)
    print(" INTELLIGENT LIVE NETWORK CLOSED-LOOP CONTROLLER")
    print("=" * 72)
    print(f"Interface       : {INTERFACE}")
    print(f"Root capacity   : {ROOT_CAPACITY_MBPS} Mbps")
    print(f"Cycle interval  : {CHECK_INTERVAL} seconds")
    print(f"Model           : {MODEL_FILE}")
    print(f"Feature source  : {FEATURE_FILE}")
    print()
    print("The controller will continuously:")
    print("  LIVE DATA -> ML -> SAFETY -> ADAPT -> TC -> FEEDBACK")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 72)

    previous_decision = None
    previous_policy = None
    cycle = 1

    try:
        while True:
            (
                previous_decision,
                previous_policy,
                cycle
            ) = controller_cycle(
                previous_decision,
                previous_policy,
                cycle
            )

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print()
        print("Controller stopped.")

        # We deliberately do not automatically remove tc here.
        # This allows the last applied policy to remain observable.
        print(
            "The last Linux tc policy remains active. "
            "Use traffic_manager.py remove when cleanup is required."
        )


if __name__ == "__main__":
    main()
