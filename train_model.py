import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# Load datasets
train_df = pd.read_csv("model/Training.csv")
test_df = pd.read_csv("model/Testing.csv")

# 🔴 REMOVE UNNAMED COLUMNS (IMPORTANT FIX)
train_df = train_df.loc[:, ~train_df.columns.str.contains('^Unnamed')]
test_df = test_df.loc[:, ~test_df.columns.str.contains('^Unnamed')]

# Separate features and target
X_train = train_df.drop("prognosis", axis=1)
y_train = train_df["prognosis"]

X_test = test_df.drop("prognosis", axis=1)
y_test = test_df["prognosis"]

# Train model
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# Test accuracy
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Medchain Model Accuracy:", accuracy)

# Save trained model
joblib.dump(model, "model.pkl")
print("Model saved as model.pkl")