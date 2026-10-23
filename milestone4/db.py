import sqlite3
import bcrypt
import datetime
import time
import os

# Google Drive DB support
GDRIVE_DIR = "/content/drive/MyDrive/TextMorph"

import sys
if "google.colab" in sys.modules:
    try:
        from google.colab import drive
        if not os.path.exists('/content/drive/MyDrive'):
            drive.mount('/content/drive')
    except Exception as e:
        print(f"⚠️ Could not mount drive: {e}")

if os.path.exists("/content/drive/MyDrive"):
    if not os.path.exists(GDRIVE_DIR):
        os.makedirs(GDRIVE_DIR)
    DB_NAME = os.path.join(GDRIVE_DIR, "users.db")
else:
    DB_NAME = "users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (email TEXT PRIMARY KEY, password BLOB, created_at TEXT)''')

    # Password History table
    c.execute('''CREATE TABLE IF NOT EXISTS password_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT,
                  password BLOB,
                  set_at TEXT,
                  FOREIGN KEY(email) REFERENCES users(email))''')

    # Login Attempts table (Rate Limiting)
    c.execute('''CREATE TABLE IF NOT EXISTS login_attempts
                 (email TEXT PRIMARY KEY,
                  attempts INTEGER DEFAULT 0,
                  last_attempt REAL)''')

    # Feedback table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT,
                  original_text TEXT,
                  generated_text TEXT,
                  task_type TEXT,
                  rating INTEGER,
                  comments TEXT,
                  created_at TEXT)''')

    # Activity History table
    c.execute('''CREATE TABLE IF NOT EXISTS activity_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT,
                  activity_type TEXT,
                  details TEXT,
                  model_used TEXT,
                  created_at TEXT)''')

    conn.commit()
    conn.close()

def _get_timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def register_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        now = _get_timestamp()
        c.execute("INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, hashed, now))
        c.execute("INSERT INTO password_history (email, password, set_at) VALUES (?, ?, ?)", (email, hashed, now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    data = c.fetchone()
    conn.close()
    if data:
        stored_hash = data[0]
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            _reset_attempts(email)
            return True
    _record_failed_attempt(email)
    return False

def check_is_old_password(email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password, set_at FROM password_history WHERE email = ? ORDER BY set_at DESC", (email,))
    history = c.fetchall()
    conn.close()
    for stored_hash, set_at in history:
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return set_at
    return None

def check_password_reused(email, new_password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password FROM password_history WHERE email = ?", (email,))
    history = c.fetchall()
    conn.close()
    for (stored_hash,) in history:
        if bcrypt.checkpw(new_password.encode('utf-8'), stored_hash):
            return True
    return False

def check_user_exists(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    data = c.fetchone()
    conn.close()
    return data is not None

def update_password(email, new_password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), salt)
    now = _get_timestamp()
    c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed, email))
    c.execute("INSERT INTO password_history (email, password, set_at) VALUES (?, ?, ?)", (email, hashed, now))
    conn.commit()
    conn.close()

# --- Rate Limiting ---
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60

def _record_failed_attempt(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = time.time()
    c.execute("SELECT attempts, last_attempt FROM login_attempts WHERE email = ?", (email,))
    row = c.fetchone()
    if row:
        attempts, last = row
        if now - last > LOCKOUT_SECONDS:
            c.execute("UPDATE login_attempts SET attempts = 1, last_attempt = ? WHERE email = ?", (now, email))
        else:
            c.execute("UPDATE login_attempts SET attempts = ?, last_attempt = ? WHERE email = ?", (attempts + 1, now, email))
    else:
        c.execute("INSERT INTO login_attempts (email, attempts, last_attempt) VALUES (?, 1, ?)", (email, now))
    conn.commit()
    conn.close()

def _reset_attempts(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def is_rate_limited(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT attempts, last_attempt FROM login_attempts WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        attempts, last = row
        elapsed = time.time() - last
        if attempts >= MAX_ATTEMPTS and elapsed < LOCKOUT_SECONDS:
            return True, LOCKOUT_SECONDS - elapsed
    return False, 0

# --- Feedback System ---
def save_feedback(email, original_text, generated_text, task_type, rating, comments):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = _get_timestamp()
    c.execute("INSERT INTO feedback (email, original_text, generated_text, task_type, rating, comments, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (email, original_text[:500], generated_text[:500], task_type, rating, comments, now))
    conn.commit()
    conn.close()

def get_all_feedback():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, email, task_type, rating, comments, created_at FROM feedback ORDER BY created_at DESC")
    feedback = c.fetchall()
    conn.close()
    return feedback

# --- Activity History System ---
def log_activity(email, activity_type, details, model_used):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = _get_timestamp()
    c.execute("INSERT INTO activity_history (email, activity_type, details, model_used, created_at) VALUES (?, ?, ?, ?, ?)",
              (email, activity_type, details, model_used, now))
    conn.commit()
    conn.close()

def get_user_activity(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT activity_type, details, model_used, created_at FROM activity_history WHERE email = ? ORDER BY created_at DESC", (email,))
    activities = c.fetchall()
    conn.close()
    return activities

# --- Admin Functions ---
def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT email, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    return users

def delete_user(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM password_history WHERE email = ?", (email,))
    c.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
    c.execute("DELETE FROM feedback WHERE email = ?", (email,))
    c.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# --- Active Users, Feature Usage, and System Logs ---

def set_user_active(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_users (
            email TEXT PRIMARY KEY,
            last_active TEXT
        )
    """)
    c.execute("""
        INSERT OR REPLACE INTO active_users (email, last_active)
        VALUES (?, ?)
    """, (email, _get_timestamp()))
    conn.commit()
    conn.close()


def remove_active_user(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_users (
            email TEXT PRIMARY KEY,
            last_active TEXT
        )
    """)
    c.execute("DELETE FROM active_users WHERE email = ?", (email,))
    conn.commit()
    conn.close()


def get_active_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_users (
            email TEXT PRIMARY KEY,
            last_active TEXT
        )
    """)
    c.execute("SELECT email, last_active FROM active_users ORDER BY last_active DESC")
    result = c.fetchall()
    conn.commit()
    conn.close()
    return result


def track_feature_usage(feature_name, email=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feature_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT,
            email TEXT,
            used_at TEXT
        )
    """)
    c.execute("""
        INSERT INTO feature_usage (feature_name, email, used_at)
        VALUES (?, ?, ?)
    """, (feature_name, email, _get_timestamp()))
    conn.commit()
    conn.close()


def get_feature_usage_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feature_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT,
            email TEXT,
            used_at TEXT
        )
    """)
    c.execute("""
        SELECT feature_name, COUNT(*) AS total
        FROM feature_usage
        GROUP BY feature_name
        ORDER BY total DESC
    """)
    result = c.fetchall()
    conn.commit()
    conn.close()
    return result


def log_system_event(event_type, details=""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        INSERT INTO system_logs (event_type, details, created_at)
        VALUES (?, ?, ?)
    """, (event_type, str(details), _get_timestamp()))
    conn.commit()
    conn.close()


def get_system_logs(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        SELECT event_type, details, created_at
        FROM system_logs
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    result = c.fetchall()
    conn.commit()
    conn.close()
    return result
def get_user_by_email(email):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT email, created_at FROM users WHERE email = ?", (email,))
def get_user_profile(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    columns = [
        row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "avatar" in columns:
        c.execute(
            "SELECT email, avatar FROM users WHERE email = ?",
            (email,)
        )
        user = c.fetchone()
    else:
        c.execute(
            "SELECT email FROM users WHERE email = ?",
            (email,)
        )
        row = c.fetchone()
        user = (row[0], None) if row else None

    conn.close()
    return user
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def log_usage(email, feature, details=""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            feature TEXT,
            details TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        INSERT INTO usage_logs (email, feature, details, created_at)
        VALUES (?, ?, ?, ?)
    """, (email, feature, str(details), _get_timestamp()))

    conn.commit()
    conn.close()

