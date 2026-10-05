import time
import os
import joblib
import pandas as pd
from datetime import datetime, timezone


MODEL_PATH = "prediction/live_congestion_model.pkl"
FEATURES_PATH = "data/live_features.csv"

CHECK_INTERVAL = 3
COOLDOWN_SECONDS = 10
REQUIRED_CONFIRMATIONS = 2


POLICIES = {
    "NORMAL": {
        "high": 7,
        "medium": 7,
        "low": 6,
        "description": "Balanced allocation"
    },

    "WARNING": {
        "high": 9,
        "medium": 6,
        "low": 5,
        "description": "Increase high-priority traffic"
    },

    "CONGESTED": {
        "high": 12,
        "medium": 5,
        "low": 3,
        "description": "Protect high-priority traffic"
    }
}


def load_model():

    bundle = joblib.load(MODEL_PATH)

    model = bundle["model"]
    features = bundle["features"]
    labels = bundle["labels"]

    return model, features, labels


def get_label_name(prediction, labels):

    if isinstance(labels, dict):
        return labels.get(
            prediction,
            str(prediction)
        )

    if isinstance(labels, list):

        try:
            return labels[int(prediction)]

        except (
            ValueError,
            IndexError,
            TypeError
        ):
            return str(prediction)

    return str(prediction)


def get_latest_prediction(
    model,
    features,
    labels
):

    if not os.path.exists(FEATURES_PATH):
        return None, 0, None, None

    try:
        df = pd.read_csv(FEATURES_PATH)

    except Exception as e:

        print(
            f"Could not read feature file: {e}"
        )

        return None, 0, None, None

    if df.empty:
        return None, 0, None, None

    latest = df.iloc[-1]

    timestamp = latest.get(
        "timestamp",
        None
    )

    input_data = {}

    for feature in features:

        if feature in latest.index:

            value = latest[feature]

            if pd.isna(value):
                value = 0

            input_data[feature] = value

        else:

            input_data[feature] = 0

    X = pd.DataFrame(
        [input_data]
    )

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

    confidence = (
        probability_map.get(
            prediction,
            0
        ) * 100
    )

    return (
        status,
        confidence,
        latest,
        timestamp
    )


def print_policy(
    status,
    confidence
):

    policy = POLICIES.get(
        status,
        POLICIES["NORMAL"]
    )

    print()
    print("=" * 70)
    print("ADAPTIVE TRAFFIC DECISION ENGINE")
    print("=" * 70)

    print()

    print(
        f"ML Status     : {status}"
    )

    print(
        f"Confidence    : {confidence:.2f}%"
    )

    print()

    print("SELECTED POLICY")
    print("-" * 70)

    print(
        f"High priority   : "
        f"{policy['high']} Mbps"
    )

    print(
        f"Medium priority : "
        f"{policy['medium']} Mbps"
    )

    print(
        f"Low priority    : "
        f"{policy['low']} Mbps"
    )

    total = (
        policy["high"] +
        policy["medium"] +
        policy["low"]
    )

    print(
        f"Total           : "
        f"{total} Mbps"
    )

    print()

    print(
        f"Policy          : "
        f"{policy['description']}"
    )

    print("=" * 70)


def main():

    print()
    print("=" * 70)
    print("STARTING ADAPTIVE DECISION ENGINE")
    print("=" * 70)

    print()

    model, features, labels = load_model()

    print(
        f"Model loaded: {len(features)} features"
    )

    print(
        f"Check interval: "
        f"{CHECK_INTERVAL} seconds"
    )

    print(
        f"Cooldown: "
        f"{COOLDOWN_SECONDS} seconds"
    )

    print(
        f"Required confirmations: "
        f"{REQUIRED_CONFIRMATIONS}"
    )

    print()

    # Last feature timestamp actually processed
    last_processed_timestamp = None

    # Candidate state waiting for confirmation
    candidate_status = None

    confirmation_count = 0

    # Last policy actually applied
    last_policy = None

    # Time when last policy was changed
    last_change_time = 0

    while True:

        try:

            (
                status,
                confidence,
                latest,
                timestamp
            ) = get_latest_prediction(
                model,
                features,
                labels
            )

            if status is None:

                print(
                    "Waiting for live prediction data..."
                )

                time.sleep(
                    CHECK_INTERVAL
                )

                continue

            # -------------------------------------------------
            # Ignore the same measurement
            # -------------------------------------------------

            if timestamp == last_processed_timestamp:

                time.sleep(
                    CHECK_INTERVAL
                )

                continue

            # This is a NEW measurement.
            last_processed_timestamp = timestamp

            # -------------------------------------------------
            # Confirmation logic
            # -------------------------------------------------

            if status == candidate_status:

                confirmation_count += 1

            else:

                candidate_status = status
                confirmation_count = 1

            # -------------------------------------------------
            # Cooldown
            # -------------------------------------------------

            current_time = time.time()

            cooldown_finished = (
                current_time -
                last_change_time
            ) >= COOLDOWN_SECONDS

            confirmed = (
                confirmation_count >=
                REQUIRED_CONFIRMATIONS
            )

            policy_change_needed = (
                status != last_policy
            )

            # -------------------------------------------------
            # Apply decision
            # -------------------------------------------------

            if (
                confirmed
                and
                cooldown_finished
                and
                policy_change_needed
            ):

                last_policy = status

                last_change_time = (
                    current_time
                )

                print_policy(
                    status,
                    confidence
                )

                print()

                print("ACTION:")

                print(
                    f"Traffic policy changed "
                    f"to {status}"
                )

                print(
                    "Traffic controller will "
                    "apply this policy."
                )

                print()

            else:

                print(
                    f"[{timestamp}] "
                    f"Status={status:<10} "
                    f"Confidence="
                    f"{confidence:6.2f}% "
                    f"Confirmations="
                    f"{confirmation_count}"
                )

            time.sleep(
                CHECK_INTERVAL
            )

        except KeyboardInterrupt:

            print()

            print(
                "Adaptive decision engine stopped."
            )

            break

        except Exception as e:

            print()

            print(
                f"ERROR: {e}"
            )

            print(
                "Retrying in 3 seconds..."
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
