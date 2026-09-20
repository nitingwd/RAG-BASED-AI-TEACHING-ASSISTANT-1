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
        gTTS(
            text=clean,
            lang=get_lang_code(language_name),
            slow=False,
        ).save(tmp.name)

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
    """Vector retrieval used by the current app.

    The function name is kept for backward compatibility with the original app.
    It currently performs FAISS similarity search rather than a BM25+vector hybrid.
    """
    vb = st.session_state.get("vectordb")
    if vb is None:
        return []

    try:
        return vb.similarity_search(query, k=max(1, int(k)))
    except Exception as e:
        print(f"Search Error: {e}")
        return []


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
                    cleaned.append(
                        {
                            "question": str(item.get("question", "")),
                            "options": list(item.get("options", []))[:4],
                            "answer": str(item.get("answer", "")),
                            "explanation": str(item.get("explanation", "")),
                            "topic": str(item.get("topic", topic_text)),
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

    # Accept exact option text or matching option letter.
    ok = a == b or (len(a) >= 2 and len(b) >= 2 and a[:2] == b[:2])

    if not ok:
        wt = st.session_state.get("weak_topics", {})
        wt[topic] = wt.get(topic, 0) + 1
        st.session_state.weak_topics = wt

    return ok, ("✅ Sahi Jawaab!" if ok else f"❌ Galat. Sahi: {correct_ans}")


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
