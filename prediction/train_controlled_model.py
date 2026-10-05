import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


DATA_FILE = "data/controlled_experiments.csv"
MODEL_FILE = "prediction/controlled_congestion_model.pkl"


FEATURES = [
    "latency_ms",
    "packet_loss_percent",
    "jitter_ms",
    "rx_mbps",
    "tx_mbps",
    "total_traffic_mbps",
]


def main():

    print("=" * 60)
    print("CONTROLLED CONGESTION MODEL TRAINING")
    print("=" * 60)

    df = pd.read_csv(DATA_FILE)

    print()
    print("Dataset rows:", len(df))

    print()
    print("Class distribution:")
    print(df["label"].value_counts())

    # Convert numeric columns
    for column in FEATURES:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Fill missing values using column medians
    for column in FEATURES:

        median = df[column].median()

        if pd.isna(median):
            median = 0

        df[column] = df[column].fillna(
            median
        )

    X = df[FEATURES]
    y = df["label"]

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.25,
            random_state=42,
            stratify=y
        )
    )

    print()
    print("Training samples:", len(X_train))
    print("Testing samples:", len(X_test))

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight="balanced",
        min_samples_leaf=2
    )

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(
        X_test
    )

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(
        f"Accuracy: {accuracy * 100:.2f}%"
    )

    print()
    print("Classification report:")

    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0
        )
    )

    print("Confusion matrix:")

    print(
        confusion_matrix(
            y_test,
            predictions,
            labels=[
                "NORMAL",
                "WARNING",
                "CONGESTED"
            ]
        )
    )

    print()
    print("Feature importance:")

    importance = sorted(
        zip(
            FEATURES,
            model.feature_importances_
        ),
        key=lambda x: x[1],
        reverse=True
    )

    for name, value in importance:

        print(
            f"{name:<30} "
            f"{value:.4f}"
        )

    bundle = {
        "model": model,
        "features": FEATURES,
        "labels": [
            "NORMAL",
            "WARNING",
            "CONGESTED"
        ]
    }

    joblib.dump(
        bundle,
        MODEL_FILE
    )

    print()
    print(
        "Model saved:",
        MODEL_FILE
    )


if __name__ == "__main__":
    main()
