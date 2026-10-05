import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_FILE = Path("prediction/live_congestion_model.pkl")
LIVE_DATA_FILE = Path("data/live_features.csv")


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

if not MODEL_FILE.exists():
    raise FileNotFoundError(
        f"Model file not found: {MODEL_FILE}"
    )

bundle = joblib.load(MODEL_FILE)

# The .pkl file contains a dictionary:
# {
#     "model": trained_model,
#     "features": feature_list,
#     "labels": label_list
# }

model = bundle["model"]
FEATURES = bundle["features"]
LABELS = bundle["labels"]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_latest_data():
    """
    Load the latest live feature row.
    """

    if not LIVE_DATA_FILE.exists():
        raise FileNotFoundError(
            f"Live feature file not found: {LIVE_DATA_FILE}"
        )

    df = pd.read_csv(LIVE_DATA_FILE)

    if df.empty:
        raise ValueError("Live feature dataset is empty.")

    return df.iloc[-1]


def safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    try:
        if pd.isna(value):
            return default

        return float(value)

    except (ValueError, TypeError):
        return default


def explain_prediction(data, prediction):
    """
    Generate a simple human-readable explanation.
    """

    reasons = []

    latency = safe_float(data.get("latency_ms"))
    jitter = safe_float(data.get("jitter_ms"))
    packet_loss = safe_float(data.get("packet_loss_percent"))
    signal = safe_float(data.get("signal_percent"))
    traffic = safe_float(data.get("total_traffic_mbps"))

    # --------------------------------------------------------
    # Congestion explanation
    # --------------------------------------------------------

    if prediction == "CONGESTED":

        if latency > 20:
            reasons.append("High latency")

        if jitter > 10:
            reasons.append("High jitter")

        if packet_loss > 1:
            reasons.append("Packet loss detected")

        if traffic > 10:
            reasons.append("High traffic load")

        if not reasons:
            reasons.append("Network conditions indicate congestion")

    # --------------------------------------------------------
    # Warning explanation
    # --------------------------------------------------------

    elif prediction == "WARNING":

        if latency > 15:
            reasons.append("Increasing latency")

        if jitter > 5:
            reasons.append("Increasing jitter")

        if packet_loss > 0:
            reasons.append("Some packet loss detected")

        if signal < 60:
            reasons.append("Weak Wi-Fi signal")

        if traffic > 8:
            reasons.append("Elevated traffic")

        if not reasons:
            reasons.append("Network conditions require monitoring")

    # --------------------------------------------------------
    # Normal explanation
    # --------------------------------------------------------

    else:

        if latency <= 20:
            reasons.append("Low latency")

        if jitter <= 10:
            reasons.append("Low jitter")

        if packet_loss == 0:
            reasons.append("No packet loss")

        if signal >= 60:
            reasons.append("Good Wi-Fi signal")

        if not reasons:
            reasons.append("Network conditions are stable")

    return reasons


# ============================================================
# MAIN PREDICTION
# ============================================================

def predict_live():

    # --------------------------------------------------------
    # Get latest live sample
    # --------------------------------------------------------

    latest = get_latest_data()

    # --------------------------------------------------------
    # Build feature dataframe
    # --------------------------------------------------------

    feature_values = {}

    for feature in FEATURES:

        if feature in latest.index:
            feature_values[feature] = safe_float(
                latest[feature]
            )

        else:
            # Missing feature
            feature_values[feature] = 0.0

    X = pd.DataFrame(
        [feature_values],
        columns=FEATURES
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    prediction = model.predict(X)[0]

    # --------------------------------------------------------
    # Convert prediction to string
    # --------------------------------------------------------

    prediction_string = str(prediction)

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    probabilities = model.predict_proba(X)[0]

    probability_map = {}

    for label, probability in zip(
        model.classes_,
        probabilities
    ):
        probability_map[str(label)] = float(probability)

    confidence = max(probabilities) * 100

    # --------------------------------------------------------
    # Explanation
    # --------------------------------------------------------

    reasons = explain_prediction(
        latest,
        prediction_string
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("LIVE NETWORK CONGESTION PREDICTION")
    print("=" * 65)

    print()
    print(f"Status     : {prediction_string}")
    print(f"Confidence : {confidence:.2f}%")

    print()
    print("CURRENT NETWORK:")
    print(
        f"Latency     : "
        f"{safe_float(latest.get('latency_ms')):.3f} ms"
    )

    print(
        f"Jitter      : "
        f"{safe_float(latest.get('jitter_ms')):.3f} ms"
    )

    print(
        f"Packet Loss : "
        f"{safe_float(latest.get('packet_loss_percent')):.2f} %"
    )

    print(
        f"Traffic     : "
        f"{safe_float(latest.get('total_traffic_mbps')):.3f} Mbps"
    )

    print(
        f"Signal      : "
        f"{safe_float(latest.get('signal_percent')):.1f} %"
    )

    print(
        f"RSSI        : "
        f"{safe_float(latest.get('rssi_dbm')):.1f} dBm"
    )

    print()
    print("WHY?")

    for reason in reasons:
        print(f" - {reason}")

    # --------------------------------------------------------
    # Class probabilities
    # --------------------------------------------------------

    print()
    print("CLASS PROBABILITIES:")

    # Always display the three project states
    for label in ["NORMAL", "WARNING", "CONGESTED"]:

        probability = probability_map.get(
            label,
            0.0
        )

        print(
            f"  {label:<10}: "
            f"{probability * 100:.2f}%"
        )

    # --------------------------------------------------------
    # Additional model information
    # --------------------------------------------------------

    print()
    print(f"Features used : {len(FEATURES)}")

    timestamp = latest.get(
        "timestamp",
        datetime.now().isoformat()
    )

    print(f"Timestamp     : {timestamp}")

    print("=" * 65)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    predict_live()
