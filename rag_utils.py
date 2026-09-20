import os
import re
import json
import io
import tempfile
from typing import Optional, List

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from gtts import gTTS
from PIL import Image
from docx import Document
from docx.shared import Inches

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader

load_dotenv()

# ============================================================
# CONFIG
# ============================================================
MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
MAX_CONTEXT_CHARS = 12000


def get_api_key():
    """Read Groq API key from Streamlit secrets first, then environment."""
    try:
        key = st.secrets.get("GROQ_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY")


def _require_api_key():
    key = get_api_key()
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY missing. Add it to Streamlit Secrets or your .env file."
        )
    return key


@st.cache_resource(show_spinner=False)
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )


def get_lang_code(lang_name):
    mapping = {
        "Hindi": "hi",
        "Gujarati": "gu",
        "Hinglish": "hi",
        "English": "en",
        "Marathi": "mr",
    }
    return mapping.get(lang_name, "hi")


def _llm(temperature=0.2):
    return ChatGroq(
        model=MODEL_NAME,
        groq_api_key=_require_api_key(),
        temperature=temperature,
    )


def _clean_text(text):
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _invoke(prompt, temperature=0.2):
    return _llm(temperature).invoke(prompt).content


def _json_from_text(text, default=None):
    """Extract the first JSON object/array from an LLM response."""
    if not text:
        return default
    text = text.strip()
    candidates = []

    first_array = text.find("[")
    last_array = text.rfind("]")
    if first_array >= 0 and last_array > first_array:
        candidates.append(text[first_array:last_array + 1])

    first_obj = text.find("{")
    last_obj = text.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        candidates.append(text[first_obj:last_obj + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return default


# ============================================================
# AUDIO
# ============================================================

def text_to_audio_file(text, language_name="Hinglish"):
    try:
        clean = _clean_text(text)[:3500]
        if not clean:
            return None

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        try:
            gTTS(text=clean, lang=get_lang_code(language_name), slow=False).save(tmp.name)
        except Exception:
            # gTTS can reject some language combinations; English is a safe fallback.
            gTTS(text=clean, lang="en", slow=False).save(tmp.name)

        if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 1000:
            return tmp.name
        return None
    except Exception as e:
        print(f"TTS Error: {e}")
        return None


def transcribe_audio(api_key, audio_path):
    try:
        key = api_key or get_api_key()
        if not key:
            return None

        client = Groq(api_key=key)
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3-turbo",
                language="hi",
                response_format="text",
            )
        return transcription if isinstance(transcription, str) else transcription.text
    except Exception as e:
        print(f"Whisper Error: {e}")
        return None


# ============================================================
# DOCUMENT PROCESSING / RAG
# ============================================================

def process_files(files, chunk_size=1000, chunk_overlap=100):
    if not files:
        st.warning("No files uploaded")
        return

    docs = []
    processed_names = []

    for file in files:
        ext = os.path.splitext(file.name)[-1].lower()
        path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file.getvalue())
                path = tmp.name

            if ext == ".pdf":
                loader = PyPDFLoader(path)
            elif ext == ".csv":
                loader = CSVLoader(path)
            elif ext == ".txt":
                loader = TextLoader(path, encoding="utf-8")
            else:
                st.warning(f"Unsupported file skipped: {file.name}")
                continue

            loaded = loader.load()
            for d in loaded:
                d.metadata["source"] = file.name
                d.metadata["file_name"] = file.name
            clean_loaded = [d for d in loaded if d.page_content.strip()]
            docs.extend(clean_loaded)
            if clean_loaded:
                processed_names.append(file.name)

        except Exception as e:
            st.error(f"Error loading {file.name}: {e}")
        finally:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    if not docs:
        st.error("No content extracted!")
        return

    chunk_size = max(300, int(chunk_size))
    chunk_overlap = max(0, min(int(chunk_overlap), chunk_size - 1))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(docs)

    try:
        vectordb = FAISS.from_documents(chunks, get_embeddings())
    except Exception as e:
        st.error(f"Embedding/FAISS error: {e}")
        return

    st.session_state.vectordb = vectordb
    st.session_state.history = []
    st.session_state.weak_topics = {}
    st.session_state.kb_files = processed_names
    st.session_state.kb_chunk_count = len(chunks)

    st.success(
        f"✅ {len(chunks)} chunks ready from {len(docs)} document sections!"
    )


def hybrid_search(query, k=8):
    """Robust lightweight hybrid retrieval without an extra BM25 dependency.

    FAISS provides semantic retrieval. A small lexical bonus is then applied so
    exact terms from the student's query are less likely to disappear from the
    final context. This keeps deployment simple while improving RAG quality.
    """
    vb = st.session_state.get("vectordb")
    if vb is None:
        return []

    try:
        k = max(1, int(k))
        candidate_n = min(max(k * 3, 12), 40)
        candidates = vb.similarity_search_with_score(query, k=candidate_n)
    except Exception:
        try:
            return vb.similarity_search(query, k=k)
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    terms = set(re.findall(r"[a-zA-Z0-9_]{3,}", str(query).lower()))
    scored = []
    for doc, distance in candidates:
        text = str(doc.page_content or "").lower()
        lexical = sum(text.count(term) for term in terms)
        # FAISS distance is lower-is-better for the common indexes used here.
        semantic = 1.0 / (1.0 + max(float(distance), 0.0))
        score = semantic + min(lexical, 8) * 0.035
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]


def _context_for(query, k=8, per_doc=1600):
    docs = hybrid_search(query, k=k)
    pieces = []
    for d in docs:
        source = d.metadata.get("source", "Unknown")
        page = d.metadata.get("page")
        page_text = f" | page {page + 1}" if isinstance(page, int) else ""
        pieces.append(
            f"[SOURCE: {source}{page_text}]\n{d.page_content[:per_doc]}"
        )
    return "\n\n".join(pieces)[:MAX_CONTEXT_CHARS], docs


def ask_question(query, k=8, mode="normal", language="Hinglish"):
    vb = st.session_state.get("vectordb")
    if vb is None:
        return "Pehle File Upload karo.", []

    docs = hybrid_search(query, k=k)
    if not docs:
        return "PDF me ye topic nahi mila.", []

    ctx_parts = []
    for d in docs:
        source = d.metadata.get("source", "Unknown")
        page = d.metadata.get("page")
        page_text = f" page {page + 1}" if isinstance(page, int) else ""
        ctx_parts.append(
            f"[SOURCE: {source}{page_text}]\n{d.page_content[:1800]}"
        )
    ctx = "\n\n".join(ctx_parts)[:MAX_CONTEXT_CHARS]

    if mode.lower() == "socratic":
        prompt = f"""
You are a patient Socratic teacher.
Language: {language}
Student question: {query}

Use ONLY the supplied study context. Do not invent facts.
Instead of immediately giving the complete answer, guide the student with
2-4 useful leading questions and a tiny hint. If the context is insufficient,
say so clearly.

STUDY CONTEXT:
{ctx}
"""
    else:
        prompt = f"""
You are a helpful AI teaching assistant.
Language: {language}
Student question: {query}

Answer using the supplied study context. Keep the explanation student-friendly.
Use headings/bullets when useful. If a claim is not supported by the context,
say 'Context me nahi hai' rather than inventing it.
At the end, add a short 'Quick Recall' section with 2-4 key points.

STUDY CONTEXT:
{ctx}
"""

    try:
        ans = _invoke(prompt, temperature=0.2)
    except Exception as e:
        return f"AI error: {e}", [d.metadata for d in docs]

    if "history" not in st.session_state:
        st.session_state.history = []

    st.session_state.history.append(
        {
            "query": query,
            "answer": ans,
            "sources": [d.metadata for d in docs],
        }
    )
    return ans, [d.metadata for d in docs]


# ============================================================
# QUIZ / PRACTICE
# ============================================================

def generate_quiz(num_q=5, language="Hinglish", topic=None):
    topic_text = topic or "the uploaded study material"
    search_query = topic or "important concepts definitions"
    docs = hybrid_search(search_query, k=8)

    if not docs:
        return [
            {
                "question": f"No study material found for {topic_text}. What should you do first?",
                "options": [
                    "a) Upload study material",
                    "b) Delete the app",
                    "c) Skip studying",
                    "d) None",
                ],
                "answer": "a) Upload study material",
                "explanation": "Upload the relevant PDF/TXT/CSV first.",
                "topic": "setup",
            }
        ]

    ctx = "\n".join(
        f"[SOURCE {d.metadata.get('source','Unknown')}] {d.page_content[:1200]}"
        for d in docs
    )[:8000]

    prompt = f"""
Create {int(num_q)} high-quality MCQs for a student.
Language: {language}
Topic focus: {topic_text}

Use ONLY this context:
{ctx}

Return ONLY a JSON array. Every item must contain:
question, options (exactly 4 strings), answer (one exact option string),
explanation, topic.
Make distractors plausible and do not repeat the same question.
"""

    try:
        data = _json_from_text(_invoke(prompt, temperature=0.4), default=None)
        if isinstance(data, list) and data:
            cleaned = []
            for item in data[: int(num_q)]:
                if isinstance(item, dict):
                    options = item.get("options", [])
                    if not isinstance(options, list):
                        options = []
                    options = [str(x).strip() for x in options[:4] if str(x).strip()]
                    answer = str(item.get("answer", "")).strip()
                    question = str(item.get("question", "")).strip()
                    if question and len(options) == 4 and answer:
                        cleaned.append(
                            {
                                "question": question,
                                "options": options,
                                "answer": answer,
                                "explanation": str(item.get("explanation", "Review the study context.")).strip(),
                                "topic": str(item.get("topic", topic_text)).strip() or topic_text,
                            }
                        )
            if cleaned:
                return cleaned
    except Exception as e:
        print(f"Quiz generation error: {e}")

    return [
        {
            "question": f"What is an important concept from {topic_text}?",
            "options": [
                "a) Refer to the uploaded notes",
                "b) Unrelated option",
                "c) Unrelated option",
                "d) Unrelated option",
            ],
            "answer": "a) Refer to the uploaded notes",
            "explanation": "Review the uploaded material for the exact concept.",
            "topic": topic_text,
        }
        for _ in range(int(num_q))
    ]


def check_quiz_answer(question, user_ans, correct_ans, topic="general"):
    normalize = lambda x: re.sub(r"\s+", " ", str(x).strip().lower())
    a = normalize(user_ans)
    b = normalize(correct_ans)

    # Exact text first; then compare option letters such as a), b), etc.
    ok = a == b
    if not ok:
        ma = re.match(r"^([a-d])(?:[\).:\-\s]|$)", a)
        mb = re.match(r"^([a-d])(?:[\).:\-\s]|$)", b)
        ok = bool(ma and mb and ma.group(1) == mb.group(1))

    if not ok:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt

    return ok, ("✅ Sahi Jawaab!" if ok else f"❌ Galat. Sahi: {correct_ans}")


def build_quiz_final_report(quiz_data, answers, language="Hinglish"):
    """Create a deterministic final quiz report with every wrong answer and its correct answer."""
    report=[]
    correct=0
    for i,q in enumerate(quiz_data or []):
        user_ans = str((answers or {}).get(i, "")).strip()
        correct_ans = str(q.get("answer", "")).strip()
        ok,_ = check_quiz_answer(q.get("question", ""), user_ans, correct_ans, q.get("topic", "general"))
        if ok: correct += 1
        report.append({
            "number": i+1,
            "question": q.get("question", ""),
            "user_answer": user_ans or "Not answered",
            "correct_answer": correct_ans,
            "is_correct": bool(ok),
            "explanation": q.get("explanation", ""),
            "topic": q.get("topic", "General"),
        })
    total=len(report)
    return {"total":total,"correct":correct,"wrong":total-correct,"score":round(correct/total*100) if total else 0,"items":report}


def build_viva_final_report(viva_data, evaluations, language="Hinglish"):
    """Create a final viva report including student answer, score, correct/reference answer and missing points."""
    items=[]
    total=len(viva_data or [])
    earned=0.0
    for i,q in enumerate(viva_data or []):
        ev=(evaluations or {}).get(i,{})
        try: score=float(ev.get("score",0))
        except Exception: score=0.0
        earned += max(0,min(10,score))
        items.append({
            "number":i+1,
            "question":q.get("q", ""),
            "user_answer":ev.get("user_answer", "Not answered"),
            "correct_answer":q.get("a", ""),
            "score":round(score,1),
            "is_correct":bool(ev.get("is_correct",False)),
            "feedback":ev.get("feedback", ""),
            "missing_points":ev.get("missing_points",[]) or [],
        })
    percent=round((earned/(total*10))*100) if total else 0
    return {"total":total,"earned":round(earned,1),"score":percent,"items":items}


def generate_adaptive_quiz(num_q=5, language="Hinglish", weak_topics=None):
    """Generate practice biased toward the student's weakest tracked topics."""
    weak_topics = weak_topics or get_weak_topics()
    if weak_topics:
        focus = ", ".join(
            t for t, _ in sorted(weak_topics.items(), key=lambda x: x[1], reverse=True)[:5]
        )
    else:
        focus = "core concepts from the uploaded material"
    return generate_quiz(num_q=num_q, language=language, topic=focus)


def get_weak_topics():
    return st.session_state.get("weak_topics", {})


# ============================================================
# STUDY CONTENT GENERATORS
# ============================================================

def generate_summary(language="Hinglish", topic=None):
    query = topic or "summary overview"
    ctx, _ = _context_for(query, k=10, per_doc=1500)
    if not ctx:
        return "Pehle study material upload karo."

    prompt = f"""
Create a detailed but easy-to-revise study summary.
Language: {language}
Topic: {topic or 'all uploaded material'}
Use ONLY the context below.
Include: core concepts, definitions, important relationships, examples,
and a final 10-point quick revision list.

CONTEXT:
{ctx}
"""
    try:
        return _invoke(prompt, temperature=0.2)
    except Exception as e:
        return f"AI error: {e}"


def predict_important_questions(language="Hinglish", topic=None):
    query = topic or "exam important questions"
    ctx, _ = _context_for(query, k=10, per_doc=1500)
    if not ctx:
        return "Pehle study material upload karo."

    prompt = f"""
Based ONLY on the supplied study material, create a revision-oriented list of
likely important questions. Do NOT claim that these questions are guaranteed
to appear in an exam.
Language: {language}
Topic: {topic or 'uploaded material'}
For each question, include a short reason based on the material and a concise
answer outline.

CONTEXT:
{ctx}
"""
    try:
        return _invoke(prompt, temperature=0.3)
    except Exception as e:
        return f"AI error: {e}"


def load_conversation_history():
    return st.session_state.get("history", [])


def story_mode_learning(topic, language="Hinglish"):
    ctx, _ = _context_for(topic, k=8, per_doc=1400)
    if not ctx:
        return "Pehle relevant study material upload karo."

    prompt = f"""
Teach {topic} as a memorable short story for a student.
Language: {language}
Use ONLY the study context. Preserve technical correctness.
After the story, add 'Real Meaning' and '3 Things To Remember'.

CONTEXT:
{ctx}
"""
    try:
        return _invoke(prompt, temperature=0.8)
    except Exception as e:
        return f"AI error: {e}"


def build_project_guide(idea, budget="low", language="Hinglish"):
    ctx, _ = _context_for(idea, k=6, per_doc=1200)

    prompt = f"""
You are an Expert IoT Project Mentor for Indian students.
Project idea: {idea}
Budget: {budget}
Language: {language}

Relevant uploaded context:
{ctx or 'No relevant context found.'}

Create a practical build guide with:
1. Project overview
2. Components table: component, quantity, purpose, approximate INR range
3. ESP32 wiring/pin table
4. Full Arduino code where appropriate
5. App/Blynk setup if applicable
6. Assembly steps
7. Testing checklist
8. Troubleshooting
9. Total budget estimate
10. Future enhancements

Do not invent exact hardware details that are not established; clearly label
reasonable examples as examples.
"""
    try:
        return _invoke(prompt, temperature=0.5)
    except Exception as e:
        return f"AI error: {e}"


def generate_podcast_script(topic, language="Hinglish"):
    ctx, _ = _context_for(topic, k=6, per_doc=1300)
    if not ctx:
        return "Pehle relevant study material upload karo."

    prompt = f"""
Write an engaging 2-host educational podcast about {topic}.
Language: {language}
Hosts: Host 1 and Host 2.
Use ONLY the context below.
Include intro, explanation, example, common mistake, recap, and a short quiz.

CONTEXT:
{ctx}
"""
    try:
        return _invoke(prompt, temperature=0.8)
    except Exception as e:
        return f"AI error: {e}"


def generate_viva_questions(topic, num_q=5, language="Hinglish"):
    ctx, _ = _context_for(topic, k=8, per_doc=1300)
    if not ctx:
        return [{"q": f"Explain {topic}.", "a": "Upload study material for a source-grounded answer."}]

    prompt = f"""
Generate {int(num_q)} viva questions for {topic}.
Language: {language}
Use ONLY the context.
Return ONLY JSON array with objects: {{"q":"...","a":"..."}}
Mix definition, why/how, application, comparison, and troubleshooting questions.

CONTEXT:
{ctx}
"""
    try:
        data = _json_from_text(_invoke(prompt, temperature=0.4), default=None)
        if isinstance(data, list) and data:
            return [
                {"q": str(x.get("q", "")), "a": str(x.get("a", ""))}
                for x in data[: int(num_q)]
                if isinstance(x, dict)
            ]
    except Exception as e:
        print(f"Viva generation error: {e}")

    return [
        {"q": f"Explain {topic}.", "a": f"Review the uploaded material for {topic}."}
        for _ in range(int(num_q))
    ]


def verify_viva_answer(question, correct_ans, user_ans, language="Hinglish"):
    prompt = f"""
Evaluate a student's viva answer.
Language: {language}
Question: {question}
Reference answer: {correct_ans}
Student answer: {user_ans}

Return ONLY JSON:
{{"verdict":"True/False","score":0,"feedback":"...","missing_points":["..."]}}
Score from 0 to 10 based on correctness and coverage.
Do not reward confident wording if the technical content is wrong.
"""
    try:
        data = _json_from_text(_invoke(prompt, temperature=0.2), default=None)
        if isinstance(data, dict):
            data.setdefault("verdict", "False")
            data.setdefault("score", 0)
            data.setdefault("feedback", "")
            data.setdefault("missing_points", [])
            return data
    except Exception as e:
        print(f"Viva verification error: {e}")

    a = _clean_text(user_ans).lower()
    b = _clean_text(correct_ans).lower()
    ok = bool(a and (a in b or b in a))
    return {
        "verdict": str(ok),
        "score": 10 if ok else 0,
        "feedback": f"Correct answer: {correct_ans}",
        "missing_points": [],
    }


# ============================================================
# ADVANCED RETENTION HELPERS
# These are optional additions for the V24 UI and do not replace
# any original function.
# ============================================================

def generate_teach_back_feedback(topic, student_explanation, language="Hinglish"):
    ctx, _ = _context_for(topic, k=8, per_doc=1300)
    prompt = f"""
You are a strict but encouraging teacher.
Topic: {topic}
Language: {language}
Student's teach-back explanation:
{student_explanation}

Reference study context:
{ctx or 'No uploaded context available.'}

Evaluate the student's explanation against the context.
Return ONLY JSON:
{{
  "score": 0,
  "verdict": "Strong/Needs Work",
  "what_was_correct": ["..."],
  "missing_or_wrong": ["..."],
  "one_better_explanation": "...",
  "next_question": "..."
}}
Score 0-10. Do not invent facts outside the context.
"""
    try:
        data = _json_from_text(_invoke(prompt, temperature=0.2), default=None)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"Teach-back error: {e}")
    return {
        "score": 0,
        "verdict": "Needs Work",
        "what_was_correct": [],
        "missing_or_wrong": ["AI evaluation failed."],
        "one_better_explanation": "Try again after checking your notes.",
        "next_question": topic,
    }


def generate_revision(topic, language="Hinglish", focus="weakness"):
    ctx, _ = _context_for(topic, k=8, per_doc=1400)
    prompt = f"""
Create a compact smart-revision session for topic: {topic}
Language: {language}
Focus: {focus}
Use ONLY this context:
{ctx or 'No context available.'}

Return sections:
1. 5-minute recap
2. 5 flashcards (Q/A)
3. 3 common traps
4. 3 self-test questions without answers first
5. answer key
"""
    try:
        return _invoke(prompt, temperature=0.35)
    except Exception as e:
        return f"AI error: {e}"


def generate_exam_attack(topic, language="Hinglish"):
    ctx, _ = _context_for(topic, k=10, per_doc=1400)
    prompt = f"""
Build an exam-focused study attack plan for {topic}.
Language: {language}
Use ONLY the supplied material.
Do not claim certainty about actual exam questions.
Include: must-know concepts, definitions, comparisons, diagrams/processes to
practice, 5 self-test questions, common mistakes, and a 30-minute plan.

CONTEXT:
{ctx or 'No context available.'}
"""
    try:
        return _invoke(prompt, temperature=0.3)
    except Exception as e:
        return f"AI error: {e}"


def generate_confusion_battle(topic_a, topic_b, language="Hinglish"):
    ctx_a, _ = _context_for(topic_a, k=5, per_doc=1100)
    ctx_b, _ = _context_for(topic_b, k=5, per_doc=1100)
    prompt = f"""
Compare two study concepts for a student.
Concept A: {topic_a}
Concept B: {topic_b}
Language: {language}
Use only supplied context. Clearly mark if either concept lacks context.
Include: definition, key difference table, when used, example, memory trick,
and 5 challenge questions.

A CONTEXT:
{ctx_a or 'Not found'}

B CONTEXT:
{ctx_b or 'Not found'}
"""
    try:
        return _invoke(prompt, temperature=0.35)
    except Exception as e:
        return f"AI error: {e}"


# ============================================================
# PPT
# ============================================================

def create_ppt_file(topic, num_slides=10, language="Hinglish"):
    ctx, _ = _context_for(topic, k=10, per_doc=1100)

    prompt = f"""
Topic: {topic}
Language: {language}
Create {int(num_slides)} educational presentation slides.
Use ONLY this context:
{ctx or 'No context available.'}
Return ONLY JSON array:
[{{"title":"...","points":["p1","p2","p3"]}}]
Keep points short enough for slides.
"""

    try:
        slides = _json_from_text(_invoke(prompt, temperature=0.4), default=None)
        if not isinstance(slides, list) or not slides:
            raise ValueError("Invalid slide JSON")
    except Exception as e:
        print(f"PPT generation error: {e}")
        slides = [
            {
                "title": f"{topic} - Slide {i + 1}",
                "points": [
                    "Important point",
                    "Key concept",
                    "Example / application",
                ],
            }
            for i in range(int(num_slides))
        ]

    from pptx import Presentation
    from pptx.util import Inches as PptInches, Pt
    from pptx.dml.color import RGBColor

    prs = Presentation()
    prs.slide_width = PptInches(13.33)
    prs.slide_height = PptInches(7.5)

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(13, 17, 38)

    title_box = slide.shapes.add_textbox(
        PptInches(0.6), PptInches(2.0), PptInches(12), PptInches(1.5)
    )
    title_box.text_frame.text = topic
    p = title_box.text_frame.paragraphs[0]
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)

    sub_box = slide.shapes.add_textbox(
        PptInches(0.6), PptInches(3.6), PptInches(12), PptInches(1)
    )
    sub_box.text_frame.text = f"AI Teaching Assistant • {language}"
    p = sub_box.text_frame.paragraphs[0]
    p.font.size = Pt(18)
    p.font.color.rgb = RGBColor(210, 210, 255)

    for i, sl in enumerate(slides[: int(num_slides)]):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(249, 250, 255)

        header = slide.shapes.add_shape(
            1, PptInches(0), PptInches(0), PptInches(13.33), PptInches(1)
        )
        header.fill.solid()
        header.fill.fore_color.rgb = RGBColor(13, 17, 38)
        header.line.fill.background()

        ht = slide.shapes.add_textbox(
            PptInches(0.6), PptInches(0.15), PptInches(11.8), PptInches(0.75)
        )
        ht.text_frame.text = f"{i + 1}. {sl.get('title', '')}"
        p = ht.text_frame.paragraphs[0]
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

        ct = slide.shapes.add_textbox(
            PptInches(0.7), PptInches(1.35), PptInches(11.7), PptInches(5.7)
        )
        tf = ct.text_frame
        tf.word_wrap = True
        points = sl.get("points", [])
        if not points:
            points = ["No points generated."]

        for idx, point in enumerate(points[:7]):
            para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            para.text = f"• {point}"
            para.space_after = Pt(12)
            para.font.size = Pt(16)
            para.font.color.rgb = RGBColor(30, 30, 30)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    tmp.close()
    prs.save(tmp.name)
    return tmp.name


# ============================================================
# IMAGE EXPORTS
# ============================================================

def images_to_pdf(image_files):
    pil_images = []

    for img_file in image_files:
        try:
            img_file.seek(0)
            pil_images.append(Image.open(img_file).convert("RGB"))
        except Exception:
            try:
                img_file.seek(0)
                pil_images.append(Image.open(io.BytesIO(img_file.read())).convert("RGB"))
            except Exception:
                continue

    pdf_buffer = io.BytesIO()
    if not pil_images:
        pdf_buffer.seek(0)
        return pdf_buffer

    if len(pil_images) == 1:
        pil_images[0].save(pdf_buffer, format="PDF")
    else:
        pil_images[0].save(
            pdf_buffer,
            format="PDF",
            save_all=True,
            append_images=pil_images[1:],
        )

    pdf_buffer.seek(0)
    return pdf_buffer


def images_to_docx(image_files):
    doc = Document()
    doc.add_heading("RAG Based AI Teaching Assistant", 0)
    doc.add_paragraph(f"Total Images: {len(image_files)}")

    for idx, img_file in enumerate(image_files):
        try:
            img_file.seek(0)
            image = Image.open(img_file)
        except Exception:
            img_file.seek(0)
            image = Image.open(io.BytesIO(img_file.read()))

        temp_buffer = io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(temp_buffer, format="PNG")
        temp_buffer.seek(0)

        doc.add_heading(f"Image {idx + 1}", level=2)
        doc.add_picture(temp_buffer, width=Inches(5.5))

    doc_buffer = io.BytesIO()
    doc.save(doc_buffer)
    doc_buffer.seek(0)
    return doc_buffer

# ============================================================
# NEXT-LEVEL SOURCE STUDIO FEATURES
# ============================================================

def _source_context(query, k=8, per_doc=1800):
    """Return grounded context from the currently indexed knowledge base.

    This helper is intentionally safe: if no files are indexed, it returns a
    clear marker instead of allowing the new Source Studio features to crash.
    """
    try:
        docs = hybrid_search(query, k=k)
    except Exception as e:
        print(f"Source retrieval error: {e}")
        return "No indexed source context is available."

    if not docs:
        return "No indexed source context is available."

    blocks = []
    for i, doc in enumerate(docs, 1):
        meta = getattr(doc, "metadata", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        src = meta.get("source", "Unknown source")
        page = meta.get("page", meta.get("page_number", ""))
        label = f"Source {i}: {os.path.basename(str(src))}"
        if page not in ("", None):
            label += f" | page {page}"
        text = _clean_text(getattr(doc, "page_content", ""))
        if text:
            blocks.append(f"[{label}]\n{text[:per_doc]}")
    return "\n\n".join(blocks) if blocks else "No indexed source context is available."


def _has_source_material():
    """Fast check used by Source Studio generators."""
    return st.session_state.get("vectordb") is not None


def get_source_inventory():
    """Return a compact inventory of indexed documents/chunks without crashing the UI."""
    db = st.session_state.get("vectordb")
    if db is None:
        return {"total_chunks": 0, "sources": []}
    try:
        docs = list(db.docstore._dict.values())
    except Exception:
        docs = []

    # FAISS/docstore internals can vary between langchain-community versions.
    # If the docstore cannot be read, use the metadata already stored by process_files.
    if not docs:
        names = st.session_state.get("kb_files", []) or []
        chunk_count = int(st.session_state.get("kb_chunk_count", 0) or 0)
        if names:
            each = max(1, chunk_count // len(names)) if chunk_count else 0
            return {
                "total_chunks": chunk_count,
                "sources": [{"name": os.path.basename(str(n)), "chunks": each, "pages": []} for n in names],
            }

    grouped = {}
    for d in docs:
        meta = getattr(d, "metadata", {}) or {}
        src = str(meta.get("source", "Unknown source"))
        name = os.path.basename(src) or "Unknown source"
        grouped.setdefault(name, {"name": name, "chunks": 0, "pages": set()})
        grouped[name]["chunks"] += 1
        p = meta.get("page", meta.get("page_number"))
        if p is not None:
            grouped[name]["pages"].add(str(p))

    sources = []
    for item in grouped.values():
        item["pages"] = sorted(
            item["pages"], key=lambda x: int(x) if str(x).isdigit() else str(x)
        )
        sources.append(item)
    return {
        "total_chunks": len(docs),
        "sources": sorted(sources, key=lambda x: x["name"].lower()),
    }


def _studio_json(prompt, fallback):
    try:
        data = _json_from_text(_invoke(prompt, temperature=0.35), default=None)
        return data if data is not None else fallback
    except Exception as e:
        print(f"Source Studio LLM error: {e}")
        return fallback


def generate_source_brief(language="Hinglish"):
    inv = get_source_inventory()
    if not inv["sources"]:
        return "## 📚 Source Brief\n\nNo indexed study material found. Please upload PDF/TXT/CSV in the Knowledge Base first."

    context = _source_context(
        "main topics, definitions, concepts, formulas, examples and important facts",
        k=10,
    )
    prompt = f"""You are a source-grounded academic assistant. Use ONLY the supplied source context.
Create a concise but useful source brief in {language}.
Include: overview, major topics, key concepts, formulas/facts if present, likely exam areas, and source coverage.
Do not invent facts. If something is not present, say it is not found.
Return plain text with clear headings.
Inventory: {json.dumps(inv, ensure_ascii=False)}
SOURCE CONTEXT:\n{context}"""
    try:
        return _invoke(prompt, temperature=0.25)
    except Exception as e:
        return f"## 📚 Source Brief\n\nCould not generate the AI brief right now.\n\nError: {e}"


def generate_flashcards(topic="all material", num_cards=10, language="Hinglish"):
    n = max(3, min(30, int(num_cards)))
    if not _has_source_material():
        return []

    context = _source_context(topic, k=10)
    fallback = [
        {
            "front": f"{topic} — Card {i + 1}",
            "back": "Review the uploaded source material for this concept.",
            "difficulty": "Medium",
            "source": "Uploaded material",
        }
        for i in range(n)
    ]
    prompt = f"""Create {n} high-quality study flashcards from ONLY the source context.
Language: {language}. Topic: {topic}.
Return ONLY JSON array. Each object MUST contain:
{{"front":"question/term","back":"answer","difficulty":"Easy|Medium|Hard","source":"source filename or Uploaded material"}}
Avoid duplicates. Keep answers concise and source-grounded.
SOURCE CONTEXT:\n{context}"""
    data = _studio_json(prompt, fallback)
    if not isinstance(data, list):
        return fallback

    normalized = []
    for i, card in enumerate(data[:n]):
        if not isinstance(card, dict):
            continue
        normalized.append(
            {
                "front": str(card.get("front") or card.get("question") or f"{topic} — Card {i + 1}"),
                "back": str(card.get("back") or card.get("answer") or "Review the uploaded source material."),
                "difficulty": str(card.get("difficulty") or "Medium"),
                "source": str(card.get("source") or "Uploaded material"),
            }
        )
    return normalized or fallback


def generate_mind_map(topic, language="Hinglish"):
    if not _has_source_material():
        return {"topic": topic, "branches": [], "message": "Please upload study material first."}

    context = _source_context(topic, k=10)
    fallback = {
        "topic": topic,
        "branches": [{"name": "Key Concepts", "children": ["Review source material"]}],
    }
    prompt = f"""Build a source-grounded mind map for {topic} in {language}.
Return ONLY JSON: {{"topic":"...","branches":[{{"name":"...","children":["..."]}}]}}
Use only the supplied material; do not invent unsupported concepts.
SOURCE CONTEXT:\n{context}"""
    data = _studio_json(prompt, fallback)
    if not isinstance(data, dict):
        return fallback

    branches = data.get("branches", [])
    normalized = []
    if isinstance(branches, list):
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            children = branch.get("children", [])
            if isinstance(children, str):
                children = [children]
            if not isinstance(children, list):
                children = []
            normalized.append(
                {
                    "name": str(branch.get("name") or "Key Concept"),
                    "children": [str(x) for x in children if str(x).strip()],
                }
            )
    return {"topic": str(data.get("topic") or topic), "branches": normalized or fallback["branches"]}


def generate_exam_paper(topic="all material", num_questions=10, difficulty="Mixed", language="Hinglish"):
    n = max(3, min(30, int(num_questions)))
    if not _has_source_material():
        return []

    context = _source_context(topic, k=12)
    fallback = [
        {
            "question": f"Explain an important concept from {topic}.",
            "answer": "Refer to the uploaded source material.",
            "difficulty": difficulty,
            "type": "Short Answer",
            "marks": 5,
            "topic": topic,
        }
        for _ in range(n)
    ]
    prompt = f"""Generate an exam paper from ONLY the source material.
Topic: {topic}; Questions: {n}; Difficulty: {difficulty}; Language: {language}.
Return ONLY JSON array. Every object MUST contain:
{{"question":"...","answer":"...","difficulty":"Easy|Medium|Hard|Mixed","type":"MCQ|Short Answer|Long Answer","marks":2|5|10,"topic":"..."}}
Cover different concepts, avoid duplicates, and never invent source-specific facts.
SOURCE CONTEXT:\n{context}"""
    data = _studio_json(prompt, fallback)
    if not isinstance(data, list):
        return fallback

    normalized = []
    for i, q in enumerate(data[:n]):
        if not isinstance(q, dict):
            continue
        try:
            marks = int(q.get("marks", 5))
        except Exception:
            marks = 5
        normalized.append(
            {
                "question": str(q.get("question") or f"Question {i + 1} from {topic}"),
                "answer": str(q.get("answer") or "Refer to the uploaded source material."),
                "difficulty": str(q.get("difficulty") or difficulty),
                "type": str(q.get("type") or "Short Answer"),
                "marks": max(1, marks),
                "topic": str(q.get("topic") or topic),
            }
        )
    return normalized or fallback


def compare_source_topics(topic_a, topic_b, language="Hinglish"):
    if not _has_source_material():
        return {
            "topic_a": topic_a,
            "topic_b": topic_b,
            "similarities": [],
            "differences": [],
            "summary": "Please upload study material first.",
        }

    context = _source_context(f"{topic_a} and {topic_b}", k=12)
    fallback = {
        "topic_a": topic_a,
        "topic_b": topic_b,
        "similarities": [],
        "differences": [],
        "summary": "Compare the two topics using the uploaded material.",
    }
    prompt = f"""Compare {topic_a} and {topic_b} using ONLY the source context.
Language: {language}.
Return ONLY JSON with keys topic_a, topic_b, similarities (array), differences (array of objects with aspect,a,b), summary.
If the source does not support a comparison, state that clearly.
SOURCE CONTEXT:\n{context}"""
    data = _studio_json(prompt, fallback)
    if not isinstance(data, dict):
        return fallback

    similarities = data.get("similarities", [])
    differences = data.get("differences", [])
    if isinstance(similarities, str):
        similarities = [similarities]
    if not isinstance(similarities, list):
        similarities = []
    if not isinstance(differences, list):
        differences = []

    norm_diff = []
    for d in differences:
        if not isinstance(d, dict):
            continue
        norm_diff.append(
            {
                "aspect": str(d.get("aspect") or "Aspect"),
                "a": str(d.get("a") or "Not found in source"),
                "b": str(d.get("b") or "Not found in source"),
            }
        )
    return {
        "topic_a": str(data.get("topic_a") or topic_a),
        "topic_b": str(data.get("topic_b") or topic_b),
        "similarities": [str(x) for x in similarities],
        "differences": norm_diff,
        "summary": str(data.get("summary") or "No supported comparison summary found."),
    }


def generate_study_guide(topic="all material", language="Hinglish"):
    if not _has_source_material():
        return "## 📘 Study Guide\n\nPlease upload PDF/TXT/CSV material first."

    context = _source_context(topic, k=12)
    prompt = f"""Create a practical study guide for {topic} in {language}, grounded ONLY in the source context.
Include: prerequisites, learning objectives, concepts in order, examples/applications found in source, common mistakes, revision checklist, and exam focus.
Use headings and bullets. Do not invent unsupported information.
SOURCE CONTEXT:\n{context}"""
    try:
        return _invoke(prompt, temperature=0.25)
    except Exception as e:
        return f"## 📘 Study Guide\n\nCould not generate the AI guide right now.\n\nError: {e}"


def build_study_pack(topic="all material", language="Hinglish"):
    brief = generate_source_brief(language)
    guide = generate_study_guide(topic, language)
    cards = generate_flashcards(topic, 12, language)
    doc = Document()
    doc.add_heading("RAG AI Teaching Assistant — Study Pack", 0)
    doc.add_paragraph(f"Topic: {topic}")
    doc.add_heading("Source Brief", level=1)
    doc.add_paragraph(str(brief))
    doc.add_heading("Study Guide", level=1)
    doc.add_paragraph(str(guide))
    doc.add_heading("Flashcards", level=1)
    for i, card in enumerate(cards, 1):
        doc.add_paragraph(f"{i}. {card.get('front','')}", style="List Number")
        doc.add_paragraph(str(card.get('back','')))
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
