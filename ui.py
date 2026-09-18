import streamlit as st
import tempfile
import os
from rag_utils import (
    process_files, ask_question, load_conversation_history, get_api_key,
    generate_quiz, generate_summary, predict_important_questions,
    check_quiz_answer, get_weak_topics, transcribe_audio,
    story_mode_learning, build_project_guide, generate_podcast_script,
    generate_viva_questions, verify_viva_answer, create_ppt_file,
    create_explainer_video, transcribe_topic_with_language
)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Advance RAG - AI Teaching Assistant", layout="wide", page_icon="🎓")

# --- PRODUCTION CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
.main {background-color: #F8F9FF;}
.dev-badge {position: fixed; bottom: 15px; right: 15px; background: #111; color: white; padding: 8px 14px; border-radius: 20px; font-size: 12px; z-index: 999; opacity: 0.8;}
.feature-card {background: white; border-radius: 16px; padding: 20px; border: 1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: all 0.2s; text-align: center;}
.feature-card:hover {box-shadow: 0 8px 20px rgba(99,102,241,0.15); border-color: #6366F1; transform: translateY(-2px);}
.hero {background: linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%); border-radius: 20px; padding: 30px; margin-bottom: 20px;}
.stButton>button {border-radius: 10px; height: 50px; font-weight: 600; border: 1px solid #E5E7EB;}
.stButton>button:hover {border-color: #6366F1; color: #6366F1;}
</style>
<div class="dev-badge">Production Build | Developer: KADIYA NARESH</div>
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

# --- SIDEBAR PRODUCTION ---
with st.sidebar:
    st.markdown("### 📁 File Upload")
    st.caption("PDF, DOCX, TXT, PPTX • Max 50MB")
    uploaded_files = st.file_uploader("Drag & drop your files here", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    st.markdown("")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."):
                process_files(uploaded_files, 1000, 100)
            st.success(f"{len(uploaded_files)} files ready!")
        else:
            st.warning("Pehle file select karo")
    st.divider()
    st.markdown("### 📊 Learning Analytics")
    weak = get_weak_topics()
    if weak:
        for t,c in sorted(weak.items(), key=lambda x:x[1], reverse=True)[:5]:
            st.write(f"🔴 {t}: {c} mistakes")
    else:
        st.info("Quiz do, weak topics yaha ayenge")
    st.divider()
    st.caption("Storage: Unlimited in FREE version")
    # Config hidden but working
    chunk_size, chunk_overlap, top_k = 1000, 100, 8

# --- HERO SECTION ---
st.markdown("""
<div class="hero">
    <h1 style="margin:0; font-size: 36px; color: #111827;">RAG Based AI Teaching Assistant</h1>
    <p style="color: #4B5563; font-size: 16px; margin-top:8px;">Ask anything, generate content, practice and learn with AI powered by your own documents. Secure, accurate, and context-aware learning.</p>
</div>
""", unsafe_allow_html=True)

# --- SESSION ---
if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []

# --- FEATURES GRID - PRODUCTION ---
st.markdown("### ✨ Features <span style='float:right; font-size:14px; color:#6B7280; font-weight:400;'>10 tools available - All FREE</span>", unsafe_allow_html=True)
st.markdown("")

# Row 1
c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    if st.button("💬 Ask Q&A\nInstant answers", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("⭐ Important Qs\nKey questions", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c3:
    if st.button("🔧 Project Builder\nStep-by-step", use_container_width=True): st.session_state.active="Projects"; st.rerun()
with c4:
    if st.button("🎬 AI Video\nEducational videos", use_container_width=True): st.session_state.active="Video"; st.rerun()
with c5:
    if st.button("📝 Quiz\nAuto quizzes", use_container_width=True): st.session_state.active="Quiz"; st.rerun()

# Row 2
c6,c7,c8,c9,c10 = st.columns(5)
with c6:
    if st.button("🎤 Viva Mode\nOral exam practice", use_container_width=True): st.session_state.active="Viva"; st.rerun()
with c7:
    if st.button("📊 PPT Maker\nSlides from content", use_container_width=True): st.session_state.active="PPT"; st.rerun()
with c8:
    if st.button("📄 Summary\nCondense material", use_container_width=True): st.session_state.active="Summary"; st.rerun()
with c9:
    if st.button("📖 Story Movie\nStory visuals", use_container_width=True): st.session_state.active="Story"; st.rerun()
with c10:
    if st.button("🎙️ Podcast\nAudio from notes", use_container_width=True): st.session_state.active="Podcast"; st.rerun()

st.divider()
active = st.session_state.active
st.header(f"▶ {active} Mode")

# --- ALL FEATURE LOGIC - SAME AS BEFORE (KUCH DELETE NAHI KIYA) ---
if active=="Ask":
    mode = st.radio("Answer Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask","Sawal bolo ya likho - What is IoT?")
    if st.button("Ask Question", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel)
            st.markdown(ans)
            with st.expander("📚 Source from PDF"): st.write(src)
elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,10,5)
    if st.button("Generate Quiz", type="primary"):
        qt,err = generate_quiz(n)
        st.error(err) if err else st.markdown(qt)
    st.divider()
    qq=universal_input("qq","Question")
    ua=universal_input("ua","Your answer")
    ca=st.text_input("Correct ans")
    tp=st.text_input("Topic","general")
    if st.button("Check Answer"):
        ok,fb=check_quiz_answer(qq,ua,ca,tp)
        st.success(fb) if ok else st.error(fb)
elif active=="Viva":
    st.info("PDF se auto questions one-by-one. 100% PDF based.")
    topic=universal_input("viva_topic","Viva topic - DBMS")
    num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva",type="primary"):
        if topic:
            with st.spinner("PDF se questions bana raha hu..."):
                qs=generate_viva_questions(topic,num)
                st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]
                st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]
            st.subheader(f"Q{idx+1}/{len(st.session_state.viva_qs)}: {curr['q']}")
            user_ans=universal_input(f"v_ans_{idx}","Answer bolo/likho")
            c1,c2=st.columns(2)
            with c1:
                if st.button("Submit Answer"):
                    if user_ans:
                        res=verify_viva_answer(curr['q'], curr['a'], user_ans)
                        is_true=res['verdict'].lower()=="true"
                        st.session_state.viva_score.append({"q":curr['q'],"your":user_ans,"correct":curr['a'],"result":"✅ Sahi" if is_true else "❌ Galat","fb":res['feedback']})
                        st.success(res['feedback']) if is_true else st.error(res['feedback'])
                        st.session_state.viva_idx+=1; st.rerun()
            with c2:
                if st.button("Stop & Show Result"):
                    st.session_state.viva_idx=len(st.session_state.viva_qs); st.rerun()
        else:
            score=st.session_state.viva_score
            true_c=sum(1 for x in score if "Sahi" in x['result']); false_c=len(score)-true_c
            st.success(f"Viva Khatam! ✅ Sahi: {true_c} | ❌ Galat: {false_c}")
            for i,s in enumerate(score):
                with st.expander(f"{i+1}. {s['q']} - {s['result']}"):
                    st.write(f"**Your:** {s['your']}"); st.write(f"**Correct:** {s['correct']}"); st.write(f"**Feedback:** {s['fb']}")
            if st.button("Start New Viva"):
                st.session_state.viva_qs=[]; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
elif active=="PPT":
    topic=universal_input("ppt","Topic - AI")
    pages=st.slider("Slides?",5,25,10)
    if st.button("Create PPT",type="primary"):
        if topic:
            with st.spinner(f"{pages} slides bana raha hu..."):
                ppt_path=create_ppt_file(topic, pages)
                with open(ppt_path,"rb") as f:
                    st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{pages}_slides.pptx")
                st.success("Ban gaya!")
elif active=="Video":
    st.info("V8 Accurate - PDF ke according. 2.5 MIN Video")
    col1, col2 = st.columns(2)
    with col1: lang = st.selectbox("Language", ["Hinglish", "Hindi", "English", "Marathi"])
    with col2: topic_text = st.text_input("Topic (jo PDF me hai)", placeholder="e.g. Deadlock in OS")
    st.write("Ya Voice me bolo:")
    audio_val = st.audio_input("🎤 Topic bolo", key="vid_audio")
    final_topic = topic_text; final_lang = lang
    if audio_val:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_val.getvalue()); ap = tmp.name
        with st.spinner("Voice sun raha hu..."):
            t, l = transcribe_topic_with_language(ap)
            if os.path.exists(ap): os.remove(ap)
            if t: final_topic = t; final_lang = l; st.success(f"🎧 Topic = {t} | Language = {l}")
    if st.button("🚀 Generate 2.5 MIN Video", type="primary"):
        if not final_topic: st.warning("Topic likho ya bolo!")
        else:
            with st.spinner(f"{final_topic} pe {final_lang} me video bana raha hu..."):
                try:
                    v_path, scenes = create_explainer_video(final_topic, final_lang, duration_sec=150)
                    if v_path and os.path.exists(v_path):
                        st.success("VIDEO BAN GAYA!"); st.video(v_path)
                        with open(v_path, "rb") as f:
                            st.download_button("⬇️ Download Video", f, file_name=f"{final_topic}_{final_lang}.mp4")
                    else: st.error(f"❌ {scenes}")
                except Exception as e:
                    st.error(f"Error: {e}"); import traceback; st.code(traceback.format_exc())
elif active=="Story":
    tp=universal_input("story","Topic - Stack")
    if st.button("Create Movie",type="primary") and tp: st.markdown(story_mode_learning(tp))
elif active=="Projects":
    idea=universal_input("proj","Project idea - Smart Dustbin")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("Generate Guide",type="primary") and idea: st.markdown(build_project_guide(idea,bud))
elif active=="Podcast":
    tp=universal_input("pod","Topic for Podcast")
    if st.button("Create Podcast Script",type="primary") and tp: st.markdown(generate_podcast_script(tp))
elif active=="Summary":
    if st.button("Generate Summary",type="primary"): st.markdown(generate_summary())
elif active=="Important":
    if st.button("Predict Important Qs",type="primary"): st.markdown(predict_important_questions())

with st.expander("🕘 Conversation History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}"); st.markdown(x['answer'][:500]); st.divider()
