import streamlit as st
import tempfile
import os
import io
import sqlite3
import hashlib
import base64
import json
from datetime import datetime, date, timedelta
from PIL import Image
from docx import Document
from docx.shared import Inches

# ============================================================
# RAG AI TEACHING ASSISTANT - V24
# IMPORTANT:
# - Existing features are preserved.
# - New student-retention features are added in this UI file.
# - Existing rag_utils.py functions are still used.
# ============================================================

st.set_page_config(
    page_title="RAG Based AI Teaching Assistant",
    layout="wide",
    page_icon="🎓"
)

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    COOKIE_OK = True
except Exception:
    COOKIE_OK = False

DB_PATH = "data/users.db"
PICS_PATH = "data/profile_pics"
os.makedirs("data", exist_ok=True)
os.makedirs(PICS_PATH, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            name TEXT,
            email TEXT,
            photo TEXT,
            bio TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            query TEXT,
            answer TEXT,
            mode TEXT,
            timestamp TEXT
        )
    """)

    # New tables are additive. Existing DBs continue to work.
    c.execute("""
        CREATE TABLE IF NOT EXISTS learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT,
            topic TEXT,
            score REAL DEFAULT 0,
            details TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            topic TEXT,
            question TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            created_at TEXT,
            fixed INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_date TEXT,
            task TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# AUTH / USER HELPERS
# ============================================================

def hash_pwd(p):
    return hashlib.sha256(p.encode()).hexdigest()


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def signup_user(username, password, name, email):
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO users
               (username, password, name, email, photo, bio, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                username.lower().strip(),
                hash_pwd(password),
                name,
                email,
                "",
                "",
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()
        return True, "Account ban gaya!"
    except sqlite3.IntegrityError:
        return False, "Username pehle se hai!"
    except Exception as e:
        return False, str(e)


def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT id, username, name, email, photo, bio
           FROM users WHERE username=? AND password=?""",
        (username.lower().strip(), hash_pwd(password))
    )
    u = c.fetchone()
    conn.close()

    if u:
        return {
            "id": u[0],
            "username": u[1],
            "name": u[2],
            "email": u[3],
            "photo": u[4],
            "bio": u[5]
        }
    return None


def get_user_by_id(user_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            """SELECT id, username, name, email, photo, bio
               FROM users WHERE id=?""",
            (user_id,)
        )
        u = c.fetchone()
        conn.close()

        if u:
            return {
                "id": u[0],
                "username": u[1],
                "name": u[2],
                "email": u[3],
                "photo": u[4],
                "bio": u[5]
            }
    except Exception:
        return None

    return None


def update_profile(user_id, name, email, bio, photo_file=None):
    photo_path = None

    if photo_file:
        ext = photo_file.name.split(".")[-1].lower()
        photo_path = f"{PICS_PATH}/{user_id}_{int(datetime.now().timestamp())}.{ext}"
        with open(photo_path, "wb") as f:
            f.write(photo_file.getbuffer())

    conn = get_conn()

    if photo_path:
        conn.execute(
            """UPDATE users SET name=?, email=?, bio=?, photo=?
               WHERE id=?""",
            (name, email, bio, photo_path, user_id)
        )
    else:
        conn.execute(
            """UPDATE users SET name=?, email=?, bio=?
               WHERE id=?""",
            (name, email, bio, user_id)
        )

    conn.commit()
    conn.close()
    return True


def save_conversation(user_id, query, answer, mode="Ask"):
    conn = get_conn()
    conn.execute(
        """INSERT INTO conversations
           (user_id, query, answer, mode, timestamp)
           VALUES (?,?,?,?,?)""",
        (
            user_id,
            query,
            answer,
            mode,
            datetime.now().isoformat()
        )
    )
    conn.commit()
    conn.close()


def get_user_conversations(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT id, query, answer, mode, timestamp
           FROM conversations
           WHERE user_id=?
           ORDER BY id DESC""",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ============================================================
# LEARNING DATABASE HELPERS
# ============================================================

def log_event(user_id, event_type, topic="", score=0, details=""):
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO learning_events
               (user_id, event_type, topic, score, details, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                user_id,
                event_type,
                topic[:300],
                float(score or 0),
                str(details)[:2000],
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def add_mistake(user_id, topic, question, user_answer, correct_answer):
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO mistakes
               (user_id, topic, question, user_answer,
                correct_answer, created_at, fixed)
               VALUES (?,?,?,?,?,?,0)""",
            (
                user_id,
                topic[:300],
                question[:2000],
                user_answer[:2000],
                correct_answer[:2000],
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_mistakes(user_id, only_open=False):
    conn = get_conn()
    c = conn.cursor()

    if only_open:
        c.execute(
            """SELECT id, topic, question, user_answer,
                      correct_answer, created_at, fixed
               FROM mistakes
               WHERE user_id=? AND fixed=0
               ORDER BY id DESC""",
            (user_id,)
        )
    else:
        c.execute(
            """SELECT id, topic, question, user_answer,
                      correct_answer, created_at, fixed
               FROM mistakes
               WHERE user_id=?
               ORDER BY id DESC""",
            (user_id,)
        )

    rows = c.fetchall()
    conn.close()
    return rows


def mark_mistake_fixed(mistake_id, user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE mistakes SET fixed=1 WHERE id=? AND user_id=?",
        (mistake_id, user_id)
    )
    conn.commit()
    conn.close()


def get_events(user_id, event_type=None, days=None):
    conn = get_conn()
    c = conn.cursor()

    if event_type and days:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute(
            """SELECT id, event_type, topic, score, details, created_at
               FROM learning_events
               WHERE user_id=? AND event_type=? AND created_at>=?
               ORDER BY id DESC""",
            (user_id, event_type, since)
        )
    elif event_type:
        c.execute(
            """SELECT id, event_type, topic, score, details, created_at
               FROM learning_events
               WHERE user_id=? AND event_type=?
               ORDER BY id DESC""",
            (user_id, event_type)
        )
    elif days:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute(
            """SELECT id, event_type, topic, score, details, created_at
               FROM learning_events
               WHERE user_id=? AND created_at>=?
               ORDER BY id DESC""",
            (user_id, since)
        )
    else:
        c.execute(
            """SELECT id, event_type, topic, score, details, created_at
               FROM learning_events
               WHERE user_id=?
               ORDER BY id DESC""",
            (user_id,)
        )

    rows = c.fetchall()
    conn.close()
    return rows


def get_topic_stats(user_id, days=None):
    rows = get_events(user_id, days=days)

    stats = {}

    for _, event_type, topic, score, details, created_at in rows:
        topic = topic.strip() if topic else "General"

        if topic not in stats:
            stats[topic] = {
                "attempts": 0,
                "correct": 0,
                "score_total": 0.0,
                "quiz": 0,
                "viva": 0,
                "study": 0
            }

        s = stats[topic]

        if event_type in ("quiz_correct", "quiz_wrong"):
            s["quiz"] += 1
            s["attempts"] += 1
            s["score_total"] += float(score or 0)
            if event_type == "quiz_correct":
                s["correct"] += 1

        elif event_type in ("viva_correct", "viva_wrong"):
            s["viva"] += 1
            s["attempts"] += 1
            s["score_total"] += float(score or 0)
            if event_type == "viva_correct":
                s["correct"] += 1

        elif event_type in ("study", "question", "summary", "revision"):
            s["study"] += 1

    return stats


def get_streak(user_id):
    rows = get_events(user_id)
    active_days = set()

    for row in rows:
        try:
            active_days.add(datetime.fromisoformat(row[5]).date())
        except Exception:
            pass

    if not active_days:
        return 0

    today = date.today()
    if today not in active_days and (today - timedelta(days=1)) not in active_days:
        return 0

    streak = 0
    d = today

    if d not in active_days:
        d = today - timedelta(days=1)

    while d in active_days:
        streak += 1
        d -= timedelta(days=1)

    return streak


def create_today_plan(user_id):
    today = date.today().isoformat()

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """SELECT id, task, status
           FROM study_plans
           WHERE user_id=? AND plan_date=?
           ORDER BY id""",
        (user_id, today)
    )
    existing = c.fetchall()

    if existing:
        conn.close()
        return existing

    tasks = [
        "10 min: Uploaded notes ka quick revision",
        "10 min: 5 adaptive quiz questions",
        "10 min: Ek weak topic explain karo",
        "5 min: Mistake Bank se 2 mistakes fix karo",
        "5 min: Viva-style oral recall"
    ]

    for task in tasks:
        conn.execute(
            """INSERT INTO study_plans
               (user_id, plan_date, task, status, created_at)
               VALUES (?,?,?,?,?)""",
            (
                user_id,
                today,
                task,
                "pending",
                datetime.now().isoformat()
            )
        )

    conn.commit()

    c.execute(
        """SELECT id, task, status
           FROM study_plans
           WHERE user_id=? AND plan_date=?
           ORDER BY id""",
        (user_id, today)
    )
    result = c.fetchall()
    conn.close()
    return result


def toggle_plan_task(task_id, user_id, status):
    new_status = "done" if status != "done" else "pending"

    conn = get_conn()
    conn.execute(
        """UPDATE study_plans SET status=?
           WHERE id=? AND user_id=?""",
        (new_status, task_id, user_id)
    )
    conn.commit()
    conn.close()


# ============================================================
# AUTH UI
# ============================================================

def auth_ui():
    cookies = None

    if COOKIE_OK:
        # Keep the existing cookie mechanism compatible.
        # For production, move this secret to Streamlit secrets.
        cookie_password = st.secrets.get(
            "COOKIE_PASSWORD",
            "kadiya_naresh_final_v23_best_color_2024"
        )

        cookies = EncryptedCookieManager(
            prefix="rag_v23_best_",
            password=cookie_password
        )

        if not cookies.ready():
            st.stop()

    if st.session_state.get("logged_in") and st.session_state.get("user"):
        return True, cookies

    if COOKIE_OK and cookies:
        uid_val = cookies.get("uid")

        if uid_val:
            try:
                uid = int(uid_val)
                u = get_user_by_id(uid)

                if u:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    return True, cookies
            except Exception:
                pass

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600;700&display=swap');

    .stApp {
        background: radial-gradient(
            1000px at 20% 10%,
            #E0E7FF 0%,
            #F0F4FF 40%,
            #FFFFFF 100%
        );
    }

    .login-card {
        background: rgba(255,255,255,0.95);
        backdrop-filter: blur(24px);
        border: 1px solid rgba(99,102,241,0.12);
        padding: 36px;
        border-radius: 28px;
        box-shadow: 0 24px 80px rgba(99,102,241,0.18);
        text-align:center;
        max-width:440px;
        width:100%;
    }

    .login-title {
        font-family:'Space Grotesk';
        font-size:28px;
        font-weight:700;
        color:#111827;
        line-height:1.2;
    }

    .login-sub {
        color:#6B7280;
        font-size:13px;
        margin-top:6px;
    }

    .pill {
        display:inline-block;
        background:linear-gradient(135deg,#EEF2FF,#E0E7FF);
        color:#6366F1;
        padding:6px 12px;
        border-radius:20px;
        font-size:11px;
        font-weight:700;
        margin:3px;
        border:1px solid #C7D2FE;
    }

    .stButton>button {
        border-radius:12px;
        height:48px;
        font-weight:700;
    }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown("""
        <div class="login-card">
            <div style="font-size:52px; margin-bottom:8px;">🎓</div>
            <div class="login-title">
                RAG Based AI<br>Teaching Assistant
            </div>
            <div class="login-sub">
                One-time login, 30 days tak yaad rahega
            </div>
            <div style="margin-top:14px;">
                <span class="pill">💬 Q&A</span>
                <span class="pill">🎤 VIVA</span>
                <span class="pill">📝 QUIZ</span>
                <span class="pill">🔊 AUDIO</span>
            </div>
        </div><br>
        """, unsafe_allow_html=True)

        t1, t2 = st.tabs(["🔐 Login", "✨ Sign Up"])

        with t1:
            username = st.text_input(
                "Username",
                placeholder="naresh123",
                key="l_user"
            )

            pwd = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
                key="l_pwd"
            )

            if st.button(
                "🚀 Login to Dashboard",
                type="primary",
                use_container_width=True
            ):
                u = login_user(username, pwd)

                if u:
                    st.session_state.logged_in = True
                    st.session_state.user = u

                    if COOKIE_OK:
                        cookies["uid"] = str(u["id"])
                        cookies.save()

                    st.rerun()
                else:
                    st.error("Galat Username/Password")

        with t2:
            name = st.text_input(
                "Full Name",
                key="s_name",
                placeholder="Kadiya Naresh"
            )

            username = st.text_input(
                "Username",
                key="s_user",
                placeholder="naresh123"
            )

            email = st.text_input(
                "Email",
                key="s_email",
                placeholder="naresh@gmail.com"
            )

            pwd = st.text_input(
                "Password",
                key="s_pwd",
                type="password",
                placeholder="Min 4 chars"
            )

            if st.button(
                "Create Account",
                use_container_width=True
            ):
                if len(username) < 3 or len(pwd) < 4:
                    st.error("Username min 3, Password min 4")
                else:
                    ok, msg = signup_user(
                        username,
                        pwd,
                        name,
                        email
                    )

                    if ok:
                        st.success(msg + " Ab Login karo")
                        st.balloons()
                    else:
                        st.error(msg)

    return False, cookies


logged_in, cookies = auth_ui()

if not logged_in:
    st.stop()

user = get_user_by_id(st.session_state.user["id"])

if not user:
    if COOKIE_OK and cookies:
        cookies["uid"] = ""
        cookies.save()

    st.session_state.clear()
    st.rerun()

st.session_state.user = user


# ============================================================
# EXISTING RAG FUNCTIONS
# ============================================================

from rag_utils import (
    process_files, ask_question, get_api_key, generate_quiz, generate_summary,
    predict_important_questions, check_quiz_answer, get_weak_topics,
    transcribe_audio, story_mode_learning, build_project_guide,
    generate_podcast_script, generate_viva_questions, verify_viva_answer,
    generate_adaptive_quiz, generate_teach_back_feedback, generate_revision,
    build_quiz_final_report, build_viva_final_report,
    generate_exam_attack, generate_confusion_battle, create_ppt_file,
    text_to_audio_file, images_to_pdf, images_to_docx,
    get_source_inventory, generate_source_brief, generate_flashcards,
    generate_mind_map, generate_exam_paper, compare_source_topics,
    generate_study_guide, build_study_pack
)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600;700&display=swap');

.main {
    background:#F8FAFF;
}

.hero-pro {
    background: linear-gradient(
        135deg,
        #4F46E5 0%,
        #7C3AED 35%,
        #EC4899 70%,
        #F59E0B 100%
    );
    border-radius:24px;
    padding:26px 28px;
    color:white;
    box-shadow:0 16px 40px rgba(99,102,241,0.25);
}

.profile-card-pro {
    background:linear-gradient(
        180deg,
        #FFFFFF 0%,
        #F8FAFF 100%
    );
    border-radius:20px;
    padding:18px;
    border:1px solid #E0E7FF;
    text-align:center;
    box-shadow:0 8px 24px rgba(99,102,241,0.08);
}

.img-circle {
    width:85px;
    height:85px;
    border-radius:50%;
    object-fit:cover;
    border:3px solid transparent;
    background:
        linear-gradient(white, white) padding-box,
        linear-gradient(135deg,#6366F1,#EC4899) border-box;
    box-shadow:0 6px 20px rgba(99,102,241,0.25);
    display:block;
    margin:0 auto;
}

.avatar-letter {
    width:85px;
    height:85px;
    border-radius:50%;
    background:linear-gradient(
        135deg,
        #6366F1 0%,
        #8B5CF6 50%,
        #EC4899 100%
    );
    display:flex;
    align-items:center;
    justify-content:center;
    margin:0 auto;
    color:white;
    font-size:32px;
    font-weight:700;
    font-family:Space Grotesk;
}

.dev-badge {
    position:fixed;
    bottom:14px;
    right:14px;
    background:#111827;
    color:white;
    padding:7px 12px;
    border-radius:20px;
    font-size:10px;
    z-index:999;
    font-weight:600;
}

/* Dashboard buttons */
section.main div[data-testid="stButton"] > button {
    border-radius:14px!important;
    height:58px!important;
    font-weight:700!important;
    font-size:13px!important;
    border:1.5px solid rgba(0,0,0,0.06)!important;
    box-shadow:0 4px 12px rgba(0,0,0,0.06)!important;
    transition:all 0.32s cubic-bezier(0.34,1.56,0.64,1)!important;
}

section.main div[data-testid="stButton"] > button:hover {
    transform:translateY(-7px) scale(1.05)!important;
    box-shadow:0 20px 40px rgba(0,0,0,0.20)!important;
    z-index:20!important;
    border-color:transparent!important;
}

.feature-card {
    padding:18px;
    border-radius:18px;
    border:1px solid #E5E7EB;
    background:white;
    box-shadow:0 6px 18px rgba(0,0,0,0.05);
    margin-bottom:12px;
}

.mini-card {
    padding:14px;
    border-radius:16px;
    background:#FFFFFF;
    border:1px solid #E5E7EB;
    text-align:center;
}

.success-card {
    padding:18px;
    border-radius:18px;
    background:linear-gradient(135deg,#ECFDF5,#F0FDFA);
    border:1px solid #A7F3D0;
}

.warning-card {
    padding:18px;
    border-radius:18px;
    background:linear-gradient(135deg,#FFFBEB,#FFF7ED);
    border:1px solid #FDE68A;
}

.dark-card {
    padding:18px;
    border-radius:18px;
    background:linear-gradient(135deg,#111827,#374151);
    color:white;
}
</style>

<div class="dev-badge">V25 • Source Intelligence + Student AI Brain</div>
""", unsafe_allow_html=True)


# ============================================================
# INPUT / AUDIO HELPERS
# ============================================================

def universal_input(key, placeholder="Bolo ya likho..."):
    c1, c2 = st.columns([5, 1])

    with c1:
        txt = st.text_input(
            " ",
            key=f"txt_{key}",
            placeholder=placeholder,
            label_visibility="collapsed"
        )

    with c2:
        aud = st.audio_input(
            "🎤",
            key=f"aud_{key}",
            label_visibility="collapsed"
        )

    if aud:
        api_key = get_api_key()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav"
        ) as tmp:
            tmp.write(aud.getvalue())
            path = tmp.name

        try:
            with st.spinner("Sun raha hu..."):
                vt = transcribe_audio(api_key, path)
        except Exception as e:
            vt = None
            st.warning(f"Voice input unavailable: {e}")
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        if vt:
            st.success(f"🎧 {vt}")
            return vt

    return txt


def play_audio_block(text, lang, key):
    if not text:
        return

    if st.button(
        f"▶️ {lang} me Suno",
        key=f"play_{key}",
        type="primary",
        use_container_width=True
    ):
        with st.spinner("Audio bana raha hu..."):
            try:
                ap = text_to_audio_file(text, lang)
                if ap and os.path.exists(ap) and os.path.getsize(ap) > 500:
                    with open(ap, "rb") as f:
                        audio_bytes = f.read()
                    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                else:
                    st.warning("Audio generate nahi ho paya. Internet/TTS check karo.")
            except Exception as e:
                st.warning(f"Audio error: {e}")
            finally:
                if 'ap' in locals() and ap and os.path.exists(ap):
                    try:
                        os.remove(ap)
                    except Exception:
                        pass


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    photo_html = ""

    if user["photo"] and os.path.exists(user["photo"]):
        try:
            with open(user["photo"], "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            ext = user["photo"].split(".")[-1]

            photo_html = (
                f'<img src="data:image/{ext};base64,{b64}" '
                f'class="img-circle">'
            )
        except Exception:
            photo_html = (
                f'<div class="avatar-letter">'
                f'{user["name"][0].upper()}'
                f'</div>'
            )
    else:
        photo_html = (
            f'<div class="avatar-letter">'
            f'{user["name"][0].upper()}'
            f'</div>'
        )

    profile_html = (
        f'<div class="profile-card-pro">{photo_html}'
        f'<h4 style="margin:12px 0 2px 0;font-family:Space Grotesk;font-size:16px;color:#111827;">{user["name"]}</h4>'
        f'<p style="margin:0;color:#6366F1;font-size:12px;font-weight:600;">@{user["username"]}</p>'
        f'<div style="margin-top:10px;display:flex;gap:6px;justify-content:center;">'
        f'<span style="background:#EEF2FF;color:#6366F1;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:700;">PRO</span>'
        f'<span style="background:#F0FDF4;color:#16A34A;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:700;">ACTIVE</span>'
        f'</div></div>'
    )
    st.markdown(profile_html, unsafe_allow_html=True)

    st.write("")

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "➕ New Chat",
            use_container_width=True,
            key="new_chat"
        ):
            st.session_state.selected_conv = None
            st.session_state.active = "Ask"
            st.rerun()

    with c2:
        if st.button(
            "🚪 Logout",
            use_container_width=True,
            key="logout"
        ):
            if COOKIE_OK and cookies:
                cookies["uid"] = ""
                cookies.save()

            st.session_state.clear()
            st.rerun()

    st.divider()

    # --------------------------------------------------------
    # Knowledge Base - EXISTING
    # --------------------------------------------------------
    st.markdown("#### 📁 Knowledge Base")

    uploaded_files = st.file_uploader(
        "PDF, CSV, TXT",
        type=["pdf", "csv", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if st.button(
        "🚀 Upload & Process",
        type="primary",
        use_container_width=True,
        key="upload"
    ):
        if uploaded_files:
            with st.spinner("Processing..."):
                process_files(
                    uploaded_files,
                    1000,
                    100
                )

            st.success("Processed!")

    st.divider()

    # --------------------------------------------------------
    # Existing recent chats
    # --------------------------------------------------------
    st.markdown("#### 💬 Recent Chats")

    convs = get_user_conversations(user["id"])

    if not convs:
        st.caption("Koi chat nahi")
    else:
        for cid, q, a, mode, ts in convs[:35]:
            title = (
                q[:28] + ".."
                if len(q) > 28
                else q
            )

            if st.button(
                f"{mode} • {title}",
                key=f"hist_{cid}",
                use_container_width=True
            ):
                st.session_state.selected_conv = {
                    "id": cid,
                    "query": q,
                    "answer": a,
                    "mode": mode,
                    "timestamp": ts
                }

                st.session_state.active = "ChatView"
                st.rerun()

    st.divider()

    selected_language = st.selectbox(
        "Output Language",
        [
            "Hinglish",
            "Hindi",
            "Gujarati",
            "English"
        ],
        index=0,
        key="glang"
    )

    st.session_state.selected_language = selected_language

    chunk_size = 1000
    chunk_overlap = 100
    top_k = 8


# ============================================================
# HERO
# ============================================================

hero_html = (
    f'<div class="hero-pro"><div style="position:relative;z-index:2;">'
    f'<h1 style="margin:0;font-family:Space Grotesk;font-size:26px;font-weight:700;">Welcome back, {user["name"].split()[0]}! 👋</h1>'
    f'<h2 style="margin:6px 0 0 0;font-family:Space Grotesk;font-size:18px;font-weight:500;opacity:0.93;">RAG Based AI Teaching Assistant</h2>'
    f'<p style="margin:8px 0 0 0;opacity:0.90;font-size:13px;">Learn → Practice → Mistake → Fix → Revise → Retest</p>'
    f'</div></div><br>'
)
st.markdown(hero_html, unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

if "active" not in st.session_state:
    st.session_state.active = "Ask"

if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []
    st.session_state.viva_idx = 0
    st.session_state.viva_score = []
if "viva_evaluations" not in st.session_state:
    st.session_state.viva_evaluations = {}
if "viva_final_report" not in st.session_state:
    st.session_state.viva_final_report = None

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
    st.session_state.quiz_results = {}
if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}
if "quiz_final_report" not in st.session_state:
    st.session_state.quiz_final_report = None
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False

if "adaptive_quiz" not in st.session_state:
    st.session_state.adaptive_quiz = None
    st.session_state.adaptive_results = []

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""


lang = st.session_state.get(
    "selected_language",
    "Hinglish"
)


# ============================================================
# DASHBOARD
# EXISTING 12 FEATURES PRESERVED
# + NEW STUDENT FEATURES
# ============================================================

st.markdown("#### ⚡ Production Dashboard - All Features")

# Existing row 1
c = st.columns(6)

with c[0]:
    if st.button(
        "💬 Ask Q&A",
        use_container_width=True,
        key="dash_ask"
    ):
        st.session_state.active = "Ask"
        st.rerun()

with c[1]:
    if st.button(
        "⭐ Important",
        use_container_width=True,
        key="dash_imp"
    ):
        st.session_state.active = "Important"
        st.rerun()

with c[2]:
    if st.button(
        "🔧 Project",
        use_container_width=True,
        key="dash_proj"
    ):
        st.session_state.active = "Projects"
        st.rerun()

with c[3]:
    if st.button(
        "📝 Quiz",
        use_container_width=True,
        key="dash_quiz"
    ):
        st.session_state.active = "Quiz"
        st.rerun()

with c[4]:
    if st.button(
        "🎤 Viva",
        use_container_width=True,
        key="dash_viva"
    ):
        st.session_state.active = "Viva"
        st.rerun()

with c[5]:
    if st.button(
        "📊 PPT Maker",
        use_container_width=True,
        key="dash_ppt"
    ):
        st.session_state.active = "PPT"
        st.rerun()


# Existing row 2
c2 = st.columns(6)

with c2[0]:
    if st.button(
        "📄 Summary",
        use_container_width=True,
        key="dash_sum"
    ):
        st.session_state.active = "Summary"
        st.rerun()

with c2[1]:
    if st.button(
        "📖 Story Mode",
        use_container_width=True,
        key="dash_story"
    ):
        st.session_state.active = "Story"
        st.rerun()

with c2[2]:
    if st.button(
        "🎙️ Podcast",
        use_container_width=True,
        key="dash_pod"
    ):
        st.session_state.active = "Podcast"
        st.rerun()

with c2[3]:
    if st.button(
        "🖼️ Img→PDF",
        use_container_width=True,
        key="dash_img"
    ):
        st.session_state.active = "Image2PDF"
        st.rerun()

with c2[4]:
    if st.button(
        "👤 Profile",
        use_container_width=True,
        key="dash_prof"
    ):
        st.session_state.active = "Profile"
        st.rerun()

with c2[5]:
    if st.button(
        "🕘 History",
        use_container_width=True,
        key="dash_hist"
    ):
        st.session_state.active = "History"
        st.rerun()


st.markdown("##### 🧠 Personal Learning System")

# New row 3
n1 = st.columns(6)

with n1[0]:
    if st.button(
        "🧠 My AI Brain",
        use_container_width=True,
        key="dash_brain"
    ):
        st.session_state.active = "Brain"
        st.rerun()

with n1[1]:
    if st.button(
        "🎯 Today's Mission",
        use_container_width=True,
        key="dash_today"
    ):
        st.session_state.active = "Today"
        st.rerun()

with n1[2]:
    if st.button(
        "🔄 Smart Revision",
        use_container_width=True,
        key="dash_revision"
    ):
        st.session_state.active = "Revision"
        st.rerun()

with n1[3]:
    if st.button(
        "❌ Mistake DNA",
        use_container_width=True,
        key="dash_mistakes"
    ):
        st.session_state.active = "Mistakes"
        st.rerun()

with n1[4]:
    if st.button(
        "📊 Readiness",
        use_container_width=True,
        key="dash_ready"
    ):
        st.session_state.active = "Readiness"
        st.rerun()

with n1[5]:
    if st.button(
        "🚨 Exam Attack",
        use_container_width=True,
        key="dash_exam"
    ):
        st.session_state.active = "ExamAttack"
        st.rerun()


# New row 4
n2 = st.columns(6)

with n2[0]:
    if st.button(
        "🧑‍🏫 Teach Back",
        use_container_width=True,
        key="dash_teach"
    ):
        st.session_state.active = "TeachBack"
        st.rerun()

with n2[1]:
    if st.button(
        "⚔️ Confusion Battle",
        use_container_width=True,
        key="dash_confusion"
    ):
        st.session_state.active = "Confusion"
        st.rerun()

with n2[2]:
    if st.button(
        "📅 Study Planner",
        use_container_width=True,
        key="dash_plan"
    ):
        st.session_state.active = "Planner"
        st.rerun()

with n2[3]:
    if st.button(
        "🔥 Streak",
        use_container_width=True,
        key="dash_streak"
    ):
        st.session_state.active = "Streak"
        st.rerun()

with n2[4]:
    if st.button(
        "📈 Weekly Report",
        use_container_width=True,
        key="dash_report"
    ):
        st.session_state.active = "Report"
        st.rerun()

with n2[5]:
    if st.button(
        "⚡ 5-Min Study",
        use_container_width=True,
        key="dash_fast"
    ):
        st.session_state.active = "FastStudy"
        st.rerun()




st.markdown("##### 🚀 Source Studio — Notebook-Style Features")
ns = st.columns(6)
source_features = [
    ("📚 Source Studio", "SourceStudio"),
    ("🗂️ Flashcards", "Flashcards"),
    ("🧠 Mind Map", "MindMap"),
    ("📝 Exam Builder", "ExamBuilder"),
    ("⚖️ Compare", "Compare"),
    ("📦 Study Pack", "StudyPack"),
]
for col, (label, target) in zip(ns, source_features):
    with col:
        if st.button(label, use_container_width=True, key=f"dash_{target.lower()}"):
            st.session_state.active = target
            st.rerun()
st.divider()

active = st.session_state.active

st.subheader(
    f"▶ {active} • {lang}"
)


# ============================================================
# CHAT VIEW - EXISTING
# ============================================================

if active == "ChatView":
    conv = st.session_state.get("selected_conv")

    if not conv:
        st.info("Sidebar se chat select karo")
    else:
        st.markdown(
            f"**{conv['mode']}** • {conv['timestamp'][:16]}"
        )

        st.markdown(
            f"#### ❓ {conv['query']}"
        )

        st.divider()
        st.markdown(conv["answer"])

        play_audio_block(
            conv["answer"],
            lang,
            f"hist_{conv['id']}"
        )


# ============================================================
# PROFILE - EXISTING
# ============================================================

elif active == "Profile":
    col1, col2 = st.columns([1, 2])

    with col1:
        if user["photo"] and os.path.exists(user["photo"]):
            st.image(user["photo"], width=200)
        else:
            st.markdown(
                f"""
                <div class='avatar-letter'
                     style='width:180px;height:180px;font-size:60px;'>
                    {user["name"][0].upper()}
                </div>
                """,
                unsafe_allow_html=True
            )

        new_photo = st.file_uploader(
            "Nayi Photo - Auto Circle",
            type=["jpg", "png", "jpeg"],
            key="photo_up"
        )

    with col2:
        new_name = st.text_input(
            "Full Name",
            value=user["name"]
        )

        new_email = st.text_input(
            "Email",
            value=user["email"]
        )

        new_bio = st.text_area(
            "Bio",
            value=user["bio"] if user["bio"] else ""
        )

        if st.button(
            "💾 Update Profile",
            type="primary",
            use_container_width=True,
            key="upd_prof"
        ):
            try:
                update_profile(user["id"], new_name.strip(), new_email.strip(), new_bio.strip(), new_photo)
                st.success("Updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Profile update failed: {e}")


# ============================================================
# HISTORY - EXISTING
# ============================================================

elif active == "History":
    convs = get_user_conversations(user["id"])

    st.metric("Total", len(convs))

    for cid, q, a, mode, ts in convs:
        with st.expander(
            f"[{mode}] {q[:70]}"
        ):
            st.markdown(a)


# ============================================================
# ASK Q&A - EXISTING
# ============================================================

elif active == "Ask":
    mode = st.radio(
        "Style:",
        ["Normal", "Socratic"],
        horizontal=True,
        key="ask_mode"
    )

    sel = (
        "socratic"
        if "Socratic" in mode
        else "normal"
    )

    q = universal_input(
        "ask",
        f"Sawal bolo ({lang} me)..."
    )

    if st.button(
        "🚀 Ask Question",
        type="primary",
        use_container_width=True,
        key="ask_q"
    ) and q:

        with st.spinner("AI soch raha hai..."):
            ans, src = ask_question(
                q,
                top_k,
                mode=sel,
                language=lang
            )

        st.session_state.last_ask = ans

        save_conversation(
            user["id"],
            q,
            ans,
            f"Ask-{sel}"
        )

        log_event(
            user["id"],
            "question",
            q[:200],
            1,
            "Q&A"
        )

        st.markdown(ans)

        with st.expander("📚 Sources"):
            st.write(src)

    if "last_ask" in st.session_state:
        play_audio_block(
            st.session_state.last_ask,
            lang,
            "ask"
        )


# ============================================================
# IMPORTANT - EXISTING
# ============================================================

elif active == "Important":
    if st.button(
        f"⭐ Generate in {lang}",
        type="primary",
        use_container_width=True,
        key="imp_gen"
    ):
        with st.spinner("Important questions bana raha hu..."):
            imp = predict_important_questions(
                language=lang
            )

        st.session_state.last_imp = imp

        save_conversation(
            user["id"],
            f"Important {lang}",
            imp,
            "Important"
        )

        log_event(
            user["id"],
            "study",
            "Important Questions",
            1
        )

        st.markdown(imp)

    if "last_imp" in st.session_state:
        play_audio_block(
            st.session_state.last_imp,
            lang,
            "imp"
        )


# ============================================================
# SUMMARY - EXISTING
# ============================================================

elif active == "Summary":
    if st.button(
        f"📄 Summary in {lang}",
        type="primary",
        use_container_width=True,
        key="sum_gen"
    ):
        with st.spinner("Summary bana raha hu..."):
            summ = generate_summary(
                language=lang
            )

        st.session_state.last_summ = summ

        save_conversation(
            user["id"],
            f"Summary {lang}",
            summ,
            "Summary"
        )

        log_event(
            user["id"],
            "summary",
            "Knowledge Base",
            1
        )

        st.markdown(summ)

    if "last_summ" in st.session_state:
        play_audio_block(
            st.session_state.last_summ,
            lang,
            "summ"
        )


# ============================================================
# STORY MODE - EXISTING
# ============================================================

elif active == "Story":
    tp = universal_input(
        "story",
        f"Topic {lang}"
    )

    if st.button(
        "🎬 Create Story",
        type="primary",
        use_container_width=True,
        key="story_gen"
    ) and tp:

        with st.spinner("Story bana raha hu..."):
            story_text = story_mode_learning(
                tp,
                language=lang
            )

        st.session_state.last_story = story_text

        save_conversation(
            user["id"],
            tp,
            story_text,
            "Story"
        )

        log_event(
            user["id"],
            "study",
            tp,
            1
        )

        st.markdown(story_text)

    if "last_story" in st.session_state:
        play_audio_block(
            st.session_state.last_story,
            lang,
            "story"
        )


# ============================================================
# PROJECT - EXISTING
# ============================================================

elif active == "Projects":
    idea = universal_input(
        "proj",
        f"Project idea {lang}"
    )

    bud = st.selectbox(
        "Budget",
        ["low", "medium", "high"],
        key="bud"
    )

    if st.button(
        "🔧 Generate Guide",
        type="primary",
        use_container_width=True,
        key="proj_gen"
    ) and idea:

        with st.spinner("Project guide bana raha hu..."):
            guide = build_project_guide(
                idea,
                bud,
                language=lang
            )

        st.session_state.last_proj = guide

        save_conversation(
            user["id"],
            idea,
            guide,
            "Project"
        )

        st.markdown(guide)

    if "last_proj" in st.session_state:
        play_audio_block(
            st.session_state.last_proj,
            lang,
            "proj"
        )


# ============================================================
# PODCAST - EXISTING
# ============================================================

elif active == "Podcast":
    tp = universal_input(
        "pod",
        f"Topic {lang}"
    )

    if st.button(
        "🎙️ Create Podcast",
        type="primary",
        use_container_width=True,
        key="pod_gen"
    ) and tp:

        with st.spinner("Podcast bana raha hu..."):
            pod_text = generate_podcast_script(
                tp,
                language=lang
            )

        st.session_state.last_pod = pod_text

        save_conversation(
            user["id"],
            tp,
            pod_text,
            "Podcast"
        )

        st.markdown(pod_text)

    if "last_pod" in st.session_state:
        play_audio_block(
            st.session_state.last_pod,
            lang,
            "pod"
        )


# ============================================================
# IMAGE -> PDF / DOCX - EXISTING
# ============================================================

elif active == "Image2PDF":
    uploaded_images = st.file_uploader(
        "Images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="img_upload"
    )

    if uploaded_images:
        cols = st.columns(5)

        for idx, img in enumerate(uploaded_images):
            with cols[idx % 5]:
                st.image(
                    img,
                    caption=f"Img {idx+1}",
                    use_container_width=True
                )

        c1, c2 = st.columns(2)

        with c1:
            if st.button(
                "📄 PDF",
                type="primary",
                use_container_width=True,
                key="pdf_btn"
            ):
                st.session_state.pdf_ready = images_to_pdf(
                    uploaded_images
                )

        with c2:
            if st.button(
                "📝 DOCX",
                type="primary",
                use_container_width=True,
                key="docx_btn"
            ):
                st.session_state.docx_ready = images_to_docx(
                    uploaded_images
                )

        if "pdf_ready" in st.session_state:
            st.download_button(
                "⬇️ PDF",
                st.session_state.pdf_ready,
                file_name="RAG_Images.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf"
            )

        if "docx_ready" in st.session_state:
            st.download_button(
                "⬇️ DOCX",
                st.session_state.docx_ready,
                file_name="RAG_Images.docx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                use_container_width=True,
                key="dl_docx"
            )


# ============================================================
# QUIZ - EXISTING + MISTAKE BANK
# ============================================================

elif active == "Quiz":
    st.markdown("## 📝 Advanced Knowledge Base Quiz")
    st.caption("Quiz complete hote hi detailed result milega: correct/wrong, aapka answer, sahi answer aur explanation.")

    n = st.number_input("Kitne Q?", 3, 20, 5, key="quiz_n")
    quiz_topic = st.text_input("Topic optional", placeholder="Example: DBMS Transaction Management", key="quiz_topic")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 Generate Advanced Quiz", type="primary", use_container_width=True, key="quiz_gen"):
            with st.spinner("Source-grounded quiz bana raha hu..."):
                quiz_list = generate_quiz(n, language=lang, topic=quiz_topic or None)
            st.session_state.quiz_data = quiz_list
            st.session_state.quiz_answers = {}
            st.session_state.quiz_results = {}
            st.session_state.quiz_final_report = None
            st.session_state.quiz_submitted = False
            st.rerun()
    with c2:
        if st.button("🔄 Reset Quiz", use_container_width=True, key="quiz_reset"):
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_results = {}
            st.session_state.quiz_final_report = None
            st.session_state.quiz_submitted = False
            st.rerun()

    if st.session_state.quiz_data and not st.session_state.quiz_submitted:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"### Q{i+1}. {qd.get('question','')}")
                options = qd.get("options", [])
                if options:
                    choice = st.radio(
                        "Select answer", options,
                        key=f"quiz_answer_{i}",
                        index=None,
                        label_visibility="collapsed"
                    )
                    if choice is not None:
                        st.session_state.quiz_answers[i] = choice
                with st.expander("💡 Hint", expanded=False):
                    st.write("Recall the exact concept from your uploaded study material before selecting.")

        answered = len(st.session_state.quiz_answers)
        total = len(st.session_state.quiz_data)
        st.progress(answered / total if total else 0)
        st.caption(f"Answered: {answered}/{total}")

        if st.button("✅ Submit Complete Quiz & Get Report", type="primary", use_container_width=True, key="quiz_submit_all"):
            if answered < total:
                st.warning(f"Pehle saare questions answer karo. {total-answered} unanswered hain.")
            else:
                report = build_quiz_final_report(st.session_state.quiz_data, st.session_state.quiz_answers, lang)
                st.session_state.quiz_final_report = report
                st.session_state.quiz_submitted = True
                for item in report["items"]:
                    if item["is_correct"]:
                        log_event(user["id"], "quiz_correct", item["topic"], 1, item["question"])
                    else:
                        log_event(user["id"], "quiz_wrong", item["topic"], 0, item["question"])
                        add_mistake(user["id"], item["topic"], item["question"], item["user_answer"], item["correct_answer"])
                log_event(user["id"], "quiz_complete", quiz_topic or "General", report["score"], f"{report['correct']}/{report['total']}")
                st.rerun()

    report = st.session_state.get("quiz_final_report")
    if report:
        st.markdown("## 📊 Quiz Final Report")
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Score", f"{report['score']}%")
        m2.metric("Correct", report["correct"])
        m3.metric("Wrong", report["wrong"])
        m4.metric("Total", report["total"])

        if report["score"] == 100:
            st.success("🎉 Perfect! Saare answers correct hain.")
        elif report["score"] >= 70:
            st.success("👍 Good performance. Wrong answers ko ek baar revise karo.")
        else:
            st.warning("📚 Kuch concepts ko dobara revise karna useful rahega.")

        for item in report["items"]:
            if item["is_correct"]:
                with st.container(border=True):
                    st.markdown(f"### Q{item['number']} — ✅ Correct")
                    st.write(item["question"])
                    st.write(f"**Your answer:** {item['user_answer']}")
                    st.write(f"**Why:** {item['explanation']}")
            else:
                with st.container(border=True):
                    st.markdown(f"### Q{item['number']} — ❌ Wrong")
                    st.write(item["question"])
                    st.error(f"**Your answer:** {item['user_answer']}")
                    st.success(f"**Correct answer:** {item['correct_answer']}")
                    st.info(f"**Explanation:** {item['explanation']}")
                    st.caption(f"Topic: {item['topic']}")

        st.download_button(
            "⬇️ Download Quiz Report (TXT)",
            "QUIZ FINAL REPORT\n\n" + "\n\n".join(
                f"Q{i['number']}. {i['question']}\nYour answer: {i['user_answer']}\nCorrect answer: {i['correct_answer']}\nStatus: {'Correct' if i['is_correct'] else 'Wrong'}\nExplanation: {i['explanation']}"
                for i in report["items"]
            ),
            file_name="quiz_final_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="quiz_report_download"
        )


# ============================================================
# VIVA - ADVANCED FINAL REPORT
# ============================================================

elif active == "Viva":
    topic = universal_input("viva_topic", f"Viva topic {lang}")
    num = st.slider("Questions?", 3, 20, 5, key="viva_num")

    if st.button("🚀 Start Advanced Viva", type="primary", use_container_width=True, key="viva_start") and topic:
        with st.spinner("Source-grounded viva questions bana raha hu..."):
            qs = generate_viva_questions(topic, num, language=lang)
        st.session_state.viva_qs = qs
        st.session_state.viva_idx = 0
        st.session_state.viva_score = []
        st.session_state.viva_evaluations = {}
        st.session_state.viva_final_report = None
        st.rerun()

    if st.session_state.viva_qs and st.session_state.viva_idx < len(st.session_state.viva_qs):
        idx = st.session_state.viva_idx
        curr = st.session_state.viva_qs[idx]
        st.markdown(f"### 🎤 Q{idx+1}/{len(st.session_state.viva_qs)}")
        st.info(curr.get("q", ""))
        user_ans = universal_input(f"v_ans_{idx}", f"Apna answer {lang}")

        if st.button("Submit Answer", key=f"v_sub_{idx}", use_container_width=True) and user_ans:
            with st.spinner("AI viva evaluator answer check kar raha hai..."):
                res = verify_viva_answer(curr["q"], curr["a"], user_ans, language=lang)
            if not isinstance(res, dict):
                res={"verdict":"False","score":0,"feedback":str(res),"missing_points":[]}
            verdict=str(res.get("verdict","False")).lower()
            try: score=float(res.get("score",0))
            except Exception: score=0.0
            is_correct=verdict in {"true","correct","yes","pass","strong"} or verdict.startswith("true") or score>=7
            st.session_state.viva_evaluations[idx]={
                "user_answer":user_ans,
                "score":score,
                "is_correct":is_correct,
                "feedback":res.get("feedback", ""),
                "missing_points":res.get("missing_points",[]) or []
            }
            st.session_state.viva_score.append({"is_correct":is_correct})
            if is_correct:
                log_event(user["id"],"viva_correct",topic,1,curr["q"])
            else:
                log_event(user["id"],"viva_wrong",topic,0,curr["q"])
                add_mistake(user["id"],topic,curr["q"],user_ans,curr["a"])
            st.session_state.viva_idx += 1
            if st.session_state.viva_idx >= len(st.session_state.viva_qs):
                report=build_viva_final_report(st.session_state.viva_qs,st.session_state.viva_evaluations,lang)
                st.session_state.viva_final_report=report
                log_event(user["id"],"viva_complete",topic,report["score"],f"{report['total']} questions")
            st.rerun()

    report=st.session_state.get("viva_final_report")
    if report:
        st.markdown("## 📊 Viva Final Report")
        a,b,c=st.columns(3)
        a.metric("Overall Score",f"{report['score']}%")
        b.metric("Marks",f"{report['earned']}/{report['total']*10}")
        c.metric("Questions",report['total'])
        st.success("🎤 Viva complete! Neeche har question ka detailed review diya gaya hai.")

        for item in report["items"]:
            with st.container(border=True):
                status="✅ Strong/Correct" if item["is_correct"] else "❌ Needs Improvement"
                st.markdown(f"### Q{item['number']} — {status}")
                st.write(item["question"])
                st.write(f"**Your answer:** {item['user_answer']}")
                if item["is_correct"]:
                    st.success(f"Score: {item['score']}/10")
                else:
                    st.error(f"Score: {item['score']}/10")
                    st.success(f"**Correct/reference answer:** {item['correct_answer']}")
                st.info(f"**AI feedback:** {item['feedback']}")
                missing=item.get("missing_points",[])
                if missing:
                    st.warning("**Missing / incorrect points:** " + "; ".join(map(str,missing)))

        st.download_button(
            "⬇️ Download Viva Report (TXT)",
            "VIVA FINAL REPORT\n\n" + "\n\n".join(
                f"Q{i['number']}. {i['question']}\nYour answer: {i['user_answer']}\nReference answer: {i['correct_answer']}\nScore: {i['score']}/10\nFeedback: {i['feedback']}\nMissing/incorrect points: {', '.join(map(str,i['missing_points']))}"
                for i in report["items"]
            ),
            file_name="viva_final_report.txt",
            mime="text/plain",
            use_container_width=True,
            key="viva_report_download"
        )


# ============================================================
# PPT - EXISTING
# ============================================================

elif active == "PPT":
    topic = universal_input(
        "ppt",
        f"Topic {lang}"
    )

    pages = st.slider(
        "Slides?",
        5,
        25,
        10,
        key="ppt_pages"
    )

    if st.button(
        "Create PPT",
        type="primary",
        use_container_width=True,
        key="ppt_create"
    ) and topic:

        with st.spinner("PPT bana raha hu..."):
            ppt_path = create_ppt_file(
                topic,
                pages,
                language=lang
            )

        if ppt_path and os.path.exists(ppt_path):
            with open(ppt_path, "rb") as f:
                st.download_button(
                    "⬇️ Download PPT",
                    f.read(),
                    file_name=f"{topic}_{lang}.pptx",
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.presentationml.presentation"
                    ),
                    key="ppt_dl"
                )


# ============================================================
# 🧠 MY AI BRAIN
# ============================================================

elif active == "Brain":
    st.markdown("## 🧠 My AI Student Brain")

    stats = get_topic_stats(user["id"])
    mistakes = get_mistakes(
        user["id"],
        only_open=True
    )
    streak = get_streak(user["id"])
    events = get_events(
        user["id"],
        days=30
    )

    total_attempts = sum(
        x["attempts"]
        for x in stats.values()
    )

    total_correct = sum(
        x["correct"]
        for x in stats.values()
    )

    accuracy = (
        round(
            total_correct / total_attempts * 100
        )
        if total_attempts
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Topics Tracked",
        len(stats)
    )

    c2.metric(
        "Practice Attempts",
        total_attempts
    )

    c3.metric(
        "Accuracy",
        f"{accuracy}%"
    )

    c4.metric(
        "🔥 Streak",
        f"{streak} days"
    )

    st.divider()

    if stats:
        st.markdown("### 📚 Your Learning Map")

        rows = []

        for topic, s in stats.items():
            attempts = s["attempts"]
            acc = (
                round(
                    s["correct"] / attempts * 100
                )
                if attempts
                else 0
            )

            rows.append(
                (
                    topic,
                    attempts,
                    acc,
                    s["study"]
                )
            )

        rows.sort(
            key=lambda x: x[2],
            reverse=True
        )

        for topic, attempts, acc, study in rows[:15]:
            st.markdown(
                f"""
                <div class="feature-card">
                    <b>{topic[:70]}</b><br>
                    Practice: {attempts} |
                    Accuracy: {acc}% |
                    Study actions: {study}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info(
            "Abhi learning data kam hai. "
            "Quiz, Viva aur Q&A use karo; AI tumhara learning profile build karega."
        )

    st.markdown("### ❌ Open Mistakes")

    if mistakes:
        st.warning(
            f"{len(mistakes)} mistakes abhi fix karni baaki hain."
        )
    else:
        st.success(
            "Great! Open Mistake Bank empty hai."
        )

    if events:
        st.caption(
            f"Last 30 days me {len(events)} learning events recorded."
        )


# ============================================================
# 🎯 TODAY'S MISSION
# ============================================================

elif active == "Today":
    st.markdown("## 🎯 Today's Mission")

    plan = create_today_plan(
        user["id"]
    )

    done = sum(
        1
        for _, _, status in plan
        if status == "done"
    )

    total = len(plan)

    st.progress(
        done / total if total else 0
    )

    st.markdown(
        f"### {done}/{total} tasks complete"
    )

    for task_id, task, status in plan:
        col1, col2 = st.columns([5, 1])

        with col1:
            if status == "done":
                st.success(
                    f"✅ {task}"
                )
            else:
                st.info(
                    f"⬜ {task}"
                )

        with col2:
            if st.button(
                "Undo" if status == "done" else "Done",
                key=f"plan_{task_id}"
            ):
                toggle_plan_task(
                    task_id,
                    user["id"],
                    status
                )

                log_event(
                    user["id"],
                    "study",
                    "Daily Mission",
                    1
                )

                st.rerun()

    if done == total and total:
        st.balloons()
        st.success(
            "🔥 Today's mission complete!"
        )

    st.divider()
    st.markdown("### 🧠 Adaptive Weak-Topic Quiz")
    st.caption("App ke recorded mistakes/weak topics ke basis par targeted practice.")
    if st.button("🎯 Generate Adaptive Quiz", type="primary", key="adaptive_generate", use_container_width=True):
        with st.spinner("Weak topics analyse karke quiz bana raha hu..."):
            try:
                st.session_state.adaptive_quiz = generate_adaptive_quiz(5, language=lang, weak_topics=get_weak_topics())
                st.session_state.adaptive_results = {}
            except Exception as e:
                st.session_state.adaptive_quiz = None
                st.error(f"Adaptive quiz error: {e}")
        st.rerun()

    aq = st.session_state.get("adaptive_quiz")
    if aq:
        if not isinstance(st.session_state.get("adaptive_results"), dict):
            st.session_state.adaptive_results = {}
        for i, qd in enumerate(aq):
            if not isinstance(qd, dict):
                continue
            question = str(qd.get("question", f"Question {i+1}"))
            options = qd.get("options", [])
            answer = str(qd.get("answer", ""))
            topic = str(qd.get("topic", "Adaptive"))
            if not isinstance(options, list) or len(options) != 4:
                continue
            st.markdown(f"**Q{i+1}. {question}**")
            choice = st.radio(f"Adaptive Q{i+1}", options, key=f"adaptive_radio_{i}", label_visibility="collapsed")
            checked = i in st.session_state.adaptive_results
            if st.button(f"Check Adaptive Q{i+1}", key=f"adaptive_chk_{i}", disabled=checked):
                ok, fb = check_quiz_answer(question, choice, answer, topic)
                st.session_state.adaptive_results[i] = {"is_correct": bool(ok), "feedback": fb}
                if ok:
                    log_event(user["id"], "quiz_correct", topic, 1, question)
                    st.success(fb)
                else:
                    log_event(user["id"], "quiz_wrong", topic, 0, question)
                    add_mistake(user["id"], topic, question, choice, answer)
                    st.error(fb)
                st.rerun()
            if checked:
                st.info(st.session_state.adaptive_results[i].get("feedback", "Checked"))


# ============================================================
# 🔄 SMART REVISION
# ============================================================

elif active == "Revision":
    st.markdown("## 🔄 Smart Revision")

    mistakes = get_mistakes(
        user["id"],
        only_open=True
    )

    stats = get_topic_stats(
        user["id"]
    )

    weak_topics = []

    for topic, s in stats.items():
        if s["attempts"]:
            acc = (
                s["correct"]
                / s["attempts"]
                * 100
            )

            if acc < 70:
                weak_topics.append(
                    (topic, acc)
                )

    weak_topics.sort(
        key=lambda x: x[1]
    )

    if weak_topics:
        st.markdown(
            "### ⚠️ Topics that need revision"
        )

        for topic, acc in weak_topics[:10]:
            st.warning(
                f"**{topic[:70]}** — {round(acc)}% accuracy"
            )
    else:
        st.success(
            "No strongly weak topic detected yet."
        )

    st.divider()

    rev_topic = st.text_input(
        "Smart revision topic",
        placeholder="Example: Transaction Management",
        key="revision_topic"
    )
    if st.button("🧠 Generate Smart Revision", key="revision_generate", type="primary", use_container_width=True) and rev_topic.strip():
        with st.spinner("Smart revision prepare ho rahi hai..."):
            try:
                st.session_state.revision_result = generate_revision(rev_topic.strip(), language=lang, focus="weakness")
            except Exception as e:
                st.session_state.revision_result = f"Revision error: {e}"

    if st.session_state.get("revision_result"):
        st.markdown("### 📚 AI Smart Revision")
        st.markdown(str(st.session_state.revision_result))
        play_audio_block(str(st.session_state.revision_result), lang, "smart_revision")

    if mistakes:
        st.markdown(
            "### ❌ Revision from Mistake Bank"
        )

        for m in mistakes[:10]:
            mid, topic, q, ua, ca, ts, fixed = m

            with st.expander(
                f"{topic[:50]} • {q[:70]}"
            ):
                st.markdown(
                    f"**Question:** {q}"
                )
                st.markdown(
                    f"**Your answer:** {ua}"
                )
                st.markdown(
                    f"**Correct answer:** {ca}"
                )

                if st.button(
                    "✅ Mark Fixed",
                    key=f"fix_rev_{mid}"
                ):
                    mark_mistake_fixed(
                        mid,
                        user["id"]
                    )

                    log_event(
                        user["id"],
                        "revision",
                        topic,
                        1
                    )

                    st.rerun()

    else:
        st.info(
            "Mistake Bank empty hai. Quiz/Viva practice karo."
        )


# ============================================================
# ❌ MISTAKE DNA
# ============================================================

elif active == "Mistakes":
    st.markdown("## ❌ Mistake DNA")

    mistakes = get_mistakes(
        user["id"]
    )

    open_mistakes = [
        m for m in mistakes
        if m[6] == 0
    ]

    fixed_mistakes = [
        m for m in mistakes
        if m[6] == 1
    ]

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Mistakes",
        len(mistakes)
    )

    c2.metric(
        "Open",
        len(open_mistakes)
    )

    c3.metric(
        "Fixed",
        len(fixed_mistakes)
    )

    if not mistakes:
        st.info(
            "Abhi Mistake DNA empty hai."
        )
    else:
        topic_count = {}

        for m in mistakes:
            topic = m[1] or "General"
            topic_count[topic] = (
                topic_count.get(topic, 0) + 1
            )

        st.markdown(
            "### 🔥 Repeated mistake areas"
        )

        for topic, count in sorted(
            topic_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:
            st.warning(
                f"**{topic[:70]}** — {count} mistake(s)"
            )

        st.divider()

        st.markdown(
            "### 📖 Mistake Review"
        )

        for m in mistakes[:30]:
            mid, topic, q, ua, ca, ts, fixed = m

            label = (
                "✅ Fixed"
                if fixed
                else "❌ Open"
            )

            with st.expander(
                f"{label} • {topic[:40]} • {q[:65]}"
            ):
                st.markdown(
                    f"**Question:** {q}"
                )

                st.markdown(
                    f"**Your answer:** {ua}"
                )

                st.markdown(
                    f"**Correct answer:** {ca}"
                )

                if not fixed:
                    if st.button(
                        "Mark as Fixed",
                        key=f"fix_m_{mid}"
                    ):
                        mark_mistake_fixed(
                            mid,
                            user["id"]
                        )

                        log_event(
                            user["id"],
                            "revision",
                            topic,
                            1,
                            "Mistake fixed"
                        )

                        st.rerun()


# ============================================================
# 📊 READINESS
# ============================================================

elif active == "Readiness":
    st.markdown("## 📊 Exam Readiness")

    stats = get_topic_stats(
        user["id"]
    )

    mistakes = get_mistakes(
        user["id"],
        only_open=True
    )

    total_attempts = sum(
        s["attempts"]
        for s in stats.values()
    )

    total_correct = sum(
        s["correct"]
        for s in stats.values()
    )

    accuracy = (
        total_correct / total_attempts * 100
        if total_attempts
        else 0
    )

    practice_component = min(
        100,
        total_attempts * 4
    )

    mistake_component = max(
        0,
        100 - len(mistakes) * 8
    )

    topic_component = min(
        100,
        len(stats) * 12
    )

    readiness = round(
        accuracy * 0.45
        + practice_component * 0.20
        + mistake_component * 0.20
        + topic_component * 0.15
    )

    readiness = max(
        0,
        min(100, readiness)
    )

    st.metric(
        "Current Readiness Indicator",
        f"{readiness}%"
    )

    st.progress(
        readiness / 100
    )

    st.caption(
        "Ye app ke recorded practice data par based "
        "learning indicator hai, exam result prediction nahi."
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Accuracy",
        f"{round(accuracy)}%"
    )

    c2.metric(
        "Attempts",
        total_attempts
    )

    c3.metric(
        "Weak/Open Mistakes",
        len(mistakes)
    )

    c4.metric(
        "Topics",
        len(stats)
    )

    st.divider()

    if readiness >= 80:
        st.success(
            "Strong practice data. Ab timed revision aur viva practice karo."
        )
    elif readiness >= 60:
        st.info(
            "Good progress. Weak topics par targeted practice karo."
        )
    else:
        st.warning(
            "Practice base build karo aur mistakes ko revise karo."
        )


# ============================================================
# 🚨 EXAM ATTACK
# ============================================================

elif active == "ExamAttack":
    st.markdown("## 🚨 Exam Attack Mode")

    st.info(
        "Upload ki hui study material ke basis par "
        "Important Questions + Summary + Quiz + Viva workflow."
    )

    exam_topic = st.text_input(
        "Exam topic (optional)",
        placeholder="Example: Transaction Management",
        key="exam_topic"
    )

    if st.button("🚨 Build Exam Attack Plan", key="exam_attack_plan", use_container_width=True):
        with st.spinner("Exam attack plan bana raha hu..."):
            try:
                st.session_state.exam_attack_plan = generate_exam_attack(exam_topic.strip() or "uploaded material", language=lang)
            except Exception as e:
                st.session_state.exam_attack_plan = f"Exam attack error: {e}"

    if st.session_state.get("exam_attack_plan"):
        st.markdown("### 🚨 Exam Attack Plan")
        st.markdown(str(st.session_state.exam_attack_plan))

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⭐ Generate Important Questions",
            type="primary",
            use_container_width=True,
            key="exam_imp"
        ):
            with st.spinner("Exam questions bana raha hu..."):
                exam_imp = predict_important_questions(
                    language=lang, topic=exam_topic.strip() or None
                )

            st.session_state.exam_imp = exam_imp

            save_conversation(
                user["id"],
                "Exam Attack - Important Questions",
                exam_imp,
                "ExamAttack"
            )

    with col2:
        if st.button(
            "📄 Generate Rapid Summary",
            type="primary",
            use_container_width=True,
            key="exam_sum"
        ):
            with st.spinner("Rapid summary bana raha hu..."):
                exam_sum = generate_summary(
                    language=lang, topic=exam_topic.strip() or None
                )

            st.session_state.exam_sum = exam_sum

    if "exam_imp" in st.session_state:
        st.markdown("### ⭐ Important Questions")
        st.markdown(
            st.session_state.exam_imp
        )

    if "exam_sum" in st.session_state:
        st.markdown("### 📄 Rapid Revision")
        st.markdown(
            st.session_state.exam_sum
        )

    st.divider()

    st.markdown(
        "### 📝 Quick Practice"
    )

    qn = st.slider(
        "Questions",
        3,
        10,
        5,
        key="exam_quiz_n"
    )

    if st.button(
        "Generate Exam Quiz",
        use_container_width=True,
        key="exam_quiz"
    ):
        with st.spinner("Exam quiz..."):
            st.session_state.exam_quiz_data = generate_quiz(
                int(qn), language=lang, topic=exam_topic.strip() or None
            )

        st.session_state.exam_quiz_results = []


    if st.session_state.get("exam_quiz_data"):
        st.markdown("### 🎯 Exam Quiz")
        if "exam_quiz_results" not in st.session_state or not isinstance(st.session_state.exam_quiz_results, dict):
            st.session_state.exam_quiz_results = {}
        for i, qd in enumerate(st.session_state.exam_quiz_data):
            if not isinstance(qd, dict):
                continue
            question = str(qd.get("question", f"Question {i+1}"))
            options = qd.get("options", [])
            answer = str(qd.get("answer", ""))
            topic = str(qd.get("topic", "Exam"))
            if not isinstance(options, list) or len(options) != 4:
                continue
            st.markdown(f"**Q{i+1}. {question}**")
            choice = st.radio(
                f"Exam Q{i+1}", options, key=f"exam_radio_{i}",
                label_visibility="collapsed"
            )
            checked = i in st.session_state.exam_quiz_results
            if st.button(f"Check Exam Q{i+1}", key=f"exam_chk_{i}", disabled=checked):
                ok, fb = check_quiz_answer(question, choice, answer, topic)
                st.session_state.exam_quiz_results[i] = {"is_correct": bool(ok), "feedback": fb}
                if ok:
                    log_event(user["id"], "quiz_correct", topic, 1, question)
                    st.success(fb)
                else:
                    log_event(user["id"], "quiz_wrong", topic, 0, question)
                    add_mistake(user["id"], topic, question, choice, answer)
                    st.error(fb)
                st.rerun()
            if checked:
                st.info(st.session_state.exam_quiz_results[i].get("feedback", "Checked"))


# ============================================================
# 🧑‍🏫 TEACH BACK
# ============================================================

elif active == "TeachBack":
    st.markdown("## 🧑‍🏫 Teach-Back Mode")

    st.write(
        "Student teacher banega. Tum topic explain karo; "
        "AI tumhari explanation me missing points identify karega."
    )

    topic = universal_input(
        "teach_topic",
        f"Topic ({lang})"
    )

    explanation = st.text_area(
        "Apni explanation yahan likho",
        height=220,
        placeholder="Example: ACID property ko main aise explain karunga..."
    )

    if st.button(
        "🧑‍🏫 Evaluate My Teaching",
        type="primary",
        use_container_width=True,
        key="teach_eval"
    ) and topic and explanation:

        with st.spinner("AI explanation analyze kar raha hai..."):
            try:
                result = generate_teach_back_feedback(
                    topic, explanation, language=lang
                )
            except Exception as e:
                result = {
                    "score": 0,
                    "verdict": "Needs Work",
                    "what_was_correct": [],
                    "missing_or_wrong": [str(e)],
                    "one_better_explanation": "Try again after checking your notes.",
                    "next_question": topic
                }

        st.session_state.teach_result = result

        log_event(
            user["id"],
            "teach_back",
            topic,
            1,
            explanation[:500]
        )

    if "teach_result" in st.session_state:
        tr = st.session_state.teach_result
        if isinstance(tr, dict):
            st.metric("Teach-back Score", f"{tr.get('score', 0)}/10")
            st.success(str(tr.get("verdict", "Needs Work")))
            st.markdown("**What was correct**")
            for x in tr.get("what_was_correct", []) or []:
                st.write("• " + str(x))
            st.markdown("**Missing / wrong**")
            for x in tr.get("missing_or_wrong", []) or []:
                st.write("• " + str(x))
            st.markdown("**Better explanation**")
            st.write(tr.get("one_better_explanation", ""))
            st.markdown("**Next question**")
            st.write(tr.get("next_question", ""))
        else:
            st.markdown(str(tr))


# ============================================================
# ⚔️ CONFUSION BATTLE
# ============================================================

elif active == "Confusion":
    st.markdown("## ⚔️ Confusion Battle")

    st.write(
        "Do similar concepts compare karo aur difference samjho."
    )

    a = st.text_input(
        "Concept A",
        placeholder="Example: Primary Key"
    )

    b = st.text_input(
        "Concept B",
        placeholder="Example: Foreign Key"
    )

    if st.button(
        "⚔️ Compare Concepts",
        type="primary",
        use_container_width=True,
        key="confusion_compare"
    ) and a and b:

        with st.spinner("Concept battle prepare ho rahi hai..."):
            try:
                result = generate_confusion_battle(a, b, language=lang)
            except Exception as e:
                result = f"Comparison error: {e}"

        st.markdown(result)

        save_conversation(
            user["id"],
            f"Compare: {a} vs {b}",
            result,
            "Confusion"
        )


# ============================================================
# 📅 STUDY PLANNER
# ============================================================

elif active == "Planner":
    st.markdown("## 📅 Study Planner")

    st.write(
        "Daily tasks ko simple checklist me manage karo."
    )

    plan = create_today_plan(
        user["id"]
    )

    done = sum(
        1
        for _, _, status in plan
        if status == "done"
    )

    total = len(plan)

    st.metric(
        "Today's completion",
        f"{done}/{total}"
    )

    for task_id, task, status in plan:
        col1, col2 = st.columns(
            [6, 1]
        )

        with col1:
            st.write(
                ("✅ " if status == "done" else "⬜ ")
                + task
            )

        with col2:
            if st.button(
                "✓" if status != "done" else "↩",
                key=f"planner_{task_id}"
            ):
                toggle_plan_task(
                    task_id,
                    user["id"],
                    status
                )
                st.rerun()


# ============================================================
# 🔥 STREAK
# ============================================================

elif active == "Streak":
    st.markdown("## 🔥 Learning Streak")

    streak = get_streak(
        user["id"]
    )

    events = get_events(
        user["id"],
        days=30
    )

    st.markdown(
        f"""
        <div class="dark-card">
            <div style="font-size:42px;">🔥</div>
            <h1 style="margin:0;">{streak} Day Streak</h1>
            <p>Har din thoda practice karo aur learning habit build karo.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    active_dates = set()
    for x in events:
        try:
            if x[5]:
                active_dates.add(datetime.fromisoformat(x[5]).date())
        except Exception:
            continue
    active_dates = sorted(active_dates, reverse=True)

    st.metric(
        "Active days in last 30 days",
        len(active_dates)
    )

    if active_dates:
        st.markdown("### Recent active days")

        st.write(
            ", ".join(
                str(d)
                for d in active_dates[:15]
            )
        )


# ============================================================
# 📈 WEEKLY REPORT
# ============================================================

elif active == "Report":
    st.markdown("## 📈 Weekly AI Learning Report")

    events = get_events(
        user["id"],
        days=7
    )

    mistakes = get_mistakes(
        user["id"]
    )

    stats = get_topic_stats(user["id"], days=7)

    attempts = sum(
        s["attempts"]
        for s in stats.values()
    )

    correct = sum(
        s["correct"]
        for s in stats.values()
    )

    accuracy = (
        round(correct / attempts * 100)
        if attempts
        else 0
    )

    week_mistakes = [
        m for m in mistakes
        if m[5] >= (
            datetime.now()
            - timedelta(days=7)
        ).isoformat()
    ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Learning events",
        len(events)
    )

    c2.metric(
        "Practice attempts",
        attempts
    )

    c3.metric(
        "Accuracy",
        f"{accuracy}%"
    )

    c4.metric(
        "New mistakes",
        len(week_mistakes)
    )

    st.divider()

    if stats:
        weak = []

        for topic, s in stats.items():
            if s["attempts"]:
                acc = (
                    s["correct"]
                    / s["attempts"]
                    * 100
                )
                weak.append(
                    (topic, acc)
                )

        weak.sort(
            key=lambda x: x[1]
        )

        st.markdown(
            "### 🎯 Topics to revisit"
        )

        for topic, acc in weak[:5]:
            st.warning(
                f"{topic[:70]} — {round(acc)}% practice accuracy"
            )

    if events:
        st.markdown(
            "### 🧾 Recent activity"
        )

        for event in events[:15]:
            _, event_type, topic, score, details, created_at = event

            st.caption(
                f"{created_at[:16]} • "
                f"{event_type} • "
                f"{topic[:60]}"
            )
    else:
        st.info(
            "Is week activity nahi mili. "
            "Aaj se practice start karo."
        )


# ============================================================
# ⚡ 5-MINUTE STUDY
# ============================================================

elif active == "FastStudy":
    st.markdown("## ⚡ 5-Minute Study Mode")

    st.write(
        "Time kam hai? Ek compact learning cycle complete karo."
    )

    topic = st.text_input(
        "Topic",
        placeholder="Example: DBMS Transaction Management",
        key="fast_topic"
    )

    if st.button(
        "⚡ Start 5-Minute Session",
        type="primary",
        use_container_width=True,
        key="fast_start"
    ) and topic.strip():

        topic = topic.strip()

        with st.spinner("Quick lesson bana raha hu..."):
            try:
                answer, sources = ask_question(
                    f"""
Teach me this topic in a 5-minute study session:
{topic}

Structure:
1. 60-second simple explanation
2. 3 key points
3. One real-life example
4. 3 recall questions
5. One exam tip

Language: {lang}
""",
                    top_k,
                    mode="normal",
                    language=lang
                )

                st.session_state.fast_result = answer

                log_event(
                    user["id"],
                    "study",
                    topic,
                    1,
                    "5-minute study"
                )

            except Exception as e:
                st.error(
                    f"Session error: {e}"
                )

    if "fast_result" in st.session_state:
        st.markdown(
            st.session_state.fast_result
        )

        play_audio_block(
            st.session_state.fast_result,
            lang,
            "fast_study"
        )



# ============================================================
# SOURCE STUDIO
# ============================================================
elif active == "SourceStudio":
    st.markdown("## 📚 Source Studio")
    st.caption("Notebook-style source intelligence: indexed files, source brief, grounded answers and study guide.")
    inventory = get_source_inventory()
    if inventory:
        cols = st.columns(min(4, max(1, len(inventory))))
        for i, item in enumerate(inventory):
            with cols[i % len(cols)]:
                st.metric(item["name"][:22], f"{item['chunks']} chunks")
    else:
        st.info("Pehle Knowledge Base me PDF/TXT/CSV upload karo.")
    topic = st.text_input("Focus topic (optional)", key="studio_topic", placeholder="Example: ACID properties")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✨ Source Brief", type="primary", use_container_width=True, key="studio_brief"):
            with st.spinner("Sources ko synthesize kar raha hu..."):
                st.session_state.studio_brief = generate_source_brief(lang)
    with c2:
        if st.button("📘 Study Guide", use_container_width=True, key="studio_guide"):
            with st.spinner("Deep study guide bana raha hu..."):
                st.session_state.studio_guide = generate_study_guide(topic or "all material", lang)
    with c3:
        if st.button("🔊 Audio Overview", use_container_width=True, key="studio_audio"):
            with st.spinner("Audio script bana raha hu..."):
                st.session_state.studio_audio = generate_podcast_script(topic or "all material", lang)
    if st.session_state.get("studio_brief"):
        st.markdown(st.session_state.studio_brief)
    if st.session_state.get("studio_guide"):
        st.markdown(st.session_state.studio_guide)
    if st.session_state.get("studio_audio"):
        st.markdown(st.session_state.studio_audio)
        play_audio_block(st.session_state.studio_audio, lang, "studio_audio")

# ============================================================
# FLASHCARDS
# ============================================================
elif active == "Flashcards":
    st.markdown("## 🗂️ AI Flashcards")
    topic = st.text_input("Topic", key="fc_topic", placeholder="Leave blank for all material")
    n = st.slider("Number of cards", 5, 30, 12, key="fc_n")
    if st.button("🧠 Generate Flashcards", type="primary", use_container_width=True, key="fc_gen"):
        with st.spinner("Flashcards bana raha hu..."):
            st.session_state.flashcards = generate_flashcards(topic or "all material", n, lang)
    cards = st.session_state.get("flashcards", [])
    if cards:
        for i, card in enumerate(cards):
            with st.expander(f"Card {i+1} • {card['difficulty']}"):
                st.markdown(f"**Q:** {card['front']}")
                st.divider()
                st.markdown(f"**A:** {card['back']}")
                st.caption(f"Source: {card['source']}")

# ============================================================
# MIND MAP
# ============================================================
elif active == "MindMap":
    st.markdown("## 🧠 Source-Grounded Mind Map")
    topic = st.text_input("Central topic", key="mm_topic", placeholder="Example: DBMS Transactions")
    if st.button("🌳 Build Mind Map", type="primary", use_container_width=True, key="mm_gen") and topic.strip():
        with st.spinner("Concept relationships nikal raha hu..."):
            st.session_state.mind_map = generate_mind_map(topic.strip(), lang)
    if st.session_state.get("mind_map"):
        st.markdown(st.session_state.mind_map)

# ============================================================
# EXAM BUILDER
# ============================================================
elif active == "ExamBuilder":
    st.markdown("## 📝 AI Exam Builder")
    topic = st.text_input("Exam topic", key="exam_topic", placeholder="Example: Query Processing & Optimization")
    c1, c2 = st.columns(2)
    with c1:
        n = st.slider("Questions", 5, 25, 10, key="exam_n")
    with c2:
        difficulty = st.selectbox("Difficulty", ["Mixed", "Easy", "Medium", "Hard"], key="exam_diff")
    if st.button("🚀 Generate Practice Paper", type="primary", use_container_width=True, key="exam_gen"):
        with st.spinner("Source-grounded exam paper bana raha hu..."):
            st.session_state.exam_paper = generate_exam_paper(topic or "all material", n, difficulty, lang)
    paper = st.session_state.get("exam_paper", [])
    if paper:
        total = sum(int(x.get("marks", 0)) for x in paper)
        st.metric("Total Marks", total)
        for i, q in enumerate(paper, 1):
            with st.expander(f"Q{i} • {q['type']} • {q['marks']} marks"):
                st.markdown(q["question"])
                st.caption(f"Topic: {q['topic']}")
                with st.expander("Show answer"):
                    st.write(q["answer"])

# ============================================================
# COMPARE
# ============================================================
elif active == "Compare":
    st.markdown("## ⚖️ Compare Two Concepts")
    a, b = st.columns(2)
    with a:
        topic_a = st.text_input("Concept A", key="cmp_a", placeholder="Example: Primary Key")
    with b:
        topic_b = st.text_input("Concept B", key="cmp_b", placeholder="Example: Foreign Key")
    if st.button("⚖️ Compare from Sources", type="primary", use_container_width=True, key="cmp_go") and topic_a.strip() and topic_b.strip():
        with st.spinner("Sources se comparison bana raha hu..."):
            st.session_state.compare_result = compare_source_topics(topic_a.strip(), topic_b.strip(), lang)
    if st.session_state.get("compare_result"):
        st.markdown(st.session_state.compare_result)

# ============================================================
# STUDY PACK
# ============================================================
elif active == "StudyPack":
    st.markdown("## 📦 One-Click Study Pack")
    topic = st.text_input("Pack topic", key="pack_topic", placeholder="Example: Complete DBMS Unit 4")
    if st.button("📦 Build DOCX Study Pack", type="primary", use_container_width=True, key="pack_build"):
        with st.spinner("Brief + guide + flashcards ko DOCX me pack kar raha hu..."):
            try:
                pack = build_study_pack(topic or "all material", lang)
                st.session_state.study_pack = pack.getvalue()
            except Exception as e:
                st.error(f"Study pack error: {e}")
    if st.session_state.get("study_pack"):
        st.download_button(
            "⬇️ Download Study Pack (.docx)",
            st.session_state.study_pack,
            file_name="RAG_AI_Study_Pack.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="pack_download",
        )


# ============================================================
# FALLBACK
# ============================================================

else:
    st.info(
        "Module select karo."
    )
