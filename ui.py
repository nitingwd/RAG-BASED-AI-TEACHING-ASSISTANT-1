import streamlit as st
import tempfile
import os
from rag_utils import (
    process_files, ask_question, load_conversation_history, get_api_key,
    generate_quiz, generate_summary, predict_important_questions,
    check_quiz_answer, get_weak_topics, transcribe_audio,
    story_mode_learning, build_project_guide, generate_podcast_script,
    generate_viva_questions, verify_viva_answer, create_ppt_file,
    create_explainer_video, transcribe_topic_with_language,
    text_to_audio_file, generate_story_movie_script,
    generate_premium_resume_data, create_premium_resume_pdf,
    generate_software_project, create_project_zip
)

st.set_page_config(page_title="Advance RAG - AI Teaching Assistant", layout="wide", page_icon="🎓")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
.main {background-color: #F8F9FF;}
.dev-badge {position: fixed; bottom: 15px; right: 15px; background: linear-gradient(135deg,#0D1126,#6366F1); color: white; padding: 8px 14px; border-radius: 20px; font-size: 12px; z-index: 999;}
.hero {background: linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%); border-radius: 20px; padding: 30px; margin-bottom: 20px;}
.stButton>button {border-radius: 10px; height: 48px; font-weight: 600;}
</style>
<div class="dev-badge">V13.2 FAISS LIGHTWEIGHT | KADIYA NARESH</div>
""", unsafe_allow_html=True)

def universal_input(key, placeholder="Bolo ya likho..."):
    c1,c2 = st.columns([5,1])
    with c1:
        txt = st.text_input(" ", key=f"txt_{key}", placeholder=placeholder, label_visibility="collapsed")
    with c2:
        aud = st.audio_input("🎤", key=f"aud_{key}", label_visibility="collapsed")
    if aud:
        api_key = get_api_key()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(aud.getvalue()); path = tmp.name
        with st.spinner("Sun raha hu..."):
            vt = transcribe_audio(api_key, path)
        if os.path.exists(path): os.remove(path)
        if vt:
            st.success(f"🎧 {vt}"); return vt
    return txt

def play_audio_block(text, lang, key):
    if not text: return
    st.markdown(f"#### 🔊 {lang} Audio - Poora Output Suno")
    if st.button(f"▶️ {lang} me Suno", key=f"play_{key}", type="primary"):
        with st.spinner(f"{lang} me audio bana raha hu..."):
            audio_path = text_to_audio_file(text, lang)
            if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 500:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                st.download_button(f"⬇️ Download {lang} MP3", audio_bytes, file_name=f"{key}_{lang}.mp3", mime="audio/mp3", key=f"dl_{key}")
                st.success(f"✅ {lang} Audio Ready!")
            else:
                st.error("Audio fail - net check karo")

with st.sidebar:
    st.markdown("### 📁 File Upload")
    uploaded_files = st.file_uploader("PDF, CSV, TXT", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."):
                process_files(uploaded_files, 1000, 100)
    st.divider()
    st.markdown("### 🌐 Global Language")
    selected_language = st.selectbox("Output Language", ["Hinglish","Hindi","Gujarati","English"], index=0, key="glang")
    st.session_state.selected_language = selected_language
    st.success(f"Active: {selected_language}")
    st.divider()
    st.markdown("### 📊 Weak Topics")
    weak = get_weak_topics()
    if weak:
        for t,c in sorted(weak.items(), key=lambda x:x[1], reverse=True)[:5]:
            st.write(f"🔴 {t}: {c}")
    chunk_size, chunk_overlap, top_k = 1000, 100, 8

st.markdown("""
<div class="hero">
    <h1 style="margin:0; font-size: 36px; color: #111827;">RAG Based AI Teaching Assistant</h1>
    <p style="color: #4B5563;">🔊 Audio + 💼 Premium Resume Photo+Theme + 💻 Software Builder - FAISS Fast</p>
</div>
""", unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None

st.markdown("### ✨ Features - V13.2 Lightweight")
c1,c2,c3,c4,c5,c6 = st.columns(6)
with c1:
    if st.button("💬 Ask Q&A", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("⭐ Important", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c3:
    if st.button("🔧 Project", use_container_width=True): st.session_state.active="Projects"; st.rerun()
with c4:
    if st.button("🎬 Video", use_container_width=True): st.session_state.active="Video"; st.rerun()
with c5:
    if st.button("📝 Quiz", use_container_width=True): st.session_state.active="Quiz"; st.rerun()
with c6:
    if st.button("🎤 Viva", use_container_width=True): st.session_state.active="Viva"; st.rerun()

c7,c8,c9,c10,c11,c12 = st.columns(6)
with c7:
    if st.button("📊 PPT", use_container_width=True): st.session_state.active="PPT"; st.rerun()
with c8:
    if st.button("📄 Summary", use_container_width=True): st.session_state.active="Summary"; st.rerun()
with c9:
    if st.button("📖 Story", use_container_width=True): st.session_state.active="Story"; st.rerun()
with c10:
    if st.button("🎙️ Podcast", use_container_width=True): st.session_state.active="Podcast"; st.rerun()
with c11:
    if st.button("💼 Resume", use_container_width=True): st.session_state.active="Resume"; st.rerun()
with c12:
    if st.button("💻 Software", use_container_width=True): st.session_state.active="Software"; st.rerun()

st.divider()
active = st.session_state.active
lang = st.session_state.get('selected_language','Hinglish')
st.header(f"▶ {active} Mode | 🌐 {lang} | 🔊 Audio Enabled")

if active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask",f"Sawal bolo ({lang} me)...")
    if st.button("Ask Question", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel, language=lang)
            st.session_state.last_ask = ans
            st.markdown(ans)
            with st.expander("📚 Source"): st.write(src)
    if "last_ask" in st.session_state:
        play_audio_block(st.session_state.last_ask, lang, "ask")

elif active=="Important":
    if st.button(f"Generate Important Qs in {lang}",type="primary"):
        imp = predict_important_questions(language=lang)
        st.session_state.last_imp = imp
        st.markdown(imp)
    if "last_imp" in st.session_state:
        play_audio_block(st.session_state.last_imp, lang, "imp")

elif active=="Summary":
    if st.button(f"Generate Summary in {lang}",type="primary"):
        summ = generate_summary(language=lang)
        st.session_state.last_summ = summ
        st.markdown(summ)
    if "last_summ" in st.session_state:
        play_audio_block(st.session_state.last_summ, lang, "summ")

elif active=="Story":
    tp=universal_input("story",f"Topic in {lang} - Stack")
    if st.button("🎬 Create Story + Audio",type="primary") and tp:
        story_text = story_mode_learning(tp, language=lang)
        st.session_state.last_story = story_text
        st.markdown(story_text)
        st.divider()
        reel = generate_story_movie_script(tp, language=lang)
        st.markdown(reel)
        st.session_state.last_story = story_text + "\n\n" + reel
    if "last_story" in st.session_state:
        play_audio_block(st.session_state.last_story, lang, "story")

elif active=="Projects":
    idea=universal_input("proj",f"Project idea ({lang})")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("Generate Guide",type="primary") and idea:
        guide = build_project_guide(idea,bud, language=lang)
        st.session_state.last_proj = guide
        st.markdown(guide)
    if "last_proj" in st.session_state:
        play_audio_block(st.session_state.last_proj, lang, "proj")

elif active=="Podcast":
    tp=universal_input("pod",f"Topic for Podcast in {lang}")
    if st.button("🎙️ Create Podcast + Audio",type="primary") and tp:
        pod_text = generate_podcast_script(tp, language=lang)
        st.session_state.last_pod = pod_text
        st.markdown(pod_text)
        ap = text_to_audio_file(pod_text, lang)
        if ap and os.path.exists(ap):
            with open(ap,"rb") as f:
                st.audio(f.read(), format="audio/mp3", autoplay=True)
            st.success(f"🔊 {lang} Podcast Auto Play")
    if "last_pod" in st.session_state:
        play_audio_block(st.session_state.last_pod, lang, "pod")

elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,15,5)
    if st.button("Generate Quiz", type="primary"):
        quiz_list = generate_quiz(n, language=lang)
        st.session_state.quiz_data = quiz_list
        st.rerun()
    if st.session_state.quiz_data:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"**Q{i+1}. {qd['question']}**")
                choice = st.radio(f"Select {i}", qd['options'], key=f"quiz_{i}", label_visibility="collapsed")
                c1,c2 = st.columns(2)
                with c1:
                    if st.button(f"🔊 Suno Q{i+1}", key=f"aud_{i}"):
                        ap = text_to_audio_file(f"{qd['question']} Options: {', '.join(qd['options'])}", lang)
                        if ap and os.path.exists(ap):
                            with open(ap,"rb") as f: st.audio(f.read(), format="audio/mp3")
                with c2:
                    if st.button(f"Check Q{i+1}", key=f"chk_{i}"):
                        ok, fb = check_quiz_answer(qd['question'], choice, qd['answer'], qd.get('topic','general'))
                        st.success(fb) if ok else st.error(fb)
                        exp_text = f"{fb}. Explanation: {qd.get('explanation','')}"
                        ap2 = text_to_audio_file(exp_text, lang)
                        if ap2 and os.path.exists(ap2):
                            with open(ap2,"rb") as f: st.audio(f.read(), format="audio/mp3")
                        st.info(f"📖 {qd.get('explanation','')}")

elif active=="Viva":
    topic=universal_input("viva_topic",f"Viva topic ({lang})")
    num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva",type="primary"):
        if topic:
            qs=generate_viva_questions(topic,num, language=lang)
            st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]
            st.subheader(f"Q{idx+1}: {curr['q']}")
            if st.button(f"🔊 Suno Question in {lang}", key=f"v_aud_{idx}"):
                ap = text_to_audio_file(curr['q'], lang)
                if ap and os.path.exists(ap):
                    with open(ap,"rb") as f: st.audio(f.read(), format="audio/mp3")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer in {lang}")
            if st.button("Submit", key=f"v_sub_{idx}"):
                if user_ans:
                    res=verify_viva_answer(curr['q'], curr['a'], user_ans, language=lang)
                    st.session_state.viva_score.append({"q":curr['q'],"your":user_ans,"correct":curr['a'],"result":res['verdict'],"fb":res['feedback']})
                    ap2 = text_to_audio_file(res['feedback'], lang)
                    if ap2 and os.path.exists(ap2):
                        with open(ap2,"rb") as f: st.audio(f.read(), format="audio/mp3", autoplay=True)
                    st.write(res['feedback'])
                    st.session_state.viva_idx+=1; st.rerun()
        else:
            score=st.session_state.viva_score
            st.success(f"Viva Done! {len(score)} Qs")

elif active=="PPT":
    topic=universal_input("ppt",f"Topic in {lang} - AI")
    pages=st.slider("Slides?",5,25,10)
    if st.button("Create PPT",type="primary"):
        if topic:
            ppt_path=create_ppt_file(topic, pages, language=lang)
            with open(ppt_path,"rb") as f:
                st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{lang}.pptx")
            st.success("Ban gaya!")
            play_audio_block(f"{topic} par {pages} slides ka PPT {lang} me ban gaya hai.", lang, "ppt")

elif active=="Video":
    st.info(f"FULL CUSTOMIZABLE VIDEO - {lang} - Lightweight Mode")
    st.warning("⚠️ Video generation is disabled in lightweight mode to avoid install error. Resume + All other features 100% working!")
    col1, col2 = st.columns(2)
    with col1:
        v_lang = st.selectbox("🌐 Video Language", ["Hinglish","Hindi","Gujarati","English","Marathi"], index=0)
    with col2:
        duration_option = st.selectbox("⏱️ Duration", ["30 sec","60 sec","90 sec","2 min","2.5 min","5 min","Custom"])
        if duration_option=="Custom":
            duration_sec = st.number_input("Seconds", 20, 600, 150)
        else:
            mapping = {"30 sec":30,"60 sec":60,"90 sec":90,"2 min":120,"2.5 min":150,"5 min":300}
            duration_sec = mapping[duration_option]
    topic_text = st.text_input(f"Topic - {v_lang} me", placeholder="Deadlock")
    audio_val = st.audio_input("🎤 Topic bolo", key="vid_audio")
    final_topic = topic_text; final_lang = v_lang
    if audio_val:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_val.getvalue()); ap = tmp.name
        with st.spinner("Sun raha hu..."):
            t, l = transcribe_topic_with_language(ap)
            if os.path.exists(ap): os.remove(ap)
            if t: final_topic = t; final_lang = l; st.success(f"Topic = {t} | Lang = {l}")
    if st.button(f"🚀 Generate {duration_sec} sec Video", type="primary"):
        if not final_topic: st.warning("Topic likho!")
        else:
            with st.spinner(f"{final_topic} pe {final_lang} me {duration_sec}s video..."):
                v_path, scenes = create_explainer_video(final_topic, final_lang, duration_sec=duration_sec)
                if v_path and os.path.exists(v_path):
                    st.success(f"VIDEO BAN GAYA! Audio {final_lang} me hai")
                    st.video(v_path)
                    with open(v_path, "rb") as f:
                        st.download_button("⬇️ Download Video", f, file_name=f"{final_topic}_{final_lang}_{duration_sec}s.mp4")
                else:
                    st.warning(f"{scenes} - Lightweight mode me video disabled hai. App ko live karne ke liye hataya gaya hai.")

elif active=="Resume":
    st.subheader("💼 Premium Resume - Photo + Color + Reference")
    st.success("✅ Premium Sidebar | Photo | 5 Colors | Reference | ATS 95% | FREE")

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        photo = st.file_uploader("📸 Photo Upload (Optional)", type=['jpg','png','jpeg'], key="resume_photo")
        theme = st.selectbox("🎨 Theme Color", ["0D1126 - Dark Blue Premium","0F172A - Sky Blue","1E293B - Emerald Green","7C2D12 - Sunset Orange","581C87 - Royal Purple"])
        theme_code = theme.split(" - ")[0]
        if photo:
            st.image(photo, width=120, caption="Your Photo")
    with col_up2:
        st.markdown("**Theme Preview:**")
        st.markdown(f"""
        <div style="display:flex;gap:8px;margin-top:10px">
        <div style="width:35px;height:35px;background:#0D1126;border-radius:8px;border:2px solid #6366F1" title="Dark Blue"></div>
        <div style="width:35px;height:35px;background:#0F172A;border-radius:8px;border:2px solid #0EA5E9" title="Sky"></div>
        <div style="width:35px;height:35px;background:#1E293B;border-radius:8px;border:2px solid #10B981" title="Green"></div>
        <div style="width:35px;height:35px;background:#7C2D12;border-radius:8px;border:2px solid #F97316" title="Orange"></div>
        <div style="width:35px;height:35px;background:#581C87;border-radius:8px;border:2px solid #A855F7" title="Purple"></div>
        </div>
        <p style="font-size:12px;color:gray;margin-top:8px">Selected: {theme}</p>
        """, unsafe_allow_html=True)

    st.divider()
    c1,c2 = st.columns(2)
    with c1:
        name = st.text_input("Full Name", "Kadiya Naresh")
        role = st.text_input("Target Role", "Full Stack Developer")
        email = st.text_input("Email", "naresh@example.com")
        phone = st.text_input("Phone", "+91 98765 43210")
        location = st.text_input("Location", "Ahmedabad, Gujarat")
    with c2:
        linkedin = st.text_input("LinkedIn", "linkedin.com/in/naresh")
        github = st.text_input("GitHub", "github.com/naresh")
        portfolio = st.text_input("Portfolio / Website", "naresh.dev")
        languages_input = st.text_input("Languages (comma)", "English, Hindi, Gujarati")

    st.markdown("### 📝 Full Details - Sab kuch detail me likh do")
    skills_input = st.text_area("Experience + Projects + Skills + Education + Awards + References",
        "Experience: Intern at XYZ 6 months, built dashboard with 40% improvement, Led team\nProjects: E-commerce MERN 1000 users, Chat App with Socket.io 500 users\nSkills: MERN, Python, AWS, Docker\nEducation: B.Tech CSE GTU SPCE 2021-25 8.5 CGPA\nCertifications: AWS Certified, Google Cloud\nAwards: Hackathon Winner 2024, Topper\nReferences: Prof. Shah - HOD SPCE - shah@spce.edu, Dr. Patel - Manager XYZ - patel@xyz.com",
        height=180)

    if st.button("🚀 Generate PREMIUM Resume with Photo & Theme", type="primary", use_container_width=True):
        photo_path = None
        if photo:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(photo.getvalue())
                photo_path = tmp.name

        with st.spinner(f"Premium resume bana raha hu - {theme} me..."):
            user_info = f"Name:{name}, Role:{role}, Email:{email}, Phone:{phone}, Location:{location}, LinkedIn:{linkedin}, Github:{github}, Portfolio:{portfolio}, Languages:{languages_input}, Details:{skills_input}"
            resume_data = generate_premium_resume_data(user_info, lang)
            if resume_data:
                resume_data['location'] = location
                resume_data['portfolio'] = portfolio
                resume_data['languages'] = [x.strip() for x in languages_input.split(",") if x.strip()]

                pdf_path = create_premium_resume_pdf(resume_data, photo_path=photo_path, theme_color=theme_code)
                st.success(f"✅ Premium Resume Ready! Theme: {theme}")
                with open(pdf_path,"rb") as f:
                    st.download_button("⬇️ Download PREMIUM PDF - Photo + Sidebar", f, file_name=f"{name.replace(' ','_')}_PREMIUM_{theme_code}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                with st.expander("📄 Resume Data JSON"):
                    st.json(resume_data)
                st.balloons()
                play_audio_block(f"{name} ka premium resume ban gaya hai {role} ke liye {theme} theme me photo ke saath", lang, "resume")
            else:
                st.error("Failed - GROQ API key check karo")

elif active=="Software":
    st.subheader("💻 Software Builder - Production Ready - FREE")
    st.success("Abhi Sab FREE Hai - Full Production ZIP")
    req = st.text_area("Requirement Detail me Likh", "Mujhe ek Smart Dustbin Dashboard chahiye jisme React frontend, Node backend, MongoDB, map, auth ho", height=120)
    tech = st.selectbox("Tech Stack", ["MERN (React+Node+Mongo)", "Next.js + Prisma + Tailwind", "Python Django + React", "Only Frontend React + Tailwind"])
    if st.button("⚡ Generate Production Project", type="primary"):
        if req:
            with st.spinner(f"{tech} me full code generate ho raha hai... 40 sec"):
                project = generate_software_project(req, tech, lang)
                if project:
                    st.session_state.last_project = project
                    st.balloons()
                    st.success(f"✅ {project.get('project_name')} Ready - {len(project.get('files',[]))} files")
                    st.write(f"Features: {', '.join(project.get('features',[]))}")
    if "last_project" in st.session_state:
        proj = st.session_state.last_project
        st.divider()
        st.markdown(f"### 📦 {proj.get('project_name')}")
        with st.expander("📁 Files Preview"):
            for f in proj.get('files',[])[:6]:
                st.code(f"{f['path']}\n---\n{f['content'][:600]}...", language="javascript")
        zip_path = create_project_zip(proj)
        with open(zip_path,"rb") as f:
            zip_bytes = f.read()
            st.download_button(f"⬇️ Download FULL Production ZIP ({len(proj.get('files',[]))} Files)", zip_bytes, file_name=f"{proj.get('project_name')}_PRODUCTION.zip", mime="application/zip", type="primary", use_container_width=True)
        st.info("✅ Frontend + Backend + package.json +.env.example + README - Direct VS Code me npm install")
        play_audio_block(f"{proj.get('project_name')} ka production code ready hai", lang, "software")

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}"); st.markdown(x['answer'][:500]); st.divider()
