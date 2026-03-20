import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import bcrypt
import jwt
import datetime
import time
import os
import re
import hmac
import hashlib
import struct
import db
from readability import ReadabilityAnalyzer

# Configuration
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-this")
EMAIL_ADDRESS = "maddivarshith06@gmail.com"
OTP_EXPIRY_MINUTES = 10

# Initialize DB
if 'db_initialized' not in st.session_state:
    db.init_db()
    st.session_state['db_initialized'] = True

# --- UI Theme (Neon Style) ---
st.set_page_config(page_title="Infosys LLM Secure Auth", page_icon="⚡", layout="wide")

def apply_neon_theme():
    st.markdown("""
    <style>
        /* Main Background */
        .stApp {
            background-color: #0e1117;
            color: #ffffff;
        }
        /* Headers */
        h1, h2, h3 {
            color: #00ffcc !important;
            font-family: 'Courier New', monospace;
            text-shadow: 0 0 10px #00ffcc;
        }
        /* Inputs */
        .stTextInput > div > div > input {
            background-color: #1f2937;
            color: #00ffcc;
            border: 1px solid #374151;
            border-radius: 5px;
        }
        .stTextInput > div > div > input:focus {
            border-color: #00ffcc;
            box-shadow: 0 0 5px #00ffcc;
        }
        /* Buttons */
        .stButton > button {
            background-color: #1f2937;
            color: #00ffcc;
            border: 1px solid #00ffcc;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            transition: all 0.3s ease;
            width: 100%;
        }
        .stButton > button:hover {
            background-color: #00ffcc;
            color: #0e1117;
            box-shadow: 0 0 15px #00ffcc;
        }
        /* Strength Meter */
        .strength-weak { color: #ff4b4b; font-weight: bold; }
        .strength-medium { color: #ffa500; font-weight: bold; }
        .strength-strong { color: #00ffcc; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

apply_neon_theme()

# --- Helpers ---

def get_relative_time(date_str):
    if not date_str: return "some time ago"
    try:
        past = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        diff = datetime.datetime.utcnow() - past
        days = diff.days
        if days > 365: return f"{days // 365} years ago"
        elif days > 30: return f"{days // 30} months ago"
        elif days > 0: return f"{days} days ago"
        else: return "recently"
    except: return date_str

def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def check_password_strength(password):
    score = 0
    feedback = []

    # Definitions: Strong=8+Alphanum, Medium=6+Spec+Alphanum, Weak=Fallback
    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password))
    has_space = bool(re.search(r"\s", password))

    if has_space: return "Weak", ["No spaces allowed"]
    is_alphanum = (has_upper or has_lower) and has_digit

    if len(password) >= 8 and is_alphanum: return "Strong", []
    if len(password) >= 6 and is_alphanum and has_special: return "Medium", ["Add 2 chars for Strong"]
    return "Weak", ["Too short"]

# --- Security Logic ---

def generate_otp():
    secret = secrets.token_bytes(20)
    counter = int(time.time())
    msg = struct.pack(">Q", counter)
    hmac_hash = hmac.new(secret, msg, hashlib.sha1).digest()
    offset = hmac_hash[19] & 0xf
    code = ((hmac_hash[offset] & 0x7f) << 24 | (hmac_hash[offset + 1] & 0xff) << 16 | (hmac_hash[offset + 2] & 0xff) << 8 | (hmac_hash[offset + 3] & 0xff))
    otp = code % 1000000
    return f"{otp:06d}"

def create_otp_token(otp, email):
    otp_hash = bcrypt.hashpw(otp.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    payload = {
        'otp_hash': otp_hash,
        'sub': email,
        'type': 'password_reset',
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_otp_token(token, input_otp, email):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        if payload.get('sub') != email: return False, "Token mismatch"
        if bcrypt.checkpw(input_otp.encode('utf-8'), payload['otp_hash'].encode('utf-8')):
            return True, "Valid"
        return False, "Invalid OTP"
    except Exception as e:
        return False, str(e)

def send_email(to_email, otp, app_pass):
    msg = MIMEMultipart()
    msg['From'] = f"Infosys LLM <{EMAIL_ADDRESS}>"
    msg['To'] = to_email
    msg['Subject'] = "🔐 Infosys LLM - Password Reset OTP"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .container {{
                font-family: 'Courier New', monospace;
                background-color: #0e1117;
                padding: 40px;
                text-align: center;
                color: #ffffff;
            }}
            .card {{
                background-color: #1f2937;
                border-radius: 12px;
                box-shadow: 0 0 20px rgba(0, 255, 204, 0.2);
                padding: 40px;
                max-width: 500px;
                margin: 0 auto;
                border: 1px solid #374151;
            }}
            .header {{
                color: #00ffcc;
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 20px;
                text-shadow: 0 0 5px #00ffcc;
            }}
            .otp-box {{
                background-color: #0e1117;
                color: #00ffcc;
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 8px;
                padding: 20px;
                border-radius: 8px;
                margin: 30px 0;
                display: inline-block;
                border: 1px solid #00ffcc;
                box-shadow: 0 0 10px rgba(0, 255, 204, 0.3);
            }}
            .text {{
                color: #9ca3af;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 20px;
            }}
            .footer {{
                color: #6b7280;
                font-size: 12px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="header">⚡ Infosys LLM Security</div>
                <div class="text">
                    Use this OTP to reset your password for <span style="color:#00ffcc;">{to_email}</span>.
                </div>
                <div class="otp-box">
                    {otp}
                </div>
                <div class="text">
                    Valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.
                </div>
                <div class="footer">
                    &copy; 2026 Infosys LLM Secure Auth
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(EMAIL_ADDRESS, app_pass if app_pass else EMAIL_PASSWORD)
        s.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        s.quit()
        return True, "Sent"
    except Exception as e:
        return False, str(e)

# --- Navigation ---

if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = 'login'

def switch_page(page):
    st.session_state['page'] = page
    st.rerun()

def logout():
    st.session_state['user'] = None
    st.session_state['page'] = 'login'
    st.rerun()

# --- Pages ---

def login_page():
    st.title("⚡ Infosys LLM Login")

    with st.form("login"):
        email = st.text_input("Email *")
        password = st.text_input("Password *", type='password')
        submit = st.form_submit_button("Login")

        if submit:
            # 1. Check Rate Limit
            is_locked, wait_time = db.is_rate_limited(email)
            if is_locked:
                st.error(f"⛔ Account Locked! Too many failed attempts. Try again in {int(wait_time)} seconds.")
            elif not email or not password:
                st.error("Fields cannot be empty.")
            else:
                # 2. Authenticate
                if db.authenticate_user(email, password):
                    st.session_state['user'] = email
                    st.success("Login Successful!")
                    time.sleep(1)
                    if email == "admin@llm.com":
                        switch_page("admin_dashboard")
                    else:
                        switch_page("chat")
                else:
                    # Generic error for security, but we know it failed
                    st.error("Invalid credentials.")
                    old_dt = db.check_is_old_password(email, password)
                    if old_dt:
                        st.warning(f"Note: You used an old password from {get_relative_time(old_dt)}.")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Create Account"): switch_page("register")
    if c2.button("Forgot Password"): switch_page("forgot")
    

def register_page():
    st.title("⚡ New Account")

    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")

    question = st.selectbox("Security Question", [
        "What is your pet name?",
        "What is your mother’s maiden name?",
        "What is your favorite teacher?",
        "What is your favorite food?",
        "What is your birth city?"
    ])

    answer = st.text_input("Security Answer")

    if password:
        s, f = check_password_strength(password)
        st.markdown(f"Strength: **{s}**")

    if st.button("Register"):
        if not all([username, email, password, confirm, answer]):
            st.error("All fields required")
        elif not is_valid_email(email):
            st.error("Invalid email")
        elif password != confirm:
            st.error("Passwords do not match")
        elif s == "Weak":
            st.error("Password too weak")
        else:
            if db.register_user(email, username, password, question, answer):
                st.success("Account created successfully")
                time.sleep(1)
                switch_page("login")
            else:
                st.error("User already exists")

    if st.button("Back"):
        switch_page("login")

def forgot_page():
    st.title("⚡ Reset Password")
    if 'stage' not in st.session_state: st.session_state['stage'] = 'email'

    if st.session_state['stage'] == 'email':
        email = st.text_input("Email *")
        if st.button("Next"):
            if db.check_user_exists(email):
                st.session_state['reset_email'] = email
                st.session_state['stage'] = 'otp'
                st.rerun()
            else: st.error("Not found.")
        if st.button("Back"): switch_page("login")

    elif st.session_state['stage'] == 'otp':
        st.info(f"Sending to {st.session_state['reset_email']}")
        if st.button("Send OTP"):
            otp = generate_otp()
            ok, msg = send_email(st.session_state['reset_email'], otp, EMAIL_PASSWORD)
            if ok:
                st.session_state['token'] = create_otp_token(otp, st.session_state['reset_email'])
                st.session_state['stage'] = 'verify'
                st.rerun()
            else: st.error(msg)

    elif st.session_state['stage'] == 'verify':
        otp = st.text_input("Enter OTP *")
        if st.button("Verify"):
            ok, msg = verify_otp_token(st.session_state['token'], otp, st.session_state['reset_email'])
            if ok:
                st.session_state['stage'] = 'reset'
                st.rerun()
            else: st.error(msg)

    elif st.session_state['stage'] == 'reset':
        p1 = st.text_input("New Password *", type='password')
        p2 = st.text_input("Confirm *", type='password')
        if st.button("Update"):
            if p1!=p2: st.error("Mismatch")
            elif db.check_password_reused(st.session_state['reset_email'], p1): st.error("Cannot reuse old password")
            else:
                db.update_password(st.session_state['reset_email'], p1)
                st.success("Updated!")
                time.sleep(1)
                switch_page("login")

def readability_page():
    st.markdown("<h2 style='text-align:center;color:#ff00ff'>📊 Analysis Results</h2>", unsafe_allow_html=True)

    # -------- FILE UPLOAD --------
    uploaded_file = st.file_uploader("Upload a file (txt or pdf)", type=["txt", "pdf"])

    text = ""

    if uploaded_file is not None:
        if uploaded_file.type == "text/plain":
            text = uploaded_file.read().decode("utf-8")

        elif uploaded_file.type == "application/pdf":
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""

    else:
        text = st.text_area("Enter text to analyze")

    # -------- ANALYZE --------
    if st.button("Analyze"):
        if not text:
            st.error("Enter text")
            return

        analyzer = ReadabilityAnalyzer(text)
        metrics = analyzer.get_all_metrics()

        # -------- LEVEL --------
        grade = metrics["Flesch-Kincaid Grade"]

        if grade < 6:
            level = "Easy (School Level)"
        elif grade < 10:
            level = "Medium (High School)"
        else:
            level = "Advanced (College)"

        st.markdown(f"""
        <div style="background:#1f2937;padding:20px;border-radius:10px;text-align:center">
            <h2 style="color:#ff00ff">Overall Level: {level}</h2>
            <p>Approximate Grade Level: {grade:.2f}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='color:#ff00ff'>📈 Detailed Metrics</h3>", unsafe_allow_html=True)

        import plotly.graph_objects as go

        # -------- COLORED GAUGE --------
        def gauge(title, value, color, max_val=100):
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=value,
                title={'text': title},
                gauge={
                    'axis': {'range': [0, max_val]},
                    'bar': {'color': color}
                }
            ))
            return fig

        # -------- METRICS --------
        col1, col2, col3 = st.columns(3)

        with col1:
            st.plotly_chart(gauge("Flesch Reading Ease", metrics["Flesch Reading Ease"], "cyan", 100), use_container_width=True)

        with col2:
            st.plotly_chart(gauge("Flesch-Kincaid Grade", metrics["Flesch-Kincaid Grade"], "magenta", 20), use_container_width=True)

        with col3:
            st.plotly_chart(gauge("SMOG Index", metrics["SMOG Index"], "yellow", 20), use_container_width=True)

        col4, col5 = st.columns(2)

        with col4:
            st.plotly_chart(gauge("Gunning Fog", metrics["Gunning Fog"], "green", 20), use_container_width=True)

        with col5:
            st.plotly_chart(gauge("Coleman-Liau", metrics["Coleman-Liau"], "orange", 20), use_container_width=True)
def chat_page():
    st.sidebar.title(f"👤 {st.session_state['user']}")
    if st.sidebar.button("📊 Readability"):
        switch_page("readability")
    if st.sidebar.button("Logout"): logout()

    st.title("🤖 Infosys LLM Chat")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask me anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = f"Simulated Response to: {prompt} (This is a Secure Mock)"
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

def admin_page():
    st.sidebar.title("🛡️ Admin Panel")
    if st.sidebar.button("Logout"): logout()

    st.title("👥 User Management")
    users = db.get_all_users()

    for u_email, u_created in users:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"**{u_email}**")
        c2.write(u_created)
        if u_email != "admin@llm.com":
            if c3.button("Delete", key=u_email):
                db.delete_user(u_email)
                st.warning(f"Deleted {u_email}")
                time.sleep(0.5)
                st.rerun()

# --- Router ---
if st.session_state['user']:
    if st.session_state['user'] == "admin@llm.com":
        admin_page()
    else:
        if st.session_state['page'] == 'chat':
            chat_page()
        elif st.session_state['page'] == 'readability':
            readability_page()
else:
    if st.session_state['page'] == 'login':
        login_page()
    elif st.session_state['page'] == 'register':
        register_page()
    elif st.session_state['page'] == 'forgot':
        forgot_page()
    elif st.session_state['page'] == 'admin_dashboard':
        admin_page()
