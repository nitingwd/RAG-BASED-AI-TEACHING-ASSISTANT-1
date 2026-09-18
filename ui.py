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
    text_to_audio_file, get_lang_code, generate_story_movie_script
)

st.set_page_config(page_title="Advance RAG - AI Teaching Assistant", layout="wide", page_icon="🎓")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
.main {background-color: #F8F9FF;}
.dev-badge {position: fixed; bottom: 15px; right: 15px; background: #111; color: white; padding: 8px 14px; border-radius: 20px; font-size: 12px; z-index: 999;}
.hero {background: linear-gradient(135deg, #E0E7FF 0%, #C7D2FE 100%); border-radius: 20px; padding: 30px; margin-bottom: 20px;}
.stButton>button {border-radius: 10px; height: 48px; font-weight: 600;}
</style>
<div class="dev-badge">Production V11 | KADIYA NARESH</div>
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

with st.sidebar:
    st.markdown("### 📁 File Upload")
    uploaded_files = st.file_uploader("PDF, CSV, TXT", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
        if uploaded_files:
            with st.spinner("Processing..."):
                process_files(uploaded_files, 1000, 100)
            st.success(f"{len(uploaded_files)} files ready!")
    st.divider()
    st.markdown("### 🌐 Global Language")
    selected_language = st.selectbox("Output Language", ["Hinglish","Hindi","Gujarati","English"], index=0)
    st.session_state.selected_language = selected_language
    st.info(f"Active: {selected_language} | Sab features isi me ayenge")
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
    <p style="color: #4B5563;">All FREE | Multilingual | Audio + Video | 100% PDF Based</p>
</div>
""", unsafe_allow_html=True)

if "active" not in st.session_state: st.session_state.active = "Ask"
if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []; st.session_state.viva_idx = 0; st.session_state.viva_score = []
if "quiz_data" not in st.session_state: st.session_state.quiz_data = None

st.markdown("### ✨ Features - All FREE")
c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    if st.button("💬 Ask Q&A", use_container_width=True): st.session_state.active="Ask"; st.rerun()
with c2:
    if st.button("⭐ Important Qs", use_container_width=True): st.session_state.active="Important"; st.rerun()
with c3:
    if st.button("🔧 Project Builder", use_container_width=True): st.session_state.active="Projects"; st.rerun()
with c4:
    if st.button("🎬 AI Video", use_container_width=True): st.session_state.active="Video"; st.rerun()
with c5:
    if st.button("📝 Quiz", use_container_width=True): st.session_state.active="Quiz"; st.rerun()
c6,c7,c8,c9,c10 = st.columns(5)
with c6:
    if st.button("🎤 Viva Mode", use_container_width=True): st.session_state.active="Viva"; st.rerun()
with c7:
    if st.button("📊 PPT Maker", use_container_width=True): st.session_state.active="PPT"; st.rerun()
with c8:
    if st.button("📄 Summary", use_container_width=True): st.session_state.active="Summary"; st.rerun()
with c9:
    if st.button("📖 Story Movie", use_container_width=True): st.session_state.active="Story"; st.rerun()
with c10:
    if st.button("🎙️ Podcast", use_container_width=True): st.session_state.active="Podcast"; st.rerun()

st.divider()
active = st.session_state.active
lang = st.session_state.get('selected_language','Hinglish')
st.header(f"▶ {active} Mode | 🌐 {lang}")

if active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask",f"Sawal bolo ({lang} me) - What is IoT?")
    if st.button("Ask Question", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel, language=lang)
            st.markdown(ans)
            if st.button("🔊 Suno Answer"):
                ap = text_to_audio_file(ans, lang)
                if ap: st.audio(ap)
            with st.expander("📚 Source"): st.write(src)

elif active=="Quiz":
    st.info(f"Quiz ab perfect hai - {lang} me")
    n = st.number_input("Kitne Q?",3,15,5)
    if st.button("Generate Quiz", type="primary"):
        with st.spinner("PDF se quiz bana raha hu..."):
            quiz_list = generate_quiz(n, language=lang)
            st.session_state.quiz_data = quiz_list
            st.rerun()
    if st.session_state.quiz_data:
        for i, qd in enumerate(st.session_state.quiz_data):
            with st.container(border=True):
                st.markdown(f"**Q{i+1}. {qd['question']}**")
                choice = st.radio(f"Select {i}", qd['options'], key=f"quiz_{i}", label_visibility="collapsed")
                if st.button(f"Check Q{i+1}", key=f"chk_{i}"):
                    ok, fb = check_quiz_answer(qd['question'], choice, qd['answer'], qd.get('topic','general'))
                    st.success(fb) if ok else st.error(fb)
                    if qd.get('explanation'):
                        st.info(f"📖 PDF se Explanation: {qd['explanation']}")

elif active=="Viva":
    topic=universal_input("viva_topic",f"Viva topic ({lang}) - DBMS")
    num=st.slider("Questions?",3,20,5)
    if st.button("Start Viva",type="primary"):
        if topic:
            with st.spinner("PDF se questions..."):
                qs=generate_viva_questions(topic,num, language=lang)
                st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]
            st.subheader(f"Q{idx+1}/{len(st.session_state.viva_qs)}: {curr['q']}")
            user_ans=universal_input(f"v_ans_{idx}",f"Answer in {lang}")
            c1,c2=st.columns(2)
            with c1:
                if st.button("Submit"):
                    if user_ans:
                        res=verify_viva_answer(curr['q'], curr['a'], user_ans, language=lang)
                        is_true=res['verdict'].lower()=="true"
                        st.session_state.viva_score.append({"q":curr['q'],"your":user_ans,"correct":curr['a'],"result":"✅" if is_true else "❌","fb":res['feedback']})
                        st.success(res['feedback']) if is_true else st.error(res['feedback'])
                        st.session_state.viva_idx+=1; st.rerun()
            with c2:
                if st.button("Stop"): st.session_state.viva_idx=len(st.session_state.viva_qs); st.rerun()
        else:
            score=st.session_state.viva_score
            true_c=sum(1 for x in score if "✅" in x['result'])
            st.success(f"Viva Done! Sahi: {true_c}/{len(score)}")
            for i,s in enumerate(score):
                with st.expander(f"{i+1}. {s['q']} - {s['result']}"):
                    st.write(f"Your: {s['your']}"); st.write(f"Correct: {s['correct']}")

elif active=="PPT":
    topic=universal_input("ppt",f"Topic in {lang} - AI")
    pages=st.slider("Slides?",5,25,10)
    if st.button("Create Premium PPT",type="primary"):
        if topic:
            with st.spinner(f"{pages} slides {lang} me bana raha hu..."):
                ppt_path=create_ppt_file(topic, pages, language=lang)
                with open(ppt_path,"rb") as f:
                    st.download_button("⬇️ Download PPT", f, file_name=f"{topic}_{lang}_{pages}_slides.pptx")
                st.success("Premium PPT Ban gaya!")

elif active=="Video":
    st.info(f"FULL CUSTOMIZABLE VIDEO - {lang}")
    col1, col2, col3 = st.columns(3)
    with col1:
        v_lang = st.selectbox("🌐 Video Language", ["Hinglish","Hindi","Gujarati","English","Marathi"], index=0)
    with col2:
        duration_option = st.selectbox("⏱️ Duration", ["30 sec","60 sec","90 sec","2 min","2.5 min","5 min","Custom"])
        if duration_option=="Custom":
            custom_sec = st.number_input("Seconds likho", 20, 600, 150)
            duration_sec = custom_sec
        else:
            mapping = {"30 sec":30,"60 sec":60,"90 sec":90,"2 min":120,"2.5 min":150,"5 min":300}
            duration_sec = mapping[duration_option]
    with col3:
        voice = st.selectbox("🎙️ Voice", ["Auto (Lang wise)","Male Deep","Female Soft"])

    topic_text = st.text_input(f"Topic (PDF me ho) - {v_lang} me", placeholder="e.g. Deadlock in OS")
    st.write("Ya Voice me bolo:")
    audio_val = st.audio_input("🎤 Topic bolo", key="vid_audio")
    final_topic = topic_text; final_lang = v_lang
    if audio_val:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_val.getvalue()); ap = tmp.name
        with st.spinner("Voice sun raha hu..."):
            t, l = transcribe_topic_with_language(ap)
            if os.path.exists(ap): os.remove(ap)
            if t: final_topic = t; final_lang = l; st.success(f"🎧 Topic = {t} | Language = {l}")

    st.caption(f"Selected: {duration_sec} sec video in {final_lang} - {duration_sec//30} scenes banenge")
    if st.button(f"🚀 Generate {duration_sec} sec Video", type="primary"):
        if not final_topic: st.warning("Topic likho ya bolo!")
        else:
            with st.spinner(f"{final_topic} pe {final_lang} me {duration_sec} sec video..."):
                try:
                    v_path, scenes = create_explainer_video(final_topic, final_lang, duration_sec=duration_sec)
                    if v_path and os.path.exists(v_path):
                        st.success("VIDEO BAN GAYA!"); st.video(v_path)
                        with open(v_path, "rb") as f:
                            st.download_button("⬇️ Download Video", f, file_name=f"{final_topic}_{final_lang}_{duration_sec}s.mp4")
                        with st.expander("📜 Scenes Detail"): st.json(scenes)
                    else: st.error(f"❌ {scenes}")
                except Exception as e:
                    st.error(f"Error: {e}"); import traceback; st.code(traceback.format_exc())

elif active=="Story":
    tp=universal_input("story",f"Topic in {lang} - Stack")
    if st.button("🎬 Create Blockbuster Movie",type="primary") and tp:
        with st.spinner(f"{lang} me story bana raha hu..."):
            story_text = story_mode_learning(tp, language=lang)
            st.markdown(story_text)
            st.divider()
            col1,col2 = st.columns(2)
            with col1:
                if st.button("🔊 Movie Script Suno", key="story_audio"):
                    ap = text_to_audio_file(story_text, lang)
                    if ap: st.audio(ap); st.success("Audio ready!")
            with col2:
                if st.button("🎥 Viral Reel Script"):
                    st.markdown(generate_story_movie_script(tp, language=lang))

elif active=="Projects":
    idea=universal_input("proj",f"Project idea ({lang}) - Smart Dustbin")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("Generate Guide",type="primary") and idea:
        st.markdown(build_project_guide(idea,bud, language=lang))

elif active=="Podcast":
    tp=universal_input("pod",f"Topic for Podcast in {lang}")
    if st.button("🎙️ Create Podcast + Audio",type="primary") and tp:
        with st.spinner(f"{lang} me podcast..."):
            pod_text = generate_podcast_script(tp, language=lang)
            st.markdown(pod_text)
            st.divider()
            ap = text_to_audio_file(pod_text, lang)
            if ap:
                st.success(f"🔊 {lang} Podcast Audio Ready!")
                st.audio(ap, format="audio/mp3")
                with open(ap,"rb") as f:
                    st.download_button("⬇️ Download Podcast MP3", f, file_name=f"{tp}_{lang}_podcast.mp3")

elif active=="Summary":
    if st.button(f"Generate Summary in {lang}",type="primary"):
        st.markdown(generate_summary(language=lang))

elif active=="Important":
    if st.button(f"Predict Important Qs in {lang}",type="primary"):
        st.markdown(predict_important_questions(language=lang))

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}"); st.markdown(x['answer'][:500]); st.divider()
