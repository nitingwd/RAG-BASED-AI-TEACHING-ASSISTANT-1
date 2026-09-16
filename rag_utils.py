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

def create_ppt_file(topic, num_slides=5):
    docs = hybrid_search(topic, k=6)
    ctx = "\n".join([d.page_content[:1200] for d in docs])
    llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=get_api_key(), temperature=0.85)

    prompt = f"""You are IIT professor + designer.
Topic: {topic}
Context: {ctx[:7000]}
Create {num_slides} UNIQUE slides JSON. Each slide 4 points, each point 40-50 words detailed real working, no repeat.
Outline for 5: 1.What is OS, 2.Types, 3.Process Management, 4.Memory Management, 5.Deadlock & File System
Return JSON: [{{"title":"","subtitle":"","points":["40-50 words each x4"],"visual_steps":["Step A","Step B","Step C","Step D"],"real_example":"Windows/Linux example"}}] Only JSON."""

    try:
        txt = llm.invoke(prompt).content
        s = txt.find('['); e = txt.rfind(']')+1
        slides_data = json.loads(txt[s:e])
    except:
        slides_data = [
            {"title":"What is Operating System? The Soul of Computer","subtitle":"Bridge between User and Hardware","points":["Operating System is system software that acts as intermediary between user and computer hardware. It manages CPU, RAM, disk, I/O devices and provides common services. Without OS, you need to write assembly code to access hard disk sectors manually. OS provides abstraction so developer just says 'open file'.","Kernel is core part of OS that directly interacts with hardware in privileged mode. It has two types: Monolithic like Linux where all drivers in kernel for speed, Microkernel like QNX where only essential in kernel for stability. Windows uses Hybrid kernel for balance.","OS provides 5 major services: Process management to run multiple apps, Memory management to allocate RAM efficiently using paging, File management via NTFS/ext4, Device management for printer/mouse, Security via user permissions and firewall. This makes computer usable.","Real Example: When you double-click Chrome icon, OS does 10 things in 0.5 sec - checks permissions, loads Chrome.exe from SSD to RAM using virtual memory, allocates 500MB RAM, creates process PCB, gives CPU core via scheduler, handles network, graphics rendering, all automatically."],"visual_steps":["User Clicks App","OS Kernel Takes Control","Allocates CPU+RAM+Disk","App Runs Smoothly"],"real_example":"Windows 11, Linux Kernel 6.8, Android 14 all are OS"},
            {"title":"Types of Operating System - Evolution","subtitle":"From Batch to Real-Time","points":["Batch OS was first OS in 1960s where jobs collected in batches on punch cards and executed one by one without user interaction. Example: IBM 7094 used for payroll. Problem: If one job failed, whole batch waited. CPU idle time was 80% because I/O was slow.","Time-Sharing OS invented in 1970s to solve batch problem. It divides CPU time into tiny slices of 10-100ms called quantum and gives each user a slice. Example: University Linux server where 200 students code together. You feel your terminal is only yours, but actually CPU switches 1000 times per second.","Real-Time OS gives guarantee that response will come within deadline like 1 microsecond. Used where delay means disaster. Hard RTOS used in ISRO rocket Chandrayaan where thruster must fire within 0.1ms, Soft RTOS in video streaming where few ms delay ok. Example: VxWorks used in Mars Rover.","Modern OS types: Distributed OS like Google's Borg runs one OS on 10000 machines, Embedded OS like FreeRTOS runs in washing machine with 16KB RAM, Mobile OS like Android optimized for touch and battery. Future is AI OS that predicts your next app."],"visual_steps":["1960 Batch OS","1970 Time-Sharing","1990 Real-Time OS","2025 AI-based OS"],"real_example":"ISRO uses RTOS, Google uses Distributed OS, Your smartwatch uses Embedded OS"},
            {"title":"Process Management & CPU Scheduling - Heart of OS","subtitle":"How OS Runs 100 Apps Together?","points":["Process is program in execution. When you open Chrome, OS creates process with PCB containing PID, state, program counter, registers, memory limits, open files. Process states are 5: New when created, Ready when waiting for CPU, Running when CPU executing, Waiting when waiting for I/O like disk, Terminated when finished. OS manages 200+ processes together.","CPU Scheduling is algorithm to choose which Ready process gets CPU next. FCFS is simple queue but suffers convoy effect where small process waits behind big process like at ration shop. SJF picks shortest job first gives best average waiting time but needs prediction. Both not practical for interactive system.","Round Robin is used in all modern OS like Windows/Linux. Each process gets fixed time quantum like 100ms. If not finished, preempted and goes to end of queue. Plus priority scheduling where system processes get higher priority than user apps. This gives fair chance and responsiveness.","Context Switch is magic: When time quantum over, OS saves all registers of current process to its PCB in 1 microsecond, loads next process registers, flushes TLB, switches memory map. Happens 1000 times/sec. That's why you can run YouTube + VS Code + Chrome together without hanging. Without scheduling, one app would freeze whole system."],"visual_steps":["New Process Created","Ready Queue Waiting","CPU Scheduling Picks One","Context Switch 1000/sec"],"real_example":"Open Task Manager in Windows - you see Round Robin live"},
            {"title":"Memory Management - Paging, Segmentation, Virtual Memory","subtitle":"How 8GB RAM Runs 20GB Apps?","points":["Memory Management solves problem: RAM is small and fragmented. OS uses Paging where it divides RAM into 4KB frames and program into 4KB pages. Page Table maps logical pages to physical frames. This allows program to be stored non-contiguously. Example: Chrome needs 500MB but RAM has only 10 small free holes, paging fits it. No external fragmentation.","Segmentation divides program by logical meaning: Code segment, Data segment, Stack segment, Heap. Each segment has different size and permission like code is read-only. Modern OS uses both Paging + Segmentation: Segmentation for logical protection, Paging for physical allocation. Example: In Linux, code segment shared between 2 Chrome processes to save RAM.","Virtual Memory is biggest invention: OS uses hard disk as extension of RAM. When RAM full, it moves inactive pages to swap space on disk. Page fault happens when program accesses swapped page, OS brings it back. This allows running 20GB of apps in 8GB RAM. Without virtual memory, Photoshop + Chrome would crash.","Real Working: Windows uses pagefile.sys (16GB on C drive), Linux uses swap partition. When you open 20 Chrome tabs, OS keeps only 5 active tabs in RAM, rest in disk. When you switch tab, 50ms lag comes due to page fault. TLB cache speeds up page table lookup by 90%."],"visual_steps":["Program Divided into 4KB Pages","Page Table Maps to RAM Frames","RAM Full -> Swap to Disk","TLB Cache Speeds Up"],"real_example":"Windows pagefile.sys, Linux swap, Mac uses same"},
            {"title":"Deadlock & File System - Critical Challenges","subtitle":"When System Freezes Completely","points":["Deadlock is situation where 2+ processes wait forever for each other's resources. Real life: Two people crossing narrow bridge from opposite sides, both block. In OS: Process A holds Printer and wants Scanner, Process B holds Scanner and wants Printer, both wait forever. System freezes, mouse also hangs. Must have 4 conditions together: Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait.","Deadlock Handling: Prevention breaks one condition like allow preemption where OS forcefully takes printer. Avoidance uses Banker's Algorithm where OS checks safe state before giving resource, like bank checks if giving loan keeps bank safe. Detection & Recovery allows deadlock then kills one process. Example: Windows detects deadlock after 10 sec and shows Not Responding.","File System manages how files stored on disk. FAT32 old, stores file in linked list, slow. NTFS used in Windows has journaling, security, encryption, supports 16TB file. ext4 used in Linux faster for small files. Allocation: Contiguous fast but fragmentation, Linked no fragmentation but slow random access, Indexed best used in NTFS/ext4 with inode table.","Summary & Future: OS is most complex software with 50 million lines of code in Windows. Without OS, hardware is iron box. Future OS will be AI-based: Microsoft Copilot OS predicts your next file and preloads in RAM, manages battery by learning your usage, auto fixes deadlock. Learning OS is must for every CS student for placements."],"visual_steps":["Process A Holds R1 Wants R2","Process B Holds R2 Wants R1","Circular Wait = Deadlock","Prevention / Banker's Algo"],"real_example":"Blue Screen of Death is deadlock, NTFS is file system of Windows 11"},
        ]

    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)

    def draw_pro_diagram(slide, left, top, steps):
        colors = [RGBColor(99,102,241), RGBColor(16,185,129), RGBColor(245,158,11), RGBColor(236,72,153)]
        for i, step in enumerate(steps[:4]):
            shadow = slide.shapes.add_shape(5, left+Inches(0.05), top + i*Inches(1.15)+Inches(0.05), Inches(4.3), Inches(0.85))
            shadow.fill.solid(); shadow.fill.fore_color.rgb = RGBColor(0,0,0); shadow.line.fill.background()
            box = slide.shapes.add_shape(5, left, top + i*Inches(1.15), Inches(4.3), Inches(0.85))
            box.fill.solid(); box.fill.fore_color.rgb = colors[i % 4]; box.line.color.rgb = RGBColor(255,255,255); box.line.width = Pt(1.5)
            tf = box.text_frame; tf.word_wrap=True
            tf.text = f"STEP {i+1}\n{step}"
            tf.paragraphs[0].font.size=Pt(10); tf.paragraphs[0].font.bold=True; tf.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            tf.paragraphs[1].font.size=Pt(12); tf.paragraphs[1].font.bold=True; tf.paragraphs[1].font.color.rgb=RGBColor(255,255,255)
            if i < 3:
                arr = slide.shapes.add_shape(5, left+Inches(1.9), top + i*Inches(1.15)+Inches(0.85), Inches(0.04), Inches(0.3))
                arr.fill.solid(); arr.fill.fore_color.rgb = RGBColor(255,255,255); arr.line.fill.background()

    for i, sl in enumerate(slides_data[:num_slides]):
        if i == 0:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor(13,17,38)
            t = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(7.5), Inches(1.2))
            t.text_frame.word_wrap=True; t.text_frame.text = sl.get('title','').upper()
            t.text_frame.paragraphs[0].font.size=Pt(32); t.text_frame.paragraphs[0].font.bold=True; t.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            sub = slide.shapes.add_textbox(Inches(0.8), Inches(2), Inches(7.2), Inches(4.5))
            sub.text_frame.word_wrap=True
            full_text = "\n\n".join([f"• {p}" for p in sl.get('points',[])])
            sub.text_frame.text = full_text[:1500]
            for para in sub.text_frame.paragraphs:
                para.font.size=Pt(10); para.font.color.rgb=RGBColor(200,210,255); para.space_after=Pt(10)
            draw_pro_diagram(slide, Inches(8.6), Inches(1), sl.get('visual_steps',[]))
        else:
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            slide.background.fill.solid(); slide.background.fill.fore_color.rgb=RGBColor(249,250,255)
            header=slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.33), Inches(1.0))
            header.fill.solid(); header.fill.fore_color.rgb=RGBColor(13,17,38); header.line.fill.background()
            ht=slide.shapes.add_textbox(Inches(0.6), Inches(0.15), Inches(7), Inches(0.8))
            ht.text_frame.text=f"{i+1}. {sl.get('title','')}"; ht.text_frame.paragraphs[0].font.size=Pt(19); ht.text_frame.paragraphs[0].font.bold=True; ht.text_frame.paragraphs[0].font.color.rgb=RGBColor(255,255,255)
            card=slide.shapes.add_shape(5, Inches(0.4), Inches(1.2), Inches(7.8), Inches(6.1))
            card.fill.solid(); card.fill.fore_color.rgb=RGBColor(255,255,255); card.line.color.rgb=RGBColor(220,225,255); card.line.width=Pt(1)
            ct=slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(7.2), Inches(5.9))
            tf=ct.text_frame; tf.word_wrap=True
            for pt in sl.get('points',[]):
                pa=tf.add_paragraph(); pa.text=f"• {pt}"; pa.space_after=Pt(10); pa.font.size=Pt(10); pa.font.color.rgb=RGBColor(30,35,60)
            ex=tf.add_paragraph(); ex.text=f"\n💡 {sl.get('real_example','')}"; ex.font.size=Pt(10); ex.font.bold=True; ex.font.color.rgb=RGBColor(99,102,241); ex.space_before=Pt(10)
            vbg=slide.shapes.add_shape(5, Inches(8.6), Inches(1.2), Inches(4.4), Inches(6.1))
            vbg.fill.solid(); vbg.fill.fore_color.rgb=RGBColor(13,17,38); vbg.line.fill.background()
            vt=slide.shapes.add_textbox(Inches(8.8), Inches(1.3), Inches(4), Inches(0.5))
            vt.text_frame.text="VISUAL WORKFLOW"; vt.text_frame.paragraphs[0].font.size=Pt(11); vt.text_frame.paragraphs[0].font.bold=True; vt.text_frame.paragraphs[0].font.color.rgb=RGBColor(99,102,241)
            draw_pro_diagram(slide, Inches(8.8), Inches(1.9), sl.get('visual_steps',[]))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    prs.save(tmp.name)
    return tmp.name
