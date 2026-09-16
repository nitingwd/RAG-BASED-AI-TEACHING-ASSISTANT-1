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
    prompt = f"""Topic: {topic}
Context: {ctx}
{num_q} viva questions banao JSON array me. Har object: {{"q":"question", "a":"correct short answer in 2 lines"}}
Sirf JSON array dena."""
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
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.5)
    prompt = f"""You are top PPT designer. Topic: {topic}, Slides: {num_slides}
Context: {ctx[:6000]}
Create {num_slides} slides JSON array. Each: {{"title":"Catchy Title", "subtitle":"1 line subtitle", "points":["Detailed explanation 15-20 words with how/why","Point 2 deep","Point 3","Point 4"], "visual":"What diagram/flowchart/architecture/table to draw", "example":"Real world example 1 line"}}
Structure: 1=Title, 2=Agenda, 3 to {num_slides-2}=Core with deep explanation, {num_slides-1}=Applications, {num_slides}=Summary. English only. Only JSON."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [{"title": f"{topic} Slide {i+1}", "subtitle":"Deep Dive", "points":[f"Detailed about {topic}", "Working mechanism", "Advantages"], "visual":f"Diagram of {topic}", "example":f"Used in {topic} industry"} for i in range(num_slides)]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)

    for i, sl in enumerate(slides_data[:num_slides]):
        if i == 0:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor(10, 20, 50)
            bar = slide.shapes.add_shape(1, Inches(0), Inches(5.6), Inches(13.33), Inches(0.12))
            bar.fill.solid(); bar.fill.fore_color.rgb = RGBColor(0, 210, 255); bar.line.fill.background()
            t = slide.shapes.add_textbox(Inches(0.8), Inches(1), Inches(11), Inches(1.2))
            t.text_frame.text = sl.get('title','').upper(); t.text_frame.paragraphs[0].font.size=Pt(42); t.text_frame.paragraphs[0].font.bold=True; t.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            sub = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(8), Inches(0.8))
            sub.text_frame.text = sl.get('subtitle',''); sub.text_frame.paragraphs[0].font.size=Pt(20); sub.text_frame.paragraphs[0].font.color.rgb=RGBColor(0,210,255)
            pts = slide.shapes.add_textbox(Inches(0.8), Inches(3.2), Inches(6.5), Inches(2))
            tf=pts.text_frame; tf.word_wrap=True
            for pt in sl.get('points',[])[:3]:
                pa=tf.add_paragraph(); pa.text=f"✦ {pt}"; pa.space_after=Pt(10); pa.font.size=Pt(15); pa.font.color.rgb=RGBColor(210,210,210)
        elif i==1:
            slide = prs.slides.add_slide(prs.slide_layouts[5]); slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(255,255,255)
            tb=slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(0.8)); tb.text_frame.text=f"AGENDA: {sl.get('title','')}"; tb.text_frame.paragraphs[0].font.size=Pt(30); tb.text_frame.paragraphs[0].font.bold=True; tb.text_frame.paragraphs[0].font.color.rgb=RGBColor(10,20,50)
            left=slide.shapes.add_textbox(Inches(0.7), Inches(1.4), Inches(6), Inches(5.5)); tf=left.text_frame; tf.word_wrap=True
            for idx, pt in enumerate(sl.get('points',[])):
                pa=tf.add_paragraph(); pa.text=f"{idx+1:02d} {pt}"; pa.font.size=Pt(17); pa.space_after=Pt(18); pa.font.color.rgb=RGBColor(30,30,30)
            right=slide.shapes.add_shape(1, Inches(7.5), Inches(1.4), Inches(5), Inches(5.2)); right.fill.solid(); right.fill.fore_color.rgb=RGBColor(235,242,255); right.line.fill.background()
            vt=slide.shapes.add_textbox(Inches(7.7), Inches(1.6), Inches(4.6), Inches(4.8)); vt.text_frame.word_wrap=True; vt.text_frame.text=f"🎨 VISUAL\n{sl.get('visual','')}\n\n💡 EXAMPLE\n{sl.get('example','')}"; vt.text_frame.paragraphs[0].font.size=Pt(13)
        else:
            slide = prs.slides.add_slide(prs.slide_layouts[5]); slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(248,249,252)
            header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.05)); header.fill.solid(); header.fill.fore_color.rgb=RGBColor(10,20,50); header.line.fill.background()
            ht=slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(8), Inches(0.7)); ht.text_frame.text=sl.get('title',''); ht.text_frame.paragraphs[0].font.size=Pt(26); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            hs=slide.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(8), Inches(0.35)); hs.text_frame.text=sl.get('subtitle',''); hs.text_frame.paragraphs[0].font.size=Pt(13); hs.text_frame.paragraphs[0].font.color.rgb=RGBColor(0,210,255)
            card=slide.shapes.add_shape(1, Inches(0.5), Inches(1.3), Inches(7.5), Inches(5.8)); card.fill.solid(); card.fill.fore_color.rgb=RGBColor(255,255,255); card.line.color.rgb=RGBColor(220,220,220)
            ct=slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(7), Inches(5.3)); tf=ct.text_frame; tf.word_wrap=True
            for pt in sl.get('points',[]):
                pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(12); pa.font.size=Pt(15); pa.font.color.rgb=RGBColor(30,30,30)
            if sl.get('example'):
                ex=tf.add_paragraph(); ex.text=f"\n💡 Example: {sl.get('example')}"; ex.font.size=Pt(13); ex.font.bold=True; ex.font.color.rgb=RGBColor(0,100,160); ex.space_before=Pt(16)
            vcard=slide.shapes.add_shape(1, Inches(8.5), Inches(1.3), Inches(4.3), Inches(5.8)); vcard.fill.solid(); vcard.fill.fore_color.rgb=RGBColor(10,20,50); vcard.line.fill.background()
            vt=slide.shapes.add_textbox(Inches(8.7), Inches(1.5), Inches(3.9), Inches(0.4)); vt.text_frame.text="VISUALIZATION"; vt.text_frame.paragraphs[0].font.size=Pt(11); vt.text_frame.paragraphs[0].font.bold=True; vt.text_frame.paragraphs[0].font.color.rgb=RGBColor(0,210,255)
            vc=slide.shapes.add_textbox(Inches(8.7), Inches(2), Inches(3.9), Inches(4.8)); vc.text_frame.word_wrap=True; vc.text_frame.text=f"{sl.get('visual','')}\n\n[ Diagram Placeholder ]\n→ Use flowchart / block diagram\n→ Add icons & arrows\n→ Keep visual clean\n\nDeep Explanation:\nThis slide explains {sl.get('title','')} with real-world context for easy understanding."; vc.text_frame.paragraphs[0].font.size=Pt(12); vc.text_frame.paragraphs[0].font.color.rgb=RGBColor(220,220,220)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name
