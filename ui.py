import streamlit as st
import tempfile
import os
from rag_utils import (
    process_files, ask_question, load_conversation_history, get_api_key,
    generate_quiz, generate_summary, predict_important_questions,
    text_to_speech, check_quiz_answer, get_weak_topics, transcribe_audio,
    generate_ppt_slides, generate_lab_manual, generate_podcast_script,
    story_mode_learning, build_project_guide, real_life_example,
    generate_flashcards, make_study_plan, viva_simulator, viva_followup,
    get_mentor_report, analyze_pyq
)

st.set_page_config(page_title="Advance RAG", layout="wide")
st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

def universal_input(key, placeholder="Bolo ya likho..."):
    c1,c2 = st.columns([4,1])
    with c1:
        txt = st.text_input(" ", key=f"txt_{key}", placeholder=placeholder, label_visibility="collapsed")
    with c2:
        aud = st.audio_input("🎤", key=f"aud_{key}", label_visibility="collapsed")
    if aud:
        api_key = get_api_key()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(aud.getvalue())
            path = tmp.name
        with st.spinner("Sun raha hu..."):
            vt = transcribe_audio(api_key, path)
        os.remove(path)
        if vt:
            st.success(f"🎧 {vt}")
            return vt
    return txt

st.sidebar.header("Configuration")
uploaded_files = st.sidebar.file_uploader("Upload PDF/CSV/TXT", type=["pdf","csv","txt"], accept_multiple_files=True)
chunk_size = st.sidebar.number_input("Chunk Size", 200, 2000, 1000, 100)
chunk_overlap = st.sidebar.number_input("Chunk Overlap", 0, 500, 100, 10)
top_k = st.sidebar.number_input("Docs to Retrieve", 1, 10, 3)
if st.sidebar.button("Submit & Process"):
    if uploaded_files:
        process_files(uploaded_files, chunk_size, chunk_overlap)
    else:
        st.warning("Upload karo pehle.")
st.sidebar.divider()
weak = get_weak_topics()
st.sidebar.subheader("📊 Weak Topics")
if weak:
    for t,c in sorted(weak.items(), key=lambda x:x[1], reverse=True):
        st.sidebar.write(f"- {t}: {c}")
else:
    st.sidebar.info("Quiz do!")

if "active" not in st.session_state:
    st.session_state.active = "Ask"

st.title("RAG Based AI Teaching Assistant")
st.caption("Har feature me Type + Voice dono hai")
st.subheader("📦 Features")

c1,c2,c3,c4 = st.columns(4)
with c1:
    if st.button("⌨️ Ask\nQ&A", use_container_width=True):
        st.session_state.active="Ask"
        st.rerun()
    if st.button("📝 Quiz\nMCQ", use_container_width=True):
        st.session_state.active="Quiz"
        st.rerun()
    if st.button("📄 Summary", use_container_width=True):
        st.session_state.active="Summary"
        st.rerun()
with c2:
    if st.button("⭐ Important Qs", use_container_width=True):
        st.session_state.active="Important"
        st.rerun()
    if st.button("📊 PYQ Analyzer", use_container_width=True):
        st.session_state.active="PYQ"
        st.rerun()
    if st.button("🎤 Viva Mode", use_container_width=True):
        st.session_state.active="Viva"
        st.rerun()
with c3:
    if st.button("💡 Example + Cards", use_container_width=True):
        st.session_state.active="Example"
        st.rerun()
    if st.button("🧠 AI Mentor", use_container_width=True):
        st.session_state.active="Mentor"
        st.rerun()
    if st.button("📖 Story Movie", use_container_width=True):
        st.session_state.active="Story"
        st.rerun()
with c4:
    if st.button("🔧 Project Builder", use_container_width=True):
        st.session_state.active="Projects"
        st.rerun()
    if st.button("📊 PPT Maker", use_container_width=True):
        st.session_state.active="PPT"
        st.rerun()
    if st.button("🔬 Lab Manual", use_container_width=True):
        st.session_state.active="Lab"
        st.rerun()
    if st.button("🎙️ Podcast", use_container_width=True):
        st.session_state.active="Podcast"
        st.rerun()

st.divider()
active = st.session_state.active
st.header(f"▶ {active}")

if active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask","Sawal bolo ya likho - What is IoT?")
    if st.button("Ask", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel)
            st.markdown(ans)
            ap=text_to_speech(ans)
            if ap:
                st.audio(ap)

elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,10,5)
    if st.button("Quiz Banao"):
        qt,err = generate_quiz(n)
        if err:
            st.error(err)
        else:
            st.markdown(qt)
    st.divider()
    qq=universal_input("qq","Question bolo/likho")
    ua=universal_input("ua","Tumhara answer")
    ca=st.text_input("Correct ans")
    tp=st.text_input("Topic","general")
    if st.button("Check Karo"):
        ok,fb=check_quiz_answer(qq,ua,ca,tp)
        if ok:
            st.success(fb)
        else:
            st.error(fb)

elif active=="Story":
    tp=universal_input("story","Topic bolo - jaise Stack")
    if st.button("🎬 Movie Banao",type="primary"):
        if tp:
            s=story_mode_learning(tp)
            st.markdown(s)
            ap=text_to_speech(s)
            if ap:
                st.audio(ap)

elif active=="Example":
    conc=universal_input("ex","Concept bolo - DBMS")
    if st.button("Example se Samjhao"):
        if conc:
            st.markdown(real_life_example(conc))
    if st.button("Flashcards Banao"):
        st.markdown(generate_flashcards())
    ed=st.date_input("Exam kab?")
    hr=st.number_input("Ghante?",1,12,4)
    if st.button("Plan Banao"):
        st.markdown(make_study_plan(str(ed),hr))

elif active=="Viva":
    if "vq" not in st.session_state:
        st.session_state.vq=""
    tp=universal_input("viva","Viva topic bolo")
    if st.button("Viva Start"):
        if tp:
            st.session_state.vq=viva_simulator(tp)
            st.rerun()
    if st.session_state.vq:
        st.info(st.session_state.vq)
        a=universal_input("viva_ans","Jawab bolo/likho")
        if st.button("Submit"):
            st.session_state.vq=viva_followup(st.session_state.vq,a)
            st.rerun()

elif active=="Projects":
    idea=universal_input("proj","Project idea bolo - Smart Dustbin")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("🚀 Guide Banao",type="primary"):
        if idea:
            st.markdown(build_project_guide(idea,bud))

elif active=="PPT":
    tp=universal_input("ppt","Topic bolo - PPT ke liye")
    if st.button("📊 PPT Banao",type="primary"):
        if tp:
            st.markdown(generate_ppt_slides(tp))

elif active=="Lab":
    tp=universal_input("lab","Experiment bolo - Ultrasonic Sensor")
    if st.button("🔬 Manual Banao",type="primary"):
        if tp:
            st.markdown(generate_lab_manual(tp))

elif active=="Podcast":
    tp=universal_input("pod","Topic bolo - Podcast ke liye")
    if st.button("🎙️ Podcast Script Banao",type="primary"):
        if tp:
            script=generate_podcast_script(tp)
            st.markdown(script)
            ap=text_to_speech(script)
            if ap:
                st.audio(ap)

elif active=="Summary":
    if st.button("Summary Banao",type="primary"):
        st.markdown(generate_summary())
elif active=="Important":
    if st.button("Predict Karo",type="primary"):
        st.markdown(predict_important_questions())
elif active=="PYQ":
    fs=st.file_uploader("PYQ PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Analyze Karo",type="primary"):
        if fs:
            st.markdown(analyze_pyq(fs))
elif active=="Mentor":
    if st.button("📈 Report Banao",type="primary"):
        st.markdown(get_mentor_report())

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}")
        st.markdown(x['answer'][:500])
        st.divider()
