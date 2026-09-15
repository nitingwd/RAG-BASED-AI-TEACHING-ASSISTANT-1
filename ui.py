import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, get_api_key, generate_quiz, generate_summary, predict_important_questions, text_to_speech, check_quiz_answer, get_weak_topics

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; box-shadow: 0px 4px 8px rgba(0,0,0,0.3); color: white; font-size: 14px; font-weight: bold; z-index: 999;}
.card-grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;}
.rect-card {background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); border-radius: 15px; padding: 20px; color: white; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.1);}
.rect-card h4 {margin: 0 0 8px 0; font-size: 18px;}
.rect-card p {margin: 0; font-size: 13px; opacity: 0.9; line-height: 1.4;}
.rect-2 {background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);}
.rect-3 {background: linear-gradient(135deg, #8E2DE2 0%, #4A00E0 100%);}
.rect-4 {background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333;}
.rect-5 {background: linear-gradient(135deg, #e53935 0%, #e35d5b 100%);}
.rect-6 {background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%);}
@media (max-width: 768px) {.card-grid {grid-template-columns: repeat(2, 1fr);}}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")
st.caption("Upload PDF/CSV/TXT → Ask → Quiz → Viva → PYQ → AI Mentor → Story Mode")

# ===== RECTANGLE FEATURES DASHBOARD =====
st.subheader("📦 Saare Features - Ek Nazar Me")

st.markdown("""
<div class="card-grid">
<div class="rect-card"><h4>⌨️ Ask Question</h4><p>Syllabus se sawal pucho, page citation ke sath jawab + audio me suno</p></div>
<div class="rect-card rect-2"><h4>📝 Smart Quiz</h4><p>Auto MCQ banao, answer check karo, weak topics track karo</p></div>
<div class="rect-card rect-3"><h4>📄 Summary</h4><p>Poori PDF ka 1-page Hinglish summary, headings ke sath</p></div>
<div class="rect-card rect-4"><h4>⭐ Important Qs</h4><p>Exam me aane wale 10 most important questions predict karo</p></div>
<div class="rect-card rect-5"><h4>📊 PYQ Analyzer</h4><p>PYQ upload karo, topic weightage + repeating questions dekho</p></div>
<div class="rect-card rect-6"><h4>🎤 Viva Simulator</h4><p>Strict professor se viva practice karo, cross-questions ke sath</p></div>
<div class="rect-card rect-2"><h4>💡 Desi Example</h4><p>Tough concept ko chai-dukaan, cricket example se samjho</p></div>
<div class="rect-card rect-3"><h4>🧠 AI Mentor</h4><p>Tumhare quiz history se personal 7-din ka study plan</p></div>
<div class="rect-card"><h4>📖 Story Mode</h4><p>Boring topic ko Bollywood movie story me badal do</p></div>
</div>
""", unsafe_allow_html=True)

st.info("👇 Neeche tabs me jao aur koi bhi rectangle wala feature use karo")

# ===== Tumhara purana code same =====
st.sidebar.header("Configuration")
uploaded_files = st.sidebar.file_uploader("Upload documents (PDF, CSV, TXT)", type=["pdf", "csv", "txt"], accept_multiple_files=True)
chunk_size = st.sidebar.number_input("Chunk Size", min_value=200, max_value=2000, value=1000, step=100)
chunk_overlap = st.sidebar.number_input("Chunk Overlap", min_value=0, max_value=500, value=100, step=10)
top_k = st.sidebar.number_input("Documents to Retrieve", min_value=1, max_value=10, value=3)

if st.sidebar.button("Submit & Process"):
    if uploaded_files:
        with st.spinner("🔄 Processing documents..."):
            process_files(uploaded_files, chunk_size, chunk_overlap)
        st.success("✅ Documents processed!")
    else:
        st.warning("⚠️ Please upload at least one document.")

st.sidebar.divider()
st.sidebar.subheader("📊 Weak Topics")
weak = get_weak_topics()
if weak:
    for topic, count in sorted(weak.items(), key=lambda x: x[1], reverse=True):
        st.sidebar.markdown(f"- **{topic}**: {count} baar galat")
else:
    st.sidebar.info("Abhi koi weak topic nahi. Quiz do!")

st.subheader("💬 Study Dashboard")
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["⌨️ Ask", "📝 Quiz", "📄 Summary", "⭐ Important Qs", "📊 PYQ", "🎤 Viva", "💡 Example", "🧠 AI Mentor", "📖 Story Mode"])

with tab1:
    mode = st.radio("Mode chuno:", ["Normal", "Socratic (Khud se socho)"], horizontal=True)
    sel_mode = "socratic" if "Socratic" in mode else "normal"
    if sel_mode == "socratic":
        st.info("🧠 Socratic Mode ON: AI seedha answer nahi dega, tumse sawal puchega.")
    query = st.text_input("Apna question likho")
    if st.button("Ask"):
        if query:
            with st.spinner("🤔 Answer nikal rahe hain..."):
                answer, sources = ask_question(query, top_k, mode=sel_mode)
            st.markdown(f"**Answer (Text):** {answer}")
            with st.spinner("🔊 Audio bana rahe hain..."):
                audio_path = text_to_speech(answer)
            if audio_path:
                st.markdown("**Answer (Audio):**")
                st.audio(audio_path)
            if sources:
                st.write("### 📚 Sources")
                for src in sources:
                    with st.expander(f"📄 {src.get('source','?')} | Page: {src.get('page','?')}"):
                        st.json(src)
        else:
            st.warning("⚠️ Pehle question likho.")

with tab2:
    st.subheader("📝 Auto Quiz Generator")
    num_q = st.number_input("Kitne questions?", min_value=3, max_value=10, value=5)
    if st.button("Quiz Banao"):
        with st.spinner("Quiz ban raha hai..."):
            q_text, err = generate_quiz(num_q)
        if err:
            st.error(err)
        else:
            st.markdown(q_text)
    st.divider()
    st.subheader("✅ Answer Check Karo")
    with st.form("quiz_check"):
        q = st.text_input("Question copy-paste karo")
        user_ans = st.text_input("Tumhara answer (a/b/c/d)")
        correct_ans = st.text_input("Correct answer (quiz se dekho)")
        topic = st.text_input("Topic", value="general")
        submitted = st.form_submit_button("Check Karo")
        if submitted and q:
            is_ok, feedback = check_quiz_answer(q, user_ans, correct_ans, topic)
            if is_ok:
                st.success(feedback)
            else:
                st.error(feedback)
                st.info("Ye topic Weak Topics me add ho gaya hai!")

with tab3:
    st.subheader("📄 Smart Summary")
    if st.button("Summary Banao"):
        with st.spinner("Summary ban raha hai..."):
            s = generate_summary()
        st.markdown(s)

with tab4:
    st.subheader("⭐ Exam Predictor")
    if st.button("Important Questions Dekho"):
        with st.spinner("Predict kar rahe hain..."):
            imp = predict_important_questions()
        st.markdown(imp)

with tab5:
    st.subheader("📊 PYQ Paper Analyzer")
    pyq_files = st.file_uploader("PYQ PDF upload karo", type=["pdf"], accept_multiple_files=True, key="pyq")
    if st.button("Analyze Karo"):
        if pyq_files:
            from rag_utils import analyze_pyq
            with st.spinner("Analyzing..."):
                st.markdown(analyze_pyq(pyq_files))
        else:
            st.warning("Pehle PDF upload karo")

with tab6:
    st.subheader("🎤 Viva Simulator - Professor Mode")
    if "viva_q" not in st.session_state:
        st.session_state.viva_q = ""
    topic = st.text_input("Viva topic likho (e.g. DBMS Normalization)")
    if st.button("Viva Start Karo"):
        from rag_utils import viva_simulator
        with st.spinner("Professor question soch rahe hain..."):
            st.session_state.viva_q = viva_simulator(topic)
    if st.session_state.viva_q:
        st.info(f"Professor: {st.session_state.viva_q}")
        ans = st.text_area("Tumhara jawab:")
        if st.button("Jawab Submit Karo"):
            from rag_utils import viva_followup
            with st.spinner("Professor soch rahe hain..."):
                nxt = viva_followup(st.session_state.viva_q, ans)
            st.session_state.viva_q = nxt
            st.rerun()

with tab7:
    st.subheader("💡 Tough Concept -> Desi Example")
    st.write("Flashcards + Real-life example dono yahi milega")
    conc = st.text_input("Kaunsa concept samajh nahi aaya?")
    if st.button("Example se Samjhao"):
        from rag_utils import real_life_example
        with st.spinner("Example soch rahe hain..."):
            st.markdown(real_life_example(conc))
    st.divider()
    if st.button("Flashcards Banao"):
        from rag_utils import generate_flashcards
        with st.spinner("Bana rahe hain..."):
            st.markdown(generate_flashcards())
    st.divider()
    st.subheader("📅 Study Planner")
    exam_date = st.date_input("Exam kab hai?")
    hours = st.number_input("Roz kitne ghante?", 1, 12, 4)
    if st.button("Plan Banao"):
        from rag_utils import make_study_plan
        with st.spinner("Planning..."):
            st.markdown(make_study_plan(str(exam_date), hours))

with tab8:
    st.subheader("🧠 Tumhara AI Personal Mentor")
    st.write("Ye tumhare saare quiz ko dekh ke personal plan banata hai.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Attempted", len(st.session_state.get("history", [])))
    with col2:
        st.metric("Weak Topics", len(weak))
    with col3:
        if weak:
            top_weak = max(weak, key=weak.get)
            st.metric("Sabse Weak", top_weak[:15])
    if st.button("📈 Mera Mentor Report Banao", type="primary"):
        from rag_utils import get_mentor_report
        with st.spinner("Mentor analyze kar raha hai..."):
            report = get_mentor_report()
        st.markdown(report)
        st.success("Roz follow karo, topper bano!")

with tab9:
    st.subheader("📖 Syllabus to Movie Story Mode")
    st.write("Boring topic ko Bollywood story me badal do, kabhi nahi bhuloge!")
    story_topic = st.text_input("Kaunsa topic movie banana hai? (e.g. Thermodynamics Laws)")
    if st.button("🎬 Movie Banao", type="primary"):
        if story_topic:
            from rag_utils import story_mode_learning
            with st.spinner("Script likhi ja rahi hai... Interval ke baad milte hain..."):
                story = story_mode_learning(story_topic)
            st.markdown(story)
            st.divider()
            st.write("🔊 Story sunna hai?")
            if st.button("Audio Suno"):
                ap = text_to_speech(story)
                if ap:
                    st.audio(ap)
        else:
            st.warning("Pehle topic likho")

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    if history:
        for i, h in enumerate(reversed(history), 1):
            st.markdown(f"**Q{i}:** {h['query']} `[{h.get('mode','normal')}]`")
            st.markdown(f"**A{i}:** {h['answer']}")
            st.divider()
    else:
        st.write("Abhi koi history nahi hai.")
