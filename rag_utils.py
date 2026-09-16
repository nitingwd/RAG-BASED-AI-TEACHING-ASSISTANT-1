import os
import streamlit as st
import tempfile
import json
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
        st.error(f"Voice error: {e}")
        return None

def text_to_speech(text):
    try:
        from gtts import gTTS
        tts = gTTS(text=text[:600], lang='hi')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except:
        return None

def process_files(files, chunk_size=1000, chunk_overlap=100):
    if not files:
        st.warning("File upload karo.")
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
                loader = TextLoader(path)
            else:
                continue
            loaded = loader.load()
            for d in loaded:
                d.metadata["source"] = file.name
            docs.extend([d for d in loaded if d.page_content.strip()])
        finally:
            if os.path.exists(path):
                os.remove(path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    vectordb = Chroma.from_documents(chunks, get_embeddings())
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    if "weak_topics" not in st.session_state:
        st.session_state.weak_topics = {}
    st.success(f"Ho gaya! {len(chunks)} chunks.")

def hybrid_search(query, k=3):
    vb = st.session_state.get("vectordb")
    if not vb:
        return []
    return vb.similarity_search(query, k=k)

def ask_question(query, k=3, mode="normal"):
    api_key = get_api_key()
    if not api_key:
        return "GROQ_API_KEY nahi mili.", []
    vb = st.session_state.get("vectordb")
    if not vb:
        return "Pehle Submit & Process dabao.", []
    docs = hybrid_search(query, k=k)
    if not docs:
        return "Jawab nahi mila.", []
    context = "\n\n".join([f"[{d.metadata.get('source','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    system = "Socratic teacher ho. Seedha answer mat do, sawal pucho." if mode=="socratic" else "B.Tech teaching assistant ho. Sirf context se Hinglish me jawab do."
    answer = llm.invoke(f"{system}\nContext:\n{context}\nQ: {query}").content
    st.session_state.history.append({"query": query, "answer": answer, "sources": [d.metadata for d in docs], "mode": mode})
    return answer, [d.metadata for d in docs]

def generate_quiz(num_q=5):
    vb = st.session_state.get("vectordb")
    if not vb:
        return None, "Pehle docs upload karo."
    docs = hybrid_search("important concepts", k=5)
    context = "\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.5)
    return llm.invoke(f"{num_q} MCQ banao Format: Q1.? a) b) c) d) Answer:\nContext:{context}").content, None

def check_quiz_answer(question, user_answer, correct_answer, topic="general"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    ok = user_answer.strip().lower() == correct_answer.strip().lower()
    if not ok:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt
        fb = llm.invoke(f"Galat jawab Hinglish me samjhao. Q:{question} User:{user_answer} Correct:{correct_answer}").content
    else:
        fb = "Bilkul sahi! 🔥"
    return ok, fb

def get_weak_topics():
    return st.session_state.get("weak_topics", {})

def generate_summary():
    docs = hybrid_search("summary", k=8)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"1-page Hinglish summary do:\n{ctx}").content

def predict_important_questions():
    docs = hybrid_search("exam important", k=6)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"10 Important Questions with marks predict karo:\n{ctx}").content

def load_conversation_history():
    return st.session_state.get("history", [])

def analyze_pyq(files):
    text = ""
    for f in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(f.getvalue())
            path = tmp.name
        try:
            text += "\n".join([d.page_content[:2000] for d in PyPDFLoader(path).load()[:3]])
        finally:
            if os.path.exists(path):
                os.remove(path)
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"PYQ analysis weightage ke sath:\n{text[:8000]}").content

def generate_flashcards(num=10):
    docs = hybrid_search("definitions", k=5)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"{num} flashcards Front/Back me:\n{ctx}").content

def make_study_plan(exam_date, hours_per_day):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"Exam {exam_date}, {hours_per_day} hrs daily ka plan Hinglish me").content

def viva_simulator(topic):
    docs = hybrid_search(topic, k=3)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.7).invoke(f"Strict viva professor {topic} pe Q pucho. Context:{ctx}").content

def viva_followup(last_q, student_ans):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"Viva Q:{last_q} A:{student_ans} Feedback + next tough Q").content

def real_life_example(concept):
    docs = hybrid_search(concept, k=2)
    ctx = "\n".join([d.page_content[:600] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"{concept} ko desi example se samjhao. Context:{ctx}").content

def get_mentor_report():
    weak = st.session_state.get("weak_topics", {})
    history = st.session_state.get("history", [])
    if not weak and not history:
        return "Pehle Quiz do."
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"Weak:{weak} History:{len(history)} pe 7-din plan do Hinglish me").content

def story_mode_learning(topic):
    docs = hybrid_search(topic, k=4)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Topic {topic} ko Bollywood movie story me badal do. Context:{ctx}").content

def build_project_guide(project_idea, budget="low"):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4).invoke(f"Project Idea:{project_idea} Budget:{budget} Complete guide: Problem, Market, Components Price Table, Circuit, Full Code, Building Steps Hinglish me").content

def generate_ppt_slides(topic):
    docs = hybrid_search(topic, k=5)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"Topic {topic} pe 15 slides PPT content banao: Title, Objective, 10 content slides with [Diagram idea], Example, Summary, Viva Q. Hinglish. Context:{ctx}").content

def generate_lab_manual(experiment_name):
    docs = hybrid_search(experiment_name, k=5)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"Experiment {experiment_name} pe Lab Manual: Aim, Apparatus, Theory, Circuit, Code, Procedure, Observation Table, Result, Viva Q 5. Hinglish. Context:{ctx}").content

def generate_podcast_script(topic):
    docs = hybrid_search(topic, k=3)
    ctx = "\n".join([d.page_content[:600] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Topic {topic} pe 2 doston ka 3-min Hinglish podcast script banao. Format Host1: Host2:. Context:{ctx}").content

def generate_viva_questions(topic, num_q=10):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:700] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.6)
    prompt = f"""Topic: {topic}
Context: {ctx}
{num_q} viva questions banao JSON array me. Har object: {{"q":"question", "a":"correct short answer in 2 lines"}}
Sirf JSON array dena, koi extra text nahi."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('[')
        e = txt.rfind(']') + 1
        return json.loads(txt[s:e])
    except:
        return [{"q": f"Explain {topic} - Question {i+1}?", "a": "As per document, detailed explanation."} for i in range(num_q)]

def verify_viva_answer(question, correct_ans, user_ans):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"""Q:{question}
Correct:{correct_ans}
Student:{user_ans}
Check karo sahi hai ya galat. JSON me jawab do: {{"verdict":"True/False", "feedback":"Hinglish me 2 line feedback + sahi answer"}}"""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('{')
        e = txt.rfind('}') + 1
        return json.loads(txt[s:e])
    except:
        is_true = len(user_ans.strip()) > 5
        return {"verdict": "True" if is_true else "False", "feedback": f"Correct ans: {correct_ans}"}

def create_ppt_file(topic, num_slides=10):
    docs = hybrid_search(topic, k=5)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4)
    prompt = f"""Topic: {topic}, Slides: {num_slides}
Context: {ctx}
Give {num_slides} slides JSON array. Each object: {{"title":"Slide Title", "points":["point1","point2","point3"], "note":"speaker note"}}
Make it professional English, B.Tech level. First slide Title slide, Last slide Thank You + Q&A.
Only JSON array."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('[')
        e = txt.rfind(']') + 1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [{"title": f"{topic} - Slide {i+1}", "points": [f"Point about {topic}", "Explanation", "Example"], "note": f"Explain {topic}"} for i in range(num_slides)]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    for i, sl in enumerate(slides_data[:num_slides]):
        if i == 0:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(20, 30, 70)
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1), Inches(12), Inches(2))
            tf = txBox.text_frame
            tf.text = sl.get('title', topic)
            p = tf.paragraphs[0]
            p.font.size = Pt(44)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(12), Inches(2))
            tf2 = txBox2.text_frame
            tf2.text = "\n".join(sl.get('points', []))
            tf2.paragraphs[0].font.size = Pt(20)
            tf2.paragraphs[0].font.color.rgb = RGBColor(220, 220, 255)
        else:
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(245, 245, 245)
            titleBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(1))
            titleBox.text_frame.text = sl.get('title', '')
            titleBox.text_frame.paragraphs[0].font.size = Pt(32)
            titleBox.text_frame.paragraphs[0].font.bold = True
            titleBox.text_frame.paragraphs[0].font.color.rgb = RGBColor(20, 30, 70)
            contentBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(7.5), Inches(5))
            tf = contentBox.text_frame
            tf.word_wrap = True
            for pt in sl.get('points', []):
                p = tf.add_paragraph()
                p.text = f"• {pt}"
                p.level = 0
                p.font.size = Pt(18)
            noteBox = slide.shapes.add_textbox(Inches(8.5), Inches(1.2), Inches(4), Inches(5))
            noteBox.text_frame.text = "Speaker Note:\n" + sl.get('note', '')
            noteBox.text_frame.paragraphs[0].font.size = Pt(14)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name
