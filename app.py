from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Backend is running!"

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_db():
    conn = sqlite3.connect("db.sqlite3")
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------
# POLICY ENGINE
# -----------------------------
def validate_policy(role, amount, remaining_budget):

    # Only Officer and Admin roles allowed
    if role not in ["Officer", "Admin"]:
        return False, "Unauthorized role"

    # Amount must be positive
    if amount <= 0:
        return False, "Invalid amount"

    # Check budget
    if amount > remaining_budget:
        return False, "Budget exceeded"

    # Optional rule: require higher approval
    if amount > 100000:
        return False, "Requires higher approval"

    return True, "Approved"

# -----------------------------
# API: SUBMIT TRANSACTION
# -----------------------------
@app.route("/submit-transaction", methods=["POST"])
def submit_transaction():

    data = request.get_json(force=True)  # ensures JSON is parsed
    department = data.get("department")
    amount_str = data.get("amount")
    role = data.get("role")

    # Check if amount is valid
    if amount_str is None:
        return {"error": "Amount is required"}, 400

    try:
        amount = float(amount_str)
    except ValueError:
        return {"error": "Amount must be a number"}, 400

    conn = get_db()
    cursor = conn.cursor()

    # Get department budget
    cursor.execute("SELECT * FROM budgets WHERE department=?", (department,))
    budget = cursor.fetchone()

    if not budget:
        return jsonify({"status": "Rejected", "reason": "Department not found"})

    remaining_budget = budget["remaining_budget"]

    # Policy validation
    valid, message = validate_policy(role, amount, remaining_budget)

    if not valid:
        return jsonify({"status": "Rejected", "reason": message})

    # Update budget
    new_remaining = remaining_budget - amount
    new_used = budget["used_budget"] + amount

    cursor.execute("""
        UPDATE budgets 
        SET remaining_budget=?, used_budget=? 
        WHERE department=?
    """, (new_remaining, new_used, department))

    # Insert transaction record
    cursor.execute("""
        INSERT INTO transactions (department, amount, status, timestamp)
        VALUES (?, ?, ?, ?)
    """, (department, amount, "Approved", datetime.now()))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "Approved",
        "remaining_budget": new_remaining,
        "tx_hash": "PENDING"   # Blockchain placeholder
    })

# -----------------------------
# API: GET BUDGET
# -----------------------------
@app.route("/budget/<department>", methods=["GET"])
def get_budget(department):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM budgets WHERE department=?", (department,))
    budget = cursor.fetchone()

    conn.close()

    if not budget:
        return jsonify({"error": "Department not found"}), 404

    return jsonify(dict(budget))

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)