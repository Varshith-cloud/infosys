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
