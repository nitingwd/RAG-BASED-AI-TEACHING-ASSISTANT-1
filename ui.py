import streamlit as st
import tempfile
import os
from rag_utils import (
    process_files, ask_question, load_conversation_history, get_api_key,
    generate_quiz, generate_summary, predict_important_questions,
    check_quiz_answer, get_weak_topics, transcribe_audio,
    story_mode_learning, build_project_guide, generate_podcast_script,
    generate_viva_questions, verify_viva_answer, create_ppt_file,
    create_explainer_video, transcribe_topic_with_language
)

st.set_page_config(page_title="Advance RAG", layout="wide")
st.markdown("""
<style>
.dev-corner {position: fixed; bottom: 20px; right: 20px; background: linear-gradient(135deg, #3f51b5, #9c27b0, #e91e63); padding: 10px 20px; border-radius: 20px; color: white; font-size: 14px; font-weight: bold; z-index: 999;}
</style>
<div class="dev-corner">Developer : KADIYA NARESH</div>
""", unsafe_allow_html=True)

def universal_input(key, placeholder="Bolo ya likho..."):
    c1,c2 = st.columns([4,1])
    with c1:
        txt = st.text_input(" ", key=f"txt_{key}", placeholder=placeholder, label_visibility="collapsed")
    with c2:
        aud = st.audio_input("🎤", key=f"aud_{key}", label_visibility="collapsed")
    if aud:
        api_key = get_api_key()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(aud.getvalue())
            path = tmp.name
        with st.spinner("Sun raha hu..."):
            vt = transcribe_audio(api_key, path)
        os.remove(path)
        if vt:
            st.success(f"🎧 {vt}")
            return vt
    return txt

st.sidebar.header("Configuration")
uploaded_files = st.sidebar.file_uploader("Upload PDF/CSV/TXT", type=["pdf","csv","txt"], accept_multiple_files=True)
chunk_size = st.sidebar.number_input("Chunk Size", 200, 2000, 1000, 100)
chunk_overlap = st.sidebar.number_input("Chunk Overlap", 0, 500, 100, 10)
top_k = st.sidebar.number_input("Docs to Retrieve", 1, 10, 3)
if st.sidebar.button("Submit & Process"):
    if uploaded_files:
        process_files(uploaded_files, chunk_size, chunk_overlap)
    else:
        st.warning("Upload karo pehle.")
st.sidebar.divider()
weak = get_weak_topics()
st.sidebar.subheader("📊 Weak Topics")
if weak:
    for t,c in sorted(weak.items(), key=lambda x:x[1], reverse=True):
        st.sidebar.write(f"- {t}: {c}")
else:
    st.sidebar.info("Quiz do!")

if "active" not in st.session_state:
    st.session_state.active = "Ask"
if "viva_qs" not in st.session_state:
    st.session_state.viva_qs = []
    st.session_state.viva_idx = 0
    st.session_state.viva_score = []

st.title("RAG Based AI Teaching Assistant")
st.caption("Har feature me Type + Voice dono hai")
st.subheader("📦 Features")

c1,c2,c3,c4 = st.columns(4)
with c1:
    if st.button("⌨️ Ask Q&A", use_container_width=True):
        st.session_state.active="Ask"; st.rerun()
    if st.button("📝 Quiz", use_container_width=True):
        st.session_state.active="Quiz"; st.rerun()
    if st.button("📄 Summary", use_container_width=True):
        st.session_state.active="Summary"; st.rerun()
with c2:
    if st.button("⭐ Important Qs", use_container_width=True):
        st.session_state.active="Important"; st.rerun()
    if st.button("🎤 Viva Mode", use_container_width=True):
        st.session_state.active="Viva"; st.rerun()
    if st.button("📖 Story Movie", use_container_width=True):
        st.session_state.active="Story"; st.rerun()
with c3:
    if st.button("🔧 Project Builder", use_container_width=True):
        st.session_state.active="Projects"; st.rerun()
    if st.button("📊 PPT Maker Pro", use_container_width=True):
        st.session_state.active="PPT"; st.rerun()
    if st.button("🎙️ Podcast", use_container_width=True):
        st.session_state.active="Podcast"; st.rerun()
with c4:
    if st.button("🎬 AI Video", use_container_width=True):
        st.session_state.active="Video"; st.rerun()

st.divider()
active = st.session_state.active
st.header(f"▶ {active}")

if active=="Ask":
    mode = st.radio("Mode:", ["Normal","Socratic"], horizontal=True)
    sel = "socratic" if "Socratic" in mode else "normal"
    q = universal_input("ask","Sawal bolo ya likho - What is IoT?")
    if st.button("Ask", type="primary"):
        if q:
            ans,src = ask_question(q, top_k, mode=sel)
            st.markdown(ans)

elif active=="Quiz":
    n = st.number_input("Kitne Q?",3,10,5)
    if st.button("Quiz Banao"):
        qt,err = generate_quiz(n)
        st.error(err) if err else st.markdown(qt)
    st.divider()
    qq=universal_input("qq","Question bolo/likho")
    ua=universal_input("ua","Tumhara answer")
    ca=st.text_input("Correct ans")
    tp=st.text_input("Topic","general")
    if st.button("Check Karo"):
        ok,fb=check_quiz_answer(qq,ua,ca,tp)
        st.success(fb) if ok else st.error(fb)

elif active=="Viva":
    st.info("PDF se auto questions ayenge one-by-one. Answer do, verify hoga, sahi answer milega. Last me list milega.")
    topic=universal_input("viva_topic","Viva topic bolo - DBMS")
    num=st.slider("Kitne questions chahiye?",3,20,5)
    if st.button("Viva Start Karo",type="primary"):
        if topic:
            with st.spinner("PDF se questions bana raha hu..."):
                qs=generate_viva_questions(topic,num)
                st.session_state.viva_qs=qs; st.session_state.viva_idx=0; st.session_state.viva_score=[]
                st.rerun()
    if st.session_state.viva_qs:
        idx=st.session_state.viva_idx
        if idx < len(st.session_state.viva_qs):
            curr=st.session_state.viva_qs[idx]
            st.subheader(f"Q{idx+1}/{len(st.session_state.viva_qs)}: {curr['q']}")
            user_ans=universal_input(f"v_ans_{idx}","Answer bolo/likho")
            col1,col2=st.columns(2)
            with col1:
                if st.button("Answer Submit Karo"):
                    if user_ans:
                        res=verify_viva_answer(curr['q'], curr['a'], user_ans)
                        is_true=res['verdict'].lower()=="true"
                        st.session_state.viva_score.append({"q":curr['q'],"your":user_ans,"correct":curr['a'],"result":"✅ Sahi" if is_true else "❌ Galat","fb":res['feedback']})
                        st.success(res['feedback']) if is_true else st.error(res['feedback'])
                        st.session_state.viva_idx+=1
                        st.rerun()
            with col2:
                if st.button("Stop Viva - Result Dikhao"):
                    st.session_state.viva_idx=len(st.session_state.viva_qs)
                    st.rerun()
        else:
            score=st.session_state.viva_score
            true_c=sum(1 for x in score if "Sahi" in x['result']); false_c=len(score)-true_c
            st.success(f"Viva Khatam! ✅ Sahi: {true_c} | ❌ Galat: {false_c}")
            for i,s in enumerate(score):
                with st.expander(f"{i+1}. {s['q']} - {s['result']}"):
                    st.write(f"**Tumhara:** {s['your']}")
                    st.write(f"**Correct:** {s['correct']}")
                    st.write(f"**Feedback:** {s['fb']}")
            if st.button("Naya Viva Start Karo"):
                st.session_state.viva_qs=[]; st.session_state.viva_idx=0; st.session_state.viva_score=[]; st.rerun()

elif active=="PPT":
    st.info("English me premium PPT with visualization - direct download.")
    topic=universal_input("ppt","Topic bolo - AI")
    pages=st.slider("Kitne slides chahiye?",5,25,10)
    if st.button("📊 PPT Banao",type="primary"):
        if topic:
            with st.spinner(f"{pages} slides ka shaandar PPT bana raha hu..."):
                ppt_path=create_ppt_file(topic, pages)
                with open(ppt_path,"rb") as f:
                    st.download_button("⬇️ PPT Download Karo", f, file_name=f"{topic}_{pages}_slides.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
                st.success("Ban gaya! Ab design premium hai - visualization ke saath.")

elif active=="Video":
    st.info("🎬 Naya Feature: Voice ya Text se bolo - AI Video banega usi language me jisme chahiye! Good explanation + visualization + voice.")
    col1, col2 = st.columns(2)
    with col1:
        lang = st.selectbox("Video ki Language chuno", ["Hinglish", "Hindi", "English", "Marathi"], key="vid_lang")
    with col2:
        topic_text = st.text_input("Topic likho", placeholder="e.g. Deadlock in OS", key="vid_topic_text")

    st.write("Ya Voice me bolo:")
    audio_val = st.audio_input("🎤 Topic bolo - jaise 'Mujhe deadlock Hindi me samjha do'", key="vid_audio")

    final_topic = topic_text
    final_lang = lang

    if audio_val:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_val.getvalue())
            ap = tmp.name
        with st.spinner("Voice sun raha hu aur language detect kar raha hu..."):
            t, l = transcribe_topic_with_language(ap)
            os.remove(ap)
            if t:
                final_topic = t
                final_lang = l
                st.success(f"🎧 Samajh gaya: **Topic = {t}** | **Language = {l}**")
                st.info(f"Ab {l} me video banega!")

    if st.button("🚀 AI Video Banao", type="primary"):
        if not final_topic:
            st.warning("Pehle topic likho ya bolo!")
        else:
            with st.spinner(f"🎬 {final_topic} pe {final_lang} me 60 sec ka video bana raha hu... Thoda time lagega (1-2 min)"):
                try:
                    v_path, scenes = create_explainer_video(final_topic, final_lang)
                    if v_path and os.path.exists(v_path):
                        st.success("Video ban gaya! 🔥")
                        st.video(v_path)
                        with open(v_path, "rb") as f:
                            st.download_button("⬇️ Video Download Karo", f, file_name=f"{final_topic}_{final_lang}.mp4", mime="video/mp4")
                        with st.expander("📜 Script Dekho"):
                            for i, s in enumerate(scenes):
                                st.write(f"**Scene {i+1}: {s['title']}**")
                                st.write(s['explain'])
                                st.divider()
                    else:
                        st.error(scenes if isinstance(scenes, str) else "Video nahi bana, dubara try karo")
                except Exception as e:
                    st.error(f"Error: {e}")

elif active=="Story":
    tp=universal_input("story","Topic bolo - jaise Stack")
    if st.button("🎬 Movie Banao",type="primary") and tp:
        st.markdown(story_mode_learning(tp))
elif active=="Projects":
    idea=universal_input("proj","Project idea bolo - Smart Dustbin")
    bud=st.selectbox("Budget",["low (under ₹1500)","medium (₹1500-5000)","high (₹5000+)"])
    if st.button("🚀 Guide Banao",type="primary") and idea:
        st.markdown(build_project_guide(idea,bud))
elif active=="Podcast":
    tp=universal_input("pod","Topic bolo - Podcast ke liye")
    if st.button("🎙️ Podcast Script Banao",type="primary") and tp:
        st.markdown(generate_podcast_script(tp))
elif active=="Summary":
    if st.button("Summary Banao",type="primary"): st.markdown(generate_summary())
elif active=="Important":
    if st.button("Predict Karo",type="primary"): st.markdown(predict_important_questions())

with st.expander("🕘 History"):
    h=load_conversation_history()
    for x in reversed(h[-10:]):
        st.markdown(f"**Q:** {x['query']}"); st.markdown(x['answer'][:500]); st.divider()
