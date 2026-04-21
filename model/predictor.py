
import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

# ── Paths ──────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TRAIN_CSV   = os.path.join(BASE_DIR, "Training.csv")
TEST_CSV    = os.path.join(BASE_DIR, "Testing.csv")
MODEL_PKL   = os.path.join(BASE_DIR, "rf_model.pkl")
ENCODER_PKL = os.path.join(BASE_DIR, "label_encoder.pkl")
COLS_PKL    = os.path.join(BASE_DIR, "feature_cols.pkl")

# ── Canonical diseases (CLEANED) ───────────────────────────
# ── Disease descriptions ──────────────────────────────────
DISEASE_INFO = {
    "Diabetes": "A chronic condition affecting blood sugar regulation.",
    "Hypertension": "Persistently high blood pressure requiring monitoring.",
    "Malaria": "A mosquito-borne parasitic disease causing fever and chills.",
    "Dengue": "A viral infection spread by mosquitoes causing high fever.",
    "Typhoid": "A bacterial infection from contaminated food or water.",
    "Common Cold": "A viral upper respiratory tract infection.",
    "Pneumonia": "A lung infection causing inflammation and breathing difficulty.",
    "Heart attack": "Blocked blood flow to the heart — medical emergency.",
    "Tuberculosis": "A bacterial lung infection spread through air.",
    "Chicken pox": "A contagious viral disease causing itchy blisters.",
    "Acne": "A skin condition involving pimples and inflammation.",
    "Arthritis": "Inflammation of joints causing pain and stiffness.",
}

# ── Disease precautions ───────────────────────────────────
DISEASE_PRECAUTIONS = {
    "Diabetes": ["Monitor blood sugar", "Low sugar diet", "Exercise", "Doctor consultation"],
    "Hypertension": ["Reduce salt intake", "Regular BP check", "Avoid stress"],
    "Malaria": ["Use mosquito nets", "Take antimalarials", "Consult doctor"],
    "Dengue": ["Hydration", "Paracetamol only", "Platelet monitoring"],
    "Typhoid": ["Antibiotics", "Boiled water", "Hygiene"],
    "Common Cold": ["Rest", "Fluids", "Steam inhalation"],
    "Pneumonia": ["Antibiotics", "Hospital care if severe"],
    "Heart attack": ["Call emergency services immediately"],
    "Tuberculosis": ["Complete antibiotic course", "Isolation"],
    "Chicken pox": ["Calamine lotion", "Avoid scratching"],
    "Acne": ["Gentle skincare", "Avoid oil-based products"],
    "Arthritis": ["Pain relievers", "Physiotherapy"],
}
# ── Synthetic fallback dataset ─────────────────────────────
def _generate_synthetic_data(n_per_class=30):
    np.random.seed(42)
    cols = [f"symptom_{i}" for i in range(132)]
    rows, labels = [], []

    for idx, disease in enumerate(DISEASES):
        start = (idx * 3) % 127
        for _ in range(n_per_class):
            row = [0] * 132
            for s in range(start, min(start + 5, 132)):
                row[s] = 1
            row[np.random.randint(0, 132)] = 1
            rows.append(row)
            labels.append(disease)

    df = pd.DataFrame(rows, columns=cols)
    df["prognosis"] = labels
    return df, cols

# ── Load & clean Kaggle data ───────────────────────────────
def _load_real_data():
    train_df = pd.read_csv(TRAIN_CSV)
    test_df  = pd.read_csv(TEST_CSV)

    # Remove junk unnamed columns
    train_df = train_df.loc[:, ~train_df.columns.str.contains("^Unnamed")]
    test_df  = test_df.loc[:, ~test_df.columns.str.contains("^Unnamed")]

    # Normalize prognosis text
    for df in (train_df, test_df):
        df["prognosis"] = (
            df["prognosis"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # 🔥 REMOVE BAD LABEL COMPLETELY
        df.drop(df[df["prognosis"] == "peptic ulcer diseae"].index, inplace=True)

        df["prognosis"] = df["prognosis"].str.title()

    feature_cols = [c for c in train_df.columns if c != "prognosis"]

    # Ensure numeric symptoms
    for col in feature_cols:
        train_df[col] = pd.to_numeric(train_df[col], errors="coerce").fillna(0).astype(int)
        test_df[col]  = pd.to_numeric(test_df[col],  errors="coerce").fillna(0).astype(int)

    return train_df, test_df, feature_cols

# ── Train model ────────────────────────────────────────────
def train_model():
    print("[AI] Training Random Forest model…")

    if os.path.exists(TRAIN_CSV) and os.path.exists(TEST_CSV):
        train_df, test_df, feature_cols = _load_real_data()
        print("[AI] Loaded real Kaggle dataset.")
    else:
        print("[AI] Kaggle CSV not found — using synthetic data.")
        train_df, feature_cols = _generate_synthetic_data()
        test_df = train_df.sample(frac=0.2, random_state=42)

    X_train = train_df[feature_cols].values
    y_train = train_df["prognosis"].values
    X_test  = test_df[feature_cols].values
    y_test  = test_df["prognosis"].values

    # ✅ FIT ENCODER ON ACTUAL DATA (NO UNSEEN LABELS EVER)
    le = LabelEncoder()
    le.fit(pd.concat([pd.Series(y_train), pd.Series(y_test)]))

    y_train_enc = le.transform(y_train)
    y_test_enc  = le.transform(y_test)

    clf = RandomForestClassifier(
        n_estimators=150,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train_enc)

    acc = accuracy_score(y_test_enc, clf.predict(X_test)) * 100
    print(f"[AI] Model accuracy: {acc:.2f}%")

    with open(MODEL_PKL, "wb") as f:
        pickle.dump(clf, f)
    with open(ENCODER_PKL, "wb") as f:
        pickle.dump(le, f)
    with open(COLS_PKL, "wb") as f:
        pickle.dump(feature_cols, f)

    return round(acc, 2)

# ── Load model ─────────────────────────────────────────────
def load_model():
    if not os.path.exists(MODEL_PKL):
        train_model()

    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    with open(ENCODER_PKL, "rb") as f:
        le = pickle.load(f)
    with open(COLS_PKL, "rb") as f:
        cols = pickle.load(f)

    return clf, le, cols

# ── Prediction ─────────────────────────────────────────────
def predict_disease(symptom_list):
    clf, le, cols = load_model()

    # Build input vector
    vec = np.zeros(len(cols))
    symptom_list = [s.lower().replace(" ", "_") for s in symptom_list]

    matched = []
    for i, col in enumerate(cols):
        if col.lower().replace(" ", "_") in symptom_list:
            vec[i] = 1
            matched.append(col)

    # Predict probabilities
    proba = clf.predict_proba([vec])[0]
    idx = int(np.argmax(proba))

    disease = le.inverse_transform([idx])[0]
    confidence = round(float(proba[idx]) * 100, 2)

    # Top-3 differential diagnoses
    top3_idx = np.argsort(proba)[-3:][::-1]
    differentials = [
        {
            "disease": le.inverse_transform([i])[0],
            "probability": round(float(proba[i]) * 100, 2)
        }
        for i in top3_idx
    ]

    return {
        "disease": disease,
        "confidence": confidence,
        "matched_symptoms": matched,

        # ✅ THESE FIX YOUR ERROR
        "description": DISEASE_INFO.get(
            disease,
            "A medical condition that requires professional evaluation."
        ),
        "precautions": DISEASE_PRECAUTIONS.get(
            disease,
            ["Consult a qualified doctor", "Rest and hydration", "Follow medical advice"]
        ),
        "differentials": differentials,
    }

# ── Symptoms list ──────────────────────────────────────────
def get_all_symptoms():
    if os.path.exists(COLS_PKL):
        with open(COLS_PKL, "rb") as f:
            return pickle.load(f)
    if os.path.exists(TRAIN_CSV):
        df = pd.read_csv(TRAIN_CSV)
        return [c for c in df.columns if c != "prognosis"]
    _, cols = _generate_synthetic_data(1)
    return cols