from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "collegebloodsecret"

ADMIN_USERNAME = "admin"
HASHED_PASSWORD = generate_password_hash("1234")

DEPT_CODES = {
    "21": "CSE",
    "22": "ECE",
    "23": "ME",
    "24": "CE",
    "25": "EEE"
}

# ---------------- DATABASE ----------------

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            erp_id TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            batch TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            blood_group TEXT NOT NULL,
            phone TEXT NOT NULL,
            available TEXT NOT NULL,
            approved TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- HOME ----------------

@app.route('/')
def home():
    return render_template("index.html")

# ---------------- REGISTER ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        erp_id = request.form['erp_id']

        if not erp_id.isdigit() or len(erp_id) != 11:
            error = "ERP ID must be exactly 11 digits."
            return render_template("register.html", error=error)

        batch_year = int("20" + erp_id[:2])
        dept_code = erp_id[2:4]

        if dept_code not in DEPT_CODES:
            error = "Invalid Department Code in ERP."
            return render_template("register.html", error=error)

        department = DEPT_CODES[dept_code]

        current_year = datetime.now().year
        year_diff = current_year - batch_year + 1

        if year_diff <= 1:
            academic_year = "1st Year"
        elif year_diff == 2:
            academic_year = "2nd Year"
        elif year_diff == 3:
            academic_year = "3rd Year"
        else:
            academic_year = "4th Year"

        conn = get_db_connection()

        existing = conn.execute(
            "SELECT * FROM donors WHERE erp_id=?", (erp_id,)
        ).fetchone()

        if existing:
            conn.close()
            error = "ERP ID already registered."
            return render_template("register.html", error=error)

        conn.execute("""
            INSERT INTO donors (name, erp_id, department, batch,
                                academic_year, blood_group, phone,
                                available, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form['name'],
            erp_id,
            department,
            str(batch_year),
            academic_year,
            request.form['blood_group'],
            request.form['phone'],
            "Yes",
            "No"
        ))

        conn.commit()
        conn.close()

        return redirect(url_for('donor_login'))

    return render_template("register.html", error=error)

# ---------------- FIND DONOR ----------------

@app.route('/search', methods=['GET', 'POST'])
def search():
    donors = []

    if request.method == 'POST':
        blood_group = request.form.get('blood_group')
        department = request.form.get('department')
        batch = request.form.get('batch')

        query = """
            SELECT * FROM donors
            WHERE approved='Yes' AND available='Yes'
        """
        params = []

        if blood_group and blood_group != "All":
            query += " AND blood_group=?"
            params.append(blood_group)

        if department and department != "All":
            query += " AND department=?"
            params.append(department)

        if batch and batch != "All":
            query += " AND batch=?"
            params.append(batch)

        conn = get_db_connection()
        donors = conn.execute(query, params).fetchall()
        conn.close()

    return render_template("search.html", donors=donors)

# ---------------- DONOR LOGIN ----------------

@app.route('/donor_login', methods=['GET', 'POST'])
def donor_login():
    error = None

    if request.method == 'POST':
        erp_id = request.form['erp_id']

        conn = get_db_connection()
        donor = conn.execute(
            "SELECT * FROM donors WHERE erp_id=?", (erp_id,)
        ).fetchone()
        conn.close()

        if donor:
            session['donor_id'] = donor["id"]
            return redirect(url_for('donor_dashboard'))
        else:
            error = "Invalid ERP ID"

    return render_template("donor_login.html", error=error)

# ---------------- DONOR DASHBOARD ----------------

@app.route('/donor_dashboard')
def donor_dashboard():
    if not session.get('donor_id'):
        return redirect(url_for('donor_login'))

    conn = get_db_connection()
    donor = conn.execute(
        "SELECT * FROM donors WHERE id=?",
        (session['donor_id'],)
    ).fetchone()
    conn.close()

    return render_template("donor_dashboard.html", donor=donor)

@app.route('/admin_toggle/<int:id>')
def admin_toggle(id):
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    donor = conn.execute(
        "SELECT available FROM donors WHERE id=?",
        (id,)
    ).fetchone()

    new_status = "No" if donor["available"] == "Yes" else "Yes"

    conn.execute(
        "UPDATE donors SET available=? WHERE id=?",
        (new_status, id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/donor_logout')
def donor_logout():
    session.pop('donor_id', None)
    return redirect(url_for('home'))

# ---------------- ADMIN ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and \
           check_password_hash(HASHED_PASSWORD, request.form['password']):
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid Credentials"

    return render_template("login.html", error=error)

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    donors = conn.execute("SELECT * FROM donors").fetchall()

    blood_stats = conn.execute("""
        SELECT blood_group, COUNT(*) as count
        FROM donors
        WHERE approved='Yes'
        GROUP BY blood_group
    """).fetchall()

    conn.close()

    blood_labels = [row["blood_group"] for row in blood_stats]
    blood_counts = [row["count"] for row in blood_stats]

    return render_template(
        "dashboard.html",
        donors=donors,
        blood_labels=blood_labels,
        blood_counts=blood_counts
    )

@app.route('/approve/<int:id>')
def approve(id):
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute("UPDATE donors SET approved='Yes' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)