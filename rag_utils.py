import os
import streamlit as st
import tempfile
import json
import textwrap
import math
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from dotenv import load_dotenv
from groq import Groq

# Video feature imports
try:
    from gtts import gTTS
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, ColorClip, CompositeVideoClip, TextClip

    # FIX for Pillow 10+ ANTIALIAS error
    if not hasattr(Image, 'ANTIALIAS'):
        try:
            Image.ANTIALIAS = Image.Resampling.LANCZOS
        except:
            Image.ANTIALIAS = Image.LANCZOS

    VIDEO_AVAILABLE = True
except Exception as e:
    print(f"Video import error: {e}")
    VIDEO_AVAILABLE = False

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

def create_ppt_file(topic, num_slides=5):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:1200] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.85)
    prompt = f"""You are IIT professor + designer.
Topic: {topic}
Context: {ctx[:7000]}
Create {num_slides} UNIQUE slides JSON. Each slide 4 points, each point 40-50 words detailed real working, no repeat.
Return JSON: [{{"title":"","subtitle":"","points":["40-50 words each x4"],"visual_steps":["Step A","Step B","Step C","Step D"],"real_example":"Windows/Linux example"}}] Only JSON."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [{"title":"What is "+topic,"subtitle":"Intro","points":["Point 1","Point 2","Point 3","Point 4"],"visual_steps":["Step1","Step2","Step3","Step4"],"real_example":"Example"}]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    prs = Presentation()
    prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
    def draw_pro_diagram(slide, left, top, steps):
        colors = [RGBColor(99,102,241), RGBColor(16,185,129), RGBColor(245,158,11), RGBColor(236,72,153)]
        for i, step in enumerate(steps[:4]):
            box = slide.shapes.add_shape(5, left, top + i*Inches(1.15), Inches(4.3), Inches(0.85))
            box.fill.solid(); box.fill.fore_color.rgb = colors[i % 4]; box.line.color.rgb = RGBColor(255,255,255); box.line.width = Pt(1.5)
            tf = box.text_frame; tf.word_wrap=True
            tf.text = f"STEP {i+1}\n{step}"
            tf.paragraphs[0].font.size=Pt(10); tf.paragraphs[0].font.bold=True; tf.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            tf.paragraphs[1].font.size=Pt(12); tf.paragraphs[1].font.bold=True; tf.paragraphs[1].font.color.rgb=RGBColor(255,255,255)
    for i, sl in enumerate(slides_data[:num_slides]):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(249,250,255)
        header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.0))
        header.fill.solid(); header.fill.fore_color.rgb=RGBColor(13,17,38); header.line.fill.background()
        ht=slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(7), Inches(0.8))
        ht.text_frame.text=f"{i+1}. {sl.get('title','')}"; ht.text_frame.paragraphs[0].font.size=Pt(19); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
        ct=slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(7.2), Inches(5.9))
        tf=ct.text_frame; tf.word_wrap=True
        for pt in sl.get('points',[]):
            pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(10); pa.font.size=Pt(10); pa.font.color.rgb=RGBColor(30,35,60)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name

def transcribe_topic_with_language(audio_path):
    text = transcribe_audio(get_api_key(), audio_path)
    if not text:
        return None, "Hinglish"
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Extract topic and language from: '{text}'. Return JSON {{\"topic\":\"...\",\"language\":\"Hindi/English/Hinglish/Marathi\"}} only."
    try:
        res = llm.invoke(prompt).content
        s = res.find('{'); e = res.rfind('}')+1
        data = json.loads(res[s:e])
        return data.get('topic', text), data.get('language', 'Hinglish')
    except:
        return text, "Hinglish"

def create_explainer_video(topic, language="Hinglish", duration_sec=60):
    if not VIDEO_AVAILABLE:
        return None, "Install gTTS, moviepy, Pillow"

    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.8)
    docs = hybrid_search(topic, k=3)
    ctx = "\n".join([d.page_content[:500] for d in docs]) if docs else ""

    prompt = f"""Topic: {topic}, Lang: {language}, Context: {ctx[:2000]}
    Create 4 scenes JSON for PREMIUM TUTOR VIDEO in {language}.
    Each: {{"title":"Title 4 words","explain":"45 words simple tutor style like 'Dekho dosto...' in {language}","diagram":"What whiteboard diagram to draw","example":"One real life example"}}
    Only JSON array 4 objects, language {language}."""

    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        scenes = json.loads(txt[s:e])
    except:
        scenes = [
            {"title": f"What is {topic}?", "explain": f"Dekho dosto, {topic} bahut simple hai. Real life example se samjhte hain.", "diagram": "User -> OS -> Hardware", "example": "Windows me"},
            {"title": "Internal Working", "explain": f"Ab iska internal kaam samjho. Pehle input, fir process, fir output.", "diagram": "Input -> Process -> Output", "example": "Chrome example"},
            {"title": "Real Life Magic", "explain": f"Iska real use Google, ISRO me hota hai. Bina iske system hang ho jayega.", "diagram": "Real World Use Case", "example": "Google Server"},
            {"title": "Quick Summary", "explain": f"Toh final me {topic} ka matlab hai management aur speed. Exam me pakka ayega.", "diagram": "Summary Points", "example": "Exam important"}
        ]

    temp_dir = tempfile.mkdtemp()
    clips = []

    def create_tutor_avatar():
        avatar = Image.new('RGB', (300, 300), color=(13,17,38))
        d = ImageDraw.Draw(avatar)
        d.ellipse([(10,10),(290,290)], fill=(99,102,241), outline=(255,255,255), width=6)
        d.text((95, 60), "AI", fill=(255,255,255))
        d.text((55, 160), "TUTOR", fill=(255,255,255))
        p = os.path.join(temp_dir, "tutor.png")
        avatar.save(p)
        return p

    tutor_path = create_tutor_avatar()

    for i, scene in enumerate(scenes):
        W, H = 1280, 720
        bg_img = Image.new('RGB', (W, H), (13, 17, 38))
        draw = ImageDraw.Draw(bg_img)
        for x in range(0, W, 80):
            draw.line([(x, 0), (x, H)], fill=(30, 40, 70), width=1)
        for y in range(0, H, 80):
            draw.line([(0, y), (W, y)], fill=(30, 40, 70), width=1)

        draw.rectangle([(0, 0), (W, 100)], fill=(99, 102, 241))
        try:
            font_title = ImageFont.truetype("arial.ttf", 42)
            font_body = ImageFont.truetype("arial.ttf", 24)
        except:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        draw.text((30, 25), f"{i+1}. {scene['title']}", font=font_title, fill=(255,255,255))
        wrapped = textwrap.wrap(scene['explain'], width=58)
        y = 130
        for line in wrapped[:6]:
            draw.text((30, y), line, font=font_body, fill=(220, 230, 255))
            y += 40

        draw.rectangle([(30, 430), (850, 700)], fill=(25, 35, 70), outline=(0, 220, 255), width=3)
        draw.text((50, 440), f"BOARD: {scene['diagram']}", font=font_body, fill=(0, 220, 255))
        draw.text((50, 475), f"--> {scene['diagram']}", font=font_body, fill=(255, 255, 255))
        draw.text((50, 515), f"Example: {scene['example']}", font=font_body, fill=(245, 158, 11))

        bg_path = os.path.join(temp_dir, f"bg_{i}.png")
        bg_img.save(bg_path)

        lang_code = 'hi' if 'hindi' in language.lower() or 'hinglish' in language.lower() else 'en'
        audio_path = os.path.join(temp_dir, f"aud_{i}.mp3")
        try:
            tts = gTTS(text=scene['explain'], lang=lang_code, slow=False)
            tts.save(audio_path)
            audio = AudioFileClip(audio_path)
            dur = audio.duration + 0.8
        except:
            audio = None
            dur = 5

        bg_clip = ImageClip(bg_path).set_duration(dur)
        bg_clip = bg_clip.resize(lambda t: 1 + 0.04 * math.sin(t * 0.6))

        tutor_clip = ImageClip(tutor_path).set_duration(dur).resize(0.65)
        tutor_clip = tutor_clip.set_position(lambda t: (980, 420 + 8 * math.sin(t * 2.5)))

        final_scene = CompositeVideoClip([bg_clip, tutor_clip])
        if audio:
            final_scene = final_scene.set_audio(audio)

        clips.append(final_scene)

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tempfile.gettempdir(), f"{topic.replace(' ','_')}_PREMIUM_TUTOR.mp4")
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
    return out_path, scenes
