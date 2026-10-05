import time
import os
import joblib
import pandas as pd
from datetime import datetime


MODEL_PATH = "prediction/live_congestion_model.pkl"
FEATURES_PATH = "data/live_features.csv"

INTERVAL_SECONDS = 3


def load_model():
    bundle = joblib.load(MODEL_PATH)

    model = bundle["model"]
    features = bundle["features"]
    labels = bundle["labels"]

    return model, features, labels


def get_label_name(prediction, labels):
    """
    Convert the model's numeric/string prediction
    into a human-readable class name.

    Supports both:
        ['NORMAL', 'WARNING', 'CONGESTED']

    and:
        {0: 'NORMAL', 1: 'WARNING', 2: 'CONGESTED'}
    """

    if isinstance(labels, dict):
        return labels.get(prediction, str(prediction))

    if isinstance(labels, list):
        try:
            return labels[int(prediction)]
        except (ValueError, IndexError, TypeError):
            return str(prediction)

    return str(prediction)


def get_class_name(class_id, labels):
    """
    Convert a model class ID into a readable class name.
    """

    if isinstance(labels, dict):
        return labels.get(class_id, str(class_id))

    if isinstance(labels, list):
        try:
            return labels[int(class_id)]
        except (ValueError, IndexError, TypeError):
            return str(class_id)

    return str(class_id)


def get_value(row, column, default=0):
    """
    Safely read a value from a pandas row.
    """

    value = row.get(column, default)

    if pd.isna(value):
        return default

    return value


def explain_prediction(row, status):
    reasons = []

    latency = get_value(row, "latency_ms", 0)
    jitter = get_value(row, "jitter_ms", 0)
    packet_loss = get_value(row, "packet_loss_percent", 0)
    traffic = get_value(row, "total_traffic_mbps", 0)
    signal = get_value(row, "signal_percent", 0)

    if status == "NORMAL":

        if latency < 20:
            reasons.append("Low latency")

        if jitter < 10:
            reasons.append("Low jitter")

        if packet_loss == 0:
            reasons.append("No packet loss")

        if signal >= 70:
            reasons.append("Good Wi-Fi signal")

    elif status == "WARNING":

        if latency >= 20:
            reasons.append(
                f"Elevated latency ({latency:.2f} ms)"
            )

        if jitter >= 10:
            reasons.append(
                f"Elevated jitter ({jitter:.2f} ms)"
            )

        if packet_loss >= 1:
            reasons.append(
                f"Packet loss detected ({packet_loss:.2f}%)"
            )

        if signal < 70:
            reasons.append(
                f"Weak signal ({signal:.0f}%)"
            )

        if not reasons:
            reasons.append(
                "Network conditions are degrading"
            )

    elif status == "CONGESTED":

        if latency >= 40:
            reasons.append(
                f"High latency ({latency:.2f} ms)"
            )

        if jitter >= 20:
            reasons.append(
                f"High jitter ({jitter:.2f} ms)"
            )

        if packet_loss >= 5:
            reasons.append(
                f"High packet loss ({packet_loss:.2f}%)"
            )

        if traffic > 0:
            reasons.append(
                f"High traffic load ({traffic:.2f} Mbps)"
            )

        if not reasons:
            reasons.append(
                "ML model detected congestion"
            )

    if not reasons:
        reasons.append(
            "Network conditions are within monitored range"
        )

    return reasons


def predict_latest(model, features, labels):

    if not os.path.exists(FEATURES_PATH):
        print("Waiting for feature data...")
        return

    df = pd.read_csv(FEATURES_PATH)

    if df.empty:
        print("Feature file is empty. Waiting...")
        return

    latest = df.iloc[-1]

    input_data = {}

    for feature in features:

        if feature in latest.index:
            value = latest[feature]

            if pd.isna(value):
                value = 0

            input_data[feature] = value

        else:
            input_data[feature] = 0

    X = pd.DataFrame([input_data])

    prediction = model.predict(X)[0]

    probabilities = model.predict_proba(X)[0]

    probability_map = dict(
        zip(
            model.classes_,
            probabilities
        )
    )

    status = get_label_name(
        prediction,
        labels
    )

    confidence = probability_map.get(
        prediction,
        0
    ) * 100

    os.system("clear")

    print("=" * 70)
    print("LIVE NETWORK CONGESTION MONITOR")
    print("=" * 70)

    print()

    print(f"Status     : {status}")
    print(f"Confidence : {confidence:.2f}%")

    print()

    print("CURRENT NETWORK")
    print("-" * 70)

    latency = get_value(
        latest,
        "latency_ms",
        0
    )

    jitter = get_value(
        latest,
        "jitter_ms",
        0
    )

    packet_loss = get_value(
        latest,
        "packet_loss_percent",
        0
    )

    traffic = get_value(
        latest,
        "total_traffic_mbps",
        0
    )

    signal = get_value(
        latest,
        "signal_percent",
        0
    )

    rssi = get_value(
        latest,
        "rssi_dbm",
        0
    )

    print(f"Latency     : {latency:.3f} ms")
    print(f"Jitter      : {jitter:.3f} ms")
    print(f"Packet Loss : {packet_loss:.2f} %")
    print(f"Traffic     : {traffic:.3f} Mbps")
    print(f"Signal      : {signal:.1f} %")
    print(f"RSSI        : {rssi:.1f} dBm")

    print()

    print("WHY?")
    print("-" * 70)

    reasons = explain_prediction(
        latest,
        status
    )

    for reason in reasons:
        print(f" - {reason}")

    print()

    print("CLASS PROBABILITIES")
    print("-" * 70)

    for class_id in model.classes_:

        class_name = get_class_name(
            class_id,
            labels
        )

        probability = probability_map.get(
            class_id,
            0
        ) * 100

        print(
            f"  {class_name:<10}: "
            f"{probability:.2f}%"
        )

    print()

    print("-" * 70)

    print(
        f"Features used : {len(features)}"
    )

    timestamp = latest.get(
        "timestamp",
        datetime.now().isoformat()
    )

    print(
        f"Timestamp     : {timestamp}"
    )

    print()

    print(
        "Next update in 3 seconds..."
    )

    print("=" * 70)


def main():

    print(
        "Loading live congestion model..."
    )

    model, features, labels = load_model()

    print(
        "Model loaded successfully."
    )

    print(
        f"Features: {len(features)}"
    )

    print()

    print(
        "Starting live monitoring..."
    )

    time.sleep(2)

    while True:

        try:

            predict_latest(
                model,
                features,
                labels
            )

            time.sleep(
                INTERVAL_SECONDS
            )

        except KeyboardInterrupt:

            print()

            print(
                "Live monitoring stopped."
            )

            break

        except Exception as e:

            print()

            print("ERROR:")
            print(e)

            print()

            print(
                "Retrying in 3 seconds..."
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
