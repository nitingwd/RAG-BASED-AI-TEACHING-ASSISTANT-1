import streamlit as st
import sqlite3, os, json, hashlib, random, time

DB_PATH = "data/users.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, mobile TEXT UNIQUE, password TEXT, role TEXT, profile TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS otps
    (mobile TEXT PRIMARY KEY, otp TEXT, expiry REAL)''')
    conn.commit()
    conn.close()

init_db()

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def signup(name, email, mobile, password, role):
    try:
        conn = get_conn()
        profile = json.dumps({"name": name, "email": email, "mobile": mobile, "role": role, "history": []})
        conn.execute("INSERT INTO users (name, email, mobile, password, role, profile) VALUES (?,?,?,?,?,?)",
                     (name, email, mobile, hash_pwd(password), role, profile))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def login(email, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, email, mobile, role, profile FROM users WHERE email=? AND password=?",
              (email, hash_pwd(password)))
    u = c.fetchone()
    conn.close()
    if u:
        return {"id": u[0], "name": u[1], "email": u[2], "mobile": u[3], "role": u[4], "profile": json.loads(u[5])}
    return None

def login_mobile(mobile):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, email, mobile, role, profile FROM users WHERE mobile=?", (mobile,))
    u = c.fetchone()
    conn.close()
    if u:
        return {"id": u[0], "name": u[1], "email": u[2], "mobile": u[3], "role": u[4], "profile": json.loads(u[5])}
    return None

def create_otp_code(mobile):
    otp = str(random.randint(100000, 999999))
    conn = get_conn()
    conn.execute("REPLACE INTO otps (mobile, otp, expiry) VALUES (?,?,?)", (mobile, otp, time.time()+300))
    conn.commit()
    conn.close()
    return otp

def verify_otp_code(mobile, otp_input):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT otp, expiry FROM otps WHERE mobile=?", (mobile,))
    row = c.fetchone()
    conn.close()
    if not row: return False
    otp, exp = row
    if time.time() > exp: return False
    return otp == otp_input

def google_login_code(email):
    # Google email se user hai toh login, nahi toh auto-create
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, email, mobile, role, profile FROM users WHERE email=?", (email,))
    u = c.fetchone()
    if u:
        conn.close()
        return {"id": u[0], "name": u[1], "email": u[2], "mobile": u[3], "role": u[4], "profile": json.loads(u[5])}
    else:
        name = email.split("@")[0]
        profile = json.dumps({"name": name, "email": email, "mobile": "", "role": "student", "history": []})
        c.execute("INSERT INTO users (name, email, mobile, password, role, profile) VALUES (?,?,?,?,?,?)",
                  (name, email, f"google_{random.randint(1000,9999)}", "google", "student", profile))
        conn.commit()
        c.execute("SELECT id, name, email, mobile, role, profile FROM users WHERE email=?", (email,))
        u = c.fetchone()
        conn.close()
        return {"id": u[0], "name": u[1], "email": u[2], "mobile": u[3], "role": u[4], "profile": json.loads(u[5])}

def auth_ui():
    if st.session_state.get("logged_in"):
        return True

    st.markdown("<h2 style='text-align:center'>🎓 SUBMIT - Login</h2>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🔐 Login", "📝 Sign Up", "📱 Mobile + 🔵 Google"])

    with tab1:
        email = st.text_input("Email", key="l_email")
        pwd = st.text_input("Password", type="password", key="l_pwd")
        if st.button("Login", type="primary", use_container_width=True, key="login_btn"):
            user = login(email, pwd)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Galat Email/Password")

    with tab2:
        name = st.text_input("Full Name", key="s_name")
        mobile = st.text_input("Mobile", key="s_mob")
        email = st.text_input("Email", key="s_email")
        pwd = st.text_input("Password", type="password", key="s_pwd")
        role = st.selectbox("Role", ["student", "teacher"], key="s_role")
        if st.button("Sign Up", use_container_width=True, key="signup_btn"):
            if signup(name, email, mobile, pwd, role):
                st.success("Account ban gaya! Ab Login tab me jao")
            else:
                st.error("Email/Mobile pehle se exist karta hai")

    with tab3:
        st.write("**📱 Mobile OTP Login**")
        mob = st.text_input("Mobile No", key="otp_mob")
        if st.button("OTP Generate Karo", key="gen_otp"):
            otp = create_otp_code(mob)
            st.session_state.show_otp = otp
            st.success(f"OTP Generate Ho Gaya: {otp}") # SMS API lagne tak yahi OTP dikhega

        if st.session_state.get("show_otp"):
            st.info(f"DEBUG OTP (SMS API tak): {st.session_state.show_otp}")

        otp_in = st.text_input("OTP Daalo", key="otp_in")
        if st.button("OTP Verify", key="verify_otp"):
            if verify_otp_code(mob, otp_in):
                user = login_mobile(mob)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Is mobile ka account nahi, pehle Sign Up karo")
            else:
                st.error("Galat OTP")

        st.divider()
        st.write("**🔵 Google Login**")
        g_email = st.text_input("Apna Google Email Daalo", key="g_email")
        if st.button("Google Se Login", use_container_width=True, key="g_login"):
            if "@gmail.com" in g_email or "@" in g_email:
                user = google_login_code(g_email)
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Sahi Email daalo")

    return False

def logout():
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()
