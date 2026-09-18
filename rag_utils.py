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

# ========== PREMIUM RESUME V13.1 - PHOTO + THEME + SIDEBAR ==========
def generate_premium_resume_data(user_info, language="English"):
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.2)
    prompt = f"You are FAANG Resume Expert. User: {user_info} Create JSON ENGLISH ASCII ONLY: {{\"name\":\"\",\"role\":\"\",\"email\":\"\",\"phone\":\"\",\"location\":\"\",\"linkedin\":\"\",\"github\":\"\",\"portfolio\":\"\",\"summary\":\"\",\"skills\":{{\"Languages\":[],\"Frontend\":[],\"Backend\":[],\"Tools\":[],\"Database\":[]}},\"experience\":[{{\"role\":\"\",\"company\":\"\",\"duration\":\"\",\"location\":\"\",\"points\":[]}}],\"projects\":[{{\"name\":\"\",\"tech\":\"\",\"points\":[],\"link\":\"\"}}],\"education\":[{{\"degree\":\"\",\"college\":\"\",\"year\":\"\",\"cgpa\":\"\"}}],\"certifications\":[],\"awards\":[],\"languages\":[],\"references\":[{{\"name\":\"\",\"role\":\"\",\"company\":\"\",\"contact\":\"\"}}]}} Only JSON"
    try: txt = llm.invoke(prompt).content; s=txt.find('{'); e=txt.rfind('}')+1; return json.loads(txt[s:e])
    except: return None

def create_premium_resume_pdf(resume_data, photo_path=None, theme_color="0D1126"):
    from fpdf import FPDF
    def clean(t):
        if not t: return ""
        t = str(t).encode('ascii','ignore').decode('ascii')
        t = re.sub(r'[^\x20-\x7E\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t)
        return t.strip()

    themes = {
        "0D1126": {"primary":(13,17,38), "accent":(99,102,241), "light":(224,231,255)},
        "0F172A": {"primary":(15,23,42), "accent":(14,165,233), "light":(186,230,253)},
        "1E293B": {"primary":(30,41,59), "accent":(16,185,129), "light":(167,243,208)},
        "7C2D12": {"primary":(124,45,18), "accent":(249,115,22), "light":(254,215,170)},
        "581C87": {"primary":(88,28,135), "accent":(168,85,247), "light":(233,213,255)},
    }
    colors = themes.get(theme_color, themes["0D1126"])

    pdf = FPDF('P','mm','A4')
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()
    W=210; H=297; SIDEBAR_W=70

    pdf.set_fill_color(*colors["primary"])
    pdf.rect(0,0,SIDEBAR_W,H,'F')
    y=8
    if photo_path and os.path.exists(photo_path):
        try:
            im = Image.open(photo_path).convert("RGB")
            im = im.resize((400,400))
            temp_photo = os.path.join(tempfile.gettempdir(), "resume_photo.jpg")
            im.save(temp_photo)
            pdf.image(temp_photo, x=15, y=y, w=40, h=40)
            y+=48
        except: y+=5

    def sidebar_title(title, y_pos):
        pdf.set_xy(4, y_pos)
        pdf.set_font("Helvetica",'B',9)
        pdf.set_text_color(*colors["accent"])
        pdf.cell(SIDEBAR_W-8,6, clean(title).upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(4); pdf.set_draw_color(*colors["accent"]); pdf.line(4, pdf.get_y(), SIDEBAR_W-8, pdf.get_y()); pdf.ln(2)
        return pdf.get_y()

    def sidebar_text(txt, y_pos, bold=False):
        pdf.set_xy(4, y_pos)
        pdf.set_font("Helvetica",'B' if bold else '',7.5)
        pdf.set_text_color(220,230,255)
        pdf.multi_cell(SIDEBAR_W-8,4, clean(txt)[:180], new_x="LMARGIN", new_y="NEXT")
        return pdf.get_y()+1

    y=sidebar_title("Contact", y)
    y=sidebar_text(clean(resume_data.get('email','')), y)
    y=sidebar_text(clean(resume_data.get('phone','')), y)
    y=sidebar_text(clean(resume_data.get('location','')), y)
    y=sidebar_text(clean(resume_data.get('linkedin','')), y)
    y=sidebar_text(clean(resume_data.get('github','')), y)
    y=sidebar_text(clean(resume_data.get('portfolio','')), y)
    y+=3
    y=sidebar_title("Skills", y)
    for cat, vals in resume_data.get('skills',{}).items():
        vals_clean=[clean(v) for v in vals if clean(v)][:6]
        if not vals_clean: continue
        y=sidebar_text(f"{clean(cat)}:", y, bold=True)
        for v in vals_clean:
            pdf.set_x(6); pdf.set_font("Helvetica",'',7); pdf.set_text_color(255,255,255)
            pdf.cell(SIDEBAR_W-10,4, f"- {v[:22]}", new_x="LMARGIN", new_y="NEXT"); y=pdf.get_y()
        y+=1
    y=sidebar_title("Education", y)
    for edu in resume_data.get('education',[])[:2]:
        y=sidebar_text(clean(edu.get('degree','')), y, bold=True)
        y=sidebar_text(clean(edu.get('college','')), y)
        y=sidebar_text(f"{clean(edu.get('year',''))} {clean(edu.get('cgpa',''))}", y); y+=1
    if resume_data.get('languages'):
        y=sidebar_title("Languages", y)
        for lang in resume_data.get('languages',[])[:4]:
            y=sidebar_text(f"- {lang}", y)

    main_x=SIDEBAR_W+4; main_w=W-SIDEBAR_W-8
    pdf.set_xy(main_x,10)
    pdf.set_font("Helvetica",'B',20)
    pdf.set_text_color(*colors["primary"])
    pdf.cell(main_w,10, clean(resume_data.get('name','NARESH')).upper()[:35], new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(main_x); pdf.set_font("Helvetica",'B',11); pdf.set_text_color(*colors["accent"])
    pdf.cell(main_w,6, clean(resume_data.get('role','Developer')).upper()[:45], new_x="LMARGIN", new_y="NEXT"); pdf.ln(3)

    def main_section(title):
        pdf.set_x(main_x); pdf.set_fill_color(*colors["light"])
        pdf.set_font("Helvetica",'B',10); pdf.set_text_color(*colors["primary"])
        pdf.cell(main_w,7, f" {clean(title).upper()}", fill=True, new_x="LMARGIN", new_y="NEXT"); pdf.ln(1)

    def main_para(txt):
        pdf.set_x(main_x); pdf.set_font("Helvetica",'',9.5); pdf.set_text_color(40,40,40)
        pdf.multi_cell(main_w,4.5, clean(txt)[:600], new_x="LMARGIN", new_y="NEXT"); pdf.ln(1)

    main_section("Summary"); main_para(resume_data.get('summary','Developer'))
    main_section("Experience")
    for exp in resume_data.get('experience',[])[:3]:
        pdf.set_x(main_x); pdf.set_font("Helvetica",'B',9.5); pdf.set_text_color(20,20,20)
        pdf.cell(main_w,5, f"{clean(exp.get('role',''))} | {clean(exp.get('company',''))}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(main_x); pdf.set_font("Helvetica",'I',7.5); pdf.set_text_color(100,100,100)
        pdf.cell(main_w,4, f"{clean(exp.get('duration',''))} | {clean(exp.get('location',''))}", new_x="LMARGIN", new_y="NEXT")
        for p in exp.get('points',[])[:3]:
            p=clean(p)
            if p:
                pdf.set_x(main_x+2); pdf.set_font("Helvetica",'',8.5); pdf.set_text_color(50,50,50)
                pdf.multi_cell(main_w-2,4, f"• {p[:150]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    main_section("Projects")
    for proj in resume_data.get('projects',[])[:3]:
        pdf.set_x(main_x); pdf.set_font("Helvetica",'B',9.5)
        pdf.cell(main_w,5, f"{clean(proj.get('name',''))} | {clean(proj.get('tech',''))}", new_x="LMARGIN", new_y="NEXT")
        for p in proj.get('points',[])[:2]:
            p=clean(p)
            if p:
                pdf.set_x(main_x+2); pdf.set_font("Helvetica",'',8.5)
                pdf.multi_cell(main_w-2,4, f"• {p[:150]}", new_x="LMARGIN", new_y="NEXT")
        if proj.get('link'):
            pdf.set_x(main_x+2); pdf.set_font("Helvetica",'',7); pdf.set_text_color(*colors["accent"])
            pdf.cell(main_w,3, f"Link: {clean(proj.get('link',''))[:60]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    if resume_data.get('certifications'):
        main_section("Certifications")
        for c in resume_data.get('certifications',[])[:4]:
            pdf.set_x(main_x+2); pdf.set_font("Helvetica",'',8.5); pdf.set_text_color(50,50,50)
            pdf.cell(main_w,4, f"• {clean(c)[:80]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    if resume_data.get('awards'):
        main_section("Awards")
        for a in resume_data.get('awards',[])[:3]:
            pdf.set_x(main_x+2); pdf.set_font("Helvetica",'',8.5)
            pdf.cell(main_w,4, f"• {clean(a)[:80]}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    if resume_data.get('references'):
        main_section("References")
        for ref in resume_data.get('references',[])[:2]:
            pdf.set_x(main_x); pdf.set_font("Helvetica",'B',8.5); pdf.set_text_color(20,20,20)
            pdf.cell(main_w,4, f"{clean(ref.get('name',''))} - {clean(ref.get('role',''))} @ {clean(ref.get('company',''))}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(main_x); pdf.set_font("Helvetica",'',7.5); pdf.set_text_color(80,80,80)
            pdf.cell(main_w,4, f"{clean(ref.get('contact',''))}", new_x="LMARGIN", new_y="NEXT"); pdf.ln(1)

    tmp=tempfile.NamedTemporaryFile(delete=False, suffix=".pdf"); pdf.output(tmp.name); return tmp.name

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
