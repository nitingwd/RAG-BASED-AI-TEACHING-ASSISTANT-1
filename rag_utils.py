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

def create_explainer_video(topic, language="Hinglish", duration_sec=300):
    if not VIDEO_AVAILABLE:
        return None, "Install gTTS, moviepy, Pillow"

    api_key = get_api_key()
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=api_key, temperature=0.85)
    docs = hybrid_search(topic, k=5)
    ctx = "\n".join([d.page_content[:800] for d in docs]) if docs else ""

    prompt = f"""Topic: {topic}, Language: {language}, Context: {ctx[:5000]}
You are making a 5 MINUTE VIRAL AI EXPLAINER VIDEO SCRIPT.
Create 8 SCENES JSON. Each scene must be VERY DETAILED, story-based, like a movie.
Each JSON object:
{{
 "title": "Scene title 3-5 words",
 "story_character": "Who is talking - e.g. AI Tutor, Student Rohit, Shopkeeper",
 "explain": "100-130 words LONG FULL explanation in {language}. Story way, dialogue way. Example: 'Dekho Rohit, socho tum ek chai ki dukaan chalate ho...' Must be deep concept, not short. Must clear full topic.",
 "dialogue": "Short 1-line dialogue between characters like Rohit: Are sir ye kaise hota hai? Tutor: Chalo batata hu...",
 "diagram": "Detailed visual description what to show on whiteboard - e.g. Customer -> Queue -> CPU Scheduler -> Execution with arrows moving",
 "visual_action": "What moves in scene - e.g. Characters talking, arrow moves from Customer to Server, CPU blinks, Queue grows",
 "real_life_story": "Full real life kahani example 20 words"
}}
Topic must be explained from ZERO to HERO in 5 mins.
Language MUST be {language} only.
Return ONLY JSON array of 8 objects.
"""

    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        scenes = json.loads(txt[s:e])
    except:
        scenes = [
            {"title": f"Part 1: Kya hai {topic}?", "story_character": "AI Tutor", "explain": f"Dekho dosto, aaj hum {topic} ko ek kahani se samjhenge. Socho tum Ahmedabad me ek famous chai ki dukaan chalate ho. Subah 7 baje 50 customer ek saath aa jate hain. Ab sabko ek saath chai kaise doge? Yahi problem computer me bhi hoti hai. {topic} wahi solution hai jo sab kaam ko line me lagake fast manage karta hai.", "dialogue": "Rohit: Sir ye chai aur OS ka kya connection? Tutor: Bahut bada connection hai beta!", "diagram": "Chai Shop: 50 Customers -> 1 Shopkeeper -> Queue System", "visual_action": "Customers crowd moves, queue forms, shopkeeper serves", "real_life_story": "Chai shop jaisa hi CPU kaam karta hai"},
            {"title": "Part 2: Andar Kya Hota Hai?", "story_character": "Student Rohit + Tutor", "explain": f"Ab andar ki baat samjho. Jab tum shop me entry karte ho, ek token milta hai, right? Computer me har program ko bhi ek PCB milta hai - Process Control Block. Isme uska naam, kitni RAM chahiye, kahan tak kaam hua hai, sab likha hota hai. OS ye token dekh ke decide karta hai kisko pehle chai deni hai.", "dialogue": "Rohit: Matlab PCB token jaisa hai? Tutor: Exactly! Bilkul token jaisa!", "diagram": "Token Counter -> PCB Structure -> RAM Allocation Diagram", "visual_action": "Token slides to PCB, PCB glows, RAM blocks fill", "real_life_story": "Token system = PCB"},
            {"title": "Part 3: Bheed Kaise Manage?", "story_character": "AI Tutor", "explain": f"Ab sabse bada sawal, 50 logon ko kaise manage karoge? Ek ko 2 min doge toh dusra gussa ho jayega. OS ek trick use karta hai - Scheduling! Round Robin, FCFS, Priority. Matlab har customer ko 30 second do, fir next ko. Isse sab khush, koi bore nahi. Computer me har app ko 10 millisecond CPU milta hai, fir dusre ko.", "dialogue": "Tutor: Socho sabko thoda-thoda time doge to sab khush! Rohit: Samajh gaya sir, time sharing!", "diagram": "Queue: C1(30s) -> C2(30s) -> C3(30s) -> C1 again - circular arrow", "visual_action": "Timer ticks, customers rotate, CPU time slice animation", "real_life_story": "Sabko thoda time dena = Scheduling"},
            {"title": "Part 4: RAM Ki Kahani", "story_character": "Shopkeeper Example", "explain": f"Ab RAM ko samjho. Tumhari dukaan chhoti hai, sirf 4 table hain. 10 customer aa gaye toh? Tum kya karte ho? Ek ko bithate ho, dusre ko bolte ho bahar wait karo, jagah khali hote hi bula lete ho. Yahi Paging hai! OS RAM ko 4KB ke chhote pages me tod deta hai, jo active hai usko RAM me, jo so raha hai usko Hard Disk pe bhej deta hai.", "dialogue": "Shopkeeper: Table khali nahi hai, bahar wait karo! OS: RAM full hai, page ko disk pe bhejo!", "diagram": "4 Tables = RAM Frames, 10 Customers = Pages, Swapping animation", "visual_action": "Tables fill, customers swap between inside/outside", "real_life_story": "Table management = Paging"},
            {"title": "Part 5: Deadlock - Sab Atak Gaye!", "story_character": "Two Customers Fight", "explain": f"Ab ek mazedar problem. Customer A ne Table pakad liya aur Spoon maang raha hai. Customer B ne Spoon pakad liya aur Table maang raha hai. Dono ek dusre ka wait kar rahe hain, koi chai nahi pi raha! Yahi Deadlock hai. OS me Process A ne Printer pakda, Process B ne Scanner. Dono ek dusre ka resource maang rahe hain. System hang!", "dialogue": "A: Mujhe spoon do! B: Pehle table do! Tutor: Dekha, yehi deadlock hai!", "diagram": "A holds Table waits Spoon, B holds Spoon waits Table - Cross arrows, RED Deadlock sign", "visual_action": "Two characters stuck, red cross blinks, deadlock text pops", "real_life_story": "Dono ek dusre ka wait = Deadlock"},
            {"title": "Part 6: Solution Kaise?", "story_character": "AI Tutor - Hero Entry", "explain": f"Toh iska solution kya hai dosto? OS 3 tarike use karta hai. 1. Prevention - pehle se rule banao ek saath sirf ek cheez maango. 2. Avoidance - Banker Algorithm, socho bank jaise, loan dene se pehle check karo koi deadlock toh nahi hoga. 3. Detection & Recovery - ek ko bahar nikalo, uska token cancel karo. Jaise dukaan me ek customer ko bolo bhai tum kal aana.", "dialogue": "Tutor: Solution simple hai, ek ko sacrifice karna padega! Rohit: Matlab ek process kill?", "diagram": "3 Solutions: Lock Rule -> Banker Check -> Kill one Process - Green Tick", "visual_action": "Solutions pop one by one with green tick, one character exits", "real_life_story": "Ek ko nikal do to sab chalega"},
            {"title": "Part 7: Real Life Superpowers", "story_character": "Real World Examples", "explain": f"Ab socho ye sab kahan use hota hai? Tum jab BGMI khelte ho, WhatsApp chalate ho, YouTube chalate ho ek saath, ye OS hi hai jo sabko manage kar raha hai. Google ke server pe 1 lakh customer ek saath aate hain, wahan {topic} nahi hota toh Google 1 second me crash ho jayega. ISRO ke rocket me bhi same concept hai, ek chhota deadlock toh rocket fail!", "dialogue": "Rohit: Wow sir, matlab OS har jagah hai! Tutor: Haan beta, OS ke bina duniya ruk jayegi!", "diagram": "Phone: BGMI + WhatsApp + YouTube running parallel - OS managing, Google Server farm, ISRO Rocket", "visual_action": "Phone apps animate, server lights blink, rocket launches", "real_life_story": "Har jagah OS ka jadoo"},
            {"title": "Part 8: Final Master Summary", "story_character": "AI Tutor Final", "explain": f"Toh final summary suno dosto, 5 minute me master ban gaye tum. {topic} ka matlab hai smart management. Chai ki dukaan se Google tak same rule - Token do (PCB), line lagao (Scheduling), table manage karo (Paging), deadlock roko (Prevention). Exam me bas ye kahani likh dena, teacher impress ho jayega, full marks pakke! Aur yaad rakho, OS hi computer ki jaan hai.", "dialogue": "Tutor: Toh batao Rohit, samajh aaya? Rohit: Haan sir, ab toh kabhi nahi bhoolunga!", "diagram": "Full Mind Map: {topic} -> PCB -> Scheduling -> Paging -> Deadlock -> Real Life", "visual_action": "Mind map grows, all concepts connect, final celebration confetti", "real_life_story": "Kahani khatam, concept clear forever"}
        ]

    temp_dir = tempfile.mkdtemp()
    clips = []

    def create_human_tutor():
        W, H = 400, 400
        img = Image.new('RGB', (W, H), (0,0,0,0))
        img = Image.new('RGB', (W,H), (13,17,38))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(50,20),(350,320)], fill=(255, 220, 180), outline=(255,255,255), width=4)
        draw.ellipse([(110,120),(160,170)], fill=(0,0,0))
        draw.ellipse([(240,120),(290,170)], fill=(0,0,0))
        draw.ellipse([(125,135),(145,155)], fill=(255,255,255))
        draw.ellipse([(255,135),(275,155)], fill=(255,255,255))
        draw.arc([(130,180),(270,260)], 20, 160, fill=(0,0,0), width=5)
        draw.rectangle([(80,300),(320,400)], fill=(99,102,241))
        draw.text((140, 330), "AI TUTOR", fill=(255,255,255))
        p = os.path.join(temp_dir, "human_tutor.png")
        img.save(p)
        return p

    def create_student_avatar(name="ROHIT"):
        W,H = 300,300
        img = Image.new('RGB', (W,H), (25,35,70))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(50,20),(250,220)], fill=(255, 210, 170), outline=(245,158,11), width=3)
        draw.ellipse([(90,100),(130,140)], fill=(0,0,0))
        draw.ellipse([(170,100),(210,140)], fill=(0,0,0))
        draw.text((100, 230), name, fill=(255,255,255))
        p = os.path.join(temp_dir, f"{name}.png")
        img.save(p)
        return p

    tutor_path = create_human_tutor()
    student_path = create_student_avatar()

    for i, scene in enumerate(scenes):
        W, H = 1920, 1080
        bg_img = Image.new('RGB', (W, H), (13, 17, 38))
        draw = ImageDraw.Draw(bg_img)
        for x in range(0, W, 100):
            draw.line([(x,0),(x,H)], fill=(22,30,60), width=1)
        draw.rectangle([(0,0),(W,120)], fill=(99,102,241))
        draw.text((30, 20), f"PART {i+1}/8: {scene['title']}", fill=(255,255,255))
        draw.text((30, 70), f"{scene['story_character']} • {scene['dialogue'][:75]}", fill=(220,230,255))
        draw.rectangle([(30,140),(1300, 650)], fill=(25,35,70), outline=(255,255,255), width=2)
        wrapped = textwrap.wrap(scene['explain'], width=70)
        y = 160
        for line in wrapped[:10]:
            draw.text((50, y), line, fill=(255,255,255))
            y += 42
        draw.rectangle([(30,670),(1300, 760)], fill=(245,158,11))
        draw.text((50, 690), f"💬 {scene['dialogue'][:95]}", fill=(0,0,0))
        draw.rectangle([(1330,140),(1890, 900)], fill=(10,20,45), outline=(0,220,255), width=4)
        draw.text((1350, 150), "LIVE VISUALIZATION BOARD", fill=(0,220,255))
        diag_wrapped = textwrap.wrap(scene['diagram'], width=35)
        yy = 230
        for dline in diag_wrapped[:6]:
            draw.text((1350, yy), f"→ {dline}", fill=(200,255,200))
            yy += 35
        draw.text((1350, yy+20), f"ACTION: {scene['visual_action'][:60]}", fill=(236,72,153))
        draw.text((1350, yy+70), f"STORY: {scene['real_life_story']}", fill=(16,185,129))
        draw.text((1350, yy+120), "▶▶▶ Animation Moving ▶▶▶", fill=(255,255,255))
        draw.rectangle([(1350, yy+160),(1500, yy+210)], fill=(99,102,241))
        draw.rectangle([(1520, yy+160),(1670, yy+210)], fill=(16,185,129))
        draw.rectangle([(1690, yy+160),(1840, yy+210)], fill=(245,158,11))
        bg_path = os.path.join(temp_dir, f"bg_{i}.png")
        bg_img.save(bg_path)

        lang_code = 'hi' if 'hindi' in language.lower() or 'hinglish' in language.lower() else 'en'
        audio_path = os.path.join(temp_dir, f"aud_{i}.mp3")
        try:
            tts = gTTS(text=scene['explain'], lang=lang_code, slow=False)
            tts.save(audio_path)
            audio = AudioFileClip(audio_path)
            dur = audio.duration + 1.2
        except:
            audio = None
            dur = 38

        bg_clip = ImageClip(bg_path).set_duration(dur)
        bg_clip = bg_clip.resize(lambda t: 1 + 0.03 * math.sin(t*0.8))
        tutor_clip = ImageClip(tutor_path).set_duration(dur).resize(0.55)
        tutor_clip = tutor_clip.set_position(lambda t: (30 + 5*math.sin(t*2), 780 + 3*math.sin(t*3)))
        stud_clip = ImageClip(student_path).set_duration(dur).resize(0.45)
        stud_clip = stud_clip.set_position(lambda t: (350 + 4*math.cos(t*2), 800 + 3*math.cos(t*2.5)))
        final_scene = CompositeVideoClip([bg_clip, tutor_clip, stud_clip])
        if audio:
            final_scene = final_scene.set_audio(audio)
        clips.append(final_scene)

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tempfile.gettempdir(), f"{topic.replace(' ','_')}_5MIN_FULL.mp4")
    final.write_videofile(out_path, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
    return out_path, scenes
