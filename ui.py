import streamlit as st
import tempfile
import os
import io
import sqlite3
import hashlib
from datetime import datetime
from PIL import Image
from docx import Document
from docx.shared import Inches

# ================= AUTH SYSTEM - PERSISTENT FIXED =================
DB_PATH = "data/users.db"
PICS_PATH = "data/profile_pics"
os.makedirs("data", exist_ok=True)
os.makedirs(PICS_PATH, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    # Kabhi bhi DROP nahi karenge - sirf create if not exists
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
        clean_user = username.lower().strip()
        conn = get_conn()
        conn.execute("INSERT INTO users (username, password, name, email, photo, bio, created_at) VALUES (?,?,?,?,?,?,?)",
                     (clean_user, hash_pwd(password), name, email, "", "", datetime.now().isoformat()))
        conn.commit(); conn.close()
        return True, "Account ban gaya!"
    except sqlite3.IntegrityError:
        return False, "Ye Username pehle se hai! Dusra try karo"
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
    if st.session_state.get("logged_in"):
        return True
    st.set_page_config(page_title="RAG Based AI Teaching Assistant", layout="centered", page_icon="🎓")
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600&display=swap');
   .stApp {background: radial-gradient(1200px at 20% 10%, #E0E7FF 0%, #F8F9FF 50%, #FFFFFF 100%);}
   .login-card {background: rgba(255,255,255,0.9); backdrop-filter: blur(20px); border: 1px solid rgba(99,102,241,0.15); padding: 36px; border-radius: 24px; box-shadow: 0 20px 60px rgba(99,102,241,0.15); text-align:center;}
   .login-title {font-family: 'Space Grotesk'; font-size: 30px; font-weight: 700; color: #111827; margin:0; line-height:1.2;}
   .login-sub {color: #6B7280; font-family: 'Inter'; margin-top:8px; font-size:14px;}
   .pill {display:inline-block; background: #EEF2FF; color: #6366F1; padding:6px 14px; border-radius: 20px; font-size: 11px; font-weight:700; margin: 3px;}
   .stButton>button {border-radius: 12px; height: 48px; font-weight: 700;}
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div class="login-card">
            <div style="font-size:50px;">🎓</div>
            <h1 class="login-title">RAG Based AI<br>Teaching Assistant</h1>
            <p class="login-sub">Your Personal AI Tutor for Viva, Quiz, Projects & More</p>
            <div style="margin-top:14px;">
                <span class="pill">💬 Q&A</span><span class="pill">🎤 VIVA</span><span class="pill">📝 QUIZ</span><span class="pill">🔊 AUDIO</span>
            </div>
        </div><br>
        """, unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Create Account"])
        with tab1:
            username = st.text_input("Username", placeholder="Ex: naresh123", key="l_user")
            pwd = st.text_input("Password", type="password", placeholder="••••••••", key="l_pwd")
            if st.button("🚀 Login to Dashboard", type="primary", use_container_width=True):
                if not username or not pwd:
                    st.error("Username aur Password dalo")
                else:
                    user = login_user(username, pwd)
                    if user:
                        st.session_state.logged_in = True; st.session_state.user = user; st.rerun()
                    else:
                        st.error("Galat Username/Password! Pehle Sign Up karo")
        with tab2:
            name = st.text_input("Full Name", placeholder="Kadiya Naresh", key="s_name")
            username = st.text_input("Choose Username", placeholder="naresh123", key="s_user")
            email = st.text_input("Email", placeholder="naresh@gmail.com", key="s_email")
            pwd = st.text_input("Create Password", type="password", placeholder="Min 4 characters", key="s_pwd")
            if st.button("✨ Create My Account", use_container_width=True):
                if len(username) < 3 or len(pwd) < 4:
                    st.error("Username min 3 aur Password min 4 char")
                elif not name:
                    st.error("Name dalo")
                else:
                    ok, msg = signup_user(username, pwd, name, email)
                    if ok: st.success(msg + " Ab Login karo!"); st.balloons()
                    else: st.error(msg)
    return False

if not auth_ui():
    st.stop()

user = get_user_by_id(st.session_state.user['id'])
if not user:
    st.session_state.clear(); st.rerun()
st.session_state.user = user

# ================= SAFE IMPORT =================
try:
    from rag_utils import (process_files, ask_question, get_api_key, generate_quiz, generate_summary, predict_important_questions, check_quiz_answer, get_weak_topics, transcribe_audio, story_mode_learning, build_project_guide, generate_podcast_script, generate_viva_questions, verify_viva_answer, create_ppt_file, text_to_audio_file, images_to_pdf, images_to_docx)
    RAG_OK = True
except ImportError:
    from rag_utils import (process_files, ask_question, get_api_key, generate_quiz, generate_summary, predict_important_questions, check_quiz_answer, get_weak_topics, transcribe_audio, story_mode_learning, build_project_guide, generate_podcast_script, generate_viva_questions, verify_viva_answer, create_ppt_file, text_to_audio_file)
    RAG_OK = False
    def images_to_pdf(image_files):
        images = [Image.open(img).convert("RGB") for img in image_files]
        pdf_buffer = io.BytesIO()
        images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:]) if len(images)>1 else images[0].save(pdf_buffer, format="PDF")
        pdf_buffer.seek(0); return pdf_buffer
    def images_to_docx(image_files):
        doc = Document(); doc.add_heading('RAG Based AI Teaching Assistant', 0); doc_buffer = io.BytesIO()
        for img_file in image_files:
            image = Image.open(img_file); temp_buffer = io.BytesIO(); image.save(temp_buffer, format='PNG'); temp_buffer.seek(0); doc.add_picture(temp_buffer, width=Inches(5.5))
        doc.save(doc_buffer); doc_buffer.seek(0); return doc_buffer

st.set_page_config(page_title="RAG Based AI Teaching Assistant", layout="wide", page_icon="🎓")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&display=swap');
.main {background: #F8FAFF;}
.hero-pro {background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%); border-radius: 22px; padding: 24px 28px; color:white; position:relative; overflow:hidden;}
.hero-pro::after {content:''; position:absolute; top:-60%; right:-15%; width:380px; height:380px; background: rgba(255,255,255,0.15); border-radius:50%; filter: blur(35px);}
.dev-badge {position: fixed; bottom: 15px; right: 15px; background: #111827; color: white; padding: 8px 14px; border-radius: 20px; font-size: 11px; z-index: 999;}
.stButton>button {border-radius: 12px; height: 46px; font-weight: 600; transition: all 0.2s;}
.stButton>button:hover {transform: translateY(-1px); box-shadow: 0 8px 20px rgba(99,102,241,0.25);}
</style>
<div class="dev-badge">V18 PRODUCTION READY | KADIYA NARESH</div>
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
    if st.button(f"▶️ {lang} me Suno", key=f"play_{key}", type="primary"):
        with st.spinner("Audio bana raha hu..."):
            audio_path = text_to_audio_file(text, lang)
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 500:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                st.download_button(f"⬇️ Download MP3", audio_bytes, file_name=f"{key}_{lang}.mp3", mime="audio/mp3", key=f"dl_{key}")

with st.sidebar:
    st.markdown(f"""
    <div style="background:white; border-radius:16px; padding:16px; border:1px solid #EEF2FF; text-align:center;">
        <div style="font-size:40px;">🎓</div>
        <h3 style="margin:4px 0 0 0; font-family:Space Grotesk;">{user['name']}</h3>
        <p style="margin:0; color:#6B7280; font-size:12px;">@{user['username']}</p>
        <p style="margin:0; color:#9CA3AF; font-size:11px;">{user['email']}</p>
    </div>
    """, unsafe_allow_html=True)
    if user['photo'] and os.path.exists(user['photo']):
        st.image(user['photo'], use_container_width=True)
    c1,c2 = st.columns(2)
    with c1:
        if st.button("➕ New Chat", use_container_width=True): st.session_state.selected_conv=None; st.session_state.active="Ask"; st.rerun()
    with c2:
        if st.button("🚪 Logout", use_container_width=True): st.session_state.clear(); st.rerun()
    st.divider()
    st.markdown("### 📁 Knowledge Base")
    uploaded_files = st.file_uploader("PDF, CSV, TXT", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."): process_files(uploaded_files, 1000, 100)
            st.success("Done!"); save_conversation(user['id'], f"Uploaded {len(uploaded_files)} files", "Files processed", "Upload")
    st.divider()
    st.markdown("### 💬 Tumhari Chats - Click Karo")
    search = st.text_input("Search", placeholder="Search...", label_visibility="collapsed", key="search_chat")
    convs = get_user_conversations(user['id'])
    if not convs:
        st.caption("Koi chat nahi")
    else:
        for cid, q, a, mode, ts in convs[:40]:
            if search and search.lower() not in q.lower(): continue
            title = (q[:26] + "..") if len(q) > 26 else q
            if st.button(f"[{mode}] {title}", key=f"hist_{cid}", use_container_width=True):
                st.session_state.selected_conv = {"id": cid, "query": q, "answer": a, "mode": mode, "timestamp": ts}
                st.session_state.active = "ChatView"; st.rerun()
    st.divider()
    selected_language = st.selectbox("🌐 Language", ["Hinglish","Hindi","Gujarati","English"], index=0, key="glang")
    st.session_state.selected_language = selected_language
    st.caption(f"Active: {selected_language} | Chats: {len(convs)}")
    chunk_size, chunk_overlap, top_k = 1000, 100, 8

st.markdown(f"""
<div class="hero-pro">
    <h1 style="margin:0; font-family:Space Grotesk; font-size:28px;">Welcome {user['name'].split()[0]}! 👋</h1>
    <h2 style="margin:4px 0 0 0; font-family:Space Grotesk; font-size:20px; opacity:0.95;">RAG Based AI Teaching Assistant</h2>
    <p style="margin:8px 0 0 0; opacity:0.85; font-size:14px;">Total Chats: {len(convs)} | Ask, Viva, Quiz, Projects, Audio - All in One</p>
</div><br>
""", unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state: st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None; st.session_state.quiz_results = []

st.markdown("### ⚡ Quick Actions - Production Dashboard")
cols = st.columns(6)
for col, (label, act) in zip(cols, [("💬 Ask Q&A","Ask"), ("⭐ Important","Important"), ("🔧 Project","Projects"), ("📝 Quiz","Quiz"), ("🎤 Viva","Viva"), ("📊 PPT","PPT")]):
    with col:
        if st.button(label, use_container_width=True): st.session_state.active=act; st.rerun()
cols2 = st.columns(6)
for col, (label, act) in zip(cols2, [("📄 Summary","Summary"), ("📖 Story","Story"), ("🎙️ Podcast","Podcast"), ("🖼️ PDF Tool","Image2PDF"), ("👤 Profile","Profile"), ("🕘 History","History")]):
    with col:
        if st.button(label, use_container_width=True): st.session_state.active=act; st.rerun()
st.divider()

active = st.session_state.active
lang = st.session_state.get('selected_language','Hinglish')
st.subheader(f"▶ {active} | 🌐 {lang}")

if active=="ChatView":
    conv = st.session_state.get("selected_conv")
    if not conv: st.info("Sidebar se chat select karo")
    else:
        st.markdown(f"#### {conv['mode']} | {conv['timestamp'][:16]}")
        st.markdown(f"**Q:** {conv['query']}")
        st.divider(); st.markdown(conv['answer']); play_audio_block(conv['answer'], lang, f"hist_{conv['id']}")
        if st.button("⬅️ Back"): st.session_state.active="Ask"; st.rerun()
elif active=="Profile":
    c1,c2 = st.columns([1,2])
    with c1:
        if user['photo'] and os.path.exists(user['photo']): st.image(user['photo'], width=220)
        else: st.markdown("### No Photo")
        new_photo = st.file_uploader("Photo Add / Badlo", type=["jpg","png","jpeg"], key="photo_up")
    with c2:
        new_name = st.text_input("Name", value=user['name']); new_email = st.text_input("Email", value=user['email'])
        new_bio = st.text_area("Bio", value=user['bio'] if user['bio'] else "", placeholder="I am a student...")
        if st.button("Update Profile", type="primary"):
            update_profile(user['id'], new_name, new_email, new_bio, new_photo); st.success("Updated! Profile me photo dikhegi"); st.rerun()
    st.divider(); st.write(f"**Username:** {user['username']} | **Total Chats:** {len(get_user_conversations(user['id']))}")
elif active=="History":
    convs = get_user_conversations(user['id'])
    st.metric("Total Conversations", len(convs))
    for cid, q, a, mode, ts in convs:
        with st.expander(f"[{mode}] {q[:60]} - {ts[:16]}"): st.markdown(f"**Q:** {q}"); st.markdown(a)
elif active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True); sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask",f"Sawal bolo ({lang} me)...")
    if st.button("Ask Question", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel, language=lang)
            st.session_state.last_ask = ans; save_conversation(user['id'], q, ans, f"Ask-{sel}"); st.markdown(ans)
            with st.expander("📚 Source"): st.write(src)
    if "last_ask" in st.session_state: play_audio_block(st.session_state.last_ask, lang, "ask")
elif active=="Important":
    if st.button(f"Generate Important Qs in {lang}",type="primary"):
        imp = predict_important_questions(language=lang); st.session_state.last_imp = imp; save_conversation(user['id'], f"Important Qs {lang}", imp, "Important"); st.markdown(imp)
    if "last_imp" in st.session_state: play_audio_block(st.session_state.last_imp, lang, "imp")
elif active=="Summary":
    if st.button(f"Generate Summary in {lang}",type="primary"):
        summ = generate_summary(language=lang); st.session_state.last_summ = summ; save_conversation(user['id'], f"Summary {lang}", summ, "Summary"); st.markdown(summ)
    if "last_summ" in st.session_state: play_audio_block(st.session_state.last_summ, lang, "summ")
elif active=="Story":
    tp=universal_input("story",f"Topic in {lang}")
    if st.button("🎬 Create Story",type="primary") and tp:
        story_text = story_mode_learning(tp, language=lang); st.session_state.last_story = story_text; save_conversation(user['id'], tp, story_text, "Story"); st.markdown(story_text)
    if "last_story" in st.session_state: play_audio_block(st.session_state.last_story, lang, "story")
elif active=="Projects":
    idea=universal_input("proj",f"Project idea ({lang})"); bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("Generate Guide",type="primary") and idea:
        guide = build_project_guide(idea,bud, language=lang); st.session_state.last_proj = guide; save_conversation(user['id'], idea, guide, "Project"); st.markdown(guide)
    if "last_proj" in st.session_state: play_audio_block(st.session_state.last_proj, lang, "proj")
elif active=="Podcast":
    tp=universal_input("pod",f"Topic for Podcast in {lang}")
    if st.button("🎙️ Create Podcast",type="primary") and tp:
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
            if st.button("📄 PDF Convert", type="primary", use_container_width=True):
                pdf_data = images_to_pdf(uploaded_images); st.session_state.pdf_ready = pdf_data; st.success("PDF Ready!")
        with c2:
            if st.button("📝 DOCX Convert", type="primary", use_container_width=True):
                docx_data = images_to_docx(uploaded_images); st.session_state.docx_ready = docx_data; st.success("DOCX Ready!")
        if "pdf_ready" in st.session_state: st.download_button("⬇️ Download PDF", st.session_state.pdf_ready, file_name="RAG_Teaching_Images.pdf", mime="application/pdf", use_container_width=True)
        if "docx_ready" in st.session_state: st.download_button("⬇️ Download DOCX", st.session_state.docx_ready, file_name="RAG_Teaching_Images.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,15,5)
    if st.button("Generate Quiz", type="primary"):
        quiz_list = generate_quiz(n, language=lang); st.session_state.quiz_data = quiz_list; st.session_state.quiz_results = []; st.rerun()
    if st.session_state.quiz_data:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"**Q{i+1}. {qd['question']}**")
                choice = st.radio(f"Select {i}", qd['options'], key=f"quiz_{i}", label_visibility="collapsed")
                if st.button(f"Check Q{i+1}", key=f"chk_{i}"):
                    ok, fb = check_quiz_answer(qd['question'], choice, qd['answer'], qd.get('topic','general'))
                    st.session_state.quiz_results.append({"is_correct": ok}); st.success(fb) if ok else st.error(fb)
        if st.session_state.quiz_results:
            st.divider(); st.metric("Score", f"{sum(1 for r in st.session_state.quiz_results if r['is_correct'])}/{len(st.session_state.quiz_results)}")
elif active=="Viva":
    topic=universal_input("viva_topic",f"Viva topic ({lang})"); num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva",type="primary") and topic:
        qs=generate_viva_questions(topic,num, language=lang); st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]; st.subheader(f"Q{idx+1}: {curr['q']}")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer in {lang}")
            if st.button("Submit", key=f"v_sub_{idx}") and user_ans:
                res=verify_viva_answer(curr['q'], curr['a'], user_ans, language=lang)
                is_correct = "true" in str(res.get('verdict','')).lower()
                st.session_state.viva_score.append({"is_correct": is_correct}); st.success(res.get('feedback','')) if is_correct else st.error(res.get('feedback',''))
                st.session_state.viva_idx+=1; st.rerun()
        else:
            st.balloons(); st.success(f"Viva Done! Score: {sum(1 for s in st.session_state.viva_score if s['is_correct'])}/{len(st.session_state.viva_score)}")
elif active=="PPT":
    topic=universal_input("ppt",f"Topic in {lang}"); pages=st.slider("Slides?",5,25,10)
    if st.button("Create PPT",type="primary") and topic:
        ppt_path=create_ppt_file(topic, pages, language=lang)
        with open(ppt_path,"rb") as f: st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{lang}.pptx")
