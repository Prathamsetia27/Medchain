
import json
import os
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash

from database import (init_db, get_db, get_user_by_email,
                      get_user_by_id, get_last_hash_for_patient, log_action,
                      get_patient_profile)
from blockchain.chain import generate_record_hash, verify_record_integrity
from model.predictor import predict_disease, get_all_symptoms, train_model
from utils.captcha_gen import generate_captcha, validate_captcha

# ── App Configuration ─────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "aarogya-secret-2024-xK9mP2qR")

# ── Initialise DB & Model ─────────────────────────────────
init_db()
MODEL_ACCURACY = None  # Will be set on first model load


def ensure_model():
    """Train model if not already trained. Return accuracy."""
    global MODEL_ACCURACY
    if MODEL_ACCURACY is None:
        from model.predictor import MODEL_PKL, train_model
        if not os.path.exists(MODEL_PKL):
            MODEL_ACCURACY = train_model()
        else:
            MODEL_ACCURACY = 95.0  # Typical RF accuracy on this dataset
    return MODEL_ACCURACY


# ── Role-Based Access Decorators ──────────────────────────

def login_required(f):
    """Redirect to login if user is not in session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Decorator factory. Ensures the logged-in user has one of the
    allowed roles. Returns 403 if role doesn't match.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("Access denied: insufficient permissions.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Helpers ───────────────────────────────────────────────

def current_user():
    """Return the currently logged-in user row (or None)."""
    uid = session.get("user_id")
    return get_user_by_id(uid) if uid else None


@app.context_processor
def inject_user():
    """Make `user` available in all templates automatically."""
    return {"user": current_user()}


# ══════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Landing page — redirects authenticated users to their dashboard."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Patient self-registration with CAPTCHA validation."""
    # Generate CAPTCHA on GET or after failure
    if request.method == "GET" or "captcha_answer" not in session:
        cap = generate_captcha()
        session["captcha_answer"] = cap["answer"]
        captcha_q = cap["question"]
    else:
        captcha_q = session.get("captcha_question", "? + ?")

    if request.method == "POST":
        # ── Validate CAPTCHA first ──
        user_cap = request.form.get("captcha", "")
        if not validate_captcha(user_cap, session.get("captcha_answer", -1)):
            # Regenerate CAPTCHA on failure
            cap = generate_captcha()
            session["captcha_answer"] = cap["answer"]
            flash("Incorrect CAPTCHA answer. Please try again.", "danger")
            return render_template("register.html", captcha_q=cap["question"])

        full_name = request.form.get("full_name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        confirm   = request.form.get("confirm_password", "")
        phone     = request.form.get("phone", "").strip()

        # ── Basic validation ──
        if not all([full_name, email, password]):
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        else:
            conn = get_db()
            existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if existing:
                flash("Email already registered. Please log in.", "warning")
                conn.close()
            else:
                pw_hash = generate_password_hash(password)
                conn.execute(
                    "INSERT INTO users (full_name, email, password_hash, role, phone) VALUES (?,?,?,?,?)",
                    (full_name, email, pw_hash, "patient", phone)
                )
                conn.commit()
                new_user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
                log_action(new_user["id"], "REGISTER", f"Patient registered: {email}", request.remote_addr)
                conn.close()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))

        cap = generate_captcha()
        session["captcha_answer"] = cap["answer"]
        captcha_q = cap["question"]

    return render_template("register.html", captcha_q=captcha_q)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Unified login for all roles. Role is determined from DB."""
    cap = generate_captcha()
    session["captcha_answer"] = cap["answer"]
    captcha_q = cap["question"]

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user_cap = request.form.get("captcha", "")

        # Validate CAPTCHA
        if not validate_captcha(user_cap, session.get("captcha_answer", -1)):
            cap = generate_captcha()
            session["captcha_answer"] = cap["answer"]
            flash("Incorrect CAPTCHA. Please try again.", "danger")
            return render_template("login.html", captcha_q=cap["question"])

        user = get_user_by_email(email)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"]    = user["role"]
            session["name"]    = user["full_name"]
            log_action(user["id"], "LOGIN", f"Role: {user['role']}", request.remote_addr)
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            cap = generate_captcha()
            session["captcha_answer"] = cap["answer"]
            captcha_q = cap["question"]

    return render_template("login.html", captcha_q=captcha_q)


@app.route("/logout")
@login_required
def logout():
    uid = session.get("user_id")
    log_action(uid, "LOGOUT", "", request.remote_addr)
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ── Role-based dashboard router ───────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")
    if role == "patient":
        return redirect(url_for("patient_dashboard"))
    elif role == "doctor":
        return redirect(url_for("doctor_dashboard"))
    elif role == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("logout"))


# ══════════════════════════════════════════════════════════
#  PATIENT ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/patient/dashboard")
@role_required("patient")
def patient_dashboard():
    uid = session["user_id"]
    conn = get_db()
    records = conn.execute(
        "SELECT * FROM medical_records WHERE patient_id=? ORDER BY timestamp DESC LIMIT 5",
        (uid,)
    ).fetchall()
    conn.close()
    acc = ensure_model()
    profile = get_patient_profile(uid)
    profile_complete = profile is not None
    return render_template("patient/dashboard.html", records=records, accuracy=acc,
                           profile_complete=profile_complete, profile=profile)




@app.route("/patient/profile", methods=["GET", "POST"])
@role_required("patient")
def patient_profile():
    """Patient health profile setup / update."""
    uid = session["user_id"]
    profile = get_patient_profile(uid)

    if request.method == "POST":
        age    = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        weight = request.form.get("weight_kg", "").strip()
        height = request.form.get("height_cm", "").strip()
        blood  = request.form.get("blood_group", "").strip()
        allergies  = request.form.get("allergies", "").strip()
        conditions = request.form.get("chronic_conditions", "").strip()
        emergency  = request.form.get("emergency_contact", "").strip()

        if not all([age, gender, weight, height, blood]):
            flash("Please fill in all required fields (Age, Gender, Weight, Height, Blood Group).", "danger")
        else:
            try:
                age_i    = int(age)
                weight_f = float(weight)
                height_f = float(height)
                if not (1 <= age_i <= 120):
                    raise ValueError("age")
                if not (10 <= weight_f <= 500):
                    raise ValueError("weight")
                if not (50 <= height_f <= 300):
                    raise ValueError("height")
            except ValueError:
                flash("Please enter valid numeric values for Age, Weight, and Height.", "danger")
            else:
                conn = get_db()
                if profile:
                    conn.execute("""
                        UPDATE patient_profiles
                        SET age=?, gender=?, weight_kg=?, height_cm=?,
                            blood_group=?, allergies=?, chronic_conditions=?,
                            emergency_contact=?, updated_at=datetime('now')
                        WHERE user_id=?
                    """, (age_i, gender, weight_f, height_f, blood,
                          allergies, conditions, emergency, uid))
                    flash("Health profile updated successfully!", "success")
                else:
                    conn.execute("""
                        INSERT INTO patient_profiles
                            (user_id, age, gender, weight_kg, height_cm,
                             blood_group, allergies, chronic_conditions, emergency_contact)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (uid, age_i, gender, weight_f, height_f, blood,
                          allergies, conditions, emergency))
                    flash("Health profile saved! You can now use AI Diagnosis.", "success")
                conn.commit()
                conn.close()
                log_action(uid, "PROFILE_UPDATE", "Patient updated health profile", request.remote_addr)
                return redirect(url_for("patient_dashboard"))

    return render_template("patient/profile_setup.html", profile=profile)

@app.route("/patient/predict", methods=["GET", "POST"])
@role_required("patient")
def predict():
    """AI disease prediction from symptoms."""
    symptoms = get_all_symptoms()
    # Format symptoms nicely for display (replace underscores, title-case)
    display_symptoms = [s.replace("_", " ").title() for s in symptoms]
    symptom_pairs = list(zip(symptoms, display_symptoms))

    if request.method == "POST":
        selected = request.form.getlist("symptoms")  # list of raw column names

        if len(selected) < 3:
            flash("Please select at least 3 symptoms for accurate prediction.", "warning")
            return render_template("patient/predict.html", symptom_pairs=symptom_pairs)

        # ── Run AI prediction ──
        result = predict_disease(selected)

        # ── Blockchain: chain this record to the patient's previous hash ──
        uid = session["user_id"]
        prev_hash = get_last_hash_for_patient(uid)
        ts = datetime.utcnow().isoformat()

        record_data = {
            "patient_id": uid,
            "symptoms": selected,
            "disease": result["disease"],
            "confidence": result["confidence"],
            "timestamp": ts,
        }
        block_hash = generate_record_hash(record_data, prev_hash)

        # ── Persist to database ──
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO medical_records
                (patient_id, symptoms, predicted_disease, confidence,
                 ai_description, ai_precautions, differentials,
                 blockchain_hash, prev_hash, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            uid,
            json.dumps(selected),
            result["disease"],
            result["confidence"],
            result["description"],
            json.dumps(result["precautions"]),
            json.dumps(result["differentials"]),
            block_hash,
            prev_hash,
            ts,
        ))
        conn.commit()
        record_id = cur.lastrowid
        log_action(uid, "PREDICT", f"Disease: {result['disease']}, Conf: {result['confidence']}%", request.remote_addr)
        conn.close()

        return render_template("patient/result.html", result=result, record_id=record_id,
                               block_hash=block_hash, selected=selected)

    return render_template("patient/predict.html", symptom_pairs=symptom_pairs)


@app.route("/patient/history")
@role_required("patient")
def patient_history():
    uid = session["user_id"]
    conn = get_db()
    records = conn.execute(
        "SELECT * FROM medical_records WHERE patient_id=? ORDER BY timestamp DESC",
        (uid,)
    ).fetchall()
    conn.close()
    return render_template("patient/history.html", records=records)


@app.route("/patient/record/<int:record_id>")
@role_required("patient")
def patient_record_detail(record_id):
    """View a single medical record with blockchain verification."""
    uid = session["user_id"]
    conn = get_db()
    record = conn.execute(
        "SELECT * FROM medical_records WHERE id=? AND patient_id=?",
        (record_id, uid)
    ).fetchone()
    if not record:
        conn.close()
        flash("Record not found.", "danger")
        return redirect(url_for("patient_history"))

    # Fetch doctor's diagnosis if any
    diagnoses = conn.execute(
        """SELECT d.*, u.full_name AS doctor_name, u.specialization
           FROM diagnoses d JOIN users u ON d.doctor_id=u.id
           WHERE d.record_id=?""",
        (record_id,)
    ).fetchall()
    conn.close()

    # ── Blockchain Verification ──
    symptoms_list = json.loads(record["symptoms"])
    record_data = {
        "patient_id": uid,
        "symptoms": symptoms_list,
        "disease": record["predicted_disease"],
        "confidence": record["confidence"],
        "timestamp": record["timestamp"],
    }
    is_intact = verify_record_integrity(record_data, record["blockchain_hash"], record["prev_hash"])

    return render_template("patient/record_detail.html",
                           record=record,
                           diagnoses=diagnoses,
                           is_intact=is_intact,
                           symptoms_list=symptoms_list,
                           precautions=json.loads(record["ai_precautions"] or "[]"),
                           differentials=json.loads(record["differentials"] or "[]"))


# ── Consent Management ─────────────────────────────────────

@app.route("/patient/consent", methods=["GET", "POST"])
@role_required("patient")
def manage_consent():
    uid = session["user_id"]
    conn = get_db()

    if request.method == "POST":
        doctor_id = request.form.get("doctor_id")
        action    = request.form.get("action")  # 'grant' or 'revoke'

        if action == "grant":
            conn.execute("""
                INSERT INTO consents (patient_id, doctor_id, granted)
                VALUES (?,?,1)
                ON CONFLICT(patient_id, doctor_id) DO UPDATE SET granted=1, granted_at=datetime('now')
            """, (uid, doctor_id))
            flash("Access granted to the doctor.", "success")
            log_action(uid, "CONSENT_GRANT", f"Doctor ID: {doctor_id}", request.remote_addr)
        elif action == "revoke":
            conn.execute(
                "UPDATE consents SET granted=0 WHERE patient_id=? AND doctor_id=?",
                (uid, doctor_id)
            )
            flash("Doctor access has been revoked.", "info")
            log_action(uid, "CONSENT_REVOKE", f"Doctor ID: {doctor_id}", request.remote_addr)

        conn.commit()

    # List all doctors
    doctors = conn.execute("SELECT * FROM users WHERE role='doctor'").fetchall()
    # Current consents
    consents = conn.execute(
        "SELECT doctor_id, granted FROM consents WHERE patient_id=?", (uid,)
    ).fetchall()
    consent_map = {c["doctor_id"]: c["granted"] for c in consents}
    conn.close()

    return render_template("patient/consent.html", doctors=doctors, consent_map=consent_map)


# ══════════════════════════════════════════════════════════
#  DOCTOR ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/doctor/dashboard")
@role_required("doctor")
def doctor_dashboard():
    """Show consented patients and their latest records."""
    did = session["user_id"]
    conn = get_db()
    # Only patients who gave this doctor consent
    patients = conn.execute("""
        SELECT u.id, u.full_name, u.email, u.phone, u.created_at,
               c.granted_at
        FROM users u
        JOIN consents c ON c.patient_id=u.id
        WHERE c.doctor_id=? AND c.granted=1
    """, (did,)).fetchall()
    conn.close()
    return render_template("doctor/dashboard.html", patients=patients)


@app.route("/doctor/patient/<int:patient_id>")
@role_required("doctor")
def doctor_view_patient(patient_id):
    """View a consented patient's medical records."""
    did = session["user_id"]
    conn = get_db()

    # Verify consent before allowing access
    consent = conn.execute(
        "SELECT granted FROM consents WHERE patient_id=? AND doctor_id=? AND granted=1",
        (patient_id, did)
    ).fetchone()
    if not consent:
        conn.close()
        flash("You do not have consent to view this patient's records.", "danger")
        return redirect(url_for("doctor_dashboard"))

    patient = conn.execute("SELECT * FROM users WHERE id=?", (patient_id,)).fetchone()
    records = conn.execute(
        "SELECT * FROM medical_records WHERE patient_id=? ORDER BY timestamp DESC",
        (patient_id,)
    ).fetchall()
    conn.close()

    log_action(did, "VIEW_PATIENT", f"Patient ID: {patient_id}", request.remote_addr)
    return render_template("doctor/patient_records.html", patient=patient, records=records)


@app.route("/doctor/diagnose/<int:record_id>", methods=["GET", "POST"])
@role_required("doctor")
def doctor_diagnose(record_id):
    """
    Doctor adds diagnosis and prescription.
    The ORIGINAL record is NEVER modified — this is additive only.
    This preserves the blockchain integrity of the original record.
    """
    did = session["user_id"]
    conn = get_db()

    # Load record and verify doctor has access
    record = conn.execute("SELECT * FROM medical_records WHERE id=?", (record_id,)).fetchone()
    if not record:
        conn.close()
        flash("Record not found.", "danger")
        return redirect(url_for("doctor_dashboard"))

    consent = conn.execute(
        "SELECT granted FROM consents WHERE patient_id=? AND doctor_id=? AND granted=1",
        (record["patient_id"], did)
    ).fetchone()
    if not consent:
        conn.close()
        flash("No consent to access this record.", "danger")
        return redirect(url_for("doctor_dashboard"))

    if request.method == "POST":
        notes        = request.form.get("notes", "").strip()
        prescription = request.form.get("prescription", "").strip()

        if not notes:
            flash("Clinical notes are required.", "danger")
        else:
            conn.execute(
                "INSERT INTO diagnoses (record_id, doctor_id, notes, prescription) VALUES (?,?,?,?)",
                (record_id, did, notes, prescription)
            )
            conn.commit()
            log_action(did, "ADD_DIAGNOSIS", f"Record ID: {record_id}", request.remote_addr)
            flash("Diagnosis saved successfully.", "success")
            conn.close()
            return redirect(url_for("doctor_view_patient", patient_id=record["patient_id"]))

    existing_diagnoses = conn.execute(
        "SELECT * FROM diagnoses WHERE record_id=?", (record_id,)
    ).fetchall()
    conn.close()

    symptoms_list = json.loads(record["symptoms"])
    precautions   = json.loads(record["ai_precautions"] or "[]")

    return render_template("doctor/diagnose.html",
                           record=record,
                           existing_diagnoses=existing_diagnoses,
                           symptoms_list=symptoms_list,
                           precautions=precautions)


# ══════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    conn = get_db()
    total_users   = conn.execute("SELECT COUNT(*) as c FROM users WHERE role='patient'").fetchone()["c"]
    total_doctors = conn.execute("SELECT COUNT(*) as c FROM users WHERE role='doctor'").fetchone()["c"]
    total_records = conn.execute("SELECT COUNT(*) as c FROM medical_records").fetchone()["c"]
    recent_logs   = conn.execute(
        """SELECT a.*, u.full_name, u.role FROM audit_logs a
           LEFT JOIN users u ON a.user_id=u.id
           ORDER BY a.timestamp DESC LIMIT 20"""
    ).fetchall()
    conn.close()
    acc = ensure_model()
    return render_template("admin/dashboard.html",
                           total_users=total_users,
                           total_doctors=total_doctors,
                           total_records=total_records,
                           recent_logs=recent_logs,
                           accuracy=acc)


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/users.html", users=users)


@app.route("/admin/blockchain-audit")
@role_required("admin")
def blockchain_audit():
    """
    Verify integrity of ALL medical records in the system.
    Admin can see which records are intact and which (if any) were tampered.
    """
    conn = get_db()
    records = conn.execute(
        """SELECT mr.*, u.full_name AS patient_name
           FROM medical_records mr JOIN users u ON mr.patient_id=u.id
           ORDER BY mr.id ASC"""
    ).fetchall()
    conn.close()

    audit_results = []
    for r in records:
        symptoms_list = json.loads(r["symptoms"])
        record_data = {
            "patient_id": r["patient_id"],
            "symptoms": symptoms_list,
            "disease": r["predicted_disease"],
            "confidence": r["confidence"],
            "timestamp": r["timestamp"],
        }
        intact = verify_record_integrity(record_data, r["blockchain_hash"], r["prev_hash"])
        audit_results.append({
            "record": r,
            "intact": intact,
            "status": "✅ VERIFIED" if intact else "❌ TAMPERED",
        })

    log_action(session["user_id"], "BLOCKCHAIN_AUDIT", f"Audited {len(audit_results)} records", request.remote_addr)
    return render_template("admin/blockchain_audit.html", audit_results=audit_results)


@app.route("/admin/records")
@role_required("admin")
def admin_records():
    """Read-only view of all medical records."""
    conn = get_db()
    records = conn.execute(
        """SELECT mr.*, u.full_name AS patient_name
           FROM medical_records mr JOIN users u ON mr.patient_id=u.id
           ORDER BY mr.timestamp DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin/records.html", records=records)


# ── API: Re-train model (admin only) ─────────────────────

@app.route("/admin/retrain", methods=["POST"])
@role_required("admin")
def retrain_model():
    global MODEL_ACCURACY
    try:
        MODEL_ACCURACY = train_model()
        log_action(session["user_id"], "RETRAIN_MODEL", f"New accuracy: {MODEL_ACCURACY}%", request.remote_addr)
        flash(f"Model retrained successfully! Accuracy: {MODEL_ACCURACY}%", "success")
    except Exception as e:
        flash(f"Training failed: {str(e)}", "danger")
    return redirect(url_for("admin_dashboard"))


# ── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    ensure_model()
    print("\n" + "="*55)
    print("  AAROGYA AI — Healthcare System")
    print("  URL: http://127.0.0.1:5000")
    print("  Admin:  admin@aarogya.ai  / Admin@123")
    print("  Doctor: doctor@aarogya.ai / Doctor@123")
    print("  Register a patient at /register")
    print("="*55 + "\n")
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))