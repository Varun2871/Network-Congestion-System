import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

DATA_FILE = "data/congestion_experiments.csv"

# Load dataset
df = pd.read_csv(DATA_FILE)

# Features
features = [
    "capacity_mbps",
    "offered_load_mbps",
    "received_throughput_mbps",
    "jitter_ms",
    "packet_loss_percent",
]

X = df[features]
y = df["congested"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42,
    stratify=y,
)

# Train model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
)

model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

# Results
accuracy = accuracy_score(y_test, y_pred)

print("\n=== Network Congestion Prediction ===")
print(f"Dataset size : {len(df)}")
print(f"Training set : {len(X_train)}")
print(f"Test set     : {len(X_test)}")
print(f"Accuracy     : {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(classification_report(y_test, y_pred, zero_division=0))

print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))

# Feature importance
print("\nFeature Importance:")
for name, importance in sorted(
    zip(features, model.feature_importances_),
    key=lambda x: x[1],
    reverse=True,
):
    print(f"{name:30s} {importance:.4f}")
