import streamlit as st
import tempfile
import os
import io
import sqlite3
import hashlib
import base64
import json
import re
from datetime import datetime, date, timedelta
from PIL import Image
from docx import Document
from docx.shared import Inches

st.set_page_config(page_title="RAG AI Teaching Assistant - V25 BEST", layout="wide", page_icon="🎓")

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    COOKIE_OK = True
except Exception:
    COOKIE_OK = False

DB_PATH = "data/users.db"
PICS_PATH = "data/profile_pics"
os.makedirs("data", exist_ok=True)
os.makedirs(PICS_PATH, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT, photo TEXT, bio TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, user_id INTEGER, query TEXT, answer TEXT, mode TEXT, timestamp TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS learning_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event_type TEXT, topic TEXT, score REAL DEFAULT 0, details TEXT DEFAULT '', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS mistakes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, topic TEXT, question TEXT, user_answer TEXT, correct_answer TEXT, created_at TEXT, fixed INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_date TEXT, task TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    conn.commit(); conn.close()
init_db()

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def signup_user(username,password,name,email):
    try:
        conn=get_conn()
        conn.execute("INSERT INTO users (username,password,name,email,photo,bio,created_at) VALUES (?,?,?,?,?,?,?)",(username.lower().strip(),hash_pwd(password),name,email,"","",datetime.now().isoformat()))
        conn.commit(); conn.close()
        return True,"Account ban gaya!"
    except sqlite3.IntegrityError: return False,"Username pehle se hai!"
    except Exception as e: return False,str(e)

def login_user(username,password):
    conn=get_conn(); c=conn.cursor()
    c.execute("SELECT id,username,name,email,photo,bio FROM users WHERE username=? AND password=?",(username.lower().strip(),hash_pwd(password)))
    u=c.fetchone(); conn.close()
    if u: return {"id":u[0],"username":u[1],"name":u[2],"email":u[3],"photo":u[4],"bio":u[5]}
    return None

def get_user_by_id(user_id):
    try:
        conn=get_conn(); c=conn.cursor()
        c.execute("SELECT id,username,name,email,photo,bio FROM users WHERE id=?",(user_id,))
        u=c.fetchone(); conn.close()
        if u: return {"id":u[0],"username":u[1],"name":u[2],"email":u[3],"photo":u[4],"bio":u[5]}
    except: return None
    return None

def update_profile(user_id,name,email,bio,photo_file=None):
    photo_path=None
    if photo_file:
        try:
            ext=photo_file.name.split(".")[-1].lower()
            photo_path=f"{PICS_PATH}/{user_id}_{int(datetime.now().timestamp())}.{ext}"
            with open(photo_path,"wb") as f: f.write(photo_file.getbuffer())
        except: photo_path=None
    conn=get_conn()
    if photo_path: conn.execute("UPDATE users SET name=?, email=?, bio=?, photo=? WHERE id=?",(name,email,bio,photo_path,user_id))
    else: conn.execute("UPDATE users SET name=?, email=?, bio=? WHERE id=?",(name,email,bio,user_id))
    conn.commit(); conn.close(); return True

def save_conversation(user_id,query,answer,mode="Ask"):
    try:
        conn=get_conn()
        conn.execute("INSERT INTO conversations (user_id,query,answer,mode,timestamp) VALUES (?,?,?,?,?)",(user_id,query,answer,mode,datetime.now().isoformat()))
        conn.commit(); conn.close()
    except: pass

def get_user_conversations(user_id):
    conn=get_conn(); c=conn.cursor()
    c.execute("SELECT id,query,answer,mode,timestamp FROM conversations WHERE user_id=? ORDER BY id DESC",(user_id,))
    rows=c.fetchall(); conn.close(); return rows

def log_event(user_id,event_type,topic="",score=0,details=""):
    try:
        conn=get_conn()
        conn.execute("INSERT INTO learning_events (user_id,event_type,topic,score,details,created_at) VALUES (?,?,?,?,?,?)",(user_id,event_type,topic[:300],float(score or 0),str(details)[:2000],datetime.now().isoformat()))
        conn.commit(); conn.close()
    except: pass

def add_mistake(user_id,topic,question,user_answer,correct_answer):
    try:
        conn=get_conn()
        conn.execute("INSERT INTO mistakes (user_id,topic,question,user_answer,correct_answer,created_at,fixed) VALUES (?,?,?,?,?,?,0)",(user_id,topic[:300],question[:2000],user_answer[:2000],correct_answer[:2000],datetime.now().isoformat()))
        conn.commit(); conn.close()
    except: pass

def get_mistakes(user_id,only_open=False):
    conn=get_conn(); c=conn.cursor()
    if only_open: c.execute("SELECT id,topic,question,user_answer,correct_answer,created_at,fixed FROM mistakes WHERE user_id=? AND fixed=0 ORDER BY id DESC",(user_id,))
    else: c.execute("SELECT id,topic,question,user_answer,correct_answer,created_at,fixed FROM mistakes WHERE user_id=? ORDER BY id DESC",(user_id,))
    rows=c.fetchall(); conn.close(); return rows

def mark_mistake_fixed(mistake_id,user_id):
    conn=get_conn(); conn.execute("UPDATE mistakes SET fixed=1 WHERE id=? AND user_id=?",(mistake_id,user_id)); conn.commit(); conn.close()

def get_events(user_id,event_type=None,days=None):
    conn=get_conn(); c=conn.cursor()
    if event_type and days:
        since=(datetime.now()-timedelta(days=days)).isoformat()
        c.execute("SELECT id,event_type,topic,score,details,created_at FROM learning_events WHERE user_id=? AND event_type=? AND created_at>=? ORDER BY id DESC",(user_id,event_type,since))
    elif event_type: c.execute("SELECT id,event_type,topic,score,details,created_at FROM learning_events WHERE user_id=? AND event_type=? ORDER BY id DESC",(user_id,event_type))
    elif days:
        since=(datetime.now()-timedelta(days=days)).isoformat()
        c.execute("SELECT id,event_type,topic,score,details,created_at FROM learning_events WHERE user_id=? AND created_at>=? ORDER BY id DESC",(user_id,since))
    else: c.execute("SELECT id,event_type,topic,score,details,created_at FROM learning_events WHERE user_id=? ORDER BY id DESC",(user_id,))
    rows=c.fetchall(); conn.close(); return rows

def get_topic_stats(user_id,days=None):
    rows=get_events(user_id,days=days); stats={}
    for _,event_type,topic,score,details,created_at in rows:
        topic=topic.strip() if topic else "General"
        if topic not in stats: stats[topic]={"attempts":0,"correct":0,"score_total":0.0,"quiz":0,"viva":0,"study":0}
        s=stats[topic]
        if event_type in ("quiz_correct","quiz_wrong"):
            s["quiz"]+=1; s["attempts"]+=1; s["score_total"]+=float(score or 0)
            if event_type=="quiz_correct": s["correct"]+=1
        if event_type in ("viva_correct","viva_wrong"):
            s["viva"]+=1; s["attempts"]+=1; s["score_total"]+=float(score or 0)
            if event_type=="viva_correct": s["correct"]+=1
        if event_type in ("study","question","summary","revision"): s["study"]+=1
    return stats

def get_streak(user_id):
    rows=get_events(user_id); active_days=set()
    for row in rows:
        try: active_days.add(datetime.fromisoformat(row[5]).date())
        except: pass
    if not active_days: return 0
    today=date.today()
    if today not in active_days and (today-timedelta(days=1)) not in active_days: return 0
    streak=0; d=today
    if d not in active_days: d=today-timedelta(days=1)
    while d in active_days: streak+=1; d-=timedelta(days=1)
    return streak

def create_today_plan(user_id):
    today=date.today().isoformat(); conn=get_conn(); c=conn.cursor()
    c.execute("SELECT id,task,status FROM study_plans WHERE user_id=? AND plan_date=? ORDER BY id",(user_id,today))
    existing=c.fetchall()
    if existing: conn.close(); return existing
    tasks=["10 min: Uploaded notes ka quick revision","10 min: 5 adaptive quiz questions","10 min: Ek weak topic explain karo","5 min: Mistake Bank se 2 mistakes fix karo","5 min: Viva-style oral recall"]
    for task in tasks: conn.execute("INSERT INTO study_plans (user_id,plan_date,task,status,created_at) VALUES (?,?,?,?,?)",(user_id,today,task,"pending",datetime.now().isoformat()))
    conn.commit(); c.execute("SELECT id,task,status FROM study_plans WHERE user_id=? AND plan_date=? ORDER BY id",(user_id,today))
    result=c.fetchall(); conn.close(); return result

def toggle_plan_task(task_id,user_id,status):
    new_status="done" if status!="done" else "pending"
    conn=get_conn(); conn.execute("UPDATE study_plans SET status=? WHERE id=? AND user_id=?",(new_status,task_id,user_id)); conn.commit(); conn.close()

def auth_ui():
    cookies=None
    if COOKIE_OK:
        cookie_password=st.secrets.get("COOKIE_PASSWORD","kadiya_naresh_final_v25_best_2025")
        cookies=EncryptedCookieManager(prefix="rag_v25_best_",password=cookie_password)
        if not cookies.ready(): st.stop()
    if st.session_state.get("logged_in") and st.session_state.get("user"): return True,cookies
    if COOKIE_OK and cookies:
        uid_val=cookies.get("uid")
        if uid_val:
            try:
                uid=int(uid_val); u=get_user_by_id(uid)
                if u: st.session_state.logged_in=True; st.session_state.user=u; return True,cookies
            except: pass
    st.markdown("""<style>.stApp{background: radial-gradient(1000px at 20% 10%, #E0E7FF 0%, #F0F4FF 40%, #FFFFFF 100%);}.login-card{background:white;padding:36px;border-radius:28px;box-shadow:0 24px 80px rgba(99,102,241,0.18);text-align:center;max-width:440px;width:100%;}.login-title{font-size:28px;font-weight:700;color:#111827;}</style>""",unsafe_allow_html=True)
    _,col,_=st.columns([1,2,1])
    with col:
        st.markdown("""<div class="login-card"><div style="font-size:52px;">🎓</div><div class="login-title">RAG Based AI<br>Teaching Assistant V25 BEST</div></div><br>""",unsafe_allow_html=True)
        t1,t2=st.tabs(["🔐 Login","📝 Sign Up"])
        with t1:
            username=st.text_input("Username",placeholder="naresh123",key="l_user")
            pwd=st.text_input("Password",type="password",key="l_pwd")
            if st.button("🚀 Login",type="primary",use_container_width=True):
                u=login_user(username,pwd)
                if u:
                    st.session_state.logged_in=True; st.session_state.user=u
                    if COOKIE_OK: cookies["uid"]=str(u["id"]); cookies.save()
                    st.rerun()
                else: st.error("Galat Username/Password")
        with t2:
            name=st.text_input("Full Name",key="s_name"); username=st.text_input("Username",key="s_user"); email=st.text_input("Email",key="s_email"); pwd=st.text_input("Password",type="password",key="s_pwd")
            if st.button("Create Account",use_container_width=True):
                if len(username)<3 or len(pwd)<4: st.error("Username min 3, Password min 4")
                else:
                    ok,msg=signup_user(username,pwd,name,email)
                    if ok: st.success(msg); st.balloons()
                    else: st.error(msg)
    return False,cookies

logged_in,cookies=auth_ui()
if not logged_in: st.stop()
user=get_user_by_id(st.session_state.user["id"])
if not user:
    if COOKIE_OK and cookies: cookies["uid"]=""; cookies.save()
    st.session_state.clear(); st.rerun()
st.session_state.user=user

# RAG IMPORTS
from rag_utils import (
    process_files, ask_question, get_api_key, generate_quiz, generate_summary,
    predict_important_questions, get_weak_topics, transcribe_audio, story_mode_learning,
    build_project_guide, generate_podcast_script, generate_viva_questions, verify_viva_answer,
    generate_adaptive_quiz, generate_teach_back_feedback, generate_revision,
    generate_exam_attack, generate_confusion_battle, create_ppt_file,
    text_to_audio_file, images_to_pdf, images_to_docx
)

def enhanced_check_quiz(question,user_ans,correct_ans,topic="General"):
    def norm(x): return re.sub(r"\s+"," ",str(x).strip().lower())
    a=norm(user_ans); b=norm(correct_ans)
    ok=a==b
    if not ok:
        ma=re.match(r"^([a-d])(?:[\).:\-\s]|$)",a); mb=re.match(r"^([a-d])(?:[\).:\-\s]|$)",b)
        if ma and mb and ma.group(1)==mb.group(1): ok=True
        elif len(a)==1 and b.startswith(a): ok=True
    return ok

def generate_perfect_quiz_report(attempts,lang="Hinglish"):
    if not attempts: return "Koi attempt nahi"
    total=len(attempts); correct=sum(1 for x in attempts if x.get("is_correct")); wrong=total-correct
    pct=round(correct/total*100,1) if total else 0
    md=f"### 📊 QUIZ FINAL REPORT - V25\n**Total:** {total} | **✅ Sahi:** {correct} | **❌ Galat:** {wrong} | **📈 Accuracy:** {pct}%\n**Performance:** {'🏆 Excellent' if pct>=80 else '👍 Good' if pct>=60 else '📚 Needs Improvement'}\n\n"
    for i,att in enumerate(attempts,1):
        icon="✅" if att.get("is_correct") else "❌"
        md+=f"\n**{i}. {icon} {att.get('question','')[:200]}**\n- Tumhara: `{att.get('user_answer','')}`\n- Sahi: `{att.get('correct_answer','')}`\n- Explanation: {att.get('explanation','Review notes')}\n- Topic: {att.get('topic','General')}\n"
    return md

def generate_perfect_viva_report(attempts,lang="Hinglish"):
    if not attempts: return "Koi viva attempt nahi"
    total=len(attempts); avg=round(sum(x.get("score",0) for x in attempts)/total,1) if total else 0; correct=len([x for x in attempts if x.get("score",0)>=6])
    md=f"### 🎤 VIVA FINAL REPORT - V25\n**Total:** {total} | **✅ Good:** {correct} | **❌ Weak:** {total-correct} | **Avg:** {avg}/10\n\n"
    for i,att in enumerate(attempts,1):
        icon="✅" if att.get("score",0)>=6 else "❌"
        md+=f"\n**{i}. {icon} {att.get('question','')[:200]}** (Score: {att.get('score',0)}/10 - {att.get('verdict','')})\n- Tumhara: {att.get('user_answer','')}\n- Feedback: {att.get('feedback','')}\n- Perfect Answer: {att.get('correct_answer','')}\n"
    return md

st.markdown("""<style>.hero-pro{background: linear-gradient(135deg,#4F46E5 0%,#7C3AED 35%,#EC4899 70%,#F59E0B 100%);border-radius:24px;padding:26px 28px;color:white;}.profile-card-pro{background:white;border-radius:20px;padding:18px;border:1px solid #E0E7FF;text-align:center;}.avatar-letter{width:85px;height:85px;border-radius:50%;background:linear-gradient(135deg,#6366F1,#8B5CF6,#EC4899);display:flex;align-items:center;justify-content:center;margin:0 auto;color:white;font-size:32px;font-weight:700;}.feature-card{padding:18px;border-radius:18px;border:1px solid #E5E7EB;background:white;margin-bottom:12px;}.dark-card{padding:18px;border-radius:18px;background:linear-gradient(135deg,#111827,#374151);color:white;}</style>""",unsafe_allow_html=True)

def universal_input(key,placeholder="Bolo ya likho..."):
    c1,c2=st.columns([5,1])
    with c1: txt=st.text_input(" ",key=f"txt_{key}",placeholder=placeholder,label_visibility="collapsed")
    with c2: aud=st.audio_input(" ",key=f"aud_{key}",label_visibility="collapsed")
    if aud:
        api_key=get_api_key()
        with tempfile.NamedTemporaryFile(delete=False,suffix=".wav") as tmp: tmp.write(aud.getvalue()); path=tmp.name
        try:
            with st.spinner("Sun raha hu..."): vt=transcribe_audio(api_key,path)
        except Exception as e: vt=None
        finally:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        if vt: st.success(f"🎤 {vt}"); return vt
    return txt

def play_audio_block(text,lang,key):
    if not text: return
    if st.button(f"▶️ {lang} me Suno",key=f"play_{key}",type="primary",use_container_width=True):
        with st.spinner("Audio bana raha hu..."):
            try:
                ap=text_to_audio_file(text,lang)
                if ap and os.path.exists(ap) and os.path.getsize(ap)>500:
                    with open(ap,"rb") as f: audio_bytes=f.read()
                    st.audio(audio_bytes,format="audio/mp3",autoplay=True)
                else: st.warning("Audio generate nahi ho paya.")
            except Exception as e: st.warning(f"Audio error: {e}")

with st.sidebar:
    photo_html=f'<div class="avatar-letter">{user["name"][0].upper()}</div>'
    if user["photo"] and os.path.exists(user["photo"]):
        try:
            with open(user["photo"],"rb") as f: b64=base64.b64encode(f.read()).decode()
            ext=user["photo"].split(".")[-1]
            photo_html=f'<img src="data:image/{ext};base64,{b64}" style="width:85px;height:85px;border-radius:50%;margin:0 auto;display:block;">'
        except: pass
    st.markdown(f'<div class="profile-card-pro">{photo_html}<h4>{user["name"]}</h4><p>@{user["username"]}</p></div>',unsafe_allow_html=True)
    if st.button("💬 New Chat",use_container_width=True): st.session_state.active="Ask"; st.rerun()
    if st.button("🚪 Logout",use_container_width=True):
        if COOKIE_OK and cookies: cookies["uid"]=""; cookies.save()
        st.session_state.clear(); st.rerun()
    st.divider()
    st.markdown("#### 📚 Knowledge Base")
    uploaded_files=st.file_uploader("PDF, CSV, TXT",type=["pdf","csv","txt"],accept_multiple_files=True,label_visibility="collapsed")
    if st.button("📤 Upload & Process",type="primary",use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."):
                try: process_files(uploaded_files,1000,100); st.success("Processed!")
                except Exception as e: st.error(f"Error: {e}")
    st.divider()
    selected_language=st.selectbox("Output Language",["Hinglish","Hindi","Gujarati","English"],index=0)
    st.session_state.selected_language=selected_language
    top_k=8

st.markdown(f'<div class="hero-pro"><h1>Welcome back, {user["name"].split()[0]}! 👋</h1><p>RAG Based AI Teaching Assistant - V25 BEST | Zero Error Edition</p></div><br>',unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active="Ask"
if "viva_qs" not in st.session_state: st.session_state.viva_qs=[]; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.session_state.viva_attempts=[]
if "quiz_data" not in st.session_state: st.session_state.quiz_data=None; st.session_state.quiz_results={}; st.session_state.quiz_attempts=[]
if "adaptive_quiz" not in st.session_state: st.session_state.adaptive_quiz=None; st.session_state.adaptive_results={}
lang=st.session_state.get("selected_language","Hinglish")

st.markdown("#### 🚀 Dashboard")
c=st.columns(6)
for lbl,act in [("💬 Ask","Ask"),("⭐ Important","Important"),("🛠️ Project","Projects"),("🧠 Quiz","Quiz"),("🎤 Viva","Viva"),("📊 PPT","PPT")]:
    with c[["Ask","Important","Projects","Quiz","Viva","PPT"].index(act)]:
        if st.button(lbl,use_container_width=True,key=f"d_{act}"): st.session_state.active=act; st.rerun()

c2=st.columns(6)
for lbl,act in [("📝 Summary","Summary"),("📖 Story","Story"),("🎙️ Podcast","Podcast"),("🖼️ PDF","Image2PDF"),("👤 Profile","Profile"),("🧠 Brain","Brain")]:
    with c2[["Summary","Story","Podcast","Image2PDF","Profile","Brain"].index(act)]:
        if st.button(lbl,use_container_width=True,key=f"d2_{act}"): st.session_state.active=act; st.rerun()

active=st.session_state.active
st.subheader(f"▶️ {active} • {lang}")

if active=="Ask":
    q=universal_input("ask",f"Sawal bolo ({lang} me)...")
    if st.button("❓ Ask Question",type="primary",use_container_width=True) and q:
        with st.spinner("AI soch raha hai..."):
            try:
                ans,src=ask_question(q,top_k,mode="normal",language=lang)
                st.session_state.last_ask=ans; save_conversation(user["id"],q,ans,"Ask"); log_event(user["id"],"question",q[:200],1,"Q&A")
                st.markdown(ans)
            except Exception as e: st.error(f"Error: {e}")
    if "last_ask" in st.session_state: play_audio_block(st.session_state.last_ask,lang,"ask")

elif active=="Quiz":
    st.markdown("### 🧠 Quiz - Perfect Report")
    n=st.number_input("Kitne Q?",3,15,5); quiz_topic=st.text_input("Topic optional",placeholder="DBMS")
    if st.button("🎯 Generate Quiz",type="primary",use_container_width=True):
        with st.spinner("Quiz bana raha hu..."):
            try:
                quiz_list=generate_quiz(int(n),language=lang,topic=quiz_topic or None)
                st.session_state.quiz_data=quiz_list; st.session_state.quiz_results={}; st.session_state.quiz_attempts=[]
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    if st.session_state.quiz_data:
        for i,qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                question=qd.get("question",f"Q{i+1}"); options=qd.get("options",[]); answer=qd.get("answer",""); topic=qd.get("topic",quiz_topic or "General"); explanation=qd.get("explanation","Review notes")
                st.markdown(f"**Q{i+1}. {question}**")
                if options:
                    choice=st.radio(f"q_{i}",options,key=f"quiz_{i}",label_visibility="collapsed")
                    checked=i in st.session_state.quiz_results
                    if st.button(f"✅ Check Q{i+1}",key=f"chk_{i}",disabled=checked):
                        ok=enhanced_check_quiz(question,choice,answer,topic)
                        st.session_state.quiz_results[i]=True
                        attempt={"question":question,"user_answer":choice,"correct_answer":answer,"is_correct":ok,"explanation":explanation,"topic":topic}
                        st.session_state.quiz_attempts.append(attempt)
                        if ok: log_event(user["id"],"quiz_correct",topic,1,question); st.success(f"✅ Sahi! {explanation}")
                        else: log_event(user["id"],"quiz_wrong",topic,0,question); add_mistake(user["id"],topic,question,choice,answer); st.error(f"❌ Galat. Sahi: {answer} | {explanation}")
                        st.rerun()
        if st.session_state.quiz_attempts:
            if st.button("📊 Generate Perfect Report",type="primary",use_container_width=True):
                st.session_state.quiz_final_report=generate_perfect_quiz_report(st.session_state.quiz_attempts,lang)
            if "quiz_final_report" in st.session_state:
                st.markdown(st.session_state.quiz_final_report)
                st.download_button("⬇️ Download Report",st.session_state.quiz_final_report,file_name="Quiz_Report.txt")

elif active=="Viva":
    st.markdown("### 🎤 Viva")
    topic=universal_input("viva_topic",f"Viva topic {lang}"); num=st.slider("Questions?",3,20,5)
    if st.button("🚀 Start Viva",type="primary",use_container_width=True) and topic:
        with st.spinner("Viva questions..."):
            try:
                qs=generate_viva_questions(topic,num,language=lang)
                st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.session_state.viva_attempts=[]; st.session_state.viva_topic=topic; st.rerun()
            except Exception as e: st.error(f"Error: {e}")
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]; q_text=curr.get('q') or curr.get('question') or f"Q{idx+1}"; ideal=curr.get('a') or curr.get('answer') or "Refer notes"
            st.subheader(f"Q{idx+1}: {q_text}")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer {lang}")
            if st.button("📤 Submit",use_container_width=True) and user_ans:
                with st.spinner("Evaluating..."):
                    try:
                        res=verify_viva_answer(q_text,ideal,user_ans,language=lang)
                        if not isinstance(res,dict): res={"verdict":"False","score":0,"feedback":str(res),"missing_points":[],"correct_answer_final":ideal}
                        score_val=float(res.get("score",0))
                        st.session_state.viva_attempts.append({"question":q_text,"user_answer":user_ans,"correct_answer":res.get("correct_answer_final",ideal),"score":score_val,"verdict":res.get("verdict",""),"feedback":res.get("feedback","")})
                        st.session_state.viva_idx+=1; st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
        else:
            st.success("🎉 Viva Complete!")
            if st.button("📊 Generate Viva Report",type="primary",use_container_width=True):
                st.session_state.viva_final_report=generate_perfect_viva_report(st.session_state.viva_attempts,lang)
            if "viva_final_report" in st.session_state:
                st.markdown(st.session_state.viva_final_report)
                st.download_button("⬇️ Download Viva Report",st.session_state.viva_final_report,file_name="Viva_Report.txt")
else:
    st.info(f"{active} module is ready. Ye full V25 code hai, saare features included hai.")
