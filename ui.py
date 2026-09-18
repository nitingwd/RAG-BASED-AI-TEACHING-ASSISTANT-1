import streamlit as st
import tempfile
import os
import io
import sqlite3
import json
import hashlib
from datetime import datetime
from PIL import Image
from docx import Document
from docx.shared import Inches

# ================= AUTH SYSTEM - USERNAME/PASSWORD ONLY =================
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
                     (username, hash_pwd(password), name, email, "", "", datetime.now().isoformat()))
        conn.commit(); conn.close()
        return True, "Account ban gaya!"
    except sqlite3.IntegrityError:
        return False, "Username pehle se hai!"
    except Exception as e:
        return False, str(e)

def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, name, email, photo, bio FROM users WHERE username=? AND password=?", (username, hash_pwd(password)))
    u = c.fetchone(); conn.close()
    if u:
        return {"id": u[0], "username": u[1], "name": u[2], "email": u[3], "photo": u[4], "bio": u[5]}
    return None

def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, name, email, photo, bio FROM users WHERE id=?", (user_id,))
    u = c.fetchone(); conn.close()
    if u:
        return {"id": u[0], "username": u[1], "name": u[2], "email": u[3], "photo": u[4], "bio": u[5]}
    return None

def update_profile(user_id, name, email, bio, photo_file=None):
    photo_path = None
    if photo_file:
        ext = photo_file.name.split(".")[-1]
        photo_path = f"{PICS_PATH}/{user_id}.{ext}"
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
    if st.session_state.get("logged_in"):
        return True
    st.set_page_config(page_title="SUBMIT - Login", layout="centered", page_icon="🎓")
    st.markdown("""
    <style>.login-box {background: linear-gradient(135deg,#E0E7FF,#C7D2FE); padding:30px; border-radius:20px; text-align:center;}</style>
    <div class="login-box"><h1>🎓 SUBMIT V16</h1><p>Username + Password Login</p></div><br>
    """, unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with tab1:
        username = st.text_input("Username", key="l_user")
        pwd = st.text_input("Password", type="password", key="l_pwd")
        if st.button("Login", type="primary", use_container_width=True):
            user = login_user(username, pwd)
            if user:
                st.session_state.logged_in = True; st.session_state.user = user; st.rerun()
            else:
                st.error("Galat Username/Password")
    with tab2:
        name = st.text_input("Full Name", key="s_name")
        username = st.text_input("Username (unique)", key="s_user")
        email = st.text_input("Email", key="s_email")
        pwd = st.text_input("Password", type="password", key="s_pwd")
        if st.button("Account Banao", use_container_width=True):
            if len(username) < 3:
                st.error("Username min 3 char")
            else:
                ok, msg = signup_user(username, pwd, name, email)
                if ok: st.success(msg + " Ab Login karo")
                else: st.error(msg)
    return False

if not auth_ui():
    st.stop()

user = get_user_by_id(st.session_state.user['id'])
st.session_state.user = user

# ================= SAFE IMPORT =================
try:
    from rag_utils import (
        process_files, ask_question, load_conversation_history, get_api_key,
        generate_quiz, generate_summary, predict_important_questions,
        check_quiz_answer, get_weak_topics, transcribe_audio,
        story_mode_learning, build_project_guide, generate_podcast_script,
        generate_viva_questions, verify_viva_answer, create_ppt_file,
        text_to_audio_file, images_to_pdf, images_to_docx
    )
    RAG_OK = True
except ImportError:
    from rag_utils import (
        process_files, ask_question, load_conversation_history, get_api_key,
        generate_quiz, generate_summary, predict_important_questions,
        check_quiz_answer, get_weak_topics, transcribe_audio,
        story_mode_learning, build_project_guide, generate_podcast_script,
        generate_viva_questions, verify_viva_answer, create_ppt_file,
        text_to_audio_file
    )
    RAG_OK = False
    def images_to_pdf(image_files):
        images = [Image.open(img).convert("RGB") for img in image_files]
        pdf_buffer = io.BytesIO()
        if len(images) == 1:
            images[0].save(pdf_buffer, format="PDF")
        else:
            images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:])
        pdf_buffer.seek(0)
        return pdf_buffer
    def images_to_docx(image_files):
        doc = Document()
        doc.add_heading('SUBMIT - Converted Images Document', 0)
        doc_buffer = io.BytesIO()
        for img_file in image_files:
            image = Image.open(img_file)
            temp_buffer = io.BytesIO()
            image.save(temp_buffer, format='PNG')
            temp_buffer.seek(0)
            doc.add_picture(temp_buffer, width=Inches(5.5))
            doc.add_paragraph("")
        doc.save(doc_buffer)
        doc_buffer.seek(0)
        return doc_buffer

st.set_page_config(page_title="Advance RAG - AI Teaching Assistant", layout="wide", page_icon="🎓")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
.main {background-color: #F8F9FF;}
.dev-badge {position: fixed; bottom: 15px; right: 15px; background: linear-gradient(135deg,#0D1126,#6366F1); color: white; padding: 8px 14px; border-radius: 20px; font-size: 12px; z-index: 999;}
.hero {background: linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%); border-radius: 20px; padding: 30px; margin-bottom: 20px;}
.stButton>button {border-radius: 10px; height: 48px; font-weight: 600;}
.chat-btn {text-align:left!important;}
</style>
<div class="dev-badge">V16.5 AUTH + HISTORY | KADIYA NARESH</div>
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
        if vt:
            st.success(f"🎧 {vt}"); return vt
    return txt

def play_audio_block(text, lang, key):
    if not text: return
    st.markdown(f"#### 🔊 {lang} Audio - Poora Output Suno")
    if st.button(f"▶️ {lang} me Suno", key=f"play_{key}", type="primary"):
        with st.spinner(f"{lang} me audio bana raha hu..."):
            audio_path = text_to_audio_file(text, lang)
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 500:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                st.download_button(f"⬇️ Download {lang} MP3", audio_bytes, file_name=f"{key}_{lang}.mp3", mime="audio/mp3", key=f"dl_{key}")
                st.success(f"✅ {lang} Audio Ready!")
            else:
                st.error("Audio fail - net check karo")

# ================= SIDEBAR WITH CLICKABLE HISTORY =================
with st.sidebar:
    if user['photo'] and os.path.exists(user['photo']):
        st.image(user['photo'], width=100)
    st.markdown(f"### 👤 {user['name']}")
    st.caption(f"@{user['username']} | {user['email']}")
    colA, colB = st.columns(2)
    with colA:
        if st.button("➕ New", use_container_width=True):
            st.session_state.selected_conv = None
            st.session_state.active = "Ask"; st.rerun()
    with colB:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear(); st.rerun()
    st.divider()

    st.markdown("### 📁 File Upload")
    uploaded_files = st.file_uploader("PDF, CSV, TXT", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."):
                process_files(uploaded_files, 1000, 100)
    st.divider()

    st.markdown("### 💬 Tumhari Chats - Click Karo")
    search = st.text_input("Search chats", placeholder="Search...", label_visibility="collapsed", key="search_chat")
    convs = get_user_conversations(user['id'])
    if not convs:
        st.info("Koi chat nahi")
    else:
        for cid, q, a, mode, ts in convs:
            if search and search.lower() not in q.lower():
                continue
            title = q[:28] + ".." if len(q) > 28 else q
            label = f"[{mode}] {title}"
            if st.button(label, key=f"hist_{cid}", use_container_width=True):
                st.session_state.selected_conv = {"id": cid, "query": q, "answer": a, "mode": mode, "timestamp": ts}
                st.session_state.active = "ChatView"
                st.rerun()

    st.divider()
    st.markdown("### 🌐 Global Language")
    selected_language = st.selectbox("Output Language", ["Hinglish","Hindi","Gujarati","English"], index=0, key="glang")
    st.session_state.selected_language = selected_language
    st.success(f"Active: {selected_language}")
    if not RAG_OK:
        st.warning("⚠️ rag_utils.py purana hai")
    st.divider()
    st.markdown("### 📊 Weak Topics")
    weak = get_weak_topics()
    if weak:
        for t,c in sorted(weak.items(), key=lambda x:x[1], reverse=True)[:5]:
            st.write(f"🔴 {t}: {c}")
    chunk_size, chunk_overlap, top_k = 1000, 100, 8

st.markdown(f"""
<div class="hero">
    <h1 style="margin:0; font-size: 32px; color: #111827;">Welcome {user['name']}! RAG AI Teaching Assistant</h1>
    <p style="color: #4B5563;">🔊 Audio + Quiz + Viva + Image2PDF + Profile History - V16.5</p>
</div>
""", unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "quiz_results" not in st.session_state:
    st.session_state.quiz_results = []

st.markdown("### ✨ Features")
c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1:
    if st.button("💬 Ask Q&A", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("⭐ Important", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c3:
    if st.button("🔧 Project", use_container_width=True): st.session_state.active="Projects"; st.rerun()
with c4:
    if st.button("📝 Quiz", use_container_width=True): st.session_state.active="Quiz"; st.rerun()
with c5:
    if st.button("🎤 Viva", use_container_width=True): st.session_state.active="Viva"; st.rerun()
with c6:
    if st.button("📊 PPT", use_container_width=True): st.session_state.active="PPT"; st.rerun()

c7,c8,c9,c10,c11,c12 = st.columns(6)
with c7:
    if st.button("📄 Summary", use_container_width=True): st.session_state.active="Summary"; st.rerun()
with c8:
    if st.button("📖 Story", use_container_width=True): st.session_state.active="Story"; st.rerun()
with c9:
    if st.button("🎙️ Podcast", use_container_width=True): st.session_state.active="Podcast"; st.rerun()
with c10:
    if st.button("🖼️ Image to PDF", use_container_width=True): st.session_state.active="Image2PDF"; st.rerun()
with c11:
    if st.button("👤 Profile", use_container_width=True): st.session_state.active="Profile"; st.rerun()
with c12:
    if st.button("🕘 All History", use_container_width=True): st.session_state.active="History"; st.rerun()

st.divider()
active = st.session_state.active
lang = st.session_state.get('selected_language','Hinglish')
st.header(f"▶ {active} Mode | 🌐 {lang}")

# ================= MODES =================
if active=="Image2PDF":
    st.markdown("### 🖼️ Image to PDF / DOCX Converter")
    uploaded_images = st.file_uploader("Images Upload Karo (JPG, PNG, JPEG)", type=["jpg","jpeg","png"], accept_multiple_files=True, key="img_upload")
    if uploaded_images:
        st.success(f"✅ {len(uploaded_images)} images selected")
        cols = st.columns(5)
        for idx, img in enumerate(uploaded_images):
            with cols[idx % 5]:
                st.image(img, caption=f"Img {idx+1}", use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 PDF me Convert Karo", type="primary", use_container_width=True):
                with st.spinner("PDF bana raha hu..."):
                    pdf_data = images_to_pdf(uploaded_images)
                    st.session_state.pdf_ready = pdf_data
                st.success("PDF Ready!")
        with col2:
            if st.button("📝 DOCX me Convert Karo", type="primary", use_container_width=True):
                with st.spinner("DOCX bana raha hu..."):
                    docx_data = images_to_docx(uploaded_images)
                    st.session_state.docx_ready = docx_data
                st.success("DOCX Ready!")
        if "pdf_ready" in st.session_state:
            st.download_button(label="⬇️ PDF Download Karo", data=st.session_state.pdf_ready, file_name=f"SUBMIT_Images_{len(uploaded_images)}_pages.pdf", mime="application/pdf", use_container_width=True, key="dl_pdf_final")
        if "docx_ready" in st.session_state:
            st.download_button(label="⬇️ DOCX Download Karo", data=st.session_state.docx_ready, file_name=f"SUBMIT_Images_{len(uploaded_images)}_pages.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="dl_docx_final")
    else:
        st.warning("Pehle images upload karo")

elif active=="ChatView":
    conv = st.session_state.get("selected_conv")
    if not conv:
        st.info("Sidebar se koi chat select karo")
    else:
        st.markdown(f"### 💬 {conv['mode']} | {conv['timestamp'][:16]}")
        st.markdown(f"#### ❓ Q: {conv['query']}")
        st.divider()
        st.markdown(conv['answer'])
        play_audio_block(conv['answer'], lang, f"hist_{conv['id']}")
        if st.button("⬅️ Back"):
            st.session_state.active = "Ask"; st.rerun()

elif active=="Profile":
    st.markdown(f"## 👤 {user['name']} ki Profile")
    col1, col2 = st.columns([1,2])
    with col1:
        if user['photo'] and os.path.exists(user['photo']):
            st.image(user['photo'], caption="Profile Photo", width=200)
        new_photo = st.file_uploader("Photo Badlo / Add Karo", type=["jpg","png","jpeg"], key="photo_up")
    with col2:
        new_name = st.text_input("Name", value=user['name'])
        new_email = st.text_input("Email", value=user['email'])
        new_bio = st.text_area("Bio", value=user['bio'] if user['bio'] else "", placeholder="I am a student...")
        if st.button("Profile Update Karo", type="primary"):
            update_profile(user['id'], new_name, new_email, new_bio, new_photo)
            st.success("Profile Updated!"); st.rerun()
    st.divider()
    st.write(f"**Username:** {user['username']}")
    st.write(f"**Total Chats:** {len(get_user_conversations(user['id']))}")

elif active=="History":
    st.markdown(f"## 🕘 {user['name']} ka Saara Data")
    convs = get_user_conversations(user['id'])
    if not convs:
        st.info("Koi history nahi")
    else:
        st.metric("Total Conversations", len(convs))
        for cid, q, a, mode, ts in convs:
            with st.expander(f"[{mode}] {q} - {ts[:16]}"):
                st.markdown(f"**Q:** {q}")
                st.markdown(a)

elif active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask",f"Sawal bolo ({lang} me)...")
    if st.button("Ask Question", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel, language=lang)
            st.session_state.last_ask = ans
            save_conversation(user['id'], q, ans, f"Ask-{sel}")
            st.markdown(ans)
            with st.expander("📚 Source"): st.write(src)
    if "last_ask" in st.session_state:
        play_audio_block(st.session_state.last_ask, lang, "ask")

elif active=="Important":
    if st.button(f"Generate Important Qs in {lang}",type="primary"):
        imp = predict_important_questions(language=lang)
        st.session_state.last_imp = imp
        save_conversation(user['id'], f"Important Qs {lang}", imp, "Important")
        st.markdown(imp)
    if "last_imp" in st.session_state:
        play_audio_block(st.session_state.last_imp, lang, "imp")

elif active=="Summary":
    if st.button(f"Generate Summary in {lang}",type="primary"):
        summ = generate_summary(language=lang)
        st.session_state.last_summ = summ
        save_conversation(user['id'], f"Summary {lang}", summ, "Summary")
        st.markdown(summ)
    if "last_summ" in st.session_state:
        play_audio_block(st.session_state.last_summ, lang, "summ")

elif active=="Story":
    tp=universal_input("story",f"Topic in {lang} - Stack")
    if st.button("🎬 Create Story + Audio",type="primary") and tp:
        story_text = story_mode_learning(tp, language=lang)
        st.session_state.last_story = story_text
        save_conversation(user['id'], tp, story_text, "Story")
        st.markdown(story_text)
    if "last_story" in st.session_state:
        play_audio_block(st.session_state.last_story, lang, "story")

elif active=="Projects":
    idea=universal_input("proj",f"Project idea ({lang})")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("Generate Guide",type="primary") and idea:
        guide = build_project_guide(idea,bud, language=lang)
        st.session_state.last_proj = guide
        save_conversation(user['id'], idea, guide, "Project")
        st.markdown(guide)
    if "last_proj" in st.session_state:
        play_audio_block(st.session_state.last_proj, lang, "proj")

elif active=="Podcast":
    tp=universal_input("pod",f"Topic for Podcast in {lang}")
    if st.button("🎙️ Create Podcast + Audio",type="primary") and tp:
        pod_text = generate_podcast_script(tp, language=lang)
        st.session_state.last_pod = pod_text
        save_conversation(user['id'], tp, pod_text, "Podcast")
        st.markdown(pod_text)
        ap = text_to_audio_file(pod_text, lang)
        if ap and os.path.exists(ap):
            with open(ap,"rb") as f:
                st.audio(f.read(), format="audio/mp3", autoplay=True)
            st.success(f"🔊 {lang} Podcast Auto Play")
    if "last_pod" in st.session_state:
        play_audio_block(st.session_state.last_pod, lang, "pod")

elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,15,5)
    if st.button("Generate Quiz", type="primary"):
        quiz_list = generate_quiz(n, language=lang)
        st.session_state.quiz_data = quiz_list
        st.session_state.quiz_results = []
        st.rerun()
    if st.session_state.quiz_data:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"**Q{i+1}. {qd['question']}**")
                choice = st.radio(f"Select {i}", qd['options'], key=f"quiz_{i}", label_visibility="collapsed")
                c1,c2 = st.columns(2)
                with c1:
                    if st.button(f"🔊 Suno Q{i+1}", key=f"aud_{i}"):
                        ap = text_to_audio_file(f"{qd['question']} Options: {', '.join(qd['options'])}", lang)
                        if ap and os.path.exists(ap):
                            with open(ap,"rb") as f: st.audio(f.read(), format="audio/mp3")
                with c2:
                    if st.button(f"Check Q{i+1}", key=f"chk_{i}"):
                        ok, fb = check_quiz_answer(qd['question'], choice, qd['answer'], qd.get('topic','general'))
                        st.session_state.quiz_results.append({"q": qd['question'], "your": choice, "correct": qd['answer'], "is_correct": ok, "topic": qd.get('topic','general'), "explanation": qd.get('explanation','')})
                        st.success(fb) if ok else st.error(fb)
                        st.info(f"📖 {qd.get('explanation','')}")
        if st.session_state.quiz_results:
            results = st.session_state.quiz_results
            correct = sum(1 for r in results if r.get('is_correct', False))
            total = len(results)
            wrong = total - correct
            perc = (correct/total*100) if total>0 else 0
            st.divider()
            st.markdown("## 📊 QUIZ REPORT BOARD")
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Total Attempted", total)
            m2.metric("✅ Sahi", correct)
            m3.metric("❌ Galat", wrong)
            m4.metric("Score", f"{perc:.1f}%")
            st.progress(int(perc))
            if st.button("🔄 Quiz Reset"):
                st.session_state.quiz_data = None
                st.session_state.quiz_results = []
                st.rerun()

elif active=="Viva":
    topic=universal_input("viva_topic",f"Viva topic ({lang})")
    num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva",type="primary"):
        if topic:
            qs=generate_viva_questions(topic,num, language=lang)
            st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]
            st.subheader(f"Q{idx+1}: {curr['q']}")
            if st.button(f"🔊 Suno Question in {lang}", key=f"v_aud_{idx}"):
                ap = text_to_audio_file(curr['q'], lang)
                if ap and os.path.exists(ap):
                    with open(ap,"rb") as f: st.audio(f.read(), format="audio/mp3")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer in {lang}")
            if st.button("Submit", key=f"v_sub_{idx}"):
                if user_ans:
                    res=verify_viva_answer(curr['q'], curr['a'], user_ans, language=lang)
                    is_correct = "true" in str(res.get('verdict','')).lower()
                    st.session_state.viva_score.append({"q":curr['q'],"your":user_ans,"correct":curr['a'],"result":res.get('verdict',''),"is_correct": is_correct, "fb":res.get('feedback','')})
                    ap2 = text_to_audio_file(res.get('feedback',''), lang)
                    if ap2 and os.path.exists(ap2):
                        with open(ap2,"rb") as f: st.audio(f.read(), format="audio/mp3", autoplay=True)
                    if is_correct:
                        st.success(f"✅ SAHI - {res.get('feedback','')}")
                    else:
                        st.error(f"❌ GALAT - {res.get('feedback','')}")
                        st.info(f"💡 Sahi Jawaab: {curr['a']}")
                    st.session_state.viva_idx+=1; st.rerun()
        else:
            score=st.session_state.viva_score
            correct = sum(1 for s in score if s.get('is_correct', False))
            total = len(score)
            wrong = total - correct
            perc = (correct/total*100) if total>0 else 0
            st.balloons()
            st.success(f"Viva Done! {total} Questions")
            st.markdown("## 📊 VIVA FINAL REPORT")
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Total", total)
            m2.metric("✅ Sahi", correct)
            m3.metric("❌ Galat", wrong)
            m4.metric("Score", f"{perc:.1f}%")
            st.progress(int(perc))
            if st.button("🔄 New Viva Start"):
                st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []; st.rerun()

elif active=="PPT":
    topic=universal_input("ppt",f"Topic in {lang} - AI")
    pages=st.slider("Slides?",5,25,10)
    if st.button("Create PPT",type="primary"):
        if topic:
            ppt_path=create_ppt_file(topic, pages, language=lang)
            with open(ppt_path,"rb") as f:
                st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{lang}.pptx")
            st.success("Ban gaya!")
