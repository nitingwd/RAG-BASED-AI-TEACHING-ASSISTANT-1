import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, ask_with_voice, get_api_key, generate_quiz, generate_summary, predict_important_questions

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; box-shadow: 0px 4px 8px rgba(0,0,0,0.3); color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")
st.caption("Upload PDF/CSV/TXT → Ask → Quiz → Summary → Important Questions")

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

st.subheader("💬 Study Dashboard")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["⌨️ Text me pucho", "🎤 Bol ke pucho", "📝 Quiz", "📄 Summary", "⭐ Important Qs"])

with tab1:
    query = st.text_input("Enter your question here")
    if st.button("Ask"):
        if query:
            with st.spinner("🤔 Finding answer..."):
                answer, sources = ask_question(query, top_k)
            st.markdown(f"**Answer:** {answer}")
            if sources:
                st.write("### 📚 Sources")
                for src in sources:
                    with st.expander(f"📄 {src.get('source','?')} | Page: {src.get('page','?')}"):
                        st.json(src)
        else:
            st.warning("⚠️ Please enter a question.")

with tab2:
    st.write("Mic dabao aur apna sawal bolo (Hindi/English)")
    audio = st.audio_input("Record karo")
    if audio:
        with st.spinner("🎧 Voice samajh rahe hain..."):
            result, err = ask_with_voice(audio.getvalue())
        if err:
            st.error(err)
        else:
            st.success(f"**Tumne bola:** {result['question']}")
            st.markdown(f"**Answer:** {result['answer']}")
            if result['audio_path']:
                st.audio(result['audio_path'])
            if result['sources']:
                st.write("### 📚 Sources")
                for src in result['sources']:
                    with st.expander(f"📄 {src.get('source','?')} | Page: {src.get('page','?')}"):
                        st.json(src)

with tab3:
    st.subheader("📝 Auto Quiz Generator")
    st.write("Tumhare PDF se MCQ banayega")
    num_q = st.number_input("Kitne questions?", min_value=3, max_value=10, value=5)
    if st.button("Quiz Banao"):
        with st.spinner("Quiz ban raha hai..."):
            q_text, err = generate_quiz(num_q)
        if err:
            st.error(err)
        else:
            st.markdown(q_text)

with tab4:
    st.subheader("📄 Smart Summary")
    st.write("Poore document ka 1-page Hinglish summary")
    if st.button("Summary Banao"):
        with st.spinner("Summary ban raha hai..."):
            s = generate_summary()
        st.markdown(s)

with tab5:
    st.subheader("⭐ Exam Predictor")
    st.write("Exam me aane wale most important questions")
    if st.button("Important Questions Dekho"):
        with st.spinner("Predict kar rahe hain..."):
            imp = predict_important_questions()
        st.markdown(imp)

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    if history:
        for i, h in enumerate(reversed(history), 1):
            st.markdown(f"**Q{i}:** {h['query']}")
            st.markdown(f"**A{i}:** {h['answer']}")
            st.divider()
    else:
        st.write("Abhi koi history nahi hai.")
