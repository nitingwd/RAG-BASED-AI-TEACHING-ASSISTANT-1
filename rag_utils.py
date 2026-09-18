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
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
    if not hasattr(Image, 'ANTIALIAS'):
        try: Image.ANTIALIAS = Image.Resampling.LANCZOS
        except: Image.ANTIALIAS = Image.LANCZOS
    VIDEO_AVAILABLE = True
except:
    VIDEO_AVAILABLE = False

load_dotenv()

def get_api_key():
    try:
        if "GROQ_API_KEY" in st.secrets: return st.secrets["GROQ_API_KEY"]
    except: pass
    return os.getenv("GROQ_API_KEY")

@st.cache_resource
def get_embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'}, encode_kwargs={'normalize_embeddings': False})

# ========== NEW V11 HELPERS ==========
def get_lang_code(lang_name):
    mapping = {"Hindi":"hi", "Gujarati":"gu", "Hinglish":"hi", "English":"en", "Marathi":"mr"}
    return mapping.get(lang_name, "hi")

def text_to_audio_file(text, language_name="Hinglish"):
    try:
        if not VIDEO_AVAILABLE: return None
        lang_code = get_lang_code(language_name)
        clean_text = text[:4000]
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except:
        return None

def transcribe_audio(api_key, audio_path):
    try:
        client = Groq(api_key=api_key)
        with open(audio_path, "rb") as f:
            tr = client.audio.transcriptions.create(file=(os.path.basename(audio_path), f.read()), model="whisper-large-v3-turbo", language="hi")
        return tr.text
    except Exception as e:
        st.error(f"Voice error: {e}"); return None

def process_files(files, chunk_size=1000, chunk_overlap=100):
    if not files: st.warning("File upload karo."); return
    docs = []
    for file in files:
        ext = os.path.splitext(file.name)[-1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file.getvalue()); path = tmp.name
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
    st.session_state.vectordb = vectordb; st.session_state.history = []
    if "weak_topics" not in st.session_state: st.session_state.weak_topics = {}
    st.success(f"✅ Ho gaya! {len(chunks)} chunks | All FREE")

def hybrid_search(query, k=3):
    vb = st.session_state.get("vectordb")
    if not vb: return []
    return vb.similarity_search(query, k=k)

def ask_question(query, k=3, mode="normal", language="Hinglish"):
    api_key = get_api_key()
    if not api_key: return "GROQ_API_KEY nahi mili.", []
    vb = st.session_state.get("vectordb")
    if not vb: return "Pehle File Upload karo.", []
    docs = hybrid_search(query, k=k)
    if not docs: return "PDF me nahi mila.", []
    context = "\n\n".join([f"[{d.metadata.get('source','?')}] {d.page_content}" for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0)
    system = f"You are B.Tech Topper. Answer ONLY in {language}. If {language} is Gujarati, answer in Gujarati. If Hindi, in Hindi. Hinglish = Hindi+English mix. Sirf PDF context se jawab do. Formula exact PDF se do."
    if mode=="socratic": system = f"You are Socratic teacher. Answer in {language}. Sirf PDF se sawal puch ke sikhhao."
    answer = llm.invoke(f"{system}\nContext:\n{context}\nQ: {query}").content
    st.session_state.history.append({"query": query, "answer": answer, "sources": [d.metadata for d in docs], "mode": mode})
    return answer, [d.metadata for d in docs]

def generate_quiz(num_q=5, language="Hinglish"):
    vb = st.session_state.get("vectordb")
    if not vb: return []
    docs = hybrid_search("important concepts definitions formula", k=6)
    context = "\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3)
    prompt = f"""
Based ONLY on PDF Context, create {num_q} MCQs.
Language: {language}
Context: {context[:6000]}

Return ONLY JSON array:
[{{"question":"...","options":["a)...","b)...","c)...","d)..."],"answer":"a)...","explanation":"PDF se...","topic":"chapter name"}}]
No extra text.
"""
    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        data = json.loads(txt[s:e])
        return data
    except:
        return [{"question": f"Q{i+1} from PDF - {language} me?", "options":["a) Option 1","b) Option 2","c) Option 3","d) Option 4"], "answer":"a) Option 1", "explanation":"As per PDF", "topic":"general"} for i in range(num_q)]

def check_quiz_answer(question, user_answer, correct_answer, topic="general"):
    ok = user_answer.strip().lower()[:2] == correct_answer.strip().lower()[:2]
    if not ok:
        wt = st.session_state.get("weak_topics", {}); wt[topic] = wt.get(topic, 0) + 1; st.session_state.weak_topics = wt
        return False, f"❌ Galat! Correct: {correct_answer}"
    else:
        return True, "✅ Bilkul sahi! 🔥 Topper!"

def get_weak_topics(): return st.session_state.get("weak_topics", {})

def generate_summary(language="Hinglish"):
    docs = hybrid_search("complete summary important points", k=8); ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2).invoke(f"Context se 1-page exam-ready summary banao in {language} language. Points, formulas exact PDF se:\n{ctx}").content

def predict_important_questions(language="Hinglish"):
    docs = hybrid_search("exam important questions previous year", k=6); ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3).invoke(f"Context se 10 Most Important Questions predict karo with Marks. Language: {language}. GTU/SPU pattern. Context:{ctx}").content

def load_conversation_history(): return st.session_state.get("history", [])

def story_mode_learning(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=8); ctx = "\n".join([d.page_content[:900] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.85)
    prompt = f"Topic {topic} ko Bollywood Movie Story me badal do. Language: {language}. 5 Scenes, characters Rancho, Raju, Virus. Full concept from PDF. Context:{ctx[:7000]}. Output in {language}."
    return llm.invoke(prompt).content

def generate_story_movie_script(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=6); ctx = "\n".join([d.page_content[:800] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8)
    return llm.invoke(f"Topic {topic} pe Viral Reel script banao in {language}. 5 scenes, hook, CTA. Context:{ctx}").content

def build_project_guide(project_idea, budget="low", language="Hinglish"):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4).invoke(f"Project Idea:{project_idea} Budget:{budget} Complete guide in {language}. Components, Circuit, Code, Working, Viva Qs. Context PDF based.").content

def generate_podcast_script(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=4); ctx = "\n".join([d.page_content[:700] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Topic {topic} pe 2 doston (Naresh aur Rohit) ka 3-min {language} podcast script banao. Full explanation with concept from PDF. Context:{ctx}. Output in {language}.").content

def generate_viva_questions(topic, num_q=10, language="Hinglish"):
    docs = hybrid_search(topic, k=6); ctx = "\n".join([d.page_content[:700] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"Topic:{topic} Language:{language}\nContext:{ctx}\n{num_q} viva questions banao JSON array: {{\"q\":\"question from PDF in {language}\",\"a\":\"correct answer from PDF in {language}\"}}\nOnly JSON."
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; return json.loads(txt[s:e])
    except: return [{"q": f"Explain {topic} - Q {i+1}?", "a": "As per PDF"} for i in range(num_q)]

def verify_viva_answer(question, correct_ans, user_ans, language="Hinglish"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Q:{question}\nCorrect:{correct_ans}\nStudent:{user_ans}\nLanguage:{language}\nReturn ONLY JSON {{\"verdict\":\"True/False\", \"feedback\":\"{language} me feedback + correct answer\"}}"
    try: txt = llm.invoke(prompt).content; s = txt.find('{'); e = txt.rfind('}')+1; return json.loads(txt[s:e])
    except: return {"verdict": "False", "feedback": f"Correct: {correct_ans}"}

def create_ppt_file(topic, num_slides=10, language="Hinglish"):
    docs = hybrid_search(topic, k=8); ctx = "\n".join([d.page_content[:1200] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"Topic:{topic} Language:{language}\nContext:{ctx[:8000]}\nCreate {num_slides} slides JSON in {language}: [{{\"title\":\"\",\"points\":[\"\",\"\",\"\",\"\"],\"diagram_text\":\"visual from PDF\",\"speaker_note\":\"viva tip\"}}] Only JSON."
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; slides_data = json.loads(txt[s:e])
    except: slides_data = [{"title": topic, "points": ["Point 1 from PDF","Point 2","Point 3","Point 4"], "diagram_text":"Diagram", "speaker_note":"Tip"}]
    from pptx import Presentation; from pptx.util import Inches, Pt; from pptx.dml.color import RGBColor
    prs = Presentation(); prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
    for i, sl in enumerate(slides_data[:num_slides]):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(249,250,255)
        header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.0))
        header.fill.solid(); header.fill.fore_color.rgb=RGBColor(13,17,38); header.line.fill.background()
        ht=slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(7), Inches(0.8))
        ht.text_frame.text=f"{i+1}. {sl.get('title','')}"; ht.text_frame.paragraphs[0].font.size=Pt(19); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
        ct=slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(7.2), Inches(5.9)); tf=ct.text_frame; tf.word_wrap=True
        for pt in sl.get('points',[])[:6]:
            pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(12); pa.font.size=Pt(14); pa.font.color.rgb=RGBColor(30,35,60)
        vb=slide.shapes.add_shape(1, Inches(8.8), Inches(1.4), Inches(4), Inches(5.5))
        vb.fill.solid(); vb.fill.fore_color.rgb=RGBColor(224,231,255)
        vtx=slide.shapes.add_textbox(Inches(9), Inches(1.6), Inches(3.6), Inches(5))
        vtx.text_frame.text=f"📊 VISUAL\n{sl.get('diagram_text','')}\n\n💡 {sl.get('speaker_note','')}"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx"); prs.save(tmp.name); return tmp.name

def transcribe_topic_with_language(audio_path):
    text = transcribe_audio(get_api_key(), audio_path)
    if not text: return None, "Hinglish"
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Extract topic and language from: '{text}'. Return JSON {{\"topic\":\"...\",\"language\":\"Hindi/English/Hinglish/Gujarati/Marathi\"}} only."
    try: res = llm.invoke(prompt).content; s = res.find('{'); e = res.rfind('}')+1; data = json.loads(res[s:e]); return data.get('topic', text), data.get('language', 'Hinglish')
    except: return text, "Hinglish"

def create_explainer_video(topic, language="Hinglish", duration_sec=150):
    if not VIDEO_AVAILABLE: return None, "Install gTTS, moviepy, Pillow"
    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.2)
    docs = hybrid_search(topic, k=8)
    if not docs: return None, f"Tere PDF me '{topic}' nahi mila."

    # DURATION LOGIC - User selects
    num_scenes = max(2, min(8, duration_sec // 30))
    if duration_sec <= 40: num_scenes = 2
    elif duration_sec <= 90: num_scenes = 3
    elif duration_sec <= 160: num_scenes = 5
    else: num_scenes = 7

    ctx = "\n\n".join([f"DOC {i+1}: {d.page_content[:1000]}" for i, d in enumerate(docs)])
    prompt = f"""Use ONLY PDF Context. No hallucination.
Topic: {topic}, Language: {language}, Need {num_scenes} scenes, Total Duration {duration_sec} sec.
PDF Context: {ctx[:8000]}

Create {num_scenes} scenes JSON accurate from PDF. Each:
{{"title":"Sub-topic from PDF", "explain":"{90 if duration_sec<60 else 110} words in {language} using EXACT definitions/formulas from PDF. Start 'PDF ke according...'", "diagram":"Definition from PDF", "source":"PDF source"}}

Return ONLY JSON array {num_scenes} objects."""

    try:
        txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; scenes = json.loads(txt[s:e])
    except:
        scenes = [{"title": f"{topic} - Part {i+1}", "explain": f"PDF ke according {d.page_content[:380]}", "diagram": d.page_content[:120], "source": d.metadata.get('source','PDF')} for i, d in enumerate(docs[:num_scenes])]

    temp_dir = tempfile.mkdtemp(); clips = []
    def fast_avatar(name, bg_color):
        img = Image.new('RGB', (300, 300), bg_color); d = ImageDraw.Draw(img)
        d.ellipse([(30,20),(270,240)], fill=(255,220,180), outline=(255,255,255), width=2)
        d.ellipse([(85,90),(115,120)], fill=(0,0,0)); d.ellipse([(185,90),(215,120)], fill=(0,0,0))
        d.text((90, 250), name, fill=(255,255,255)); p = os.path.join(temp_dir, f"{name}.png"); img.save(p); return p
    tutor_path = fast_avatar("TUTOR", (99,102,241)); student_path = fast_avatar("STUDENT", (25,35,70))

    for i, scene in enumerate(scenes[:num_scenes]):
        W, H = 1280, 720; bg_img = Image.new('RGB', (W, H), (13,17,38)); draw = ImageDraw.Draw(bg_img)
        draw.rectangle([(0,0),(W,80)], fill=(99,102,241)); draw.text((20,15), f"PART {i+1}/{num_scenes}: {scene['title'][:60]}", fill=(255,255,255))
        draw.text((20,48), f"Source: {scene.get('source','PDF')[:70]} | {language} | {duration_sec}s", fill=(220,230,255))
        draw.rectangle([(20,95),(850,470)], fill=(25,35,70), outline=(70,80,130), width=1)
        wrapped = textwrap.wrap(scene['explain'], width=58); y = 105
        for line in wrapped[:8]: draw.text((30, y), line, fill=(255,255,255)); y += 34
        draw.rectangle([(20,480),(850,545)], fill=(245,158,11)); draw.text((30,495), f"PDF: {scene['diagram'][:90]}", fill=(0,0,0))
        draw.rectangle([(870,95),(1260,545)], fill=(10,20,45), outline=(0,220,255), width=2)
        draw.text((880,105), "PDF BOARD", fill=(0,220,255))
        diag = textwrap.wrap(scene['diagram'], width=30); yy = 135
        for dline in diag[:5]: draw.text((880, yy), f"→ {dline}", fill=(200,255,200)); yy += 26
        bg_path = os.path.join(temp_dir, f"bg_{i}.png"); bg_img.save(bg_path)
        lang_code = get_lang_code(language)
        audio_path = os.path.join(temp_dir, f"aud_{i}.mp3")
        try: tts = gTTS(text=scene['explain'], lang=lang_code, slow=False); tts.save(audio_path); audio = AudioFileClip(audio_path); dur = audio.duration + 0.4
        except: audio = None; dur = duration_sec / num_scenes
        bg_clip = ImageClip(bg_path).set_duration(dur)
        tutor_clip = ImageClip(tutor_path).set_duration(dur).resize(0.42).set_position((30, 555))
        stud_clip = ImageClip(student_path).set_duration(dur).resize(0.36).set_position((300, 570))
        final_scene = CompositeVideoClip([bg_clip, tutor_clip, stud_clip])
        if audio: final_scene = final_scene.set_audio(audio)
        clips.append(final_scene)
    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tempfile.gettempdir(), f"{topic.replace(' ','_')}_{language}_{duration_sec}s.mp4")
    final.write_videofile(out_path, fps=12, codec='libx264', audio_codec='aac', preset='ultrafast', threads=4, verbose=False, logger=None)
    return out_path, scenes
