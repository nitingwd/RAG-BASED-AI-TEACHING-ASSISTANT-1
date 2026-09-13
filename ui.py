import streamlit as st
from rag_utils import process_files, ask_question, load_conversation_history, ask_with_voice, get_api_key, create_explainer_video

st.set_page_config(page_title="Advance RAG", layout="wide")

st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; box-shadow: 0px 4px 8px rgba(0,0,0,0.3); color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

st.title("RAG Based AI Teaching Assistant")
st.caption("Upload PDF/CSV/TXT → Ask by Text or Voice → Get answer with sources")

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

tab1, tab2 = st.tabs(["⌨️ Text me pucho", "🎤 Bol ke pucho"])

def show_video_explainer(answer, key_prefix):
    if st.button("🎬 AI Video me Samjhao", key=f"video_{key_prefix}"):
        with st.spinner("AI video bana rahe hain..."):
            slides, audio_path, points = create_explainer_video(answer)
        if slides:
            st.success("Video ready! Ye raha AI explainer:")
            for s in slides:
                st.image(s, use_container_width=True)
            if audio_path:
                st.audio(audio_path)
            st.caption("AI ne tumhare answer se ye explainer banaya hai")
        else:
            st.error("Video nahi ban paya")

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
            if answer and "nahi" not in answer.lower()[:30]:
                show_video_explainer(answer, "text")
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
            show_video_explainer(result['answer'], "voice")

with st.expander("🕘 Conversation History"):
    history = load_conversation_history()
    if history:
        for i, h in enumerate(reversed(history), 1):
            st.markdown(f"**Q{i}:** {h['query']}")
            st.markdown(f"**A{i}:** {h['answer']}")
            st.divider()
    else:
        st.write("Abhi koi history nahi hai.")
