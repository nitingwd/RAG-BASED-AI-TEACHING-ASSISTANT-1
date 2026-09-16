Perfect! Tumne jo `ui.py` bheja usi me ab maine *har feature me Text + Voice* daal diya hai. Ek hi function `universal_input()` se sab ho raha hai.

Ye lo final `ui.py` - copy karke replace kar do:
import streamlit as st
import tempfile, os
from rag_utils import (
    process_files, ask_question, load_conversation_history, get_api_key,
    generate_quiz, generate_summary, predict_important_questions,
    text_to_speech, check_quiz_answer, get_weak_topics, transcribe_audio
)

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; color: white; font-size: 14px; font-weight: bold; z-index: 999;}
.rect-btn button {height: 110px!important; border-radius: 15px!important; font-size: 16px!important; font-weight: bold!important; border: none!important; color: white!important; box-shadow: 0 4px 12px rgba(0,0,0,0.2)!important;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

# ---- UNIVERSAL TEXT + VOICE INPUT ----
def universal_input(key, placeholder="Topic bolo ya likho..."):
    st.write("⌨️ Type karo ya 🎤 Bolo")
    c1, c2 = st.columns([3,1])
    with c1:
        txt = st.text_input(placeholder, key=f"txt_{key}", label_visibility="collapsed", placeholder=placeholder)
    with c2:
        aud = st.audio_input("🎤", key=f"aud_{key}", label_visibility="collapsed")

    if aud:
        api_key = get_api_key()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(aud.getvalue())
            path = tmp.name
        with st.spinner("Voice samajh raha hu..."):
            voice_text = transcribe_audio(api_key, path)
        os.remove(path)
        if voice_text:
            st.success(f"🎧 Suna: {voice_text}")
            return voice_text
    return txt

# Sidebar
st.sidebar.header("Configuration")
uploaded_files = st.sidebar.file_uploader("Upload documents", type=["pdf","csv","txt"], accept_multiple_files=True)
chunk_size = st.sidebar.number_input("Chunk Size", 200, 2000, 1000, 100)
chunk_overlap = st.sidebar.number_input("Chunk Overlap", 0, 500, 100, 10)
top_k = st.sidebar.number_input("Documents to Retrieve", 1, 10, 3)
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
        st.sidebar.markdown(f"- **{t}**: {c} baar galat")
else:
    st.sidebar.info("Quiz do!")

if "active" not in st.session_state:
    st.session_state.active = "Ask"

st.title("RAG Based AI Teaching Assistant")
st.subheader("📦 Features - Click to Open")

c1,c2,c3 = st.columns(3)
with c1:
    if st.button("⌨️ Ask\nSawal + Audio", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("📝 Quiz\nMCQ + Check", use_container_width=True): st.session_state.active="Quiz"; st.rerun()
with c3:
    if st.button("📄 Summary\n1-Page", use_container_width=True): st.session_state.active="Summary"; st.rerun()
c4,c5,c6 = st.columns(3)
with c4:
    if st.button("⭐ Important Qs", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c5:
    if st.button("📊 PYQ Analyzer", use_container_width=True): st.session_state.active="PYQ"; st.rerun()
with c6:
    if st.button("🎤 Viva Professor", use_container_width=True): st.session_state.active="Viva"; st.rerun()
c7,c8,c9 = st.columns(3)
with c7:
    if st.button("💡 Example + Flashcards", use_container_width=True): st.session_state.active="Example"; st.rerun()
with c8:
    if st.button("🧠 AI Mentor", use_container_width=True): st.session_state.active="Mentor"; st.rerun()
with c9:
    if st.button("📖 Story Mode Movie", use_container_width=True): st.session_state.active="Story"; st.rerun()
c10,_,_ = st.columns(3)
with c10:
    if st.button("🔧 Project Builder IoT", use_container_width=True): st.session_state.active="Projects"; st.rerun()

st.divider()
active = st.session_state.active
st.header(f"▶ {active}")

if active=="Ask":
    mode = st.radio("Mode:", ["Normal", "Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask", "Sawal likho ya bolo - jaise What is IoT?")
    if st.button("Ask", type="primary"):
        if q:
            ans, src = ask_question(q, top_k, mode=sel)
            st.markdown(ans)
            ap = text_to_speech(ans)
            if ap: st.audio(ap)

elif active=="Quiz":
    n = st.number_input("Kitne Q?", 3, 10, 5)
    if st.button("Quiz Banao"):
        qt, err = generate_quiz(n)
        st.error(err) if err else st.markdown(qt)
    st.write("--- Answer check (voice se bhi)")
    qq = universal_input("q_check_q", "Question bolo ya likho")
    ua = universal_input("q_check_a", "Tumhara answer")
    ca = st.text_input("Correct answer (teacher)")
    tp = st.text_input("Topic","general")
    if st.button("Check Karo"):
        ok,fb=check_quiz_answer(qq,ua,ca,tp)
        st.success(fb) if ok else st.error(fb)

elif active=="Story":
    from rag_utils import story_mode_learning
    tp = universal_input("story", "Topic bolo - jaise Stack, Cloud Computing")
    if st.button("🎬 Movie Banao", type="primary"):
        if tp:
            with st.spinner("Story ban rahi hai..."):
                s=story_mode_learning(tp); st.markdown(s)
                ap=text_to_speech(s)
                if ap: st.audio(ap)

elif active=="Example":
    from rag_utils import real_life_example, generate_flashcards, make_study_plan
    conc = universal_input("ex", "Concept bolo - jaise DBMS, Sensors")
    if st.button("Example se Samjhao"):
        if conc: st.markdown(real_life_example(conc))
    if st.button("Flashcards Banao"):
        st.markdown(generate_flashcards())
    st.divider()
    ed=st.date_input("Exam kab hai?"); hr=st.number_input("Ghante?",1,12,4)
    if st.button("Plan Banao"):
        st.markdown(make_study_plan(str(ed),hr))

elif active=="Viva":
    from rag_utils import viva_simulator, viva_followup
    if "vq" not in st.session_state: st.session_state.vq=""
    tp = universal_input("viva", "Viva topic bolo")
    if st.button("Viva Start"):
        if tp: st.session_state.vq=viva_simulator(tp); st.rerun()
    if st.session_state.vq:
        st.info(st.session_state.vq)
        a = universal_input("viva_ans", "Jawab bolo ya likho")
        if st.button("Submit"):
            st.session_state.vq=viva_followup(st.session_state.vq,a); st.rerun()

elif active=="Projects":
    from rag_utils import build_project_guide
    idea = universal_input("proj", "Project idea bolo - jaise Smart Dustbin")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("🚀 Guide Banao", type="primary"):
        if idea:
            with st.spinner("..."): st.markdown(build_project_guide(idea,bud))

elif active=="Summary":
    if st.button("Summary Banao", type="primary"):
        st.markdown(generate_summary())
elif active=="Important":
    if st.button("Predict Karo", type="primary"):
        st.markdown(predict_important_questions())
elif active=="PYQ":
    fs=st.file_uploader("PYQ PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Analyze Karo", type="primary"):
        from rag_utils import analyze_pyq
        if fs: st.markdown(analyze_pyq(fs))
elif active=="Mentor":
    from rag_utils import get_mentor_report
    if st.button("📈 Report Banao", type="primary"):
        st.markdown(get_mentor_report())

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}")
        st.markdown(x['answer'][:400])
        st.divider()
*Ab kya hua?*
- Har jagah ek text box + mic button
- User bolega to auto text ban jayega
- Tumhe `rag_utils.py` wala hi use karna hai jo maine pehle diya tha (usme `transcribe_audio` already hai)

Push kar do, ab Sir bolenge "NotebookLM me to type hi karna padta hai, isme to bolke bhi padh sakte hain!"
