import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

DATA_FILE = "data/live_labeled.csv"
MODEL_FILE = "prediction/live_congestion_model.pkl"

# Load live labeled data
df = pd.read_csv(DATA_FILE)

# Features available from the live monitoring system
features = [
    "rx_mbps",
    "tx_mbps",
    "total_traffic_mbps",
    "latency_ms",
    "packet_loss_percent",
    "jitter_ms",
    "rx_errors",
    "tx_errors",
    "rx_dropped",
    "tx_dropped",
    "receive_rate_mbps",
    "transmit_rate_mbps",
    "signal_percent",
    "rssi_dbm",
    "link_activity_percent",
    "total_traffic_mbps_mean_5",
    "total_traffic_mbps_std_5",
    "total_traffic_mbps_max_5",
    "latency_ms_mean_5",
    "latency_ms_std_5",
    "latency_ms_max_5",
    "packet_loss_percent_mean_5",
    "packet_loss_percent_std_5",
    "packet_loss_percent_max_5",
    "jitter_ms_mean_5",
    "jitter_ms_std_5",
    "jitter_ms_max_5",
    "signal_percent_mean_5",
    "signal_percent_std_5",
    "signal_percent_max_5",
    "link_activity_percent_mean_5",
    "link_activity_percent_std_5",
    "link_activity_percent_max_5",
    "latency_change",
    "jitter_change",
    "packet_loss_change",
    "traffic_change"
]

# Keep only features that actually exist
features = [f for f in features if f in df.columns]

X = df[features].copy()
y = df["congestion_state"]

# Replace missing values with median values
X = X.replace([float("inf"), float("-inf")], pd.NA)
X = X.fillna(X.median(numeric_only=True))
X = X.fillna(0)

print("=" * 65)
print("LIVE NETWORK CONGESTION MODEL")
print("=" * 65)

print("\nDATASET:")
print("Total samples:", len(df))
print("\nCLASS DISTRIBUTION:")
print(y.value_counts())

print("\nFEATURES USED:", len(features))

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42,
    stratify=y
)

print("\nTRAINING SAMPLES:", len(X_train))
print("TEST SAMPLES    :", len(X_test))

# Train 3-class Random Forest
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced",
    min_samples_leaf=2
)

model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)

print("\n" + "=" * 65)
print("MODEL RESULTS")
print("=" * 65)

print(f"\nAccuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0
    )
)

print("Confusion Matrix:")
labels = ["NORMAL", "WARNING", "CONGESTED"]
print(labels)
print(confusion_matrix(y_test, y_pred, labels=labels))

# Feature importance
print("\nFeature Importance:")

importance = sorted(
    zip(features, model.feature_importances_),
    key=lambda x: x[1],
    reverse=True
)

for name, value in importance:
    print(f"{name:40s} {value:.4f}")

# Save model
joblib.dump(
    {
        "model": model,
        "features": features,
        "labels": labels
    },
    MODEL_FILE
)

print("\nModel saved successfully:")
print(MODEL_FILE)
