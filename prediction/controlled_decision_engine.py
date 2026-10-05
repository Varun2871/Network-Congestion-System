import os
import time
import joblib
import pandas as pd


MODEL_FILE = "prediction/controlled_congestion_model.pkl"
DATA_FILE = "data/controlled_experiments.csv"

CHECK_INTERVAL = 3


POLICIES = {

    "NORMAL": {
        "HIGH": 8,
        "MEDIUM": 7,
        "LOW": 5
    },

    "WARNING": {
        "HIGH": 10,
        "MEDIUM": 6,
        "LOW": 4
    },

    "CONGESTED": {
        "HIGH": 12,
        "MEDIUM": 5,
        "LOW": 3
    }
}


def load_model():

    bundle = joblib.load(
        MODEL_FILE
    )

    return (
        bundle["model"],
        bundle["features"],
        bundle["labels"]
    )


def get_latest_sample():

    if not os.path.exists(DATA_FILE):
        return None

    df = pd.read_csv(
        DATA_FILE
    )

    if df.empty:
        return None

    return df.iloc[-1]


def predict(
    model,
    features,
    sample
):

    values = []

    for feature in features:

        value = sample.get(
            feature,
            0
        )

        try:
            value = float(value)
        except Exception:
            value = 0.0

        if pd.isna(value):
            value = 0.0

        values.append(value)

    X = pd.DataFrame(
        [values],
        columns=features
    )

    prediction = model.predict(X)[0]

    probabilities = model.predict_proba(X)[0]

    probability_map = dict(
        zip(
            model.classes_,
            probabilities
        )
    )

    confidence = (
        probability_map[prediction]
        * 100
    )

    return (
        prediction,
        confidence,
        probability_map
    )


def value(sample, name):

    try:

        result = float(
            sample.get(name, 0)
        )

        if pd.isna(result):
            return 0.0

        return result

    except Exception:

        return 0.0


def validate_prediction(
    ml_status,
    sample
):

    latency = value(
        sample,
        "latency_ms"
    )

    jitter = value(
        sample,
        "jitter_ms"
    )

    packet_loss = value(
        sample,
        "packet_loss_percent"
    )

    traffic = value(
        sample,
        "total_traffic_mbps"
    )

    severe_condition = (
        traffic >= 20
        or latency >= 40
        or jitter >= 20
        or packet_loss >= 5
    )

    warning_condition = (
        traffic >= 10
        or latency >= 20
        or jitter >= 10
        or packet_loss >= 1
    )

    if ml_status == "CONGESTED":

        if severe_condition:

            return "CONGESTED", "ML prediction supported"

        if warning_condition:

            return "WARNING", (
                "ML predicted CONGESTED, "
                "but measurements support WARNING"
            )

        return "NORMAL", (
            "ML predicted CONGESTED, "
            "but measurements show normal conditions"
        )

    if ml_status == "WARNING":

        if warning_condition:

            return "WARNING", (
                "ML prediction supported"
            )

        return "NORMAL", (
            "ML predicted WARNING, "
            "but measurements show normal conditions"
        )

    return "NORMAL", "ML prediction supported"


def print_policy(
    status
):

    policy = POLICIES[
        status
    ]

    print()
    print(
        "ADAPTIVE TRAFFIC POLICY"
    )

    print(
        f"HIGH    : {policy['HIGH']} Mbps"
    )

    print(
        f"MEDIUM  : {policy['MEDIUM']} Mbps"
    )

    print(
        f"LOW     : {policy['LOW']} Mbps"
    )

    print(
        f"TOTAL   : "
        f"{sum(policy.values())} Mbps"
    )


def main():

    print("=" * 60)
    print(
        "CONTROLLED ADAPTIVE DECISION ENGINE"
    )
    print("=" * 60)

    model, features, labels = (
        load_model()
    )

    print()
    print(
        "Model loaded successfully"
    )

    print(
        "Classes:",
        labels
    )

    print()
    print(
        "Safety validation enabled."
    )

    print(
        "DRY-RUN ONLY."
    )

    print(
        "No tc configuration will be changed."
    )

    print()
    print(
        "Press Ctrl+C to stop."
    )

    last_timestamp = None

    while True:

        sample = get_latest_sample()

        if sample is None:

            print(
                "Waiting for dataset..."
            )

            time.sleep(
                CHECK_INTERVAL
            )

            continue

        timestamp = sample[
            "timestamp"
        ]

        if timestamp == last_timestamp:

            time.sleep(
                CHECK_INTERVAL
            )

            continue

        last_timestamp = timestamp

        ml_status, confidence, probabilities = (
            predict(
                model,
                features,
                sample
            )
        )

        final_status, reason = (
            validate_prediction(
                ml_status,
                sample
            )
        )

        print()
        print("=" * 60)

        print(
            "NEW NETWORK OBSERVATION"
        )

        print(
            "Timestamp:",
            timestamp
        )

        print(
            f"Traffic: "
            f"{value(sample, 'total_traffic_mbps'):.3f} Mbps"
        )

        print(
            f"Latency: "
            f"{value(sample, 'latency_ms'):.3f} ms"
        )

        print(
            f"Jitter: "
            f"{value(sample, 'jitter_ms'):.3f} ms"
        )

        print(
            f"Packet loss: "
            f"{value(sample, 'packet_loss_percent'):.3f}%"
        )

        print()

        print(
            f"ML STATUS: {ml_status}"
        )

        print(
            f"ML CONFIDENCE: "
            f"{confidence:.2f}%"
        )

        print()

        print(
            f"VALIDATED STATUS: "
            f"{final_status}"
        )

        print(
            f"VALIDATION: {reason}"
        )

        print()

        print(
            "CLASS PROBABILITIES:"
        )

        for name in [
            "NORMAL",
            "WARNING",
            "CONGESTED"
        ]:

            probability = (
                probabilities
                .get(name, 0)
                * 100
            )

            print(
                f"{name:<12}: "
                f"{probability:6.2f}%"
            )

        print_policy(
            final_status
        )

        time.sleep(
            CHECK_INTERVAL
        )


if __name__ == "__main__":
    main()
