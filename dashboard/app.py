import csv
import io
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, send_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

LIVE_METRICS = DATA_DIR / "live_network_metrics.csv"
LIVE_FEATURES = DATA_DIR / "live_features.csv"
CONTROLLED_DATA = DATA_DIR / "controlled_experiments.csv"

STATE_FILE = DATA_DIR / "controller_state.json"
EVENT_FILE = DATA_DIR / "controller_events.jsonl"

INTERFACE = "eth0"

app = Flask(__name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def safe_float(value, default=0.0):
    try:
        value = float(value)

        if value != value:
            return default

        return value

    except Exception:
        return default


def read_csv_rows(path, limit=None):
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if limit:
            return rows[-limit:]

        return rows

    except Exception:
        return []


def read_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def read_events(limit=100):
    if not EVENT_FILE.exists():
        return []

    events = []

    try:
        with open(EVENT_FILE, "r", encoding="utf-8") as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    events.append(json.loads(line))

                except Exception:
                    continue

        return events[-limit:]

    except Exception:
        return []


# ---------------------------------------------------------------------
# tc observation
# ---------------------------------------------------------------------

def tc_output(command):
    try:
        result = subprocess.run(
            ["sudo", "-n", "tc"] + command,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()

        # Try without sudo for read-only observation.
        result = subprocess.run(
            ["tc"] + command,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()

        return result.stderr.strip()

    except Exception as exc:
        return str(exc)


def get_tc_live():
    return {
        "qdisc": tc_output(
            ["qdisc", "show", "dev", INTERFACE]
        ),
        "classes": tc_output(
            ["class", "show", "dev", INTERFACE]
        ),
        "class_stats": tc_output(
            ["-s", "class", "show", "dev", INTERFACE]
        ),
        "filters": tc_output(
            ["filter", "show", "dev", INTERFACE]
        ),
    }


def parse_tc_classes(text):
    classes = []

    current = None

    for line in text.splitlines():

        match = re.search(
            r"class htb (\S+) root rate ([0-9.]+)([KMG]?bit)"
            r".*ceil ([0-9.]+)([KMG]?bit)",
            line
        )

        if match:
            class_id = match.group(1)

            if class_id == "1:1":
                name = "ROOT"

            elif class_id == "1:10":
                name = "HIGH"

            elif class_id == "1:20":
                name = "MEDIUM"

            elif class_id == "1:30":
                name = "LOW"

            else:
                name = class_id

            current = {
                "class_id": class_id,
                "name": name,
                "rate": match.group(2) + match.group(3),
                "ceil": match.group(4) + match.group(5),
                "bytes": 0,
                "packets": 0,
                "overlimits": 0,
            }

            classes.append(current)
            continue

        stats = re.search(
            r"Sent (\d+) bytes (\d+) pkt.*"
            r"overlimits (\d+)",
            line
        )

        if stats and current:
            current["bytes"] = int(stats.group(1))
            current["packets"] = int(stats.group(2))
            current["overlimits"] = int(stats.group(3))

    return classes


# ---------------------------------------------------------------------
# API: current state
# ---------------------------------------------------------------------

@app.get("/api/metrics")
def api_metrics():
    """
    Unified live telemetry endpoint.

    IMPORTANT:
    The dashboard must consume the newest live telemetry from
    live_features.csv/live_network_metrics.csv.

    controller_state.json is used only for controller/ML information.
    It must never replace fresh telemetry with an older timestamp.
    """

    state = read_json(STATE_FILE, {})

    metrics_rows = read_csv_rows(
        LIVE_METRICS,
        limit=1
    )

    features_rows = read_csv_rows(
        LIVE_FEATURES,
        limit=1
    )

    latest_metrics = (
        metrics_rows[-1]
        if metrics_rows
        else {}
    )

    latest_features = (
        features_rows[-1]
        if features_rows
        else {}
    )

    # -------------------------------------------------------------
    # Prefer the newest feature-engine telemetry.
    # -------------------------------------------------------------

    def live_value(name, default=0.0):
        value = latest_features.get(name)

        if value in (None, ""):
            value = latest_metrics.get(name)

        return safe_float(value, default)

    live_timestamp = (
        latest_features.get("timestamp")
        or latest_metrics.get("timestamp")
    )

    # -------------------------------------------------------------
    # Controller state
    # -------------------------------------------------------------

    controller = state or {}

    controller_decision = controller.get(
        "decision",
        {}
    )

    controller_ml = controller.get(
        "ml",
        {}
    )

    controller_policy = controller.get(
        "policy",
        {}
    )

    controller_runtime = controller.get(
        "runtime",
        {}
    )

    # -------------------------------------------------------------
    # Determine live network state independently from stale
    # controller telemetry.
    # -------------------------------------------------------------

    traffic = live_value("total_traffic_mbps")
    latency = live_value("latency_ms")
    jitter = live_value("jitter_ms")
    loss = live_value("packet_loss_percent")

    severe = (
        traffic >= 20.0
        or latency >= 40.0
        or jitter >= 20.0
        or loss >= 5.0
    )

    warning = (
        traffic >= 10.0
        or latency >= 20.0
        or jitter >= 10.0
        or loss >= 1.0
    )

    if severe:
        live_state = "CONGESTED"
    elif warning:
        live_state = "WARNING"
    else:
        live_state = "NORMAL"

    # -------------------------------------------------------------
    # Live congestion score
    # -------------------------------------------------------------

    traffic_score = min(
        traffic / 20.0,
        1.0
    )

    latency_score = min(
        latency / 50.0,
        1.0
    )

    jitter_score = min(
        jitter / 25.0,
        1.0
    )

    loss_score = min(
        loss / 5.0,
        1.0
    )

    congestion_score = (
        traffic_score * 0.45
        + latency_score * 0.25
        + jitter_score * 0.20
        + loss_score * 0.10
    )

    # -------------------------------------------------------------
    # Return a FLAT live API contract for the dashboard.
    # -------------------------------------------------------------

    return jsonify({

        # ---------------------------------------------------------
        # Current live telemetry
        # ---------------------------------------------------------

        "timestamp": live_timestamp,

        "interface": (
            latest_features.get("interface")
            or latest_metrics.get("interface")
            or "eth0"
        ),

        "rx_mbps": live_value("rx_mbps"),

        "tx_mbps": live_value("tx_mbps"),

        "total_traffic_mbps": traffic,

        "latency_ms": latency,

        "jitter_ms": jitter,

        "packet_loss_percent": loss,

        "signal_percent": live_value(
            "signal_percent"
        ),

        "rssi_dbm": live_value(
            "rssi_dbm"
        ),

        "receive_rate_mbps": live_value(
            "receive_rate_mbps"
        ),

        "transmit_rate_mbps": live_value(
            "transmit_rate_mbps"
        ),

        "link_activity_percent": live_value(
            "link_activity_percent"
        ),

        # ---------------------------------------------------------
        # Live validated state
        # ---------------------------------------------------------

        "validated_state": live_state,

        "reason": (
            "Live telemetry indicates severe degradation."
            if severe
            else
            "Live telemetry indicates warning-level degradation."
            if warning
            else
            "Live telemetry currently indicates normal operation."
        ),

        "congestion_score": congestion_score,

        # ---------------------------------------------------------
        # ML information
        # ---------------------------------------------------------

        "ml_prediction": controller_ml.get(
            "prediction"
        ),

        "ml_confidence": safe_float(
            controller_ml.get("confidence")
        ),

        "probabilities": controller_ml.get(
            "probabilities",
            {}
        ),

        # ---------------------------------------------------------
        # Adaptive policy from controller
        # ---------------------------------------------------------

        "policy": controller_policy,

        # ---------------------------------------------------------
        # Controller information
        # ---------------------------------------------------------

        "controller_available": bool(
            controller_runtime.get(
                "running",
                False
            )
        ),

        "controller_cycle": controller.get(
            "controller_cycle"
        ),

        "controller_timestamp": controller.get(
            "timestamp"
        ),

        "controller_decision": controller_decision,

        # ---------------------------------------------------------
        # Raw data for diagnostics
        # ---------------------------------------------------------

        "raw_metrics": latest_metrics,

        "features": latest_features,

        "data_available": bool(
            latest_features or latest_metrics
        ),

        "server_time": datetime.now(
            timezone.utc
        ).isoformat(),
    })


# ---------------------------------------------------------------------
# API: history
# ---------------------------------------------------------------------

@app.get("/api/history")
def api_history():

    rows = read_csv_rows(
        LIVE_FEATURES,
        limit=180
    )

    history = []

    for row in rows:

        history.append({
            "timestamp": row.get("timestamp"),

            "traffic": safe_float(
                row.get("total_traffic_mbps")
            ),

            "rx": safe_float(
                row.get("rx_mbps")
            ),

            "tx": safe_float(
                row.get("tx_mbps")
            ),

            "latency": safe_float(
                row.get("latency_ms")
            ),

            "jitter": safe_float(
                row.get("jitter_ms")
            ),

            "loss": safe_float(
                row.get("packet_loss_percent")
            ),

            "signal": safe_float(
                row.get("signal_percent")
            ),

            "link_activity": safe_float(
                row.get("link_activity_percent")
            ),
        })

    return jsonify({
        "history": history
    })


# ---------------------------------------------------------------------
# API: controller events
# ---------------------------------------------------------------------


def api_events():
    return jsonify({
        "events": read_events(120)
    })


# ---------------------------------------------------------------------
# API: live tc
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# API: controller events
# ---------------------------------------------------------------------

@app.get("/api/events")
def api_events():

    events_file = DATA_DIR / "controller_events.jsonl"

    events = []

    if events_file.exists():

        try:

            with events_file.open(
                "r",
                encoding="utf-8",
                errors="replace"
            ) as f:

                lines = f.readlines()

            for line in lines[-100:]:

                line = line.strip()

                if not line:
                    continue

                try:
                    events.append(
                        json.loads(line)
                    )
                except Exception:
                    continue

        except Exception:
            events = []

    return jsonify({
        "events": events,
        "count": len(events),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    })


@app.get("/api/tc")
def api_tc():
    tc = get_tc_live()

    return jsonify({
        "interface": INTERFACE,
        "tc": tc,
        "classes": parse_tc_classes(
            tc["class_stats"]
        ),
    })


# ---------------------------------------------------------------------
# API: controlled experiment information
# ---------------------------------------------------------------------

@app.get("/api/experiments")
def api_experiments():
    rows = read_csv_rows(
        CONTROLLED_DATA
    )

    counts = {
        "NORMAL": 0,
        "WARNING": 0,
        "CONGESTED": 0,
    }

    for row in rows:
        label = row.get("label", "")

        if label in counts:
            counts[label] += 1

    return jsonify({
        "samples": len(rows),
        "classes": counts,
        "purpose": (
            "Controlled observations used for model development "
            "and validation. These are not current live observations."
        ),
    })


# ---------------------------------------------------------------------
# API: health
# ---------------------------------------------------------------------

@app.get("/api/health")
def api_health():
    state = read_json(STATE_FILE, {})

    running = bool(
        state.get("runtime", {}).get("running", False)
    )

    return jsonify({
        "status": "online" if running else "waiting",
        "controller_running": running,
        "state_file": STATE_FILE.exists(),
        "feature_file": LIVE_FEATURES.exists(),
        "metrics_file": LIVE_METRICS.exists(),
        "events_file": EVENT_FILE.exists(),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    })


# ---------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------

@app.get("/api/export/csv")
def export_csv():
    if not LIVE_FEATURES.exists():
        return jsonify({
            "error": "Live feature file does not exist."
        }), 404

    return send_file(
        LIVE_FEATURES,
        as_attachment=True,
        download_name="live_network_features.csv",
        mimetype="text/csv"
    )


# ---------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------

@app.get("/api/report")
def generate_report():

    try:
        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image,
            PageBreak,
        )

    except Exception as exc:
        return jsonify({
            "error": f"Report dependencies unavailable: {exc}"
        }), 500

    state = read_json(
        STATE_FILE,
        {}
    )

    history = read_csv_rows(
        LIVE_FEATURES,
        limit=120
    )

    events = read_events(50)

    experiments = read_csv_rows(
        CONTROLLED_DATA
    )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "INTELLIGENT LIVE NETWORK CONGESTION "
            "CONTROL SYSTEM",
            styles["Title"]
        )
    )

    story.append(
        Paragraph(
            "Live Operational & Closed-Loop Runtime Report",
            styles["Heading2"]
        )
    )

    story.append(Spacer(1, 8))

    telemetry = state.get("telemetry", {})
    ml = state.get("ml", {})
    decision = state.get("decision", {})
    policy = state.get("policy", {})

    overview = [
        ["Runtime State", "LIVE"],
        [
            "Controller Cycle",
            str(
                state.get(
                    "controller_cycle",
                    "-"
                )
            ),
        ],
        [
            "Traffic",
            f"{safe_float(telemetry.get('total_traffic_mbps')):.3f} Mbps",
        ],
        [
            "Latency",
            f"{safe_float(telemetry.get('latency_ms')):.2f} ms",
        ],
        [
            "Jitter",
            f"{safe_float(telemetry.get('jitter_ms')):.2f} ms",
        ],
        [
            "Packet Loss",
            f"{safe_float(telemetry.get('packet_loss_percent')):.2f}%",
        ],
        [
            "ML Prediction",
            ml.get("prediction", "UNKNOWN"),
        ],
        [
            "ML Confidence",
            f"{safe_float(ml.get('confidence')) * 100:.2f}%",
        ],
        [
            "Validated State",
            decision.get("status", "UNKNOWN"),
        ],
        [
            "Congestion Index",
            f"{safe_float(decision.get('congestion_score')) * 100:.1f}%",
        ],
        [
            "HIGH Guarantee",
            f"{safe_float(policy.get('high_mbps')):.2f} Mbps",
        ],
        [
            "MEDIUM Guarantee",
            f"{safe_float(policy.get('medium_mbps')):.2f} Mbps",
        ],
        [
            "LOW Guarantee",
            f"{safe_float(policy.get('low_mbps')):.2f} Mbps",
        ],
    ]

    table = Table(
        overview,
        colWidths=[70 * mm, 100 * mm]
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(table)

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Current Controller Decision",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            decision.get(
                "reason",
                "No decision reason available."
            ),
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # Live traffic chart
    # -------------------------------------------------------------

    if history:

        traffic_values = [
            safe_float(
                row.get("total_traffic_mbps")
            )
            for row in history
        ]

        latency_values = [
            safe_float(
                row.get("latency_ms")
            )
            for row in history
        ]

        jitter_values = [
            safe_float(
                row.get("jitter_ms")
            )
            for row in history
        ]

        fig = plt.figure(
            figsize=(8, 3.8)
        )

        plt.plot(
            traffic_values,
            label="Traffic Mbps"
        )

        plt.plot(
            latency_values,
            label="Latency ms"
        )

        plt.plot(
            jitter_values,
            label="Jitter ms"
        )

        plt.title(
            "Recent Live Network Measurements"
        )

        plt.xlabel(
            "Recent samples"
        )

        plt.legend()

        plt.grid(
            alpha=0.25
        )

        image_buffer = io.BytesIO()

        plt.savefig(
            image_buffer,
            format="png",
            dpi=150,
            bbox_inches="tight"
        )

        plt.close(fig)

        image_buffer.seek(0)

        image_path = DATA_DIR / "report_live_chart.png"

        with open(image_path, "wb") as f:
            f.write(image_buffer.read())

        story.append(
            Paragraph(
                "Live Telemetry",
                styles["Heading2"]
            )
        )

        story.append(
            Image(
                str(image_path),
                width=175 * mm,
                height=83 * mm
            )
        )

    story.append(PageBreak())

    story.append(
        Paragraph(
            "Model Development and Validation",
            styles["Heading1"]
        )
    )

    story.append(
        Paragraph(
            "Controlled experiments are used for model development "
            "and validation. They are deliberately separated from "
            "the live operational measurements shown above.",
            styles["BodyText"]
        )
    )

    counts = {
        "NORMAL": 0,
        "WARNING": 0,
        "CONGESTED": 0,
    }

    for row in experiments:
        label = row.get("label")

        if label in counts:
            counts[label] += 1

    experiment_table = Table(
        [
            ["Class", "Controlled Samples"],
            ["NORMAL", counts["NORMAL"]],
            ["WARNING", counts["WARNING"]],
            ["CONGESTED", counts["CONGESTED"]],
            ["TOTAL", len(experiments)],
        ],
        colWidths=[
            80 * mm,
            70 * mm
        ]
    )

    experiment_table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(experiment_table)

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Controlled-model validation result: approximately "
            "80% test accuracy and 0.77 macro F1 on the available "
            "controlled experimental test split. These values describe "
            "model validation and should not be interpreted as live "
            "network accuracy.",
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 14))

    story.append(
        Paragraph(
            "Closed-Loop Architecture",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            "Live measurement → feature engineering → ML prediction "
            "→ safety validation → adaptive policy selection → Linux "
            "traffic control → feedback measurement.",
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Recent Controller Events",
            styles["Heading2"]
        )
    )

    for event in events[-15:]:
        story.append(
            Paragraph(
                json.dumps(
                    event,
                    separators=(",", ":")
                ),
                styles["Code"]
            )
        )

        story.append(
            Spacer(1, 3)
        )

    doc.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="network_congestion_live_report.pdf",
        mimetype="application/pdf"
    )


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html"
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )
