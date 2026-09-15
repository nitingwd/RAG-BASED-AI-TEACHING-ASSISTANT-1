import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, get_api_key, generate_quiz, generate_summary, predict_important_questions, text_to_speech, check_quiz_answer, get_weak_topics

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; box-shadow: 0px 4px 8px rgba(0,0,0,0.3); color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")
st.caption("Upload PDF/CSV/TXT → Ask (Text + Audio) → Quiz → Summary → Important Questions")

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
tab1, tab2, tab3, tab4 = st.tabs(["⌨️ Ask (Text + Audio)", "📝 Quiz", "📄 Summary", "⭐ Important Qs"])

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

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    if history:
        for i, h in enumerate(reversed(history), 1):
            st.markdown(f"**Q{i}:** {h['query']} `[{h.get('mode','normal')}]`")
            st.markdown(f"**A{i}:** {h['answer']}")
            st.divider()
    else:
        st.write("Abhi koi history nahi hai.")
