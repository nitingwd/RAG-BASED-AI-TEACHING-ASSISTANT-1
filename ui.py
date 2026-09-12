import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history

st.set_page_config(page_title="Advance RAG", layout="wide")

# Developer Badge
st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; box-shadow: 0px 4px 8px rgba(0,0,0,0.3); color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")

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

st.subheader("💬 Ask a Question")
query = st.text_input("Enter your question here")

if st.button("Ask"):
    if query:
        with st.spinner("🤔 Finding answer..."):
            answer, sources = ask_question(query, top_k)
        st.markdown(f"**Answer:** {answer}")
        st.write("### 📚 Sources")
        for src in sources:
            st.write(f"- {src.get('source','?')} | Page: {src.get('page','?')}")
    else:
        st.warning("⚠️ Please enter a question.")

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    st.json(history)