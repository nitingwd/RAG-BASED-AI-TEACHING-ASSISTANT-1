import streamlit as st
import tempfile
import os
import io
import sqlite3
import hashlib
import base64
from datetime import datetime
from PIL import Image
from docx import Document
from docx.shared import Inches

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    COOKIE_OK = True
except:
    COOKIE_OK = False

DB_PATH = "data/users.db"
PICS_PATH = "data/profile_pics"
os.makedirs("data", exist_ok=True)
os.makedirs(PICS_PATH, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
    (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT, photo TEXT, bio TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
    (id INTEGER PRIMARY KEY, user_id INTEGER, query TEXT, answer TEXT, mode TEXT, timestamp TEXT)''')
    conn.commit(); conn.close()
init_db()

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def signup_user(username, password, name, email):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO users (username, password, name, email, photo, bio, created_at) VALUES (?,?,?,?,?,?,?)",
                     (username.lower().strip(), hash_pwd(password), name, email, "", "", datetime.now().isoformat()))
        conn.commit(); conn.close()
        return True, "Account ban gaya!"
    except sqlite3.IntegrityError:
        return False, "Username pehle se hai!"
    except Exception as e:
        return False, str(e)

def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, name, email, photo, bio FROM users WHERE username=? AND password=?", (username.lower().strip(), hash_pwd(password)))
    u = c.fetchone(); conn.close()
    if u:
        return {"id": u[0], "username": u[1], "name": u[2], "email": u[3], "photo": u[4], "bio": u[5]}
    return None

def get_user_by_id(user_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, username, name, email, photo, bio FROM users WHERE id=?", (user_id,))
        u = c.fetchone(); conn.close()
        if u:
            return {"id": u[0], "username": u[1], "name": u[2], "email": u[3], "photo": u[4], "bio": u[5]}
    except: return None
    return None

def update_profile(user_id, name, email, bio, photo_file=None):
    photo_path = None
    if photo_file:
        ext = photo_file.name.split(".")[-1]
        photo_path = f"{PICS_PATH}/{user_id}_{int(datetime.now().timestamp())}.{ext}"
        with open(photo_path, "wb") as f:
            f.write(photo_file.getbuffer())
    conn = get_conn()
    if photo_path:
        conn.execute("UPDATE users SET name=?, email=?, bio=?, photo=? WHERE id=?", (name, email, bio, photo_path, user_id))
    else:
        conn.execute("UPDATE users SET name=?, email=?, bio=? WHERE id=?", (name, email, bio, user_id))
    conn.commit(); conn.close()
    return True

def save_conversation(user_id, query, answer, mode="Ask"):
    conn = get_conn()
    conn.execute("INSERT INTO conversations (user_id, query, answer, mode, timestamp) VALUES (?,?,?,?,?)",
                 (user_id, query, answer, mode, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_user_conversations(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, query, answer, mode, timestamp FROM conversations WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall(); conn.close()
    return rows

def auth_ui():
    cookies = None
    if COOKIE_OK:
        cookies = EncryptedCookieManager(prefix="rag_v21_", password="kadiya_naresh_2024_secure_key_v21")
        if not cookies.ready():
            st.stop()
    if st.session_state.get("logged_in") and st.session_state.get("user"):
        return True, cookies
    if COOKIE_OK and cookies and cookies.get("uid"):
        try:
            uid = int(cookies.get("uid"))
            u = get_user_by_id(uid)
            if u:
                st.session_state.logged_in = True
                st.session_state.user = u
                return True, cookies
        except:
            pass
    st.set_page_config(page_title="RAG Based AI Teaching Assistant", layout="centered", page_icon="🎓")
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600;700&display=swap');
  .stApp {background: radial-gradient(1000px at 20% 10%, #E0E7FF 0%, #F0F4FF 40%, #FFFFFF 100%);}
  .login-card {background: rgba(255,255,255,0.95); backdrop-filter: blur(24px); border: 1px solid rgba(99,102,241,0.12); padding: 36px; border-radius: 28px; box-shadow: 0 24px 80px rgba(99,102,241,0.18); text-align:center; max-width:440px; width:100%;}
  .login-title {font-family:'Space Grotesk'; font-size:28px; font-weight:700; color:#111827; line-height:1.2;}
  .login-sub {color:#6B7280; font-size:13px; margin-top:6px;}
  .pill {display:inline-block; background:linear-gradient(135deg,#EEF2FF,#E0E7FF); color:#6366F1; padding:6px 12px; border-radius:20px; font-size:11px; font-weight:700; margin:3px; border:1px solid #C7D2FE;}
  .stButton>button {border-radius:12px; height:48px; font-weight:700;}
    </style>
    """, unsafe_allow_html=True)
    _, col, _ = st.columns([1,2,1])
    with col:
        st.markdown("""
        <div class="login-card">
            <div style="font-size:52px; margin-bottom:8px;">🎓</div>
            <div class="login-title">RAG Based AI<br>Teaching Assistant</div>
            <div class="login-sub">One-time login, 30 days tak yaad rahega</div>
            <div style="margin-top:14px;">
                <span class="pill">💬 Q&A</span><span class="pill">🎤 VIVA</span><span class="pill">📝 QUIZ</span><span class="pill">🔊 AUDIO</span>
            </div>
        </div><br>
        """, unsafe_allow_html=True)
        t1,t2 = st.tabs(["🔐 Login", "✨ Sign Up"])
        with t1:
            username = st.text_input("Username", placeholder="naresh123", key="l_user")
            pwd = st.text_input("Password", type="password", placeholder="••••••••", key="l_pwd")
            if st.button("🚀 Login to Dashboard", type="primary", use_container_width=True):
                u = login_user(username, pwd)
                if u:
                    st.session_state.logged_in = True; st.session_state.user = u
                    if COOKIE_OK: cookies["uid"] = str(u['id']); cookies.save()
                    st.rerun()
                else: st.error("Galat Username/Password")
        with t2:
            name = st.text_input("Full Name", key="s_name", placeholder="Kadiya Naresh")
            username = st.text_input("Username", key="s_user", placeholder="naresh123")
            email = st.text_input("Email", key="s_email", placeholder="naresh@gmail.com")
            pwd = st.text_input("Password", key="s_pwd", type="password", placeholder="Min 4 chars")
            if st.button("Create Account", use_container_width=True):
                if len(username)<3 or len(pwd)<4: st.error("Username min 3, Password min 4")
                else:
                    ok,msg = signup_user(username,pwd,name,email)
                    if ok: st.success(msg+" Ab Login karo"); st.balloons()
                    else: st.error(msg)
    return False, cookies

logged_in, cookies = auth_ui()
if not logged_in: st.stop()
user = get_user_by_id(st.session_state.user['id'])
if not user:
    if COOKIE_OK: cookies["uid"]=""; cookies.save()
    st.session_state.clear(); st.rerun()
st.session_state.user = user

try:
    from rag_utils import (process_files, ask_question, get_api_key, generate_quiz, generate_summary, predict_important_questions, check_quiz_answer, get_weak_topics, transcribe_audio, story_mode_learning, build_project_guide, generate_podcast_script, generate_viva_questions, verify_viva_answer, create_ppt_file, text_to_audio_file, images_to_pdf, images_to_docx)
    RAG_OK=True
except:
    from rag_utils import (process_files, ask_question, get_api_key, generate_quiz, generate_summary, predict_important_questions, check_quiz_answer, get_weak_topics, transcribe_audio, story_mode_learning, build_project_guide, generate_podcast_script, generate_viva_questions, verify_viva_answer, create_ppt_file, text_to_audio_file)
    RAG_OK=False
    def images_to_pdf(image_files):
        images=[Image.open(img).convert("RGB") for img in image_files]
        buf=io.BytesIO(); images[0].save(buf, format="PDF", save_all=True, append_images=images[1:]) if len(images)>1 else images[0].save(buf, format="PDF")
        buf.seek(0); return buf
    def images_to_docx(image_files):
        doc=Document(); doc.add_heading('RAG Based AI Teaching Assistant',0); buf=io.BytesIO()
        for img_file in image_files:
            image=Image.open(img_file); t=io.BytesIO(); image.save(t, format='PNG'); t.seek(0); doc.add_picture(t, width=Inches(5.5))
        doc.save(buf); buf.seek(0); return buf

st.set_page_config(page_title="RAG Based AI Teaching Assistant", layout="wide", page_icon="🎓")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600;700&display=swap');
.main {background:#F8FAFF;}
.hero-pro {background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 35%, #EC4899 70%, #F59E0B 100%); border-radius: 24px; padding: 26px 28px; color:white; position:relative; overflow:hidden; box-shadow: 0 16px 40px rgba(99,102,241,0.25);}
.hero-pro::before {content:''; position:absolute; top:-70%; right:-15%; width:500px; height:500px; background: radial-gradient(circle, rgba(255,255,255,0.22) 0%, transparent 70%); border-radius:50%;}
.profile-card-pro {background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFF 100%); border-radius:20px; padding:18px; border:1px solid #E0E7FF; text-align:center; box-shadow: 0 8px 24px rgba(99,102,241,0.08);}
.img-circle {width:85px; height:85px; border-radius:50%; object-fit:cover; border:3px solid transparent; background: linear-gradient(white, white) padding-box, linear-gradient(135deg,#6366F1,#EC4899) border-box; box-shadow: 0 6px 20px rgba(99,102,241,0.25); display:block; margin:0 auto;}
.avatar-letter {width:85px; height:85px; border-radius:50%; background: linear-gradient(135deg,#6366F1 0%, #8B5CF6 50%, #EC4899 100%); display:flex; align-items:center; justify-content:center; margin:0 auto; color:white; font-size:32px; font-weight:700; font-family:Space Grotesk; box-shadow:0 6px 20px rgba(99,102,241,0.3);}
.dev-badge {position: fixed; bottom: 14px; right: 14px; background: #111827; color: white; padding: 7px 12px; border-radius: 20px; font-size: 10px; z-index: 999; font-weight:600;}
.stButton>button {border-radius:14px; height:50px; font-weight:700; transition:all 0.25s ease; border:1.5px solid transparent;}
.stButton>button:hover {transform:translateY(-2px) scale(1.02); box-shadow:0 12px 28px rgba(0,0,0,0.15);}

/* PREMIUM COLORS FOR DASHBOARD - 12 UNIQUE GRADIENTS */
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(1) button {background: linear-gradient(135deg,#6366F1 0%,#8B5CF6 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(2) button {background: linear-gradient(135deg,#F59E0B 0%,#EF4444 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(3) button {background: linear-gradient(135deg,#10B981 0%,#06B6D4 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(4) button {background: linear-gradient(135deg,#EC4899 0%,#8B5CF6 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(5) button {background: linear-gradient(135deg,#3B82F6 0%,#6366F1 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(6) button {background: linear-gradient(135deg,#8B5CF6 0%,#EC4899 50%,#F59E0B 100%)!important; color:white!important;}

div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(1) button {background: linear-gradient(135deg,#06B6D4 0%,#3B82F6 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(2) button {background: linear-gradient(135deg,#F97316 0%,#F59E0B 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(3) button {background: linear-gradient(135deg,#14B8A6 0%,#10B981 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(4) button {background: linear-gradient(135deg,#6366F1 0%,#06B6D4 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(5) button {background: linear-gradient(135deg,#1F2937 0%,#4B5563 100%)!important; color:white!important;}
div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(6) button {background: linear-gradient(135deg,#EC4899 0%,#F59E0B 100%)!important; color:white!important;}
</style>
<div class="dev-badge">V21 PREMIUM CLEAN | KADIYA NARESH</div>
""", unsafe_allow_html=True)

def universal_input(key, placeholder="Bolo ya likho..."):
    c1,c2 = st.columns([5,1])
    with c1:
        txt = st.text_input(" ", key=f"txt_{key}", placeholder=placeholder, label_visibility="collapsed")
    with c2:
        aud = st.audio_input("🎤", key=f"aud_{key}", label_visibility="collapsed")
    if aud:
        api_key = get_api_key()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(aud.getvalue()); path = tmp.name
        with st.spinner("Sun raha hu..."):
            vt = transcribe_audio(api_key, path)
        if os.path.exists(path): os.remove(path)
        if vt: st.success(f"🎧 {vt}"); return vt
    return txt

def play_audio_block(text, lang, key):
    if not text: return
    if st.button(f"▶️ {lang} me Suno", key=f"play_{key}", type="primary", use_container_width=True):
        with st.spinner("Audio bana raha hu..."):
            ap = text_to_audio_file(text, lang)
            if ap and os.path.exists(ap) and os.path.getsize(ap)>500:
                with open(ap,"rb") as f: audio_bytes=f.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)

with st.sidebar:
    photo_html = ""
    if user['photo'] and os.path.exists(user['photo']):
        try:
            with open(user['photo'], "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                ext = user['photo'].split(".")[-1]
                photo_html = f'<img src="data:image/{ext};base64,{b64}" class="img-circle">'
        except:
            photo_html = f'<div class="avatar-letter">{user["name"][0].upper()}</div>'
    else:
        photo_html = f'<div class="avatar-letter">{user["name"][0].upper()}</div>'
    st.markdown(f"""
    <div class="profile-card-pro">
        {photo_html}
        <h4 style="margin:12px 0 2px 0; font-family:Space Grotesk; font-size:16px; color:#111827;">{user['name']}</h4>
        <p style="margin:0; color:#6366F1; font-size:12px; font-weight:600;">@{user['username']}</p>
        <p style="margin:2px 0 0 0; color:#9CA3AF; font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{user['email']}</p>
        <div style="margin-top:10px; display:flex; gap:6px; justify-content:center;">
            <span style="background:#EEF2FF; color:#6366F1; padding:3px 8px; border-radius:10px; font-size:10px; font-weight:700;">PRO</span>
            <span style="background:#F0FDF4; color:#16A34A; padding:3px 8px; border-radius:10px; font-size:10px; font-weight:700;">ACTIVE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("➕ New Chat", use_container_width=True): st.session_state.selected_conv=None; st.session_state.active="Ask"; st.rerun()
    with c2:
        if st.button("🚪 Logout", use_container_width=True):
            if COOKIE_OK: cookies["uid"]=""; cookies.save()
            st.session_state.clear(); st.rerun()
    st.divider()
    st.markdown("#### 📁 Knowledge Base")
    uploaded_files = st.file_uploader("PDF, CSV, TXT", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."): process_files(uploaded_files, 1000, 100)
            st.success("Processed!")
    st.divider()
    st.markdown("#### 💬 Recent Chats")
    convs = get_user_conversations(user['id'])
    if not convs:
        st.caption("Koi chat nahi - Naya sawal pucho!")
    else:
        for cid, q, a, mode, ts in convs[:35]:
            title = (q[:28] + "..") if len(q) > 28 else q
            if st.button(f"{mode} • {title}", key=f"hist_{cid}", use_container_width=True):
                st.session_state.selected_conv = {"id": cid, "query": q, "answer": a, "mode": mode, "timestamp": ts}
                st.session_state.active = "ChatView"; st.rerun()
    st.divider()
    selected_language = st.selectbox("Output Language", ["Hinglish","Hindi","Gujarati","English"], index=0, key="glang")
    st.session_state.selected_language = selected_language
    chunk_size, chunk_overlap, top_k = 1000, 100, 8

# ================= HERO - CLEAN NO EXTRA LINE =================
st.markdown(f"""
<div class="hero-pro">
    <div style="position:relative; z-index:2;">
        <h1 style="margin:0; font-family:Space Grotesk; font-size:26px; font-weight:700;">Welcome back, {user['name'].split()[0]}! 👋</h1>
        <h2 style="margin:6px 0 0 0; font-family:Space Grotesk; font-size:18px; font-weight:500; opacity:0.93;">RAG Based AI Teaching Assistant</h2>
    </div>
</div><br>
""", unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state: st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None; st.session_state.quiz_results = []

st.markdown("#### ⚡ Production Dashboard - All Features")
c = st.columns(6)
with c[0]:
    if st.button("💬 Ask Q&A", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c[1]:
    if st.button("⭐ Important", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c[2]:
    if st.button("🔧 Project", use_container_width=True): st.session_state.active="Projects"; st.rerun()
with c[3]:
    if st.button("📝 Quiz", use_container_width=True): st.session_state.active="Quiz"; st.rerun()
with c[4]:
    if st.button("🎤 Viva", use_container_width=True): st.session_state.active="Viva"; st.rerun()
with c[5]:
    if st.button("📊 PPT Maker", use_container_width=True): st.session_state.active="PPT"; st.rerun()
c2 = st.columns(6)
with c2[0]:
    if st.button("📄 Summary", use_container_width=True): st.session_state.active="Summary"; st.rerun()
with c2[1]:
    if st.button("📖 Story Mode", use_container_width=True): st.session_state.active="Story"; st.rerun()
with c2[2]:
    if st.button("🎙️ Podcast", use_container_width=True): st.session_state.active="Podcast"; st.rerun()
with c2[3]:
    if st.button("🖼️ Img→PDF", use_container_width=True): st.session_state.active="Image2PDF"; st.rerun()
with c2[4]:
    if st.button("👤 Profile", use_container_width=True): st.session_state.active="Profile"; st.rerun()
with c2[5]:
    if st.button("🕘 History", use_container_width=True): st.session_state.active="History"; st.rerun()
st.divider()

active = st.session_state.active
lang = st.session_state.get('selected_language','Hinglish')
st.subheader(f"▶ {active} • {lang}")

if active=="ChatView":
    conv = st.session_state.get("selected_conv")
    if not conv: st.info("Sidebar se chat select karo")
    else:
        st.markdown(f"**{conv['mode']}** • {conv['timestamp'][:16]}")
        st.markdown(f"#### ❓ {conv['query']}")
        st.divider(); st.markdown(conv['answer']); play_audio_block(conv['answer'], lang, f"hist_{conv['id']}")
elif active=="Profile":
    col1,col2 = st.columns([1,2])
    with col1:
        if user['photo'] and os.path.exists(user['photo']): st.image(user['photo'], width=200)
        else: st.markdown(f"<div class='avatar-letter' style='width:180px; height:180px; font-size:60px;'>{user['name'][0].upper()}</div>", unsafe_allow_html=True)
        new_photo = st.file_uploader("Nayi Photo - Auto Circle", type=["jpg","png","jpeg"], key="photo_up")
    with col2:
        new_name = st.text_input("Full Name", value=user['name']); new_email = st.text_input("Email", value=user['email'])
        new_bio = st.text_area("Bio", value=user['bio'] if user['bio'] else "")
        if st.button("💾 Update Profile", type="primary", use_container_width=True):
            update_profile(user['id'], new_name, new_email, new_bio, new_photo); st.success("Profile Updated!"); st.rerun()
elif active=="History":
    convs = get_user_conversations(user['id'])
    st.metric("Total", len(convs))
    for cid, q, a, mode, ts in convs:
        with st.expander(f"[{mode}] {q[:70]}"): st.markdown(a)
elif active=="Ask":
    mode = st.radio("Style:", ["Normal","Socratic"], horizontal=True); sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask",f"Sawal bolo ({lang} me)...")
    if st.button("🚀 Ask Question", type="primary", use_container_width=True) and q:
        ans,src = ask_question(q, top_k, mode=sel, language=lang)
        st.session_state.last_ask = ans; save_conversation(user['id'], q, ans, f"Ask-{sel}"); st.markdown(ans)
        with st.expander("📚 Sources"): st.write(src)
    if "last_ask" in st.session_state: play_audio_block(st.session_state.last_ask, lang, "ask")
elif active=="Important":
    if st.button(f"⭐ Generate in {lang}", type="primary", use_container_width=True):
        imp = predict_important_questions(language=lang); st.session_state.last_imp = imp; save_conversation(user['id'], f"Important {lang}", imp, "Important"); st.markdown(imp)
    if "last_imp" in st.session_state: play_audio_block(st.session_state.last_imp, lang, "imp")
elif active=="Summary":
    if st.button(f"📄 Summary in {lang}", type="primary", use_container_width=True):
        summ = generate_summary(language=lang); st.session_state.last_summ = summ; save_conversation(user['id'], f"Summary {lang}", summ, "Summary"); st.markdown(summ)
    if "last_summ" in st.session_state: play_audio_block(st.session_state.last_summ, lang, "summ")
elif active=="Story":
    tp=universal_input("story",f"Topic {lang}")
    if st.button("🎬 Create Story", type="primary", use_container_width=True) and tp:
        story_text = story_mode_learning(tp, language=lang); st.session_state.last_story = story_text; save_conversation(user['id'], tp, story_text, "Story"); st.markdown(story_text)
    if "last_story" in st.session_state: play_audio_block(st.session_state.last_story, lang, "story")
elif active=="Projects":
    idea=universal_input("proj",f"Project idea {lang}"); bud=st.selectbox("Budget",["low","medium","high"], key="bud")
    if st.button("🔧 Generate Guide", type="primary", use_container_width=True) and idea:
        guide = build_project_guide(idea,bud, language=lang); st.session_state.last_proj = guide; save_conversation(user['id'], idea, guide, "Project"); st.markdown(guide)
    if "last_proj" in st.session_state: play_audio_block(st.session_state.last_proj, lang, "proj")
elif active=="Podcast":
    tp=universal_input("pod",f"Topic {lang}")
    if st.button("🎙️ Create Podcast", type="primary", use_container_width=True) and tp:
        pod_text = generate_podcast_script(tp, language=lang); st.session_state.last_pod = pod_text; save_conversation(user['id'], tp, pod_text, "Podcast"); st.markdown(pod_text)
    if "last_pod" in st.session_state: play_audio_block(st.session_state.last_pod, lang, "pod")
elif active=="Image2PDF":
    uploaded_images = st.file_uploader("Images", type=["jpg","jpeg","png"], accept_multiple_files=True, key="img_upload")
    if uploaded_images:
        cols = st.columns(5)
        for idx, img in enumerate(uploaded_images):
            with cols[idx % 5]: st.image(img, caption=f"Img {idx+1}", use_container_width=True)
        c1,c2 = st.columns(2)
        with c1:
            if st.button("📄 PDF", type="primary", use_container_width=True):
                pdf_data = images_to_pdf(uploaded_images); st.session_state.pdf_ready = pdf_data
        with c2:
            if st.button("📝 DOCX", type="primary", use_container_width=True):
                docx_data = images_to_docx(uploaded_images); st.session_state.docx_ready = docx_data
        if "pdf_ready" in st.session_state: st.download_button("⬇️ PDF", st.session_state.pdf_ready, file_name="RAG_Images.pdf", mime="application/pdf", use_container_width=True)
        if "docx_ready" in st.session_state: st.download_button("⬇️ DOCX", st.session_state.docx_ready, file_name="RAG_Images.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,15,5)
    if st.button("Generate Quiz", type="primary", use_container_width=True):
        quiz_list = generate_quiz(n, language=lang); st.session_state.quiz_data = quiz_list; st.session_state.quiz_results = []; st.rerun()
    if st.session_state.quiz_data:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"**Q{i+1}. {qd['question']}**")
                choice = st.radio(f"q_{i}", qd['options'], key=f"quiz_{i}", label_visibility="collapsed")
                if st.button(f"Check Q{i+1}", key=f"chk_{i}"):
                    ok, fb = check_quiz_answer(qd['question'], choice, qd['answer'], qd.get('topic','general'))
                    st.session_state.quiz_results.append({"is_correct": ok}); st.success(fb) if ok else st.error(fb)
elif active=="Viva":
    topic=universal_input("viva_topic",f"Viva topic {lang}"); num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva", type="primary", use_container_width=True) and topic:
        qs=generate_viva_questions(topic,num, language=lang); st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]; st.subheader(f"Q{idx+1}: {curr['q']}")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer {lang}")
            if st.button("Submit", key=f"v_sub_{idx}", use_container_width=True) and user_ans:
                res=verify_viva_answer(curr['q'], curr['a'], user_ans, language=lang)
                is_correct = "true" in str(res.get('verdict','')).lower()
                st.session_state.viva_score.append({"is_correct": is_correct})
                st.success(res.get('feedback','')) if is_correct else st.error(res.get('feedback',''))
                st.session_state.viva_idx+=1; st.rerun()
elif active=="PPT":
    topic=universal_input("ppt",f"Topic {lang}"); pages=st.slider("Slides?",5,25,10)
    if st.button("Create PPT", type="primary", use_container_width=True) and topic:
        ppt_path=create_ppt_file(topic, pages, language=lang)
        with open(ppt_path,"rb") as f: st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{lang}.pptx")
