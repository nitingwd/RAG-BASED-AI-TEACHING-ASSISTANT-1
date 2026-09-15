import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, get_api_key, generate_quiz, generate_summary, predict_important_questions, text_to_speech, check_quiz_answer, get_weak_topics

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; color: white; font-size: 14px; font-weight: bold; z-index: 999;}
.rect-btn button {height: 110px!important; border-radius: 15px!important; font-size: 16px!important; font-weight: bold!important; border: none!important; color: white!important; box-shadow: 0 4px 12px rgba(0,0,0,0.2)!important;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")
st.caption("Rectangle pe click karo - feature neeche khul jayega")

# Sidebar
st.sidebar.header("Configuration")
uploaded_files = st.sidebar.file_uploader("Upload documents (PDF, CSV, TXT)", type=["pdf", "csv", "txt"], accept_multiple_files=True)
chunk_size = st.sidebar.number_input("Chunk Size", 200, 2000, 1000, 100)
chunk_overlap = st.sidebar.number_input("Chunk Overlap", 0, 500, 100, 10)
top_k = st.sidebar.number_input("Documents to Retrieve", 1, 10, 3)
if st.sidebar.button("Submit & Process"):
    if uploaded_files:
        with st.spinner("Processing..."):
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

# Active state
if "active" not in st.session_state:
    st.session_state.active = "Ask"

st.subheader("📦 Features - Click to Open")
# Row 1
c1,c2,c3 = st.columns(3)
with c1:
    if st.button("⌨️ Ask\nSawal + Audio", use_container_width=True, key="f_ask"):
        st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("📝 Quiz\nMCQ + Check", use_container_width=True, key="f_quiz"):
        st.session_state.active="Quiz"; st.rerun()
with c3:
    if st.button("📄 Summary\n1-Page", use_container_width=True, key="f_sum"):
        st.session_state.active="Summary"; st.rerun()
# Row 2
c4,c5,c6 = st.columns(3)
with c4:
    if st.button("⭐ Important Qs\nPredictor", use_container_width=True, key="f_imp"):
        st.session_state.active="Important"; st.rerun()
with c5:
    if st.button("📊 PYQ\nAnalyzer", use_container_width=True, key="f_pyq"):
        st.session_state.active="PYQ"; st.rerun()
with c6:
    if st.button("🎤 Viva\nProfessor Mode", use_container_width=True, key="f_viva"):
        st.session_state.active="Viva"; st.rerun()
# Row 3
c7,c8,c9 = st.columns(3)
with c7:
    if st.button("💡 Example\nDesi + Flashcards", use_container_width=True, key="f_ex"):
        st.session_state.active="Example"; st.rerun()
with c8:
    if st.button("🧠 AI Mentor\nPersonal Plan", use_container_width=True, key="f_men"):
        st.session_state.active="Mentor"; st.rerun()
with c9:
    if st.button("📖 Story Mode\nMovie", use_container_width=True, key="f_story"):
        st.session_state.active="Story"; st.rerun()
# Row 4
c10,_,_ = st.columns(3)
with c10:
    if st.button("🔧 Project Builder\nIoT + Code", use_container_width=True, key="f_proj"):
        st.session_state.active="Projects"; st.rerun()

st.divider()
active = st.session_state.active
st.header(f"▶ {active}")

# Sections - same logic as your tabs
if active=="Ask":
    mode = st.radio("Mode:", ["Normal", "Socratic (Khud se socho)"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = st.text_input("Apna question likho")
    if st.button("Ask", type="primary"):
        if q:
            ans, src = ask_question(q, top_k, mode=sel)
            st.markdown(ans)
            ap = text_to_speech(ans)
            if ap: st.audio(ap)
            if src:
                with st.expander("Sources"):
                    for s in src: st.json(s)

elif active=="Quiz":
    n = st.number_input("Kitne Q?", 3, 10, 5)
    if st.button("Quiz Banao"):
        qt, err = generate_quiz(n)
        st.error(err) if err else st.markdown(qt)
    with st.form("chk"):
        qq=st.text_input("Question"); ua=st.text_input("Tumhara ans"); ca=st.text_input("Correct ans"); tp=st.text_input("Topic","general")
        if st.form_submit_button("Check Karo"):
            ok,fb=check_quiz_answer(qq,ua,ca,tp)
            st.success(fb) if ok else st.error(fb)

elif active=="Summary":
    if st.button("Summary Banao", type="primary"):
        with st.spinner("..."): st.markdown(generate_summary())

elif active=="Important":
    if st.button("Predict Karo", type="primary"):
        with st.spinner("..."): st.markdown(predict_important_questions())

elif active=="PYQ":
    fs=st.file_uploader("PYQ PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Analyze Karo", type="primary"):
        from rag_utils import analyze_pyq
        if fs:
            with st.spinner("..."): st.markdown(analyze_pyq(fs))

elif active=="Viva":
    if "vq" not in st.session_state: st.session_state.vq=""
    tp=st.text_input("Topic")
    if st.button("Viva Start"):
        from rag_utils import viva_simulator
        st.session_state.vq=viva_simulator(tp); st.rerun()
    if st.session_state.vq:
        st.info(st.session_state.vq)
        a=st.text_area("Jawab")
        if st.button("Submit"):
            from rag_utils import viva_followup
            st.session_state.vq=viva_followup(st.session_state.vq,a); st.rerun()

elif active=="Example":
    conc=st.text_input("Concept?")
    if st.button("Example se Samjhao"):
        from rag_utils import real_life_example
        st.markdown(real_life_example(conc))
    if st.button("Flashcards Banao"):
        from rag_utils import generate_flashcards
        st.markdown(generate_flashcards())
    st.divider()
    ed=st.date_input("Exam kab hai?"); hr=st.number_input("Ghante?",1,12,4)
    if st.button("Plan Banao"):
        from rag_utils import make_study_plan
        st.markdown(make_study_plan(str(ed),hr))

elif active=="Mentor":
    from rag_utils import get_mentor_report
    col1,col2=st.columns(2)
    col1.metric("Attempted", len(st.session_state.get("history",[])))
    col2.metric("Weak", len(weak))
    if st.button("📈 Report Banao", type="primary"):
        with st.spinner("..."): st.markdown(get_mentor_report())

elif active=="Story":
    from rag_utils import story_mode_learning
    tp=st.text_input("Topic?")
    if st.button("🎬 Movie Banao", type="primary"):
        if tp:
            s=story_mode_learning(tp); st.markdown(s)
            if st.button("🔊 Suno"):
                ap=text_to_speech(s)
                if ap: st.audio(ap)

elif active=="Projects":
    from rag_utils import build_project_guide
    idea=st.text_area("Project idea")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("🚀 Guide Banao", type="primary"):
        if idea:
            with st.spinner("..."): st.markdown(build_project_guide(idea,bud))

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}")
        st.markdown(x['answer'][:400])
        st.divider()
