import streamlit as st
import jwt
import datetime
import bcrypt
import re

# ---------- CONFIG ----------
SECRET = "my_secret_key"
ALGO = "HS256"

# ---------- SESSION STORAGE ----------
if "users" not in st.session_state:
    st.session_state["users"] = {}

if "token" not in st.session_state:
    st.session_state["token"] = None

if "screen" not in st.session_state:
    st.session_state["screen"] = "login"

# ---------- JWT ----------
def generate_token(email, username):
    data = {
        "email": email,
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }
    return jwt.encode(data, SECRET, algorithm=ALGO)

def check_token(token):
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGO])
    except:
        return None

# ---------- VALIDATION ----------
def check_email(e):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', e)

def check_pass(p):
    return len(p) >= 8 and p.isalnum()

# ---------- SIGNUP ----------
def signup():
    st.title("Signup Page")

    uname = st.text_input("Username")
    mail = st.text_input("Email")
    pwd = st.text_input("Password", type="password")
    cpwd = st.text_input("Confirm Password", type="password")

    ques = st.selectbox("Security Question", [
    "What is your pet name?",
    "What is your mother’s maiden name?",
    "What is your favorite teacher?",
    "What is your favorite food?",
    "What is your birth city?"
])

    ans = st.text_input("Security Answer")

    if st.button("Register"):
        if not all([uname, mail, pwd, cpwd, ans]):
            st.error("All fields are required")
        elif not check_email(mail):
            st.error("Invalid email")
        elif not check_pass(pwd):
            st.error("Password must be 8+ alphanumeric")
        elif pwd != cpwd:
            st.error("Passwords do not match")
        elif mail in st.session_state["users"]:
            st.error("User already exists")
        else:
            hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

            st.session_state["users"][mail] = {
                "username": uname,
                "password": hashed,
                "question": ques,
                "answer": ans.lower()
            }

            st.success("Account created!")
            st.session_state["screen"] = "login"
            st.rerun()

    if st.button("Back to Login"):
        st.session_state["screen"] = "login"
        st.rerun()

# ---------- LOGIN ----------
def login():
    st.title("Login Page")

    mail = st.text_input("Email")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        user = st.session_state["users"].get(mail)

        if user:
            if bcrypt.checkpw(pwd.encode(), user["password"].encode()):
                st.session_state["token"] = generate_token(mail, user["username"])
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Wrong password")
        else:
            st.error("User not found")

    col1, col2 = st.columns(2)

    if col1.button("Signup"):
        st.session_state["screen"] = "signup"
        st.rerun()

    if col2.button("Forgot Password"):
        st.session_state["screen"] = "forgot"
        st.rerun()

# ---------- FORGOT PASSWORD ----------
def forgot():
    st.title("Forgot Password")

    mail = st.text_input("Enter Email")

    if st.button("Check"):
        user = st.session_state["users"].get(mail)

        if user:
            st.session_state["mail"] = mail
            st.session_state["q"] = user["question"]
            st.session_state["a"] = user["answer"]
        else:
            st.error("Email not found")

    if "q" in st.session_state:
        st.info(st.session_state["q"])
        ans = st.text_input("Answer")

        if st.button("Verify"):
            if ans.lower() == st.session_state["a"]:
                st.session_state["allow"] = True
            else:
                st.error("Wrong answer")

    if st.session_state.get("allow"):
        newp = st.text_input("New Password", type="password")

        if st.button("Update Password"):
            if check_pass(newp):
                hashed = bcrypt.hashpw(newp.encode(), bcrypt.gensalt()).decode()
                st.session_state["users"][st.session_state["mail"]]["password"] = hashed

                st.success("Password updated!")
                st.session_state.clear()
                st.session_state["screen"] = "login"
                st.rerun()
            else:
                st.error("Invalid password")

# ---------- DASHBOARD ----------
def dashboard():
    data = check_token(st.session_state["token"])

    if not data:
        st.session_state["token"] = None
        st.rerun()

    st.title(f"Welcome {data['username']}")
    st.success("You are logged in")

    if st.button("Logout"):
        st.session_state.clear()
        st.session_state["screen"] = "login"
        st.rerun()

# ---------- ROUTER ----------
if st.session_state["token"]:
    dashboard()
else:
    if st.session_state["screen"] == "signup":
        signup()
    elif st.session_state["screen"] == "forgot":
        forgot()
    else:
        login()
