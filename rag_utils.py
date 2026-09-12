import os
import streamlit as st
import tempfile
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from dotenv import load_dotenv

load_dotenv()

def get_api_key():
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except:
        pass
    return os.getenv("GOOGLE_API_KEY")

def get_embeddings():
    # Local free embeddings - koi API error nahi
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def process_files(files, chunk_size=1000, chunk_overlap=100):
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
                continue
            loaded = loader.load()
            for d in loaded:
                d.metadata["source"] = file.name
            docs.extend(loaded)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    
    vectordb = Chroma.from_documents(chunks, get_embeddings())
    st.session_state.vectordb = vectordb
    st.session_state.history = []

def ask_question(query, k=3):
    api_key = get_api_key()
    if not api_key:
        return "GOOGLE_API_KEY nahi mili.", []
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao.", []

    docs = vectordb.similarity_search(query, k=k)
    context = "\n\n".join([f"[Source: {d.metadata.get('source','?')} Page: {d.metadata.get('page','?')}] {d.page_content}" for d in docs])
    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key=api_key, temperature=0)
    prompt = f"""You are a B.Tech/M.Tech teaching assistant. Answer ONLY from context.
If not in context, say 'Ye aapke uploaded syllabus me nahi hai.'
Always cite page number.

Context:
{context}

Question: {query}

Answer in simple Hinglish:"""
    answer = llm.invoke(prompt).content
    sources = [doc.metadata for doc in docs]
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append({"query": query, "answer": answer, "sources": sources})
    return answer, sources

def load_conversation_history():
    return st.session_state.get("history", [])