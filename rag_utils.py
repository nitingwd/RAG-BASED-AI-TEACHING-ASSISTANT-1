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

def get_reranker():
    return None

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
            vectordb = Chroma.from_documents(chunks, embeddings)
    except Exception as e:
        st.error(f"Embedding/Chroma error: {str(e)}")
        return
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    if "weak_topics" not in st.session_state:
        st.session_state.weak_topics = {}
    st.success(f"Ho gaya! {len(chunks)} chunks process hue.")

def hybrid_search(query, k=3):
    vectordb = st.session_state.get("vectordb")
    docs = vectordb.similarity_search(query, k=k)
    return docs

def ask_question(query, k=3, mode="normal"):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili. Streamlit Secrets me add karo.", []
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao.", []
    try:
        docs = hybrid_search(query, k=k)
    except Exception as e:
        return f"Search me error: {e}", []
    if not docs:
        return "Iska jawab uploaded documents me nahi mila.", []
    context = "\n\n".join([f"[Source: {d.metadata.get('source','?')} Page: {d.metadata.get('page','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    if mode == "socratic":
        system = """You are a Socratic teaching assistant. Seedha answer MAT do.
Pehle student se 2-3 guiding sawal pucho taaki wo khud soche.
Last me hint do. Hinglish me baat karo."""
    else:
        system = """You are a B.Tech/M.Tech teaching assistant. Answer ONLY from context.
If not in context, say 'Ye aapke uploaded syllabus me nahi hai.'
Always cite like [Page X, filename]."""
    prompt = f"""{system}
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
    st.session_state.history.append({"query": query, "answer": answer, "sources": sources, "mode": mode})
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

def generate_quiz(num_q=5):
    api_key = get_api_key()
    if not api_key:
        return None, "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return None, "Pehle documents upload karke 'Submit & Process' dabao."
    docs = hybrid_search("important concepts definitions formulas", k=5)
    context = "\n\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.5)
    prompt = f"""Context se {num_q} MCQ banao. Format strictly follow karo:
Q1. question?
a)...
b)...
c)...
d)...
Answer: b)
Context:
{context}"""
    try:
        return llm.invoke(prompt).content, None
    except Exception as e:
        return None, f"Groq error: {e}"

def check_quiz_answer(question, user_answer, correct_answer, topic="general"):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
    if not is_correct:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt
        feedback = llm.invoke(f"Student ne '{question}' ka galat jawab '{user_answer}' diya. Sahi '{correct_answer}' hai. 2 line me Hinglish me samjhao kyun galat hai.").content
    else:
        feedback = "Bilkul sahi! Bahut badhiya."
    return is_correct, feedback

def get_weak_topics():
    return st.session_state.get("weak_topics", {})

def generate_summary():
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao."
    docs = hybrid_search("summary overview main topics", k=8)
    context = "\n\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    prompt = f"""Neeche ke context ka 1-page Hinglish summary do. Headings rakho:
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
    docs = hybrid_search("exam important questions", k=6)
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
    prompt = f"""PYQ ka analysis karo:
1. Topic-wise weightage table (Topic | Kitni baar | Marks)
2. Top 5 repeating questions
3. 2026 prediction
Text: {text[:8000]}"""
    return llm.invoke(prompt).content

def generate_flashcards(num=10):
    api_key = get_api_key()
    docs = hybrid_search("important definitions formulas", k=5)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.5)
    prompt = f"""Context se {num} flashcards banao. Format:
Front:...
Back:...
---
Context: {context}"""
    return llm.invoke(prompt).content

def make_study_plan(exam_date, hours_per_day):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.3)
    prompt = f"""Exam: {exam_date}, Daily: {hours_per_day} hours.
Day-wise study plan with revision slots do. Hinglish me practical plan."""
    return llm.invoke(prompt).content

def viva_simulator(topic):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.7)
    docs = hybrid_search(topic, k=3)
    context = "\n".join([d.page_content[:800] for d in docs])
    prompt = f"""Tum strict Viva professor ho. Topic: {topic}
Context: {context}
Student se pehla tough viva question pucho (Hinglish me). Answer mat do, sirf question pucho."""
    return llm.invoke(prompt).content

def viva_followup(last_q, student_ans):
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.7)
    prompt = f"""Viva chal raha hai.
Sawal: {last_q}
Jawab: {student_ans}
Pehle 2 line feedback do, phir agla tough cross-question pucho. Hinglish me."""
    return llm.invoke(prompt).content

def real_life_example(concept):
    api_key = get_api_key()
    docs = hybrid_search(concept, k=2)
    context = "\n".join([d.page_content[:600] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.6)
    prompt = f"""Concept: {concept}
Context: {context}
Isko 2 desi real-life examples (chai dukaan, cricket, train) se simple Hinglish me samjhao."""
    return llm.invoke(prompt).content

def get_mentor_report():
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.3)
    weak = st.session_state.get("weak_topics", {})
    history = st.session_state.get("history", [])
    if not weak and not history:
        return "Pehle 2-3 Quiz do, tabhi Mentor tumhara plan bana payega."
    weak_str = "\n".join([f"- {t}: {c} baar galat" for t,c in weak.items()])
    prompt = f"""Tum IIT professor mentor ho.
Total attempted: {len(history)}
Weak topics: {weak_str}
Do:
1. Performance Analysis (2 line, motivate karo)
2. Top 3 Weak Areas
3. 7-Din ka Adaptive Plan (Day-wise)
4. 1 Exam Strategy Tip
Hinglish me personal mentor jaise likho."""
    return llm.invoke(prompt).content

def story_mode_learning(topic):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili"
    vectordb = st.session_state.get("vectordb")
    if not vectordb:
        return "Pehle documents upload karke 'Submit & Process' dabao."
    docs = hybrid_search(topic, k=4)
    context = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.8)
    prompt = f"""Topic: {topic}
Context: {context}
Isko ek Bollywood movie story me badal do. Characters banao, hero-villain banao, interval-twist rakho. Har concept story ka part ho. End me 'Moral of Story = Formula' do. Full Hinglish, mazedaar, yaad rehne wala."""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Groq error: {e}"
