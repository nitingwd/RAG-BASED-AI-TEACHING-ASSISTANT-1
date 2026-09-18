import os
import streamlit as st
import tempfile
import json
import textwrap
import re
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

def get_lang_code(lang_name):
    mapping = {"Hindi":"hi", "Gujarati":"gu", "Hinglish":"hi", "English":"en", "Marathi":"mr"}
    return mapping.get(lang_name, "hi")

def text_to_audio_file(text, language_name="Hinglish"):
    try:
        clean_text = re.sub(r'[^\w\s\.\,\!\?\:\-\(\)\u0900-\u097F\u0A80-\u0AFF]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()[:3500]
        if len(clean_text) < 5: clean_text = "Audio ke liye valid text nahi mila"
        lang_code = get_lang_code(language_name)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3"); tmp.close()
        try: tts = gTTS(text=clean_text, lang=lang_code, slow=False); tts.save(tmp.name)
        except: tts = gTTS(text=clean_text, lang='hi', slow=False); tts.save(tmp.name)
        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 1000: return tmp.name
        else: return None
    except: return None

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
    system = f"You are B.Tech Topper. Answer ONLY in {language}. Sirf PDF context se jawab do."
    if mode=="socratic": system = f"You are Socratic teacher. Answer in {language}."
    answer = llm.invoke(f"{system}\nContext:\n{context}\nQ: {query}").content
    st.session_state.history.append({"query": query, "answer": answer, "sources": [d.metadata for d in docs], "mode": mode})
    return answer, [d.metadata for d in docs]

def generate_quiz(num_q=5, language="Hinglish"):
    vb = st.session_state.get("vectordb")
    if not vb: return []
    docs = hybrid_search("important concepts", k=6)
    context = "\n".join([d.page_content[:1000] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3)
    prompt = f"""Create {num_q} MCQs Language: {language} Context: {context[:6000]} Return ONLY JSON array: [{{"question":"...","options":["a)...","b)...","c)...","d)..."],"answer":"a)...","explanation":"...","topic":"..."}}]"""
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; return json.loads(txt[s:e])
    except: return [{"question": f"Q{i+1} from PDF?", "options":["a) 1","b) 2","c) 3","d) 4"], "answer":"a) 1", "explanation":"PDF", "topic":"general"} for i in range(num_q)]

def check_quiz_answer(question, user_answer, correct_answer, topic="general"):
    ok = user_answer.strip().lower()[:2] == correct_answer.strip().lower()[:2]
    if not ok:
        wt = st.session_state.get("weak_topics", {}); wt[topic] = wt.get(topic, 0) + 1; st.session_state.weak_topics = wt
        return False, f"❌ Galat! Correct: {correct_answer}"
    else: return True, "✅ Sahi! Topper!"

def get_weak_topics(): return st.session_state.get("weak_topics", {})
def generate_summary(language="Hinglish"):
    docs = hybrid_search("complete summary", k=8); ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2).invoke(f"Summary in {language}:\n{ctx}").content
def predict_important_questions(language="Hinglish"):
    docs = hybrid_search("exam important", k=6); ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.3).invoke(f"10 Important Qs in {language}. Context:{ctx}").content
def load_conversation_history(): return st.session_state.get("history", [])
def story_mode_learning(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=8); ctx = "\n".join([d.page_content[:900] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.85).invoke(f"Topic {topic} ko story me badal do {language}. Context:{ctx[:7000]}").content
def generate_story_movie_script(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=6); ctx = "\n".join([d.page_content[:800] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Reel script {topic} {language}. Context:{ctx}").content
def build_project_guide(project_idea, budget="low", language="Hinglish"):
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.4).invoke(f"Project {project_idea} Budget {budget} guide {language}").content
def generate_podcast_script(topic, language="Hinglish"):
    docs = hybrid_search(topic, k=4); ctx = "\n".join([d.page_content[:700] for d in docs])
    return ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.8).invoke(f"Podcast {topic} {language}. Context:{ctx}").content
def generate_viva_questions(topic, num_q=10, language="Hinglish"):
    docs = hybrid_search(topic, k=6); ctx = "\n".join([d.page_content[:700] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"Topic:{topic} Language:{language} Context:{ctx} {num_q} viva JSON array q,a Only JSON."
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; return json.loads(txt[s:e])
    except: return [{"q": f"Explain {topic} Q {i+1}?", "a": "PDF"} for i in range(num_q)]
def verify_viva_answer(question, correct_ans, user_ans, language="Hinglish"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Q:{question} Correct:{correct_ans} Student:{user_ans} Return JSON verdict feedback"
    try: txt = llm.invoke(prompt).content; s = txt.find('{'); e = txt.rfind('}')+1; return json.loads(txt[s:e])
    except: return {"verdict": "False", "feedback": f"Correct: {correct_ans}"}
def create_ppt_file(topic, num_slides=10, language="Hinglish"):
    docs = hybrid_search(topic, k=8); ctx = "\n".join([d.page_content[:1200] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"Topic:{topic} Language:{language} Context:{ctx[:8000]} {num_slides} slides JSON title points diagram_text speaker_note Only JSON."
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; slides_data = json.loads(txt[s:e])
    except: slides_data = [{"title": topic, "points": ["Point 1","Point 2"], "diagram_text":"Diagram", "speaker_note":"Tip"}]
    from pptx import Presentation; from pptx.util import Inches, Pt; from pptx.dml.color import RGBColor
    prs = Presentation(); prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
    for i, sl in enumerate(slides_data[:num_slides]):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(249,250,255)
        header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.0)); header.fill.solid(); header.fill.fore_color.rgb=RGBColor(13,17,38)
        ht=slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(7), Inches(0.8)); ht.text_frame.text=f"{i+1}. {sl.get('title','')}"; ht.text_frame.paragraphs[0].font.size=Pt(19); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
        ct=slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(7.2), Inches(5.9)); tf=ct.text_frame; tf.word_wrap=True
        for pt in sl.get('points',[])[:6]:
            pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(12); pa.font.size=Pt(14)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx"); prs.save(tmp.name); return tmp.name
def transcribe_topic_with_language(audio_path):
    text = transcribe_audio(get_api_key(), audio_path)
    if not text: return None, "Hinglish"
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0)
    prompt = f"Extract topic and language from: '{text}'. Return JSON topic language only."
    try: res = llm.invoke(prompt).content; s = res.find('{'); e = res.rfind('}')+1; data = json.loads(res[s:e]); return data.get('topic', text), data.get('language', 'Hinglish')
    except: return text, "Hinglish"
def create_explainer_video(topic, language="Hinglish", duration_sec=150):
    if not VIDEO_AVAILABLE: return None, "Install gTTS, moviepy"
    api_key = get_api_key(); llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.2)
    docs = hybrid_search(topic, k=8)
    if not docs: return None, f"PDF me '{topic}' nahi mila."
    num_scenes = max(2, min(8, duration_sec // 30))
    ctx = "\n\n".join([f"DOC {i+1}: {d.page_content[:1000]}" for i, d in enumerate(docs)])
    prompt = f"Use PDF. Topic: {topic}, Language: {language}, Need {num_scenes} scenes, Duration {duration_sec} sec. Context: {ctx[:8000]} JSON array title explain diagram source Only JSON."
    try: txt = llm.invoke(prompt).content; s = txt.find('['); e = txt.rfind(']')+1; scenes = json.loads(txt[s:e])
    except: scenes = [{"title": f"{topic} Part {i+1}", "explain": f"{d.page_content[:380]}", "diagram": d.page_content[:120], "source": d.metadata.get('source','PDF')} for i, d in enumerate(docs[:num_scenes])]
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
        wrapped = textwrap.wrap(scene['explain'], width=58); y = 105
        for line in wrapped[:8]: draw.text((30, y), line, fill=(255,255,255)); y += 34
        bg_path = os.path.join(temp_dir, f"bg_{i}.png"); bg_img.save(bg_path)
        lang_code = get_lang_code(language); audio_path = os.path.join(temp_dir, f"aud_{i}.mp3")
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

# ========== RESUME + SOFTWARE - FINAL FIXED VERSION ==========
def generate_premium_resume_data(user_info, language="English"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"You are FAANG Resume Expert. JSON ENGLISH ONLY ASCII. User: {user_info} Return ONLY JSON: {{\"name\":\"\",\"role\":\"\",\"email\":\"\",\"phone\":\"\",\"linkedin\":\"\",\"github\":\"\",\"summary\":\"\",\"skills\":{{\"Languages\":[],\"Frontend\":[],\"Backend\":[],\"Tools\":[]}},\"experience\":[{{\"role\":\"\",\"company\":\"\",\"duration\":\"\",\"points\":[]}}],\"projects\":[{{\"name\":\"\",\"tech\":\"\",\"points\":[],\"link\":\"\"}}],\"education\":[{{\"degree\":\"\",\"college\":\"\",\"year\":\"\",\"cgpa\":\"\"}}],\"certifications\":[]}}"
    try: txt = llm.invoke(prompt).content; s=txt.find('{'); e=txt.rfind('}')+1; return json.loads(txt[s:e])
    except: return None

def create_premium_resume_pdf(resume_data):
    from fpdf import FPDF
    def clean(text):
        if not text: return ""
        text = str(text).encode('ascii','ignore').decode('ascii')
        text = re.sub(r'[^\x20-\x7E\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    pdf = FPDF('P','mm','A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    W = 190

    pdf.set_fill_color(13,17,38)
    pdf.rect(0,0,210,35,'F')
    name = clean(resume_data.get('name','NARESH')) or "NARESH KADIYA"
    role = clean(resume_data.get('role','Developer'))
    email = clean(resume_data.get('email',''))
    phone = clean(resume_data.get('phone',''))

    pdf.set_xy(10,8)
    pdf.set_font("Helvetica",'B',18)
    pdf.set_text_color(255,255,255)
    pdf.cell(W,10, name.upper()[:40], align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(10)
    pdf.set_font("Helvetica",'',9)
    pdf.set_text_color(200,220,255)
    pdf.cell(W,6, f"{role[:25]} | {email[:30]} | {phone[:15]}", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)

    def section(title):
        pdf.set_x(10)
        pdf.set_fill_color(224,231,255)
        pdf.set_font("Helvetica",'B',11)
        pdf.set_text_color(13,17,38)
        pdf.cell(W,8, f" {clean(title).upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def para(txt):
        txt = clean(txt)
        if not txt: return
        pdf.set_x(10)
        pdf.set_font("Helvetica",'',10)
        pdf.set_text_color(30,30,30)
        pdf.multi_cell(W,5, txt, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    section("Summary")
    para(resume_data.get('summary','Experienced developer'))

    section("Skills")
    skills_text = ""
    for k,v in resume_data.get('skills',{}).items():
        vv = [clean(x) for x in v if clean(x)]
        if vv: skills_text += f"{clean(k)}: {', '.join(vv[:6])}\n"
    para(skills_text or "MERN, Python, SQL")

    section("Experience")
    for exp in resume_data.get('experience',[])[:2]:
        pdf.set_x(10)
        pdf.set_font("Helvetica",'B',10)
        pdf.cell(W,6, f"{clean(exp.get('role','Dev'))} at {clean(exp.get('company','Company'))} ({clean(exp.get('duration','2023'))})", new_x="LMARGIN", new_y="NEXT")
        for p in exp.get('points',[])[:3]:
            p = clean(p)
            if p:
                pdf.set_x(12)
                pdf.set_font("Helvetica",'',9.5)
                pdf.multi_cell(W-2,5, f"- {p[:150]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    section("Projects")
    for proj in resume_data.get('projects',[])[:2]:
        pdf.set_x(10)
        pdf.set_font("Helvetica",'B',10)
        pdf.cell(W,6, f"{clean(proj.get('name','Project'))} | {clean(proj.get('tech','MERN'))}", new_x="LMARGIN", new_y="NEXT")
        for p in proj.get('points',[])[:3]:
            p = clean(p)
            if p:
                pdf.set_x(12)
                pdf.set_font("Helvetica",'',9.5)
                pdf.multi_cell(W-2,5, f"- {p[:150]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    section("Education")
    for edu in resume_data.get('education',[])[:2]:
        para(f"{clean(edu.get('degree','B.Tech'))} - {clean(edu.get('college','GTU'))} ({clean(edu.get('year','2024'))})")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp.name)
    return tmp.name

def generate_software_project(requirement, tech_stack="MERN", language="English"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"Senior Architect. Requirement: {requirement} Tech: {tech_stack} Create JSON project_name description tech_stack files path content setup_steps features Only JSON ASCII."
    try: txt=llm.invoke(prompt).content; s=txt.find('{'); e=txt.rfind('}')+1; return json.loads(txt[s:e])
    except: return None

def create_project_zip(project_data):
    import zipfile
    temp_dir=tempfile.mkdtemp()
    project_name=project_data.get('project_name','project').replace(' ','_')
    project_name = re.sub(r'[^a-zA-Z0-9_]', '', project_name) or "project"
    for f in project_data.get('files',[]):
        fp=os.path.join(temp_dir,project_name,f['path']); os.makedirs(os.path.dirname(fp),exist_ok=True)
        with open(fp,'w',encoding='utf-8', errors='ignore') as out: out.write(f['content'])
    zip_path=os.path.join(tempfile.gettempdir(),f"{project_name}_PRODUCTION.zip")
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as zipf:
        for root,dirs,files in os.walk(os.path.join(temp_dir,project_name)):
            for file in files:
                full=os.path.join(root,file); arc=os.path.relpath(full,temp_dir); zipf.write(full,arc)
    return zip_path
