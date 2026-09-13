import os
import streamlit as st
import tempfile
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def get_api_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except:
        pass
    return os.getenv("GROQ_API_KEY")

@st.cache_resource
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )

def transcribe_audio(api_key, audio_path):
    try:
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as f:
            tr = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3-turbo",
                language="hi"
            )
        return tr.text
    except Exception as e:
        st.error(f"Voice transcribe error: {e}")
        return None

def text_to_speech(text):
    try:
        from gtts import gTTS
        tts = gTTS(text=text[:500], lang='hi')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None

def process_files(files, chunk_size=1000, chunk_overlap=100):
    if not files:
        st.warning("Pehle koi file upload karo.")
        return
    docs = []
    for file in files:
        file_ext = os.path.splitext(file.name)[-1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(file.getvalue())
            tmp_path = tmp.name
        try:
            if file_ext == ".pdf":
                loader = PyPDFLoader(tmp_path)
            elif file_ext == ".csv":
                loader = CSVLoader(tmp_path)
            elif file_ext == ".txt":
                loader = TextLoader(tmp_path)
            else:
                st.warning(f"{file.name} skip kiya - sirf PDF/CSV/TXT allowed hai")
                continue
            loaded = loader.load()
            loaded = [d for d in loaded if d.page_content and d.page_content.strip()]
            for d in loaded:
                d.metadata["source"] = file.name
            docs.extend(loaded)
        except Exception as e:
            st.error(f"{file.name} padhne me error: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    if not docs:
        st.error("Koi file se text nahi nikla. Scanned PDF hai to text wali PDF upload karo.")
        return
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    chunks = [c for c in chunks if c.page_content and c.page_content.strip()]
    if not chunks:
        st.error("Text bahut chota hai, chunk_size kam karo (500 try karo).")
        return
    try:
        with st.spinner(f"{len(chunks)} chunks ke embeddings ban rahe hain..."):
            embeddings = get_embeddings()
            test_vec = embeddings.embed_query("hello")
            if not test_vec or len(test_vec) == 0:
                st.error("Embedding model load nahi hua. App reboot karo.")
                return
            vectordb = Chroma.from_documents(chunks, embeddings)
    except Exception as e:
        st.error(f"Embedding/Chroma error: {str(e)}")
        st.info("Fix: Streamlit Cloud > Manage app > Reboot karo.")
        return
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    st.success(f"Ho gaya! {len(chunks)} chunks process hue.")

def ask_question(query, k=3):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili. Streamlit Secrets me add karo.", []
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao.", []
    try:
        docs = vectordb.similarity_search(query, k=k)
    except Exception as e:
        return f"Search me error: {e}", []
    if not docs:
        return "Iska jawab uploaded documents me nahi mila.", []
    context = "\n\n".join([f"[Source: {d.metadata.get('source','?')} Page: {d.metadata.get('page','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    prompt = f"""You are a B.Tech/M.Tech teaching assistant. Answer ONLY from context.
If not in context, say 'Ye aapke uploaded syllabus me nahi hai.'
Always cite page number.
Context:
{context}
Question: {query}
Answer in simple Hinglish:"""
    try:
        answer = llm.invoke(prompt).content
    except Exception as e:
        return f"Groq API error: {e}", []
    sources = [doc.metadata for doc in docs]
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append({"query": query, "answer": answer, "sources": sources})
    return answer, sources

def ask_with_voice(audio_bytes):
    api_key = get_api_key()
    if not api_key:
        return None, "GROQ_API_KEY nahi mili"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        q_text = transcribe_audio(api_key, tmp_path)
        if not q_text:
            return None, "Voice samajh nahi aayi"
        answer, sources = ask_question(q_text)
        mp3_path = text_to_speech(answer)
        return {"question": q_text, "answer": answer, "sources": sources, "audio_path": mp3_path}, None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def generate_quiz(topic, num_q=5):
    api_key = get_api_key()
    if not api_key:
        return None, "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return None, "Pehle documents upload karke 'Submit & Process' dabao."
    if not topic or not topic.strip():
        return None, "Pehle topic likho, jaise 'Photosynthesis'"
    docs = vectordb.similarity_search(topic, k=5)
    context = "\n\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.5)
    prompt = f"""Topic: {topic}
Neeche ke context se {num_q} MCQ banao, sirf is topic se related.
Format:
Q1. question?
a) ...
b) ...
c) ...
d) ...
Answer: b)

Context:
{context}"""
    try:
        return llm.invoke(prompt).content, None
    except Exception as e:
        return None, f"Groq error: {e}"

def generate_summary(topic):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao."
    if not topic or not topic.strip():
        return "Pehle topic likho, jaise 'Thermodynamics'"
    docs = vectordb.similarity_search(topic, k=8)
    context = "\n\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    prompt = f"""Topic: {topic}
Is topic ka Hinglish me 1-page summary do, sirf context se.
Headings:
## Important Topics
## Key Definitions
## Formulas / Points
Context:
{context}"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Groq error: {e}"

def predict_important_questions():
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao."
    docs = vectordb.similarity_search("exam important questions", k=6)
    context = "\n\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.3)
    prompt = f"""Is syllabus se exam me aane wale 10 Most Important Questions predict karo. Har question ke sath marks likho (2-mark / 5-mark / 10-mark). Simple Hinglish me.
Context:
{context}"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Groq error: {e}"

def load_conversation_history():
    return st.session_state.get("history", [])
