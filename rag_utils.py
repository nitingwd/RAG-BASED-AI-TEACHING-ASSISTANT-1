import os
import streamlit as st
import tempfile
import json
import textwrap
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from dotenv import load_dotenv
from groq import Groq

try:
    from gtts import gTTS
    from PIL import Image, ImageDraw
    from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
    if not hasattr(Image, 'ANTIALIAS'):
        try:
            Image.ANTIALIAS = Image.Resampling.LANCZOS
        except:
            Image.ANTIALIAS = Image.LANCZOS
    VIDEO_AVAILABLE = True
except:
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
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'}, encode_kwargs={'normalize_embeddings': False})

def transcribe_audio(api_key, audio_path):
    try:
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as f:
            tr = client.audio.transcriptions.create(file=(os.path.basename(audio_path), f.read()), model="whisper-large-v3-turbo", language="hi")
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
            if ext == ".pdf": loader = PyPDFLoader(path)
            elif ext == ".csv": loader = CSVLoader(path)
            elif ext == ".txt": loader = TextLoader(path)
            else: continue
            loaded = loader.load()
            for d in loaded: d.metadata["source"] = file.name
            docs.extend([d for d in loaded if d.page_content.strip()])
        finally:
            if os.path.exists(path): os.remove(path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    vectordb = Chroma.from_documents(chunks, get_embeddings())
    st.session_state.vectordb = vectordb
    st.session_state.history = []
    if "weak_topics" not in st.session_state: st.session_state.weak_topics = {}
    st.success(f"Ho gaya! {len(chunks)} chunks.")

def hybrid_search(query, k=3):
    vb = st.session_state.get("vectordb")
    if not vb: return []
    return vb.similarity_search(query, k=k)

def ask_question(query, k=3, mode="normal"):
    api_key = get_api_key()
    if not api_key: return "GROQ_API_KEY nahi mili.", []
    vb = st.session_state.get("vectordb")
    if not vb: return "Pehle Submit & Process dabao.", []
    docs = hybrid_search(query, k=k)
    if not docs: return "Jawab nahi mila.", []
    context = "\n\n".join([f"[{d.metadata.get('source','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    system = "Socratic teacher ho. Seedha answer mat do, sawal pucho." if mode=="socratic" else "B.Tech teaching assistant ho. Sirf context se Hinglish me jawab do."
    answer = llm.invoke(f"{system}\nContext:\n{context}\nQ: {query}").content
    st.session_state.history.append({"query": query, "answer": answer, "sources": [d.metadata for d in docs], "mode": mode})
    return answer, [d.metadata for d in docs]

def generate_quiz(num_q=5):
    vb = st.session_state.get("vectordb")
    if not vb: return None, "Pehle docs upload karo."
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

def get_weak_topics(): return st.session_state.get("weak_topics", {})
def generate_summary():
    docs = hybrid_search("summary", k=8)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"1-page Hinglish summary do:\n{ctx}").content
def predict_important_questions():
    docs = hybrid_search("exam important", k=6)
    ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key()).invoke(f"10 Important Questions with marks predict karo:\n{ctx}").content
def load_conversation_history(): return st.session_state.get("history", [])
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
    prompt = f"""Topic: {topic}\nContext: {ctx[:7000]}\nCreate {num_slides} slides JSON: [{{"title":"","points":["","","",""]}}] Only JSON."""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [{"title": topic, "points": ["Point 1","Point 2","Point 3","Point 4"]}]
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    prs = Presentation()
    prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
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
    if not text: return None, "Hinglish"
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Extract topic and language from: '{text}'. Return JSON {{\"topic\":\"...\",\"language\":\"Hindi/English/Hinglish/Marathi\"}} only."
    try:
        res = llm.invoke(prompt).content
        s = res.find('{'); e = res.rfind('}')+1
        data = json.loads(res[s:e])
        return data.get('topic', text), data.get('language', 'Hinglish')
    except:
        return text, "Hinglish"

# ================= V5 - 2.5 MIN SUPERFAST (5 SCENES) =================
def create_explainer_video(topic, language="Hinglish", duration_sec=150):
    if not VIDEO_AVAILABLE:
        return None, "Install gTTS, moviepy, Pillow"
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.85)
    docs = hybrid_search(topic, k=4)
    ctx = "\n".join([d.page_content[:600] for d in docs]) if docs else ""
    prompt = f"""Topic: {topic}, Lang: {language}, Context: {ctx[:3000]}
Create 5 scenes JSON for 2.5 MIN video. Each object:
{{"title":"Title", "story_character":"Tutor/Rohit", "explain":"90-110 words full story explanation in {language} like 'Dekho Rohit...' deep concept", "dialogue":"1 line dialogue", "diagram":"Customer->Queue->CPU", "visual_action":"arrow moves", "real_life_story":"Chai shop"}}
Return ONLY JSON array 5 objects, language {language}."""

    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        scenes = json.loads(txt[s:e])
    except:
        scenes = [
            {"title": f"Kya hai {topic}?", "story_character": "AI Tutor", "explain": f"Dekho dosto {topic} ko chai ki dukaan ki kahani se samjho. 50 customer ek saath aate hain, ek dukaan wala kaise manage karta hai? Yahi concept computer me {topic} kehlata hai.", "dialogue": "Rohit: Sir ye kya hai? Tutor: Chalo kahani se samjhte hain!", "diagram": "50 Customers -> Queue -> 1 Shopkeeper", "visual_action": "Queue forms", "real_life_story": "Chai shop = OS"},
            {"title": "Andar Kaise Kaam Karta?", "story_character": "Tutor + Rohit", "explain": f"Har customer ko token milta hai jise PCB kehte hain. Isme uska naam, kaam kitna hua hai sab likha hota hai. OS token dekh ke decide karta hai kisko pehle chai deni hai. Yehi PCB ka kaam hai.", "dialogue": "Rohit: PCB matlab token? Tutor: Bilkul sahi!", "diagram": "Token -> PCB Structure -> RAM", "visual_action": "Token slides", "real_life_story": "Token = PCB"},
            {"title": "Bheed Manage - Scheduling", "story_character": "AI Tutor", "explain": f"50 logo ko ek saath nahi, thoda-thoda time do. Round Robin me har ek ko 30 sec do, fir next ko. Computer me har app ko 10ms CPU milta hai. Isse sab khush rehte hain, koi hang nahi hota. Isko Scheduling kehte hain.", "dialogue": "Tutor: Sabko thoda time do! Rohit: Samajh gaya!", "diagram": "C1(30s)->C2->C3->C1 circular", "visual_action": "Timer rotates", "real_life_story": "Time sharing"},
            {"title": "Deadlock - Sab Atak Gaye", "story_character": "Two Customers", "explain": f"Customer A ne table pakda, spoon maang raha hai. B ne spoon pakda, table maang raha hai. Dono atak gaye! Yahi Deadlock hai. Computer me ek process printer pakad ke scanner maang raha hai, dusra scanner pakad ke printer. System hang ho jata hai.", "dialogue": "A: Spoon do! B: Table do! Tutor: Yehi deadlock hai!", "diagram": "A waits B, B waits A - RED CROSS", "visual_action": "Stuck animation", "real_life_story": "Dono wait = deadlock"},
            {"title": "Final Solution + Summary", "story_character": "AI Tutor Final", "explain": f"Solution simple hai: ek ko bahar nikalo, ya pehle se rule banao. Banker algorithm check karta hai loan dene se pehle deadlock hoga ya nahi. Final me yaad rakho {topic} ka matlab hai smart management. Chai ki dukaan se Google tak same rule lagta hai. Exam me ye kahani likh do, full marks pakke!", "dialogue": "Tutor: Samajh aaya? Rohit: Haan sir, kabhi nahi bhoolunga!", "diagram": "Mind Map: PCB->Scheduling->Deadlock->Solution", "visual_action": "Mind map grows, confetti", "real_life_story": "Kahani khatam, concept clear"}
        ]

    temp_dir = tempfile.mkdtemp()
    clips = []

    def fast_avatar(name, bg_color):
        img = Image.new('RGB', (300, 300), bg_color)
        d = ImageDraw.Draw(img)
        d.ellipse([(30,20),(270,240)], fill=(255,220,180), outline=(255,255,255), width=2)
        d.ellipse([(85,90),(115,120)], fill=(0,0,0))
        d.ellipse([(185,90),(215,120)], fill=(0,0,0))
        d.text((90, 250), name, fill=(255,255,255))
        p = os.path.join(temp_dir, f"{name}.png")
        img.save(p)
        return p

    tutor_path = fast_avatar("TUTOR", (99,102,241))
    student_path = fast_avatar("ROHIT", (25,35,70))

    for i, scene in enumerate(scenes):
        W, H = 1280, 720
        bg_img = Image.new('RGB', (W, H), (13,17,38))
        draw = ImageDraw.Draw(bg_img)
        draw.rectangle([(0,0),(W,80)], fill=(99,102,241))
        draw.text((20,10), f"PART {i+1}/5: {scene['title']}", fill=(255,255,255))
        draw.text((20,45), f"{scene['story_character']} • {scene['dialogue'][:80]}", fill=(220,230,255))
        draw.rectangle([(20,95),(850,470)], fill=(25,35,70), outline=(70,80,130), width=1)
        wrapped = textwrap.wrap(scene['explain'], width=60)
        y = 105
        for line in wrapped[:7]:
            draw.text((30, y), line, fill=(255,255,255))
            y += 36
        draw.rectangle([(20,480),(850,545)], fill=(245,158,11))
        draw.text((30,495), f"💬 {scene['dialogue'][:85]}", fill=(0,0,0))
        draw.rectangle([(870,95),(1260,545)], fill=(10,20,45), outline=(0,220,255), width=2)
        draw.text((880,105), "VISUAL BOARD", fill=(0,220,255))
        diag = textwrap.wrap(scene['diagram'], width=30)
        yy = 135
        for dline in diag[:5]:
            draw.text((880, yy), f"→ {dline}", fill=(200,255,200))
            yy += 26
        draw.text((880, yy+10), f"Story: {scene['real_life_story'][:45]}", fill=(16,185,129))
        draw.text((880, yy+35), f"Action: {scene['visual_action'][:45]}", fill=(236,72,153))
        bg_path = os.path.join(temp_dir, f"bg_{i}.png")
        bg_img.save(bg_path)

        lang_code = 'hi' if 'hindi' in language.lower() or 'hinglish' in language.lower() else 'en'
        audio_path = os.path.join(temp_dir, f"aud_{i}.mp3")
        try:
            tts = gTTS(text=scene['explain'], lang=lang_code, slow=False)
            tts.save(audio_path)
            audio = AudioFileClip(audio_path)
            dur = audio.duration + 0.3
        except:
            audio = None
            dur = 30

        bg_clip = ImageClip(bg_path).set_duration(dur)
        tutor_clip = ImageClip(tutor_path).set_duration(dur).resize(0.42).set_position((30, 555))
        stud_clip = ImageClip(student_path).set_duration(dur).resize(0.36).set_position((300, 570))
        final_scene = CompositeVideoClip([bg_clip, tutor_clip, stud_clip])
        if audio:
            final_scene = final_scene.set_audio(audio)
        clips.append(final_scene)

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tempfile.gettempdir(), f"{topic.replace(' ','_')}_2MIN.mp4")
    final.write_videofile(out_path, fps=12, codec='libx264', audio_codec='aac', preset='ultrafast', threads=4, verbose=False, logger=None)
    return out_path, scenes
