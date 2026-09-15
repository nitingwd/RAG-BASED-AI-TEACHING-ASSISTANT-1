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
                continue
            loaded = loader.load()
            loaded = [d for d in loaded if d.page_content and d.page_content.strip()]
            for d in loaded:
                d.metadata["source"] = file.name
            docs.extend(loaded)
        except Exception as e:
            st.error(f"{file.name} error: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    if not docs:
        st.error("Koi text nahi mila.")
        return
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    chunks = [c for c in chunks if c.page_content.strip()]
    embeddings = get_embeddings()
    vectordb = Chroma.from_documents(chunks, embeddings)
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    if "weak_topics" not in st.session_state:
        st.session_state.weak_topics = {}
    st.success(f"Ho gaya! {len(chunks)} chunks.")

def hybrid_search(query, k=3):
    vectordb = st.session_state.get("vectordb")
    return vectordb.similarity_search(query, k=k)

def ask_question(query, k=3, mode="normal"):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili.", []
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle Submit & Process dabao.", []
    docs = hybrid_search(query, k=k)
    if not docs:
        return "Jawab nahi mila.", []
    context = "\n\n".join([f"[{d.metadata.get('source','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    system = "Socratic teacher ho. Seedha answer mat do, sawal pucho." if mode=="socratic" else "B.Tech teaching assistant ho. Sirf context se jawab do. Hinglish me."
    prompt = f"{system}\nContext:\n{context}\nQ: {query}"
    try:
        answer = llm.invoke(prompt).content
    except Exception as e:
        return f"Groq error: {e}", []
    sources = [d.metadata for d in docs]
    st.session_state.history.append({"query": query, "answer": answer, "sources": sources, "mode": mode})
    return answer, sources

def generate_quiz(num_q=5):
    api_key = get_api_key()
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return None, "Pehle docs upload karo."
    docs = hybrid_search("important concepts", k=5)
    context = "\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.5)
    prompt = f"{num_q} MCQ banao:\nQ1.?\na) b) c) d)\nAnswer:\nContext:{context}"
    try:
        return llm.invoke(prompt).content, None
    except Exception as e:
        return None, str(e)

def check_quiz_answer(question, user_answer, correct_answer, topic="general"):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    ok = user_answer.strip().lower() == correct_answer.strip().lower()
    if not ok:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt
        fb = llm.invoke(f"Galat jawab samjhao Hinglish me. Q:{question} User:{user_answer} Correct:{correct_answer}").content
    else:
        fb = "Bilkul sahi!"
    return ok, fb

def get_weak_topics():
    return st.session_state.get("weak_topics", {})

def generate_summary():
    api_key = get_api_key()
    docs = hybrid_search("summary", k=8)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    return llm.invoke(f"1-page Hinglish summary do:\n{context}").content

def predict_important_questions():
    api_key = get_api_key()
    docs = hybrid_search("exam important", k=6)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.3)
    return llm.invoke(f"10 Important Questions predict karo with marks:\n{context}").content

def load_conversation_history():
    return st.session_state.get("history", [])

def analyze_pyq(files):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    text = ""
    for f in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(f.getvalue())
            path = tmp.name
        try:
            docs = PyPDFLoader(path).load()
            text += "\n".join([d.page_content[:2000] for d in docs[:3]])
        finally:
            if os.path.exists(path):
                os.remove(path)
    return llm.invoke(f"PYQ analysis karo weightage ke sath:\n{text[:8000]}").content

def generate_flashcards(num=10):
    docs = hybrid_search("definitions", k=5)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model=get_api_key() and "openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.5)
    return llm.invoke(f"{num} flashcards Front/Back me:\n{context}").content

def make_study_plan(exam_date, hours_per_day):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3)
    return llm.invoke(f"Exam {exam_date}, {hours_per_day} hrs daily ka plan do Hinglish me").content

def viva_simulator(topic):
    docs = hybrid_search(topic, k=3)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.7)
    return llm.invoke(f"Strict professor ho. Topic {topic} pe viva question pucho. Context:{context}").content

def viva_followup(last_q, student_ans):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.7)
    return llm.invoke(f"Viva: Q:{last_q} A:{student_ans} Feedback + next tough Q pucho").content

def real_life_example(concept):
    docs = hybrid_search(concept, k=2)
    context = "\n".join([d.page_content[:600] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.6)
    return llm.invoke(f"{concept} ko desi example se samjhao. Context:{context}").content

def get_mentor_report():
    weak = st.session_state.get("weak_topics", {})
    history = st.session_state.get("history", [])
    if not weak and not history:
        return "Pehle Quiz do."
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3)
    return llm.invoke(f"Weak:{weak} History:{len(history)} pe 7-din plan do Hinglish me").content

def story_mode_learning(topic):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    docs = hybrid_search(topic, k=4)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.8)
    try:
        return llm.invoke(f"Topic {topic} ko Bollywood story me badal do. Context:{context}").content
    except Exception as e:
        return f"Groq error: {e}"

def build_project_guide(project_idea, budget="low"):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.4)
    prompt = f"""Project Idea: {project_idea}
Budget: {budget}
Complete Project Guide Hinglish me:
## 1. Problem Statement
## 2. Market Need
## 3. Components List with Price Table
## 4. Circuit Connection
## 5. Full Code
## 6. Building Steps
## 7. Future Upgrade"""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Groq error: {e}"
