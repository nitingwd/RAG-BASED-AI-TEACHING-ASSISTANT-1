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

def story_mode_learning(topic):
    docs = hybrid_search(topic, k=4)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Topic {topic} ko Bollywood movie story me badal do. Context:{ctx}").content

def build_project_guide(project_idea, budget="low"):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4).invoke(f"Project Idea:{project_idea} Budget:{budget} Complete guide: Problem, Market, Components Price Table, Circuit, Full Code, Building Steps Hinglish me").content

def generate_podcast_script(topic):
    docs = hybrid_search(topic, k=3)
    ctx = "\n".join([d.page_content[:600] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Topic {topic} pe 2 doston ka 3-min Hinglish podcast script banao. Format Host1: Host2:. Context:{ctx}").content

def generate_viva_questions(topic, num_q=10):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:700] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.6)
    prompt = f"""Topic: {topic}\nContext: {ctx}\n{num_q} viva questions banao JSON array me. Har object: {{"q":"question", "a":"correct short answer in 2 lines"}}\nSirf JSON array dena."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']') + 1
        return json.loads(txt[s:e])
    except:
        return [{"q": f"Explain {topic} - Q {i+1}?", "a": "As per document"} for i in range(num_q)]

def verify_viva_answer(question, correct_ans, user_ans):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"""Q:{question}\nCorrect:{correct_ans}\nStudent:{user_ans}\nJSON do: {{"verdict":"True/False", "feedback":"Hinglish me 2 line feedback + sahi answer"}}"""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('{'); e = txt.rfind('}') + 1
        return json.loads(txt[s:e])
    except:
        return {"verdict": "False", "feedback": f"Correct: {correct_ans}"}

def create_ppt_file(topic, num_slides=10):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.7)
    prompt = f"""You are world-class professor. Topic: {topic}, Slides: {num_slides}
PDF Context: {ctx[:6000]}
Create JSON array of {num_slides} slides. Each:
{{"title":"Title","subtitle":"subtitle","points":["25-30 words real mechanism why/how works internally","Real company example Tesla/Google with how they use","Deep technical working","Application with numbers"],"visual_type":"flowchart","visual_steps":["Step1 3words","Step2","Step3","Step4"],"real_example":"Real company example"}}
Only JSON, English, very detailed."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [{"title": f"{topic} - Part {i+1}", "subtitle": "Real Deep Dive", "points": [f"{topic} ka internal working ye hai ki real me...", f"Google/ISRO me {topic} ka use aise hota hai...", "Technical depth with mechanism"], "visual_type": "flowchart", "visual_steps": ["Input", "Process", "Output", "Result"], "real_example": "Used in Google/ISRO"} for i in range(num_slides)]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)

    def draw_diagram(slide, left, top, steps):
        colors = [RGBColor(0,180,255), RGBColor(0,210,130), RGBColor(255,160,0), RGBColor(160,100,255), RGBColor(255,90,90)]
        for i, step in enumerate(steps[:5]):
            box = slide.shapes.add_shape(5, left, top + i*Inches(0.95), Inches(4.2), Inches(0.65))
            box.fill.solid(); box.fill.fore_color.rgb = colors[i % 5]; box.line.fill.background()
            tf = box.text_frame; tf.word_wrap=True; tf.text = f"{i+1}. {step}"; tf.paragraphs[0].font.size=Pt(13); tf.paragraphs[0].font.bold=True; tf.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            if i < len(steps[:5])-1:
                arr = slide.shapes.add_shape(13, left+Inches(1.8), top + i*Inches(0.95)+Inches(0.65), Inches(0.4), Inches(0.25))
                arr.fill.solid(); arr.fill.fore_color.rgb = RGBColor(80,80,80); arr.line.fill.background()

    for i, sl in enumerate(slides_data[:num_slides]):
        if i == 0:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor(8,15,45)
            t = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(8), Inches(1.3))
            t.text_frame.text = sl.get('title','').upper(); t.text_frame.paragraphs[0].font.size=Pt(40); t.text_frame.paragraphs[0].font.bold=True; t.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            sub = slide.shapes.add_textbox(Inches(0.8), Inches(2), Inches(7.5), Inches(2.5))
            sub.text_frame.word_wrap=True; sub.text_frame.text = sl.get('subtitle','') + f"\n\nREAL: {sl.get('real_example','')}\n\n" + "\n".join(sl.get('points',[])[:2])
            sub.text_frame.paragraphs[0].font.size=Pt(14); sub.text_frame.paragraphs[0].font.color.rgb=RGBColor(180,220,255)
            draw_diagram(slide, Inches(9), Inches(0.8), sl.get('visual_steps',[]))
        elif i == 1:
            slide = prs.slides.add_slide(prs.slide_layouts[5]); slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(255,255,255)
            tb=slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(0.7)); tb.text_frame.text="ROADMAP - What You Will Learn"; tb.text_frame.paragraphs[0].font.size=Pt(28); tb.text_frame.paragraphs[0].font.bold=True; tb.text_frame.paragraphs[0].font.color.rgb=RGBColor(10,20,50)
            left=slide.shapes.add_textbox(Inches(0.6), Inches(1.1), Inches(6.5), Inches(5.8)); tf=left.text_frame; tf.word_wrap=True
            for idx, pt in enumerate(sl.get('points',[])):
                pa=tf.add_paragraph(); pa.text=f"{idx+1}. {pt}"; pa.space_after=Pt(14); pa.font.size=Pt(13)
            draw_diagram(slide, Inches(8), Inches(1.1), sl.get('visual_steps',[]))
        else:
            slide = prs.slides.add_slide(prs.slide_layouts[5]); slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(246,248,255)
            header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(0.9)); header.fill.solid(); header.fill.fore_color.rgb=RGBColor(10,20,50); header.line.fill.background()
            ht=slide.shapes.add_textbox(Inches(0.5), Inches(0.1), Inches(7.5), Inches(0.7)); ht.text_frame.text=sl.get('title',''); ht.text_frame.paragraphs[0].font.size=Pt(22); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            card=slide.shapes.add_shape(5, Inches(0.4), Inches(1.1), Inches(7.2), Inches(6.1)); card.fill.solid(); card.fill.fore_color.rgb=RGBColor(255,255,255); card.line.color.rgb=RGBColor(210,210,210)
            ct=slide.shapes.add_textbox(Inches(0.6), Inches(1.2), Inches(6.8), Inches(5.9)); tf=ct.text_frame; tf.word_wrap=True
            for pt in sl.get('points',[]):
                pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(12); pa.font.size=Pt(12); pa.font.color.rgb=RGBColor(30,30,30)
            ex=tf.add_paragraph(); ex.text=f"\n🌍 Real Use: {sl.get('real_example','')}"; ex.font.size=Pt(11); ex.font.bold=True; ex.font.color.rgb=RGBColor(0,110,180); ex.space_before=Pt(14)
            vbg=slide.shapes.add_shape(5, Inches(8), Inches(1.1), Inches(5), Inches(6.1)); vbg.fill.solid(); vbg.fill.fore_color.rgb=RGBColor(15,25,60); vbg.line.fill.background()
            vt=slide.shapes.add_textbox(Inches(8.2), Inches(1.2), Inches(4.6), Inches(0.4)); vt.text_frame.text="VISUAL FLOWCHART"; vt.text_frame.paragraphs[0].font.size=Pt(11); vt.text_frame.paragraphs[0].font.bold=True; vt.text_frame.paragraphs[0].font.color.rgb=RGBColor(0,220,255)
            draw_diagram(slide, Inches(8.3), Inches(1.8), sl.get('visual_steps',[]))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name
