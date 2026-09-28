import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

app = Flask(__name__)
app.secret_key = "talentnest-secret-key-change-in-production"

serializer = URLSafeTimedSerializer(app.secret_key)    


def generate_reset_token(email):
    return serializer.dumps(email, salt="password-reset")

def verify_reset_token(token, max_age=1800):  # 30 minutes
    try:
        return serializer.loads(token, salt="password-reset", max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "talentnest.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
COLLEGE_NAME = "Oxford College"

app = Flask(__name__)
app.secret_key = "talentnest-secret-key-change-in-production"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload cap

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    """Return a request-scoped sqlite3 connection with Row factory."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

#--------forgot password-----
import smtplib
from email.mime.text import MIMEText

MAIL_USERNAME = "talenttnest@gmail.com"
MAIL_PASSWORD = "nwhdvpwtxoyqwvaw"

def send_reset_email(to_email, reset_url):
    msg = MIMEText(f"Click the link to reset your TalentNest password:\n\n{reset_url}\n\nThis link expires in 30 minutes.")
    msg["Subject"] = "TalentNest — Password Reset"
    msg["From"] = MAIL_USERNAME
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, to_email, msg.as_string())

def send_verification_email(to_email, full_name, status):

    if status == "Approved":
        subject = "TalentNest - College ID Approved"

        body = f"""
Hello {full_name},

Your Oxford College ID has been verified and approved by the TalentNest administrator.

You can now log in and use TalentNest.

Thank you,
TalentNest Admin
"""

    else:
        subject = "TalentNest - College ID Rejected"

        body = f"""
Hello {full_name},

Your Oxford College ID verification for TalentNest has been rejected by the administrator.

Please contact the TalentNest administrator for further information.

Thank you,
TalentNest Admin
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = MAIL_USERNAME
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(
            MAIL_USERNAME,
            to_email,
            msg.as_string()
        )

def init_db():
    """Create all tables if they do not already exist. Never drops data."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','client','admin')),
        college_id_card TEXT,
        verification_status TEXT DEFAULT 'Not Required'
            CHECK(verification_status IN ('Pending', 'Approved', 'Rejected', 'Not Required')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
        # Add verification columns to existing databases
    try:
        cur.execute("ALTER TABLE users ADD COLUMN college_id_card TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN verification_status TEXT DEFAULT 'Not Required'
        """)
    except sqlite3.OperationalError:
        pass

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS student_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            photo TEXT,
            about TEXT,
            college TEXT,
            branch TEXT,
            year_sem TEXT,
            category_id INTEGER,
            location TEXT,
            starting_price REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        college TEXT NOT NULL DEFAULT 'Oxford College',
        branch TEXT,
        year_sem TEXT,
        location TEXT NOT NULL DEFAULT 'Kozhikode',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            required_date TEXT,
            college TEXT,
            year TEXT,
            branch TEXT,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Accepted','Rejected','Delivered')),
            reference_image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL UNIQUE,
            client_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Seed starter categories only if the table is empty
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        starter_categories = [
            "Cake Making", "Craft", "Drawing", "Crochet",
            "Handmade Candles", "Jewellery", "Gift Making"
        ]
        cur.executemany(
            "INSERT INTO categories (category_name) VALUES (?)",
            [(c,) for c in starter_categories]
        )

    # Seed one admin account if no admin exists yet
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (full_name, email, phone, password_hash, role) VALUES (?,?,?,?,?)",
            ("Platform Admin", "admin@gmail.com", "9999999999",
             generate_password_hash("admin@123"), "admin")
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth / access-control helpers
# ---------------------------------------------------------------------------
def login_required(role=None):
    """Require login and approved college ID for students/clients."""

    def decorator(view_func):

        @wraps(view_func)
        def wrapped(*args, **kwargs):

            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login", next=request.url))

            # Admin does not need ID verification
            if session.get("role") != "admin":

                db = get_db()

                user = db.execute(
                    """
                    SELECT verification_status
                    FROM users
                    WHERE id = ?
                    """,
                    (session["user_id"],)
                ).fetchone()

                if not user or user["verification_status"] != "Approved":

                    session.clear()

                    flash(
                        "Your Oxford College ID must be approved by the admin before you can use TalentNest.",
                        "warning"
                    )

                    return redirect(url_for("login"))

            if role and session.get("role") != role:
                flash(
                    "You are not authorized to view that page.",
                    "danger"
                )
                return redirect(url_for("dashboard_redirect"))

            return view_func(*args, **kwargs)

        return wrapped

    return decorator

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    """Save an uploaded file securely; return stored filename or None."""
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name


@app.context_processor
def inject_globals():
    return {"current_role": session.get("role"), "current_name": session.get("full_name")}

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            token = generate_reset_token(email)
            reset_url = url_for("reset_password", token=token, _external=True)
            send_reset_email(email, reset_url)
        # Same message whether or not the email exists — don't reveal which accounts are real
        flash("If that email is registered, a reset link has been sent.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("reset_password", token=token))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("reset_password", token=token))

        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE email = ?",
                   (generate_password_hash(password), email))
        db.commit()
        flash("Your password has been reset. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# ---------------------------------------------------------------------------
# Error handlers - never leak raw tracebacks to end users
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You don't have permission to view this page."), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Something went wrong on our end. Please try again."), 500


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY category_name").fetchall()
    featured_services = db.execute("""
        SELECT s.id, s.service_name, s.price, s.image, u.full_name,
               c.category_name, 'Kozhikode' AS location
        FROM services s
        JOIN users u ON u.id = s.user_id
        JOIN categories c ON c.id = s.category_id
        LEFT JOIN student_profiles sp ON sp.user_id = u.id
        ORDER BY s.created_at DESC LIMIT 6
    """).fetchall()
    return render_template("index.html", categories=categories, featured_services=featured_services)


@app.route("/dashboard")
def dashboard_redirect():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "client":
        return redirect(url_for("client_dashboard"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Registration / Login / Logout
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "")
        college_id_card = request.files.get("college_id_card")

        errors = []
        if not full_name or not email or not phone or not password:
            errors.append("All fields are required.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if role not in ("student", "client"):
            errors.append("Please select a valid role.")
        if not college_id_card or college_id_card.filename == "":
            errors.append("Please upload your Oxford College ID card.")
        elif not allowed_file(college_id_card.filename):
            errors.append("ID card must be a JPG, JPEG or PNG image.")

        db = get_db()
        if not errors:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                errors.append("An account with this email already exists.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("register.html", form=request.form)

        password_hash = generate_password_hash(password)

        id_card_filename = save_upload(college_id_card)

        if not id_card_filename:
                flash("Failed to upload ID card. Please try again.", "danger")
                return render_template("register.html", form=request.form)

        db.execute(
                """
                INSERT INTO users
                (full_name, email, phone, password_hash, role, college_id_card, verification_status)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    full_name,
                    email,
                    phone,
                    password_hash,
                    role,
                    id_card_filename,
                    "Pending"
                )
            )

        db.commit()

        if role == "student":
            new_user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            db.execute("INSERT INTO student_profiles (user_id) VALUES (?)", (new_user["id"],))
            db.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            next_page = request.args.get("next")

            if next_page:
             return redirect(next_page)
            return redirect(url_for("dashboard_redirect"))

        flash("Invalid email or password.", "danger")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# STUDENT routes
# ---------------------------------------------------------------------------
@app.route("/student_dashboard")
@login_required(role="student")
def student_dashboard():
    db = get_db()
    uid = session["user_id"]
    profile = db.execute("SELECT * FROM student_profiles WHERE user_id = ?", (uid,)).fetchone()
    services_count = db.execute("SELECT COUNT(*) c FROM services WHERE user_id = ?", (uid,)).fetchone()["c"]
    pending_count = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE student_id = ? AND status = 'Pending'", (uid,)
    ).fetchone()["c"]
    accepted_count = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE student_id = ? AND status = 'Accepted'", (uid,)
    ).fetchone()["c"]
    delivered_count = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE student_id = ? AND status = 'Delivered'", (uid,)
    ).fetchone()["c"]
    return render_template(
        "student_dashboard.html", profile=profile, services_count=services_count,
        pending_count=pending_count, accepted_count=accepted_count, delivered_count=delivered_count
    )


@app.route("/student_profile", methods=["GET", "POST"])
@login_required(role="student")
def student_profile():
    db = get_db()
    uid = session["user_id"]
    categories = db.execute(
        "SELECT * FROM categories ORDER BY category_name"
    ).fetchall()

    if request.method == "POST":

        about = request.form.get("about", "").strip()
        branch = request.form.get("branch", "").strip()
        year_sem = request.form.get("year_sem", "").strip()
        graduation_year = request.form.get("graduation_year", "").strip()
        if not graduation_year.isdigit() or len(graduation_year) != 4:
            flash("Please enter a valid graduation year.", "danger")
            return redirect(url_for("student_profile"))

        graduation_year = int(graduation_year)
        location = "Kozhikode"
        category_choice = request.form.get("category", "")
        other_category = request.form.get("other_category", "").strip()

        # -----------------------------
        # Resolve category
        # -----------------------------
        if category_choice == "other" and other_category:

            existing_cat = db.execute(
                """
                SELECT id FROM categories
                WHERE category_name = ? COLLATE NOCASE
                """,
                (other_category,)
            ).fetchone()

            if existing_cat:
                category_id = existing_cat["id"]

            else:
                cur = db.execute(
                    "INSERT INTO categories (category_name) VALUES (?)",
                    (other_category,)
                )
                db.commit()
                category_id = cur.lastrowid

        elif category_choice.isdigit():

            category_id = int(category_choice)

        else:
            flash("Please select or enter a category.", "danger")
            return redirect(url_for("student_profile"))

        # -----------------------------
        # Profile photo
        # -----------------------------
        photo_file = request.files.get("photo")
        photo_filename = save_upload(photo_file)

        # -----------------------------
        # College ID card
        # -----------------------------
        college_id_file = request.files.get("college_id_card")
        college_id_filename = save_upload(college_id_file)

        # -----------------------------
        # Existing profile
        # -----------------------------
        existing_profile = db.execute(
            "SELECT * FROM student_profiles WHERE user_id = ?",
            (uid,)
        ).fetchone()

        if existing_profile:

            if photo_filename:

                db.execute(
                    """
                    UPDATE student_profiles
                    SET about=?,
                        branch=?,
                        year_sem=?,
                        graduation_year=?,
                        category_id=?,
                        photo=?
                    WHERE user_id=?
                    """,
                    (
                        about,
                        branch,
                        year_sem,
                        graduation_year,
                        category_id,
                        photo_filename,
                        uid
                    )
                )

            else:

                db.execute(
                    """
                    UPDATE student_profiles
                    SET about=?,
                        branch=?,
                        year_sem=?,
                        graduation_year=?,
                        category_id=?
                    WHERE user_id=?
                    """,
                    (
                        about,
                        branch,
                        year_sem,
                        graduation_year,
                        category_id,
                        uid
                    )
                )

        else:

            db.execute(
                """
                INSERT INTO student_profiles
                (user_id, about, branch, year_sem, category_id, graduation_year, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    about,
                    branch,
                    year_sem,
                    category_id,
                    graduation_year,
                    photo_filename
                )
            )

        # -----------------------------
        # Save College ID
        # -----------------------------
        if college_id_filename:

            db.execute(
                """
                UPDATE users
                SET college_id_card = ?,
                    verification_status = 'Pending'
                WHERE id = ?
                """,
                (college_id_filename, uid)
            )

        db.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for("student_dashboard"))

    # -----------------------------
    # GET profile
    # -----------------------------
    profile = db.execute(
        "SELECT * FROM student_profiles WHERE user_id = ?",
        (uid,)
    ).fetchone()

    # Get College ID information
    user = db.execute(
        """
        SELECT college_id_card, verification_status
        FROM users
        WHERE id = ?
        """,
        (uid,)
    ).fetchone()

    return render_template(
        "student_profile.html",
        profile=profile,
        categories=categories,
        user_college_id_card=user["college_id_card"] if user else None,
        verification_status=user["verification_status"] if user else "Not Required"
    )
    # Check if student is an Alumni
    profile = db.execute("""
        SELECT graduation_year
        FROM student_profiles
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    if profile and profile["graduation_year"] <= 2025:
        flash("Alumni cannot add services.", "warning")
        return redirect(url_for("student_dashboard"))
@app.route("/add_service", methods=["GET", "POST"])
@login_required(role="student")
def add_service():
    db = get_db()
    uid = session["user_id"]
    categories = db.execute("SELECT * FROM categories ORDER BY category_name").fetchall()

    if request.method == "POST":
        service_name = request.form.get("service_name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        category_id = request.form.get("category_id", "")

        if not service_name or not price or not category_id:
            flash("Service name, category and price are required.", "danger")
            return redirect(url_for("add_service"))
        if not price.replace(".", "", 1).isdigit():
            flash("Price must be a valid number.", "danger")
            return redirect(url_for("add_service"))

        image_filename = save_upload(request.files.get("image"))

        db.execute("""
            INSERT INTO services (user_id, category_id, service_name, description, price, image)
            VALUES (?,?,?,?,?,?)
        """, (uid, category_id, service_name, description, price, image_filename))
        db.commit()
        flash("Service added successfully.", "success")
        return redirect(url_for("my_services"))

    return render_template("add_service.html", categories=categories)


@app.route("/my_services")
@login_required(role="student")
def my_services():
    db = get_db()
    services = db.execute("""
        SELECT s.*, c.category_name FROM services s
        JOIN categories c ON c.id = s.category_id
        WHERE s.user_id = ? ORDER BY s.created_at DESC
    """, (session["user_id"],)).fetchall()
    return render_template("my_services.html", services=services)


@app.route("/edit_service/<int:service_id>", methods=["GET", "POST"])
@login_required(role="student")
def edit_service(service_id):
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not service:
        abort(404)
    if service["user_id"] != session["user_id"]:
        abort(403)

    categories = db.execute("SELECT * FROM categories ORDER BY category_name").fetchall()

    if request.method == "POST":
        service_name = request.form.get("service_name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        category_id = request.form.get("category_id", "")

        if not service_name or not price or not category_id:
            flash("Service name, category and price are required.", "danger")
            return redirect(url_for("edit_service", service_id=service_id))

        image_filename = save_upload(request.files.get("image"))
        if image_filename:
            db.execute("""
                UPDATE services SET service_name=?, description=?, price=?, category_id=?, image=?
                WHERE id=?
            """, (service_name, description, price, category_id, image_filename, service_id))
        else:
            db.execute("""
                UPDATE services SET service_name=?, description=?, price=?, category_id=?
                WHERE id=?
            """, (service_name, description, price, category_id, service_id))
        db.commit()
        flash("Service updated successfully.", "success")
        return redirect(url_for("my_services"))

    return render_template("edit_service.html", service=service, categories=categories)


@app.route("/delete_service/<int:service_id>", methods=["POST"])
@login_required(role="student")
def delete_service(service_id):
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not service:
        abort(404)
    if service["user_id"] != session["user_id"]:
        abort(403)
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    flash("Service deleted.", "info")
    return redirect(url_for("my_services"))

@app.route("/pending_bookings")
@login_required(role="student")
def pending_bookings():

    db = get_db()

    bookings = db.execute("""
        SELECT
            b.id,
            b.service_id,
            b.client_id,
            b.required_date,
            b.message,
            b.status,
            b.reference_image,
            b.created_at,

            s.service_name,

            u.full_name AS client_name,
            u.email AS client_email,
            u.phone AS client_phone,

            cp.college AS client_college,
            cp.branch AS client_branch,
            cp.year_sem AS client_year_sem,
            'Kozhikode' AS client_location

        FROM bookings b

        JOIN services s
            ON s.id = b.service_id

        JOIN users u
            ON u.id = b.client_id

        LEFT JOIN client_profiles cp
            ON cp.user_id = b.client_id

        WHERE b.student_id = ?
          AND b.status = 'Pending'

        ORDER BY b.created_at DESC

    """, (session["user_id"],)).fetchall()

    return render_template(
        "pending_bookings.html",
        bookings=bookings
    )

@app.route("/accept_booking/<int:booking_id>", methods=["POST"])
@login_required(role="student")
def accept_booking(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        abort(404)
    if booking["student_id"] != session["user_id"]:
        abort(403)
    if booking["status"] != "Pending":
        flash("This booking has already been processed.", "warning")
        return redirect(url_for("pending_bookings"))

    db.execute("UPDATE bookings SET status = 'Accepted' WHERE id = ?", (booking_id,))
    db.commit()
    flash("Booking accepted.", "success")
    return redirect(url_for("pending_bookings"))


@app.route("/reject_booking/<int:booking_id>", methods=["POST"])
@login_required(role="student")
def reject_booking(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        abort(404)
    if booking["student_id"] != session["user_id"]:
        abort(403)
    if booking["status"] != "Pending":
        flash("This booking has already been processed.", "warning")
        return redirect(url_for("pending_bookings"))

    db.execute("UPDATE bookings SET status = 'Rejected' WHERE id = ?", (booking_id,))
    db.commit()
    flash("Booking rejected.", "info")
    return redirect(url_for("pending_bookings"))


@app.route("/accepted_bookings")
@login_required(role="student")
def accepted_bookings():

    db = get_db()

    bookings = db.execute("""
        SELECT
            b.id,
            b.required_date,
            b.message,
            b.status,
            b.reference_image,
            b.created_at,

            s.service_name,

            u.full_name AS client_name,
            u.phone AS client_phone,

            cp.college AS client_college,
            cp.branch AS client_branch,
            cp.year_sem AS client_year_sem,

            'Kozhikode' AS client_location

        FROM bookings b

        JOIN services s
            ON s.id = b.service_id

        JOIN users u
            ON u.id = b.client_id

        LEFT JOIN client_profiles cp
            ON cp.user_id = b.client_id

        WHERE b.student_id = ?
          AND b.status = 'Accepted'

        ORDER BY b.created_at DESC

    """, (session["user_id"],)).fetchall()

    return render_template(
        "accepted_bookings.html",
        bookings=bookings
    )
@app.route("/delivery_done/<int:booking_id>", methods=["POST"])
@login_required(role="student")
def delivery_done(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        abort(404)
    if booking["student_id"] != session["user_id"]:
        abort(403)
    if booking["status"] != "Accepted":
        flash("Only accepted bookings can be marked as delivered.", "warning")
        return redirect(url_for("accepted_bookings"))

    db.execute("UPDATE bookings SET status = 'Delivered' WHERE id = ?", (booking_id,))
    db.commit()
    flash("Booking marked as delivered.", "success")
    return redirect(url_for("accepted_bookings"))


@app.route("/completed_bookings")
@login_required(role="student")
def completed_bookings():
    db = get_db()
    bookings = db.execute("""
        SELECT b.*, s.service_name, u.full_name AS client_name
        FROM bookings b
        JOIN services s ON s.id = b.service_id
        JOIN users u ON u.id = b.client_id
        WHERE b.student_id = ? AND b.status = 'Delivered'
        ORDER BY b.created_at DESC
    """, (session["user_id"],)).fetchall()
    return render_template("completed_bookings.html", bookings=bookings)


# ---------------------------------------------------------------------------
# CLIENT routes
# ---------------------------------------------------------------------------
@app.route("/client_dashboard")
@login_required(role="client")
def client_dashboard():

    db = get_db()
    uid = session["user_id"]

    counts = {}

    for status in ("Pending", "Accepted", "Rejected", "Delivered"):
        counts[status] = db.execute(
            "SELECT COUNT(*) c FROM bookings WHERE client_id = ? AND status = ?",
            (uid, status)
        ).fetchone()["c"]

    categories = db.execute(
        "SELECT * FROM categories ORDER BY category_name"
    ).fetchall()

    # Check for delivered booking that has not been reviewed
    delivered_booking = db.execute("""
        SELECT b.id, s.service_name, u.full_name AS student_name
        FROM bookings b
        JOIN services s ON s.id = b.service_id
        JOIN users u ON u.id = b.student_id
        LEFT JOIN reviews r ON r.booking_id = b.id
        WHERE b.client_id = ?
          AND b.status = 'Delivered'
          AND r.id IS NULL
        ORDER BY b.created_at DESC
        LIMIT 1
    """, (uid,)).fetchone()

    return render_template(
        "client_dashboard.html",
        counts=counts,
        categories=categories,
        delivered_booking=delivered_booking
    )
@app.route("/client_profile", methods=["GET", "POST"])
@login_required(role="client")
def client_profile():

    db = get_db()
    uid = session["user_id"]

    if request.method == "POST":

        # Basic details
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        # Client academic details
        branch = request.form.get("branch", "").strip()
        year_sem = request.form.get("year_sem", "").strip()

        # Fixed values
        college = "Oxford College"
        location = "Kozhikode"

        # Validate required fields
        if not full_name or not email or not phone:
            flash("Name, email and phone are required.", "danger")
            return redirect(url_for("client_profile"))

        if not branch or not year_sem:
            flash(
                "Branch and Year / Semester are required.",
                "danger"
            )
            return redirect(url_for("client_profile"))

        # Check whether another user already uses this email
        existing_user = db.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
              AND id != ?
            """,
            (email, uid)
        ).fetchone()

        if existing_user:
            flash("This email is already registered.", "danger")
            return redirect(url_for("client_profile"))

        # Update basic user information
        db.execute(
            """
            UPDATE users
            SET full_name = ?,
                email = ?,
                phone = ?
            WHERE id = ?
            """,
            (full_name, email, phone, uid)
        )

        # Check whether client profile already exists
        existing_profile = db.execute(
            """
            SELECT id
            FROM client_profiles
            WHERE user_id = ?
            """,
            (uid,)
        ).fetchone()

        if existing_profile:

            # Update existing client profile
            db.execute(
                """
                UPDATE client_profiles
                SET college = ?,
                    branch = ?,
                    year_sem = ?,
                    location
                WHERE user_id = ?
                """,
                (
                    college,
                    branch,
                    year_sem,
                    location,
                    uid
                )
            )

        else:

            # Create new client profile
            db.execute(
                """
                INSERT INTO client_profiles
                (user_id, college, branch, year_sem, location)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    college,
                    branch,
                    year_sem,
                    location
                )
            )

        # Optional ID card upload
        college_id_file = request.files.get("college_id_card")

        if college_id_file and college_id_file.filename:

            college_id_filename = save_upload(college_id_file)

            if not college_id_filename:
                flash(
                    "Invalid ID card. Please upload JPG, JPEG or PNG.",
                    "danger"
                )
                return redirect(url_for("client_profile"))

            db.execute(
                """
                UPDATE users
                SET college_id_card = ?,
                    verification_status = 'Pending'
                WHERE id = ?
                """,
                (college_id_filename, uid)
            )

        db.commit()

        # Update session name
        session["name"] = full_name

        flash(
            "Profile updated successfully.",
            "success"
        )

        return redirect(url_for("client_profile"))

    # Get user details
    user = db.execute(
        """
        SELECT id,
               full_name,
               email,
               phone,
               role,
               college_id_card,
               verification_status
        FROM users
        WHERE id = ?
        """,
        (uid,)
    ).fetchone()

    # Get client profile details
    profile = db.execute(
        """
        SELECT college,
               branch,
               year_sem,
               location
        FROM client_profiles
        WHERE user_id = ?
        """,
        (uid,)
    ).fetchone()

    return render_template(
        "client_profile.html",
        user=user,
        profile=profile
    )

@app.route("/categories")
def categories_list():
    db = get_db()
    categories = db.execute("""
        SELECT c.id, c.category_name, c.description, c.image,
               COUNT(DISTINCT s.user_id) AS student_count
        FROM categories c
        LEFT JOIN services s ON s.category_id = c.id
        GROUP BY c.id ORDER BY c.category_name
    """).fetchall()
    return render_template("categories.html", categories=categories)

@app.route("/category/<int:category_id>")
@login_required(role="client")
def category_students(category_id):
    db = get_db()

    category = db.execute(
        "SELECT * FROM categories WHERE id = ?",
        (category_id,)
    ).fetchone()

    if not category:
        abort(404)

    # Get selected price filter
    price_filter = request.args.get("price", "")

    query = """
        SELECT DISTINCT
            u.id AS user_id,
            u.full_name,
            sp.photo
        FROM services s
        JOIN users u ON u.id = s.user_id
        LEFT JOIN student_profiles sp ON sp.user_id = u.id
        WHERE s.category_id = ?
        AND (
            sp.graduation_year IS NULL
            OR sp.graduation_year > 2025
        )
    """

    params = [category["id"]]

    # Apply price filter
    if price_filter == "under200":
        query += " AND s.price < 200"

    elif price_filter == "200to500":
        query += " AND s.price >= 200 AND s.price <= 500"

    elif price_filter == "500to1000":
        query += " AND s.price > 500 AND s.price <= 1000"

    elif price_filter == "above1000":
        query += " AND s.price > 1000"

    query += " ORDER BY u.full_name"

    students = db.execute(query, params).fetchall()

    return render_template(
        "category_students.html",
        students=students,
        category=category,
        price_filter=price_filter
    )
@app.route("/student/<int:student_user_id>")
@login_required(role="client")
def view_student(student_user_id):
    db = get_db()

    # Get category selected by the client
    category_id = request.args.get("category_id", type=int)

    # Get selected price filter
    price_filter = request.args.get("price", "")

    student = db.execute("""
        SELECT * FROM users
        WHERE id = ? AND role = 'student'
    """, (student_user_id,)).fetchone()

    if not student:
        abort(404)

    profile = db.execute("""
        SELECT * FROM student_profiles
        WHERE user_id = ?
    """, (student_user_id,)).fetchone()

    # Determine Student or Alumni status
    if profile and profile["graduation_year"]:
        if profile["graduation_year"] <= 2025:
            student_status = "Alumni"
        else:
            student_status = "Student"
    else:
        student_status = "Student"

    category = None

    if category_id:
        category = db.execute("""
            SELECT * FROM categories
            WHERE id = ?
        """, (category_id,)).fetchone()

    elif profile and profile["category_id"]:
        category = db.execute("""
            SELECT * FROM categories
            WHERE id = ?
        """, (profile["category_id"],)).fetchone()

        category_id = profile["category_id"]

    # Get ONLY services from the selected category
    query = """
        SELECT
            s.*,
            c.category_name
        FROM services s
        JOIN categories c
            ON c.id = s.category_id
        WHERE s.user_id = ?
        AND s.category_id = ?
    """

    params = [student_user_id, category_id]

    # Apply price filter
    if price_filter == "under200":
        query += " AND s.price < 200"

    elif price_filter == "200to500":
        query += " AND s.price >= 200 AND s.price <= 500"

    elif price_filter == "500to1000":
        query += " AND s.price > 500 AND s.price <= 1000"

    elif price_filter == "above1000":
        query += " AND s.price > 1000"

    query += " ORDER BY s.created_at DESC"

    services = db.execute(query, params).fetchall()

    reviews = db.execute("""
        SELECT
            r.*,
            u.full_name AS client_name,
            b.service_id
        FROM reviews r
        JOIN users u
            ON u.id = r.client_id
        JOIN bookings b
            ON b.id = r.booking_id
        WHERE r.student_id = ?
        ORDER BY r.created_at DESC
    """, (student_user_id,)).fetchall()

    return render_template(
        "view_student.html",
        student=student,
        profile=profile,
        category=category,
        services=services,
        reviews=reviews,
        price_filter=price_filter,
        student_status=student_status
    )

@app.route("/book_service/<int:service_id>", methods=["GET", "POST"])
@login_required(role="client")
def book_service(service_id):

    db = get_db()
    client_id = session["user_id"]

    # Get service and student
    service = db.execute("""
        SELECT s.*,
               u.full_name AS student_name
        FROM services s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = ?
    """, (service_id,)).fetchone()

    if not service:
        abort(404)

    # Get client's profile
    client_profile = db.execute("""
        SELECT
            college,
            branch,
            year_sem,
            'Kozhikode' AS location
        FROM client_profiles
        WHERE user_id = ?
    """, (client_id,)).fetchone()

    if not client_profile:
        flash(
            "Please complete your profile before booking a service.",
            "warning"
        )
        return redirect(url_for("client_profile"))

    # Get client's phone number
    client = db.execute("""
        SELECT phone
        FROM users
        WHERE id = ?
    """, (client_id,)).fetchone()

    client_phone = client["phone"] if client else ""

    if request.method == "POST":

        required_date = request.form.get("required_date", "").strip()
        message = request.form.get("message", "").strip()

        if not required_date:
            flash(
                "Required date is mandatory.",
                "danger"
            )
            return redirect(
                url_for("book_service", service_id=service_id)
            )

        # Save reference image if provided
        reference_image = save_upload(
            request.files.get("reference_image")
        )

        # Create booking
        # Client details such as college, branch and year
        # will be retrieved later from client_profiles.
        db.execute("""
            INSERT INTO bookings (
                service_id,
                student_id,
                client_id,
                required_date,
                message,
                status,
                reference_image
            )
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (
            service_id,
            service["user_id"],
            client_id,
            required_date,
            message,
            reference_image
        ))

        db.commit()

        flash(
            "Booking request sent successfully!",
            "success"
        )

        return redirect(url_for("my_bookings"))

    return render_template(
        "book_service.html",
        service=service,
        client_profile=client_profile,
        client_phone=client_phone
    )
@app.route("/my_bookings")
@login_required(role="client")
def my_bookings():

    db = get_db()
    client_id = session["user_id"]

    bookings = db.execute("""
        SELECT
            b.id,
            b.id AS booking_id,
            b.service_id,
            s.service_name,
            u.full_name AS student_name,
            b.required_date,
            b.status,
            b.created_at
        FROM bookings b
        JOIN services s
            ON s.id = b.service_id
        JOIN users u
            ON u.id = b.student_id
        WHERE b.client_id = ?
        ORDER BY b.created_at DESC
    """, (client_id,)).fetchall()

    # Get bookings that already have a review
    reviewed_ids = {
        row["booking_id"]
        for row in db.execute("""
            SELECT booking_id
            FROM reviews
            WHERE client_id = ?
        """, (client_id,)).fetchall()
    }

    return render_template(
        "my_bookings.html",
        bookings=bookings,
        reviewed_ids=reviewed_ids
    )


@app.route("/review/<int:booking_id>", methods=["GET", "POST"])
@login_required(role="client")
def review(booking_id):

    db = get_db()
    client_id = session["user_id"]

    # Get the specific booking and the specific service/item
    booking = db.execute("""
        SELECT
            b.id,
            b.client_id,
            b.student_id,
            b.service_id,
            b.status,
            s.service_name,
            u.full_name AS student_name

        FROM bookings b

        JOIN services s
            ON s.id = b.service_id

        JOIN users u
            ON u.id = b.student_id

        WHERE b.id = ?
    """, (booking_id,)).fetchone()

    # Booking does not exist
    if not booking:
        abort(404)

    # Make sure this booking belongs to the logged-in client
    if booking["client_id"] != client_id:
        abort(403)

    # Only delivered bookings can be reviewed
    if booking["status"] != "Delivered":
        flash(
            "You can only review a delivered booking.",
            "warning"
        )
        return redirect(url_for("my_bookings"))

    # Check whether THIS specific booking was already reviewed
    existing_review = db.execute("""
        SELECT id
        FROM reviews
        WHERE booking_id = ?
          AND client_id = ?
    """, (booking_id, client_id)).fetchone()

    if existing_review:
        flash(
            "You have already reviewed this booking.",
            "info"
        )
        return redirect(url_for("my_bookings"))

    # Submit review
    if request.method == "POST":

        rating = request.form.get("rating", "")
        comment = request.form.get("comment", "").strip()

        if rating not in ("1", "2", "3", "4", "5"):
            flash(
                "Please select a rating between 1 and 5.",
                "danger"
            )
            return redirect(
                url_for("review", booking_id=booking_id)
            )

        db.execute("""
            INSERT INTO reviews (
                booking_id,
                client_id,
                student_id,
                rating,
                comment
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            booking_id,
            client_id,
            booking["student_id"],
            rating,
            comment
        ))

        db.commit()

        flash(
            "Thank you for your review!",
            "success"
        )

        return redirect(url_for("my_bookings"))

    return render_template(
        "review.html",
        booking=booking
    )

# ---------------------------------------------------------------------------
# ADMIN routes
# ---------------------------------------------------------------------------
@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()["c"]
    total_clients = db.execute("SELECT COUNT(*) c FROM users WHERE role='client'").fetchone()["c"]
    total_services = db.execute("SELECT COUNT(*) c FROM services").fetchone()["c"]
    total_bookings = db.execute("SELECT COUNT(*) c FROM bookings").fetchone()["c"]
    recent_bookings = db.execute("""
        SELECT b.id, s.service_name, cu.full_name AS client_name, su.full_name AS student_name,
               b.status, b.created_at
        FROM bookings b
        JOIN services s ON s.id = b.service_id
        JOIN users cu ON cu.id = b.client_id
        JOIN users su ON su.id = b.student_id
        ORDER BY b.created_at DESC LIMIT 8
    """).fetchall()
    return render_template(
        "admin_dashboard.html", total_students=total_students, total_clients=total_clients,
        total_services=total_services, total_bookings=total_bookings, recent_bookings=recent_bookings
    )

@app.route("/admin/verifications")
@login_required(role="admin")
def admin_verifications():
    db = get_db()

    users = db.execute("""
        SELECT id, full_name, email, phone, role,
               college_id_card, verification_status, created_at
        FROM users
        WHERE role IN ('student', 'client')
        ORDER BY
            CASE verification_status
                WHEN 'Pending' THEN 1
                WHEN 'Approved' THEN 2
                WHEN 'Rejected' THEN 3
                ELSE 4
            END,
            created_at DESC
    """).fetchall()

    return render_template(
        "admin_verifications.html",
        users=users
    )

@app.route("/admin/verification/<int:user_id>/<action>", methods=["POST"])
@login_required(role="admin")
def update_verification(user_id, action):

    if action not in ("approve", "reject"):
        abort(400)

    db = get_db()

    user = db.execute(
        """
        SELECT id, full_name, email, role
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if not user or user["role"] not in ("student", "client"):
        flash("User not found.", "danger")
        return redirect(url_for("admin_verifications"))

    new_status = "Approved" if action == "approve" else "Rejected"

    db.execute(
        """
        UPDATE users
        SET verification_status = ?
        WHERE id = ?
        """,
        (new_status, user_id)
    )

    db.commit()

    # Send email notification
    try:
        send_verification_email(
            user["email"],
            user["full_name"],
            new_status
        )

        if new_status == "Approved":
            flash(
                "User ID verified successfully and email sent.",
                "success"
            )
        else:
            flash(
                "User ID rejected and email sent.",
                "warning"
            )

    except Exception as e:
        print("VERIFICATION EMAIL ERROR:", repr(e))

        if new_status == "Approved":
            flash(
                "User ID verified, but email could not be sent.",
                "warning"
            )
        else:
            flash(
                "User ID rejected, but email could not be sent.",
                "warning"
            )

    return redirect(url_for("admin_verifications"))
@app.route("/manage_students")
@login_required(role="admin")
def manage_students():
    db = get_db()
    students = db.execute("""
    SELECT
        u.id,
        u.full_name,
        u.email,
        u.phone,
        'Oxford College' AS college,
        c.category_name AS category,
        'Kozhikode' AS location
    FROM users u
    LEFT JOIN student_profiles sp
        ON sp.user_id = u.id
    LEFT JOIN categories c
        ON c.id = sp.category_id
    WHERE u.role = 'student'
    ORDER BY u.created_at DESC
""").fetchall()
    return render_template("manage_students.html", students=students)


@app.route("/manage_clients")
@login_required(role="admin")
def manage_clients():
    db = get_db()
    clients = db.execute("""
        SELECT id, full_name, email, phone, created_at FROM users
        WHERE role = 'client' ORDER BY full_name
    """).fetchall()
    return render_template("manage_clients.html", clients=clients)


@app.route("/manage_categories", methods=["GET", "POST"])
@login_required(role="admin")
def manage_categories():
    db = get_db()
    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()
        image_filename = save_upload(request.files.get("image"))
        if category_name:
            existing = db.execute(
                "SELECT id FROM categories WHERE category_name = ? COLLATE NOCASE", (category_name,)
            ).fetchone()
            if existing:
                flash("That category already exists.", "warning")
            else:
                db.execute(
                    "INSERT INTO categories (category_name, description, image) VALUES (?, ?, ?)",
                    (category_name, description, image_filename)
                )
                db.commit()
                flash("Category added.", "success")
        return redirect(url_for("manage_categories"))

    categories = db.execute("""
        SELECT c.id, c.category_name, c.description, c.image, COUNT(s.id) AS service_count
        FROM categories c LEFT JOIN services s ON s.category_id = c.id
        GROUP BY c.id ORDER BY c.category_name
    """).fetchall()
    return render_template("manage_categories.html", categories=categories)


@app.route("/edit_category/<int:category_id>", methods=["POST"])
@login_required(role="admin")
def edit_category(category_id):
    db = get_db()
    new_name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip()
    category = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if not category:
        abort(404)
    if new_name:
        duplicate = db.execute(
            "SELECT id FROM categories WHERE category_name = ? COLLATE NOCASE AND id != ?",
            (new_name, category_id)
        ).fetchone()
        if duplicate:
            flash("Another category already has that name.", "warning")
            return redirect(url_for("manage_categories"))

        image_filename = save_upload(request.files.get("image"))
        if image_filename:
            db.execute(
                "UPDATE categories SET category_name = ?, description = ?, image = ? WHERE id = ?",
                (new_name, description, image_filename, category_id)
            )
        else:
            db.execute(
                "UPDATE categories SET category_name = ?, description = ? WHERE id = ?",
                (new_name, description, category_id)
            )
        db.commit()
        flash("Category updated.", "success")
    return redirect(url_for("manage_categories"))


@app.route("/delete_category/<int:category_id>", methods=["POST"])
@login_required(role="admin")
def delete_category(category_id):
    db = get_db()
    in_use = db.execute("SELECT COUNT(*) c FROM services WHERE category_id = ?", (category_id,)).fetchone()["c"]
    if in_use > 0:
        flash("Cannot delete a category that is currently used by services.", "danger")
    else:
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("manage_categories"))


@app.route("/manage_services")
@login_required(role="admin")
def manage_services():
    db = get_db()
    services = db.execute("""
        SELECT s.*, u.full_name AS student_name, c.category_name
        FROM services s
        JOIN users u ON u.id = s.user_id
        JOIN categories c ON c.id = s.category_id
        ORDER BY s.created_at DESC
    """).fetchall()
    return render_template("manage_services.html", services=services)


@app.route("/manage_bookings")
@login_required(role="admin")
def manage_bookings():
    db = get_db()
    bookings = db.execute("""
        SELECT b.id, s.service_name, su.full_name AS student_name,
               cu.full_name AS client_name, b.required_date, b.status
        FROM bookings b
        JOIN services s ON s.id = b.service_id
        JOIN users su ON su.id = b.student_id
        JOIN users cu ON cu.id = b.client_id
        ORDER BY b.created_at DESC
    """).fetchall()
    return render_template("manage_bookings.html", bookings=bookings)

@app.route("/delete_student/<int:student_id>", methods=["POST"])
@login_required(role="admin")
def delete_student(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
    if not student:
        abort(404)
    db.execute("DELETE FROM users WHERE id = ?", (student_id,))
    db.commit()
    flash(f"Student '{student['full_name']}' has been removed.", "info")
    return redirect(url_for("manage_students"))


@app.route("/delete_client/<int:client_id>", methods=["POST"])
@login_required(role="admin")
def delete_client(client_id):
    db = get_db()
    client = db.execute("SELECT * FROM users WHERE id = ? AND role = 'client'", (client_id,)).fetchone()
    if not client:
        abort(404)
    db.execute("DELETE FROM users WHERE id = ?", (client_id,))
    db.commit()
    flash(f"Client '{client['full_name']}' has been removed.", "info")
    return redirect(url_for("manage_clients"))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
