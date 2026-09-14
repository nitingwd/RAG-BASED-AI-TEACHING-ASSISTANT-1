import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, get_api_key, generate_quiz, generate_summary, predict_important_questions, text_to_speech, check_handwritten_answer

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

st.subheader("💬 Study Dashboard")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["⌨️ Ask (Text + Audio)", "📝 Quiz", "📄 Summary", "⭐ Important Qs", "✍️ Copy Check"])

with tab1:
    query = st.text_input("Apna question likho")
    if st.button("Ask"):
        if query:
            with st.spinner("🤔 Answer nikal rahe hain..."):
                answer, sources = ask_question(query, top_k)
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
    st.write("Tumhare PDF se MCQ banayega")
    num_q = st.number_input("Kitne questions?", min_value=3, max_value=10, value=5)
    if st.button("Quiz Banao"):
        with st.spinner("Quiz ban raha hai..."):
            q_text, err = generate_quiz(num_q)
        if err:
            st.error(err)
        else:
            st.markdown(q_text)

with tab3:
    st.subheader("📄 Smart Summary")
    st.write("Poore document ka 1-page Hinglish summary")
    if st.button("Summary Banao"):
        with st.spinner("Summary ban raha hai..."):
            s = generate_summary()
        st.session_state['last_summary'] = s
        st.markdown(s)

    if 'last_summary' in st.session_state:
        from fpdf import FPDF
        def create_pdf(text):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)
            clean_text = text.encode('latin-1', 'replace').decode('latin-1')
            for line in clean_text.split('\n'):
                pdf.multi_cell(0, 10, line)
            return pdf.output(dest='S').encode('latin-1')
        
        pdf_bytes = create_pdf(st.session_state['last_summary'])
        st.download_button(
            label="📥 Summary PDF Download Karo",
            data=pdf_bytes,
            file_name="smart_summary.pdf",
            mime="application/pdf"
        )

with tab4:
    st.subheader("⭐ Exam Predictor")
    st.write("Exam me aane wale most important questions")
    if st.button("Important Questions Dekho"):
        with st.spinner("Predict kar rahe hain..."):
            imp = predict_important_questions()
        st.markdown(imp)

with tab5:
    st.subheader("✍️ Teacher's Red Pen - Copy Check")
    st.write("Apne haath se likhe answer ki photo upload karo, AI syllabus se check karega")
    q_for_check = st.text_input("Yeh answer kis question ka hai?", key="check_q")
    img_file = st.file_uploader("Answer ki photo upload karo", type=["jpg", "jpeg", "png"], key="check_img")
    if st.button("Copy Check Karo"):
        if q_for_check and img_file:
            with st.spinner("🧐 Teacher check kar raha hai..."):
                result = check_handwritten_answer(img_file, q_for_check)
            st.markdown(result)
        else:
            st.warning("⚠️ Question aur photo dono do.")

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    if history:
        for i, h in enumerate(reversed(history), 1):
            st.markdown(f"**Q{i}:** {h['query']}")
            st.markdown(f"**A{i}:** {h['answer']}")
            st.divider()
    else:
        st.write("Abhi koi history nahi hai.")
