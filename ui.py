import streamlit as st
import matplotlib.pyplot as plt
import re
from rag_utils import process_files, ask_question, load_conversation_history, get_api_key, generate_quiz, generate_summary, predict_important_questions, text_to_speech

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

tab1, tab2, tab3, tab4 = st.tabs(["⌨️ Ask (Text + Audio)", "📝 Quiz", "📄 Summary", "⭐ Important Qs"])

def display_answer_with_graph(llm_answer):
    # TEXT: aur CODE: ko alag karo
    if "CODE:" in llm_answer:
        parts = llm_answer.split("CODE:")
        text_part = parts[0].replace("TEXT:", "").strip()
        code_part = parts[1].strip()

        st.markdown(f"**Answer (Text):** {text_part}")

        # ```python.... ``` ko saaf karo
        clean_code = re.sub(r'```python|```', '', code_part).strip()

        st.write("### 📊 Visualization")
        try:
            fig, ax = plt.subplots()
            # ax ko code me available karate hain
            exec(clean_code, {"plt": plt, "fig": fig, "ax": ax})
            st.pyplot(fig)
        except Exception as e:
            st.error(f"Graph banane me error aaya: {e}")
            st.code(clean_code)
    else:
        clean_text = llm_answer.replace("TEXT:", "").strip()
        st.markdown(f"**Answer (Text):** {clean_text}")

with tab1:
    query = st.text_input("Apna question likho (graph ke liye 'graph banao' likho)")
    if st.button("Ask"):
        if query:
            # Agar user ne graph manga hai to query me instruction add kardo
            graph_keywords = ["graph", "plot", "chart", "visualize", "diagram", "bar", "pie"]
            enhanced_query = query
            if any(k in query.lower() for k in graph_keywords):
                enhanced_query = query + "\n\nInstruction: Pehle TEXT: me samjhao, phir CODE: me sirf matplotlib ka python code do. Code me fig, ax pehle se bane hue hain, unhi ka use karo. plt.show() mat likhna."
            else:
                enhanced_query = query + "\n\nInstruction: Sirf TEXT: me jawab do."

            with st.spinner("🤔 Answer nikal rahe hain..."):
                answer, sources = ask_question(enhanced_query, top_k)

            display_answer_with_graph(answer)

            with st.spinner("🔊 Audio bana rahe hain..."):
                # Audio ke liye sirf text wala hissa bhejo
                audio_text = answer.split("CODE:")[0].replace("TEXT:", "").strip()
                audio_path = text_to_speech(audio_text)
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
        st.markdown(s)

with tab4:
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
