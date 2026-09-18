import os
import re
import json
import tempfile
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from gtts import gTTS

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader

load_dotenv()

# ========== API KEY ==========
def get_api_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except:
        pass
    return os.getenv("GROQ_API_KEY")

# ========== EMBEDDINGS ==========
@st.cache_resource(show_spinner=False)
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )

def get_lang_code(lang_name):
    mapping = {
        "Hindi": "hi",
        "Gujarati": "gu",
        "Hinglish": "hi",
        "English": "en",
        "Marathi": "mr"
    }
    return mapping.get(lang_name, "hi")

# ========== AUDIO ==========
def text_to_audio_file(text, language_name="Hinglish"):
    try:
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = clean[:3500]
        if not clean:
            return None
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        tts = gTTS(text=clean, lang=get_lang_code(language_name), slow=False)
        tts.save(tmp.name)
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 1000:
            return tmp.name
        return None
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

def transcribe_audio(api_key, audio_path):
    try:
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3-turbo",
                language="hi",
                response_format="text"
            )
        return transcription if isinstance(transcription, str) else transcription.text
    except Exception as e:
        print(f"Whisper Error: {e}")
        return None

# ========== RAG PROCESSING ==========
def process_files(files, chunk_size=1000, chunk_overlap=100):
    if not files:
        st.warning("No files uploaded")
        return
    docs = []
    for file in files:
        ext = os.path.splitext(file.name)[-1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file.getvalue())
            path = tmp.name
        try:
            if ext == ".pdf":
                loader = PyPDFLoader(path)
            elif ext == ".csv":
                loader = CSVLoader(path)
            elif ext == ".txt":
                loader = TextLoader(path, encoding='utf-8')
            else:
                continue
            loaded = loader.load()
            for d in loaded:
                d.metadata["source"] = file.name
            docs.extend([d for d in loaded if d.page_content.strip()])
        except Exception as e:
            st.error(f"Error loading {file.name}: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)

    if not docs:
        st.error("No content extracted!")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)

    vectordb = FAISS.from_documents(chunks, get_embeddings())
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    st.session_state.weak_topics = {}
    st.success(f"✅ {len(chunks)} chunks ready from {len(docs)} docs!")

def hybrid_search(query, k=8):
    vb = st.session_state.get("vectordb")
    if not vb:
        return []
    try:
        return vb.similarity_search(query, k=k)
    except Exception as e:
        print(f"Search Error: {e}")
        return []

# ========== CORE ASK ==========
def ask_question(query, k=8, mode="normal", language="Hinglish"):
    vb = st.session_state.get("vectordb")
    if not vb:
        return "Pehle File Upload karo.", []

    docs = hybrid_search(query, k=k)
    if not docs:
        return "PDF me ye topic nahi mila.", []

    ctx = "\n\n".join([d.page_content for d in docs])

    if mode == "socratic":
        sys_prompt = f"You are Socratic teacher. Don't give direct answer. Ask leading questions in {language}. Context: {ctx}"
    else:
        sys_prompt = f"You are helpful teacher. Answer in {language} from context. If not in context say 'Context me nahi hai'. Context: {ctx}"

    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    ans = llm.invoke(f"{sys_prompt}\n\nQ: {query}").content

    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append({"query": query, "answer": ans, "sources": [d.metadata for d in docs]})

    return ans, [d.metadata for d in docs]

# ========== QUIZ ==========
def generate_quiz(num_q=5, language="Hinglish"):
    docs = hybrid_search("important concepts definitions", k=6)
    ctx = "\n".join([d.page_content[:800] for d in docs])[:5000]

    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4)
    prompt = f"""
    Create {num_q} MCQs in {language} from this context.
    Context: {ctx}

    Return ONLY JSON array format like:
    [
      {{"question": "...", "options": ["a)...", "b)...", "c)...", "d)..."], "answer": "a)...", "explanation": "...", "topic": "..."}}
    ]
    No extra text.
    """
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('[')
        e = txt.rfind(']')+1
        if s!=-1 and e!=-1:
            data = json.loads(txt[s:e])
            return data
    except Exception as e:
        print(f"Quiz parse error {e}")

    return [{"question":f"Sample Q{i+1} about document?", "options":["a) Option1","b) Option2","c) Option3","d) Option4"], "answer":"a) Option1", "explanation":"Refer PDF", "topic":"general"} for i in range(num_q)]

def check_quiz_answer(question, user_ans, correct_ans, topic="general"):
    ok = user_ans.strip().lower()[:2] == correct_ans.strip().lower()[:2]
    if not ok:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt
    return ok, ("✅ Sahi Jawaab!" if ok else f"❌ Galat. Sahi: {correct_ans}")

def get_weak_topics():
    return st.session_state.get("weak_topics", {})

# ========== SUMMARY ==========
def generate_summary(language="Hinglish"):
    docs = hybrid_search("summary overview", k=10)
    ctx = "\n".join([d.page_content[:800] for d in docs])[:6000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    return llm.invoke(f"Give detailed summary in {language}. Context: {ctx}").content

def predict_important_questions(language="Hinglish"):
    docs = hybrid_search("exam important questions", k=8)
    ctx = "\n".join([d.page_content[:800] for d in docs])[:6000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3)
    return llm.invoke(f"Predict 10 most important exam questions with answers in {language}. Context: {ctx}").content

def load_conversation_history():
    return st.session_state.get("history", [])

# ========== STORY / PROJECT / PODCAST ==========
def story_mode_learning(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=8)
    ctx = "\n".join([d.page_content[:800] for d in docs])[:6000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8)
    return llm.invoke(f"Explain {topic} as interesting story in {language} easy to remember. Context: {ctx}").content

def build_project_guide(idea, budget="low", language="Hinglish"):
    docs = hybrid_search(idea, k=5)
    ctx = "\n".join([d.page_content[:700] for d in docs])[:4000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.5)
    return llm.invoke(f"Create project guide for '{idea}' budget {budget} in {language}. Include hardware, steps, cost. Context: {ctx}").content

def generate_podcast_script(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=5)
    ctx = "\n".join([d.page_content[:700] for d in docs])[:4000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8)
    return llm.invoke(f"Write 2-host podcast script (Host1, Host2) on {topic} in {language} fun style. Context: {ctx}").content

# ========== VIVA ==========
def generate_viva_questions(topic, num_q=5, language="Hinglish"):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:700] for d in docs])[:5000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4)
    prompt = f"""
    Generate {num_q} viva questions for {topic} in {language}.
    Context: {ctx}
    Return ONLY JSON array: [{{"q":"...","a":"..."}}]
    """
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        return json.loads(txt[s:e])
    except:
        return [{"q":f"Explain {topic} Question {i+1}?", "a":f"Answer about {topic}"} for i in range(num_q)]

def verify_viva_answer(question, correct_ans, user_ans, language="Hinglish"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"""
    Q: {question}
    Correct Answer: {correct_ans}
    Student Answer: {user_ans}
    Language: {language}
    Check if student is correct. Return ONLY JSON: {{"verdict":"True/False","feedback":"short feedback in {language}"}}
    """
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('{'); e = txt.rfind('}')+1
        return json.loads(txt[s:e])
    except:
        is_ok = user_ans.lower() in correct_ans.lower() or correct_ans.lower() in user_ans.lower()
        return {"verdict": str(is_ok), "feedback": f"Correct answer is: {correct_ans}"}

# ========== PPT ==========
def create_ppt_file(topic, num_slides=10, language="Hinglish"):
    docs = hybrid_search(topic, k=8)
    ctx = "\n".join([d.page_content[:1000] for d in docs])[:6000]
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4)
    prompt = f"""
    Topic: {topic} Language: {language}
    Create {num_slides} slides JSON.
    Context: {ctx}
    Return ONLY JSON: [{{"title":"...","points":["p1","p2","p3"]}}]
    """
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides = json.loads(txt[s:e])
    except:
        slides = [{"title": f"{topic} - Slide {i+1}", "points": ["Important Point 1","Important Point 2","Example"]} for i in range(num_slides)]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    # Title Slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(13,17,38)
    tx = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(1.5))
    tf = tx.text_frame; tf.word_wrap=True
    tf.text = topic
    p = tf.paragraphs[0]; p.font.size=Pt(36); p.font.bold=True; p.font.color.rgb=RGBColor(255,255,255)
    tx2 = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(12), Inches(1))
    tf2 = tx2.text_frame; tf2.text=f"Created in {language} | AI Teaching Assistant"
    tf2.paragraphs[0].font.size=Pt(18); tf2.paragraphs[0].font.color.rgb=RGBColor(200,200,255)

    for i, sl in enumerate(slides[:num_slides]):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(249,250,255)
        header = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.0))
        header.fill.solid(); header.fill.fore_color.rgb = RGBColor(13,17,38)
        ht = slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(8), Inches(0.8))
        ht.text_frame.word_wrap=True
        ht.text_frame.text = f"{i+1}. {sl.get('title','')}"
        ht.text_frame.paragraphs[0].font.size=Pt(20); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
        ct = slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(7.5), Inches(5.9))
        tf = ct.text_frame; tf.word_wrap=True
        for pt in sl.get('points',[])[:6]:
            para = tf.add_paragraph()
            para.text = f"• {pt}"
            para.space_after = Pt(12)
            para.font.size = Pt(16)
            para.font.color.rgb = RGBColor(30,30,30)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name
