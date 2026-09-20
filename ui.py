# ============================================================
# ui.py
# RAG Based AI Teaching Assistant
# Complete Streamlit UI
# ============================================================

import os
import io
import re
import json
import tempfile
from datetime import datetime

import streamlit as st
from docx import Document
from docx.shared import Inches

# ReportLab is used only for PDF report export.
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        PageBreak,
        ListFlowable,
        ListItem,
    )
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# ============================================================
# BACKEND IMPORTS
# ============================================================

from rag_utils import (
    get_api_key,
    process_files,
    ask_question,
    generate_quiz,
    check_quiz_answer,
    generate_adaptive_quiz,
    get_weak_topics,
    generate_summary,
    predict_important_questions,
    story_mode_learning,
    build_project_guide,
    generate_podcast_script,
    generate_viva_questions,
    verify_viva_answer,
    generate_teach_back_feedback,
    generate_revision,
    generate_exam_attack,
    generate_confusion_battle,
    create_ppt_file,
    images_to_pdf,
    images_to_docx,
    text_to_audio_file,
    transcribe_audio,
    load_conversation_history,
    _invoke,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Teaching Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "vectordb": None,
    "history": [],
    "weak_topics": {},
    "kb_files": [],
    "kb_chunk_count": 0,
    "kb_doc_count": 0,

    # Tutor
    "chat_messages": [],

    # Quiz
    "quiz_data": [],
    "quiz_results": [],
    "quiz_started": False,
    "quiz_finished": False,

    # Viva
    "viva_data": [],
    "viva_results": [],
    "viva_started": False,
    "viva_finished": False,

    # Project
    "project_outputs": {},

    # Feature outputs
    "feature_reports": {},

    # Settings
    "language": "Hinglish",
    "answer_length": "Detailed",
    "retrieval_k": 8,
    "chunk_size": 1000,
    "chunk_overlap": 100,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

.main-title {
    font-size: 2.3rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}

.subtitle {
    color: #6b7280;
    font-size: 1rem;
    margin-bottom: 1.3rem;
}

.card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(128,128,128,0.18);
    background: rgba(128,128,128,0.04);
    margin-bottom: 1rem;
}

.success-card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid #22c55e;
    background: rgba(34,197,94,0.08);
    margin-bottom: 1rem;
}

.warning-card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid #f59e0b;
    background: rgba(245,158,11,0.08);
    margin-bottom: 1rem;
}

.danger-card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid #ef4444;
    background: rgba(239,68,68,0.08);
    margin-bottom: 1rem;
}

.metric-card {
    padding: 1rem;
    border-radius: 16px;
    text-align: center;
    border: 1px solid rgba(128,128,128,0.2);
    background: rgba(128,128,128,0.05);
}

.metric-number {
    font-size: 1.8rem;
    font-weight: 800;
}

.metric-label {
    font-size: 0.85rem;
    color: #6b7280;
}

.small-muted {
    color: #6b7280;
    font-size: 0.85rem;
}

.result-correct {
    border-left: 5px solid #22c55e;
    padding: 0.8rem 1rem;
    background: rgba(34,197,94,0.07);
    border-radius: 10px;
    margin-bottom: 0.8rem;
}

.result-partial {
    border-left: 5px solid #f59e0b;
    padding: 0.8rem 1rem;
    background: rgba(245,158,11,0.07);
    border-radius: 10px;
    margin-bottom: 0.8rem;
}

.result-wrong {
    border-left: 5px solid #ef4444;
    padding: 0.8rem 1rem;
    background: rgba(239,68,68,0.07);
    border-radius: 10px;
    margin-bottom: 0.8rem;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    return str(value or "").strip()


def answer_length_instruction(length):
    mapping = {
        "Short": (
            "Give a concise answer. Cover only the essential points. "
            "Avoid unnecessary explanation."
        ),
        "Medium": (
            "Give a balanced answer with enough explanation, examples, "
            "and important points."
        ),
        "Detailed": (
            "Give a detailed student-friendly answer with definitions, "
            "explanation, examples, important points, and conclusion."
        ),
        "Very Detailed": (
            "Give a very comprehensive answer. Cover the topic deeply with "
            "definitions, step-by-step explanation, examples, comparisons, "
            "applications, common mistakes, and quick revision points."
        ),
    }
    return mapping.get(length, mapping["Detailed"])


def save_feature_report(name, content):
    st.session_state.feature_reports[name] = {
        "content": content,
        "time": datetime.now().strftime("%d-%m-%Y %H:%M"),
    }


def safe_score(value, default=0):
    try:
        return max(0.0, min(10.0, float(value)))
    except Exception:
        return float(default)


def classify_viva_result(result):
    """
    Robust classification.

    Supports:
    Correct
    Partial
    Incorrect
    True
    False
    true
    false
    correct
    wrong
    etc.

    Score is used as fallback.
    """

    verdict = clean_text(result.get("verdict", "")).lower()

    if verdict in {
        "correct",
        "true",
        "yes",
        "right",
        "fully correct",
        "correct answer",
    }:
        return "Correct"

    if verdict in {
        "partial",
        "partially correct",
        "partially",
        "needs work",
    }:
        return "Partial"

    if verdict in {
        "incorrect",
        "false",
        "wrong",
        "no",
        "incorrect answer",
    }:
        return "Incorrect"

    score = safe_score(result.get("score", 0))

    if score >= 8:
        return "Correct"
    elif score >= 4:
        return "Partial"
    return "Incorrect"


def normalize_result_score(result):
    score = safe_score(result.get("score", 0))

    # Viva score normally 0-10.
    # Also handle accidental percentage-like scores.
    if score > 10:
        score = score / 10.0

    return max(0.0, min(10.0, score))


def create_txt_file(text):
    return io.BytesIO(str(text).encode("utf-8"))


def create_docx_file(title, text):
    doc = Document()

    doc.add_heading(title, 0)
    doc.add_paragraph(
        f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    )

    for block in str(text).split("\n"):
        block = block.strip()

        if not block:
            doc.add_paragraph("")
            continue

        if block.startswith("# "):
            doc.add_heading(block[2:], level=1)
        elif block.startswith("## "):
            doc.add_heading(block[3:], level=2)
        elif block.startswith("### "):
            doc.add_heading(block[4:], level=3)
        elif block.startswith("- "):
            doc.add_paragraph(block[2:], style="List Bullet")
        elif re.match(r"^\d+\.\s+", block):
            doc.add_paragraph(
                re.sub(r"^\d+\.\s+", "", block),
                style="List Number",
            )
        else:
            doc.add_paragraph(block)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def create_pdf_file(title, text):
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=45,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=7,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        spaceAfter=6,
    )

    story = [
        Paragraph(title, title_style),
        Paragraph(
            f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            body_style,
        ),
        Spacer(1, 8),
    ]

    for raw_line in str(text).split("\n"):
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        if line.startswith("### "):
            story.append(
                Paragraph(safe[4:], heading_style)
            )

        elif line.startswith("## "):
            story.append(
                Paragraph(safe[3:], heading_style)
            )

        elif line.startswith("# "):
            story.append(
                Paragraph(safe[2:], heading_style)
            )

        elif line.startswith("- "):
            story.append(
                Paragraph("• " + safe[2:], body_style)
            )

        elif re.match(r"^\d+\.\s+", line):
            story.append(
                Paragraph(safe, body_style)
            )

        else:
            story.append(
                Paragraph(safe, body_style)
            )

    doc.build(story)

    buffer.seek(0)
    return buffer


def export_buttons(title, content, filename_prefix):
    st.markdown("### 📥 Export")

    txt = create_txt_file(content)
    docx = create_docx_file(title, content)
    pdf = create_pdf_file(title, content)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "📄 TXT",
            data=txt.getvalue(),
            file_name=f"{filename_prefix}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with c2:
        st.download_button(
            "📝 DOCX",
            data=docx.getvalue(),
            file_name=f"{filename_prefix}.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
        )

    with c3:
        if pdf is not None:
            st.download_button(
                "📕 PDF",
                data=pdf.getvalue(),
                file_name=f"{filename_prefix}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.info(
                "PDF export ke liye requirements.txt me "
                "`reportlab>=4.0.0` add karo."
            )


def get_all_feature_reports_text():
    if not st.session_state.feature_reports:
        return "No feature reports generated yet."

    parts = []

    for name, item in st.session_state.feature_reports.items():
        parts.append(
            f"""
============================================================
{name.upper()}
Generated: {item.get('time', '')}
============================================================

{item.get('content', '')}
"""
        )

    return "\n".join(parts)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎓 AI Teaching Assistant")

    st.caption(
        "Study • Quiz • Viva • Projects • Reports • Voice"
    )

    st.divider()

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    st.session_state.language = st.selectbox(
        "🌐 Language",
        [
            "Hinglish",
            "English",
            "Hindi",
            "Gujarati",
            "Marathi",
        ],
        index=[
            "Hinglish",
            "English",
            "Hindi",
            "Gujarati",
            "Marathi",
        ].index(st.session_state.language),
    )

    # --------------------------------------------------------
    # ANSWER LENGTH
    # --------------------------------------------------------

    st.session_state.answer_length = st.selectbox(
        "📏 Answer Length",
        [
            "Short",
            "Medium",
            "Detailed",
            "Very Detailed",
        ],
        index=[
            "Short",
            "Medium",
            "Detailed",
            "Very Detailed",
        ].index(st.session_state.answer_length),
    )

    st.caption(
        "Very Detailed select karne par AI ko maximum useful detail "
        "dene ke liye instruction milega."
    )

    st.divider()

    # --------------------------------------------------------
    # KNOWLEDGE BASE
    # --------------------------------------------------------

    st.markdown("### 📚 Knowledge Base")

    uploaded_files = st.file_uploader(
        "Study / Project Files",
        type=[
            "pdf",
            "txt",
            "csv",
            "md",
            "py",
            "js",
            "ts",
            "java",
            "c",
            "cpp",
            "h",
            "hpp",
            "cs",
            "go",
            "rs",
            "php",
            "html",
            "css",
            "sql",
            "json",
            "xml",
            "yaml",
            "yml",
            "ino",
            "sh",
            "bat",
        ],
        accept_multiple_files=True,
        help=(
            "PDF, notes, CSV aur project/source files upload kar sakte ho. "
            "Backend me supported extensions process honge."
        ),
    )

    st.session_state.chunk_size = st.slider(
        "Chunk Size",
        min_value=300,
        max_value=2000,
        value=int(st.session_state.chunk_size),
        step=100,
    )

    st.session_state.chunk_overlap = st.slider(
        "Chunk Overlap",
        min_value=0,
        max_value=500,
        value=int(st.session_state.chunk_overlap),
        step=50,
    )

    st.session_state.retrieval_k = st.slider(
        "Retrieval Depth",
        min_value=3,
        max_value=15,
        value=int(st.session_state.retrieval_k),
    )

    if st.button(
        "🔨 Build / Update Knowledge Base",
        use_container_width=True,
        type="primary",
    ):
        if uploaded_files:
            process_files(
                uploaded_files,
                chunk_size=st.session_state.chunk_size,
                chunk_overlap=st.session_state.chunk_overlap,
            )

            # Backend may not set this.
            st.session_state.kb_doc_count = len(
                st.session_state.get("kb_files", [])
            )

        else:
            st.warning("Pehle files upload karo.")

    if st.session_state.kb_files:
        st.success(
            f"📚 {len(st.session_state.kb_files)} file(s) loaded"
        )

        st.caption(
            f"Chunks: {st.session_state.kb_chunk_count}"
        )

    st.divider()

    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

    if st.button(
        "🧹 Reset Session",
        use_container_width=True,
    ):
        keys_to_reset = [
            "vectordb",
            "history",
            "weak_topics",
            "kb_files",
            "kb_chunk_count",
            "kb_doc_count",
            "chat_messages",
            "quiz_data",
            "quiz_results",
            "quiz_started",
            "quiz_finished",
            "viva_data",
            "viva_results",
            "viva_started",
            "viva_finished",
            "project_outputs",
            "feature_reports",
        ]

        for key in keys_to_reset:
            st.session_state[key] = (
                {} if key in {
                    "weak_topics",
                    "project_outputs",
                    "feature_reports",
                }
                else []
                if key in {
                    "history",
                    "kb_files",
                    "chat_messages",
                    "quiz_data",
                    "quiz_results",
                    "viva_data",
                    "viva_results",
                }
                else None
                if key == "vectordb"
                else 0
                if key in {
                    "kb_chunk_count",
                    "kb_doc_count",
                }
                else False
            )

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 RAG Based AI Teaching Assistant</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Learn smarter • Practice • Give Viva • Build Projects • Analyze Performance"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# DASHBOARD
# ============================================================

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-number">
                {len(st.session_state.get("kb_files", []))}
            </div>
            <div class="metric-label">Files</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-number">
                {st.session_state.get("kb_chunk_count", 0)}
            </div>
            <div class="metric-label">Knowledge Chunks</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-number">
                {len(st.session_state.get("quiz_results", []))}
            </div>
            <div class="metric-label">Quiz Attempts</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-number">
                {len(st.session_state.get("viva_results", []))}
            </div>
            <div class="metric-label">Viva Answers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("")


# ============================================================
# MAIN TABS
# ============================================================

tabs = st.tabs(
    [
        "🏠 Dashboard",
        "🤖 AI Tutor",
        "📖 Study Lab",
        "📝 Quiz Lab",
        "🎤 Viva Lab",
        "🚀 Project Lab",
        "🎧 Media Lab",
        "📊 Reports",
    ]
)


# ============================================================
# TAB 1 - DASHBOARD
# ============================================================

with tabs[0]:

    st.markdown("## 🏠 Dashboard")

    if st.session_state.kb_files:
        st.markdown(
            """
            <div class="success-card">
                <b>Knowledge Base Ready ✅</b><br>
                Your uploaded material is available for RAG-based learning,
                quiz generation, viva preparation and study tools.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 📚 Loaded Files")

        for filename in st.session_state.kb_files:
            st.write(f"• {filename}")

    else:
        st.markdown(
            """
            <div class="warning-card">
                <b>Knowledge Base Empty</b><br>
                Sidebar se PDF / notes / supported project files upload karke
                <b>Build / Update Knowledge Base</b> press karo.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### ✨ Available Features")

    features = [
        ("🤖 AI Tutor", "Ask questions from your uploaded study material."),
        ("📖 Study Lab", "Summary, important questions, stories and revision."),
        ("📝 Quiz Lab", "Generate quizzes and get complete performance analysis."),
        ("🎤 Viva Lab", "Practice viva and receive answer-by-answer evaluation."),
        ("🚀 Project Lab", "Project planning, architecture, debugging and documentation."),
        ("🎧 Media Lab", "Podcast, voice input, audio and PPT generation."),
        ("📊 Reports", "Generate and export complete learning reports."),
    ]

    cols = st.columns(2)

    for i, (title, description) in enumerate(features):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="card">
                    <h4>{title}</h4>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# TAB 2 - AI TUTOR
# ============================================================

with tabs[1]:

    st.markdown("## 🤖 AI Tutor")

    mode = st.radio(
        "Teaching Mode",
        [
            "Normal",
            "Socratic",
        ],
        horizontal=True,
    )

    question = st.text_area(
        "Ask your question",
        height=120,
        placeholder=(
            "Example: Explain ACID properties with a simple example..."
        ),
    )

    if st.button(
        "🚀 Ask AI",
        type="primary",
        use_container_width=True,
    ):

        if not question.strip():
            st.warning("Question enter karo.")
        else:
            with st.spinner("AI is thinking..."):

                try:
                    answer, sources = ask_question(
                        question,
                        k=st.session_state.retrieval_k,
                        mode=mode.lower(),
                        language=st.session_state.language,
                    )

                    # Optional answer-length refinement.
                    refinement_prompt = f"""
You are improving an answer generated from a student's uploaded study material.

Language: {st.session_state.language}

Student Question:
{question}

Current Answer:
{answer}

Requirement:
{answer_length_instruction(st.session_state.answer_length)}

Keep the factual meaning unchanged.
Do not invent information that is not already present.
Return only the improved answer.
"""

                    try:
                        final_answer = _invoke(
                            refinement_prompt,
                            temperature=0.2,
                        )
                    except Exception:
                        final_answer = answer

                    st.session_state.chat_messages.append(
                        {
                            "question": question,
                            "answer": final_answer,
                            "sources": sources,
                        }
                    )

                    st.markdown("### 💡 Answer")
                    st.markdown(final_answer)

                    if sources:
                        with st.expander("📚 Sources"):
                            for source in sources:
                                st.write(source)

                except Exception as e:
                    st.error(f"AI Tutor error: {e}")

    if st.session_state.chat_messages:

        st.markdown("### 🕘 Conversation History")

        for item in reversed(
            st.session_state.chat_messages[-10:]
        ):
            with st.expander(
                f"Q: {item.get('question', '')[:100]}"
            ):
                st.markdown("**Answer:**")
                st.markdown(item.get("answer", ""))

                if item.get("sources"):
                    st.caption(
                        "Sources: "
                        + ", ".join(
                            str(x.get("source", "Unknown"))
                            if isinstance(x, dict)
                            else str(x)
                            for x in item["sources"]
                        )
                    )


# ============================================================
# TAB 3 - STUDY LAB
# ============================================================

with tabs[2]:

    st.markdown("## 📖 Study Lab")

    study_topic = st.text_input(
        "Topic",
        placeholder="Example: Transaction Management",
        key="study_topic",
    )

    study_col1, study_col2, study_col3 = st.columns(3)

    with study_col1:

        if st.button(
            "📚 Smart Summary",
            use_container_width=True,
        ):

            with st.spinner("Generating summary..."):
                result = generate_summary(
                    language=st.session_state.language,
                    topic=study_topic or None,
                )

            save_feature_report("Smart Summary", result)

            st.markdown(result)

            export_buttons(
                "Smart Summary",
                result,
                "smart_summary",
            )

    with study_col2:

        if st.button(
            "🎯 Important Questions",
            use_container_width=True,
        ):

            with st.spinner("Generating important questions..."):
                result = predict_important_questions(
                    language=st.session_state.language,
                    topic=study_topic or None,
                )

            save_feature_report(
                "Important Questions",
                result,
            )

            st.markdown(result)

            export_buttons(
                "Important Questions",
                result,
                "important_questions",
            )

    with study_col3:

        if st.button(
            "📖 Story Mode",
            use_container_width=True,
        ):

            if not study_topic.strip():
                st.warning("Topic enter karo.")
            else:
                with st.spinner("Creating story..."):
                    result = story_mode_learning(
                        study_topic,
                        language=st.session_state.language,
                    )

                save_feature_report(
                    "Story Mode",
                    result,
                )

                st.markdown(result)

    st.divider()

    study_col4, study_col5, study_col6, study_col7 = st.columns(4)

    with study_col4:

        if st.button(
            "🔄 Smart Revision",
            use_container_width=True,
        ):

            if not study_topic.strip():
                st.warning("Topic enter karo.")
            else:
                with st.spinner("Preparing revision..."):
                    result = generate_revision(
                        study_topic,
                        language=st.session_state.language,
                        focus="weakness",
                    )

                save_feature_report(
                    "Smart Revision",
                    result,
                )

                st.markdown(result)

    with study_col5:

        if st.button(
            "⚔️ Exam Attack",
            use_container_width=True,
        ):

            if not study_topic.strip():
                st.warning("Topic enter karo.")
            else:
                with st.spinner("Building exam plan..."):
                    result = generate_exam_attack(
                        study_topic,
                        language=st.session_state.language,
                    )

                save_feature_report(
                    "Exam Attack",
                    result,
                )

                st.markdown(result)

    with study_col6:

        if st.button(
            "🧠 Teach-Back",
            use_container_width=True,
        ):

            if not study_topic.strip():
                st.warning("Topic enter karo.")
            else:
                st.session_state["teach_back_active"] = True

    with study_col7:

        if st.button(
            "⚖️ Confusion Battle",
            use_container_width=True,
        ):

            st.session_state["confusion_active"] = True

    if st.session_state.get("teach_back_active"):

        st.markdown("### 🧠 Teach-Back Challenge")

        explanation = st.text_area(
            "Apne words me topic explain karo",
            height=180,
            key="teach_back_explanation",
        )

        if st.button(
            "Evaluate My Explanation",
            type="primary",
        ):

            with st.spinner("Evaluating..."):
                feedback = generate_teach_back_feedback(
                    study_topic,
                    explanation,
                    language=st.session_state.language,
                )

            result_text = json.dumps(
                feedback,
                ensure_ascii=False,
                indent=2,
            )

            save_feature_report(
                "Teach-Back Evaluation",
                result_text,
            )

            st.metric(
                "Score",
                f"{safe_score(feedback.get('score', 0)):.1f}/10",
            )

            st.markdown(
                f"### Verdict: {feedback.get('verdict', 'Needs Work')}"
            )

            st.markdown("#### ✅ Correct Points")

            for item in feedback.get("what_was_correct", []):
                st.write(f"• {item}")

            st.markdown("#### ⚠️ Missing / Wrong")

            for item in feedback.get("missing_or_wrong", []):
                st.write(f"• {item}")

            st.markdown("#### 📖 Better Explanation")
            st.markdown(
                feedback.get("one_better_explanation", "")
            )

            st.markdown("#### ❓ Next Question")
            st.markdown(
                feedback.get("next_question", "")
            )

    if st.session_state.get("confusion_active"):

        st.markdown("### ⚖️ Confusion Battle")

        ca, cb = st.columns(2)

        with ca:
            topic_a = st.text_input(
                "Concept A",
                placeholder="e.g. Encoder",
                key="confusion_a",
            )

        with cb:
            topic_b = st.text_input(
                "Concept B",
                placeholder="e.g. Decoder",
                key="confusion_b",
            )

        if st.button(
            "Compare Concepts",
            type="primary",
        ):

            if not topic_a.strip() or not topic_b.strip():
                st.warning("Dono concepts enter karo.")
            else:
                with st.spinner("Comparing..."):
                    result = generate_confusion_battle(
                        topic_a,
                        topic_b,
                        language=st.session_state.language,
                    )

                save_feature_report(
                    "Confusion Battle",
                    result,
                )

                st.markdown(result)


# ============================================================
# TAB 4 - QUIZ LAB
# ============================================================

with tabs[3]:

    st.markdown("## 📝 Quiz Lab")

    quiz_topic = st.text_input(
        "Quiz Topic",
        placeholder="Example: DBMS Transaction Management",
        key="quiz_topic",
    )

    q1, q2, q3 = st.columns(3)

    with q1:
        quiz_count = st.number_input(
            "Number of Questions",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
        )

    with q2:
        quiz_mode = st.selectbox(
            "Quiz Type",
            [
                "Fresh Quiz",
                "Adaptive Weak-Topic Quiz",
            ],
        )

    with q3:
        st.metric(
            "Tracked Weak Topics",
            len(get_weak_topics()),
        )

    if st.button(
        "🚀 Generate Quiz",
        type="primary",
        use_container_width=True,
    ):

        with st.spinner("Generating quiz..."):

            if quiz_mode == "Adaptive Weak-Topic Quiz":
                quiz = generate_adaptive_quiz(
                    num_q=int(quiz_count),
                    language=st.session_state.language,
                    weak_topics=get_weak_topics(),
                )
            else:
                quiz = generate_quiz(
                    num_q=int(quiz_count),
                    language=st.session_state.language,
                    topic=quiz_topic or None,
                )

        st.session_state.quiz_data = quiz
        st.session_state.quiz_results = []
        st.session_state.quiz_started = True
        st.session_state.quiz_finished = False

        st.rerun()

    # --------------------------------------------------------
    # ACTIVE QUIZ
    # --------------------------------------------------------

    if (
        st.session_state.quiz_started
        and st.session_state.quiz_data
        and not st.session_state.quiz_finished
    ):

        st.markdown("### 📝 Answer All Questions")

        with st.form("quiz_answer_form"):

            quiz_answers = []

            for idx, item in enumerate(
                st.session_state.quiz_data
            ):

                st.markdown(
                    f"### Q{idx + 1}. "
                    f"{item.get('question', '')}"
                )

                options = item.get("options", [])

                selected = st.radio(
                    "Select answer:",
                    options,
                    key=f"quiz_answer_{idx}",
                    index=None,
                )

                quiz_answers.append(selected)

                st.caption(
                    f"Topic: {item.get('topic', 'general')}"
                )

                st.divider()

            submit_quiz = st.form_submit_button(
                "✅ Submit Complete Quiz",
                use_container_width=True,
                type="primary",
            )

        if submit_quiz:

            results = []

            for idx, item in enumerate(
                st.session_state.quiz_data
            ):

                user_answer = quiz_answers[idx]
                correct_answer = item.get("answer", "")
                topic = item.get("topic", "general")

                if user_answer is None:
                    user_answer = ""

                try:
                    is_correct, message = check_quiz_answer(
                        item.get("question", ""),
                        user_answer,
                        correct_answer,
                        topic=topic,
                    )
                except Exception:
                    # Safe fallback.
                    normalize = lambda x: re.sub(
                        r"\s+",
                        " ",
                        str(x).strip().lower(),
                    )

                    is_correct = (
                        normalize(user_answer)
                        == normalize(correct_answer)
                    )

                    message = (
                        "✅ Sahi Jawaab!"
                        if is_correct
                        else f"❌ Galat. Sahi: {correct_answer}"
                    )

                results.append(
                    {
                        "question_no": idx + 1,
                        "question": item.get("question", ""),
                        "user_answer": user_answer,
                        "correct_answer": correct_answer,
                        "is_correct": bool(is_correct),
                        "message": message,
                        "explanation": item.get(
                            "explanation",
                            "",
                        ),
                        "topic": topic,
                    }
                )

            st.session_state.quiz_results = results
            st.session_state.quiz_finished = True

            st.rerun()

    # --------------------------------------------------------
    # QUIZ FINAL REPORT
    # --------------------------------------------------------

    if (
        st.session_state.quiz_finished
        and st.session_state.quiz_results
    ):

        st.markdown("## 📊 Complete Quiz Report")

        results = st.session_state.quiz_results

        total = len(results)
        correct = sum(
            1
            for r in results
            if r.get("is_correct")
        )
        wrong = total - correct

        percentage = (
            (correct / total) * 100
            if total
            else 0
        )

        a, b, c, d = st.columns(4)

        with a:
            st.metric(
                "Total Questions",
                total,
            )

        with b:
            st.metric(
                "Correct",
                correct,
            )

        with c:
            st.metric(
                "Wrong",
                wrong,
            )

        with d:
            st.metric(
                "Score",
                f"{percentage:.1f}%",
            )

        # ----------------------------------------------------
        # Question-by-question analysis
        # ----------------------------------------------------

        st.markdown(
            "### 🔎 Question-by-Question Analysis"
        )

        for result in results:

            if result.get("is_correct"):
                css_class = "result-correct"
                icon = "✅"
                label = "CORRECT"
            else:
                css_class = "result-wrong"
                icon = "❌"
                label = "WRONG"

            st.markdown(
                f"""
                <div class="{css_class}">
                    <b>{icon} Q{result.get('question_no')} — {label}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"**Question:** {result.get('question')}"
            )

            user_answer = result.get("user_answer")
            if user_answer:
                st.markdown(
                    f"**Your Answer:** {user_answer}"
                )
            else:
                st.markdown(
                    "**Your Answer:** Not Answered"
                )

            st.markdown(
                f"**Correct Answer:** "
                f"{result.get('correct_answer')}"
            )

            explanation = result.get("explanation")
            if explanation:
                st.markdown(
                    f"**Explanation:** {explanation}"
                )

            st.caption(
                f"Topic: {result.get('topic', 'general')}"
            )

            st.divider()

        # ----------------------------------------------------
        # Weak topics
        # ----------------------------------------------------

        weak = get_weak_topics()

        if weak:

            st.markdown("### ⚠️ Weak Topics")

            sorted_weak = sorted(
                weak.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            for topic, count in sorted_weak:
                st.write(
                    f"• **{topic}** — {count} wrong answer(s)"
                )

            st.markdown(
                "### 📚 Preparation Suggestion"
            )

            weak_names = ", ".join(
                topic
                for topic, _ in sorted_weak[:8]
            )

            prep_prompt = f"""
Create a practical preparation plan for a student.

Language: {st.session_state.language}

Weak topics:
{weak_names}

The student has just completed a quiz.

Include:
1. What to revise first
2. Why these topics need revision
3. What type of questions to practice
4. A short revision schedule
5. Mistakes to avoid
6. How to improve the next quiz score

Do not claim guaranteed exam questions.
"""

            try:
                preparation = _invoke(
                    prep_prompt,
                    temperature=0.3,
                )
            except Exception:
                preparation = (
                    "Revise the weak topics and attempt another "
                    "adaptive quiz."
                )

            st.markdown(preparation)

        # ----------------------------------------------------
        # Full Quiz Report
        # ----------------------------------------------------

        report_lines = [
            "# Complete Quiz Performance Report",
            "",
            f"Total Questions: {total}",
            f"Correct Answers: {correct}",
            f"Wrong Answers: {wrong}",
            f"Score: {percentage:.1f}%",
            "",
            "## Question Analysis",
            "",
        ]

        for r in results:
            report_lines.extend(
                [
                    f"### Q{r.get('question_no')}. {r.get('question')}",
                    f"- Your Answer: {r.get('user_answer') or 'Not Answered'}",
                    f"- Correct Answer: {r.get('correct_answer')}",
                    f"- Result: {'Correct' if r.get('is_correct') else 'Wrong'}",
                    f"- Topic: {r.get('topic', 'general')}",
                    f"- Explanation: {r.get('explanation', '')}",
                    "",
                ]
            )

        if weak:
            report_lines.extend(
                [
                    "## Weak Topics",
                    "",
                ]
            )

            for topic, count in sorted(
                weak.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                report_lines.append(
                    f"- {topic}: {count} wrong answer(s)"
                )

        quiz_report = "\n".join(report_lines)

        save_feature_report(
            "Complete Quiz Report",
            quiz_report,
        )

        export_buttons(
            "Complete Quiz Report",
            quiz_report,
            "complete_quiz_report",
        )

        if st.button(
            "🔄 Start New Quiz",
            use_container_width=True,
        ):
            st.session_state.quiz_data = []
            st.session_state.quiz_results = []
            st.session_state.quiz_started = False
            st.session_state.quiz_finished = False
            st.rerun()


# ============================================================
# TAB 5 - VIVA LAB
# ============================================================

with tabs[4]:

    st.markdown("## 🎤 Viva Lab")

    st.markdown(
        """
        <div class="card">
        <b>Viva Evaluation System</b><br>
        Har answer ko individually evaluate kiya jayega.
        System Correct / Partial / Incorrect classification,
        score, feedback, missing points aur ideal answer provide karega.
        </div>
        """,
        unsafe_allow_html=True,
    )

    viva_topic = st.text_input(
        "Viva Topic / Project",
        placeholder=(
            "Example: IoT Based Smart Car using ESP32"
        ),
        key="viva_topic",
    )

    vc1, vc2 = st.columns(2)

    with vc1:
        viva_count = st.number_input(
            "Number of Viva Questions",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
        )

    with vc2:
        st.info(
            "Tip: Viva answer apne words me do. "
            "System technical correctness aur coverage dono dekhega."
        )

    if st.button(
        "🎤 Generate Viva Questions",
        type="primary",
        use_container_width=True,
    ):

        if not viva_topic.strip():
            st.warning(
                "Viva topic/project enter karo."
            )
        else:

            with st.spinner(
                "Generating viva questions..."
            ):

                questions = generate_viva_questions(
                    viva_topic,
                    num_q=int(viva_count),
                    language=st.session_state.language,
                )

            st.session_state.viva_data = questions
            st.session_state.viva_results = []
            st.session_state.viva_started = True
            st.session_state.viva_finished = False

            st.rerun()

    # --------------------------------------------------------
    # ACTIVE VIVA
    # --------------------------------------------------------

    if (
        st.session_state.viva_started
        and st.session_state.viva_data
        and not st.session_state.viva_finished
    ):

        st.markdown("### 🎙️ Viva Session")

        with st.form("viva_answer_form"):

            viva_answers = []

            for idx, item in enumerate(
                st.session_state.viva_data
            ):

                question_text = item.get(
                    "q",
                    item.get("question", ""),
                )

                st.markdown(
                    f"### Q{idx + 1}. {question_text}"
                )

                answer = st.text_area(
                    "Your Answer",
                    height=150,
                    key=f"viva_answer_{idx}",
                    placeholder=(
                        "Yaha apna viva answer likho..."
                    ),
                )

                viva_answers.append(answer)

                st.divider()

            submit_viva = st.form_submit_button(
                "🎯 Submit Complete Viva",
                use_container_width=True,
                type="primary",
            )

        if submit_viva:

            results = []

            progress = st.progress(0)

            total_questions = len(
                st.session_state.viva_data
            )

            for idx, item in enumerate(
                st.session_state.viva_data
            ):

                question_text = item.get(
                    "q",
                    item.get("question", ""),
                )

                reference_answer = item.get(
                    "a",
                    item.get("answer", ""),
                )

                student_answer = (
                    viva_answers[idx]
                    if idx < len(viva_answers)
                    else ""
                )

                with st.spinner(
                    f"Evaluating viva answer {idx + 1}/{total_questions}..."
                ):

                    try:
                        evaluation = verify_viva_answer(
                            question_text,
                            reference_answer,
                            student_answer,
                            language=st.session_state.language,
                        )
                    except Exception as e:
                        evaluation = {
                            "verdict": "Incorrect",
                            "score": 0,
                            "feedback": (
                                f"Evaluation error: {e}"
                            ),
                            "missing_points": [],
                            "correct_points": [],
                            "ideal_answer": reference_answer,
                        }

                if not isinstance(evaluation, dict):
                    evaluation = {
                        "verdict": "Incorrect",
                        "score": 0,
                        "feedback": "Invalid evaluation response.",
                        "missing_points": [],
                        "correct_points": [],
                        "ideal_answer": reference_answer,
                    }

                classification = classify_viva_result(
                    evaluation
                )

                score = normalize_result_score(
                    evaluation
                )

                # ------------------------------------------------
                # IMPORTANT:
                # Always retain reference answer.
                # Even if backend does not return ideal_answer.
                # ------------------------------------------------

                ideal_answer = clean_text(
                    evaluation.get("ideal_answer")
                )

                if not ideal_answer:
                    ideal_answer = reference_answer

                correct_points = evaluation.get(
                    "correct_points",
                    [],
                )

                if not isinstance(
                    correct_points,
                    list,
                ):
                    correct_points = [
                        str(correct_points)
                    ]

                missing_points = evaluation.get(
                    "missing_points",
                    [],
                )

                if not isinstance(
                    missing_points,
                    list,
                ):
                    missing_points = [
                        str(missing_points)
                    ]

                feedback = clean_text(
                    evaluation.get(
                        "feedback",
                        "",
                    )
                )

                results.append(
                    {
                        "question_no": idx + 1,
                        "question": question_text,
                        "user_answer": student_answer,
                        "reference_answer": reference_answer,
                        "ideal_answer": ideal_answer,
                        "classification": classification,
                        "verdict": evaluation.get(
                            "verdict",
                            classification,
                        ),
                        "score": score,
                        "feedback": feedback,
                        "correct_points": correct_points,
                        "missing_points": missing_points,
                    }
                )

                progress.progress(
                    int(
                        ((idx + 1) / total_questions)
                        * 100
                    )
                )

            st.session_state.viva_results = results
            st.session_state.viva_finished = True

            st.rerun()

    # --------------------------------------------------------
    # VIVA FINAL REPORT
    # --------------------------------------------------------

    if (
        st.session_state.viva_finished
        and st.session_state.viva_results
    ):

        results = st.session_state.viva_results

        st.markdown("## 📊 Complete Viva Report")

        total = len(results)

        correct_count = sum(
            1
            for r in results
            if r.get("classification") == "Correct"
        )

        partial_count = sum(
            1
            for r in results
            if r.get("classification") == "Partial"
        )

        incorrect_count = sum(
            1
            for r in results
            if r.get("classification") == "Incorrect"
        )

        total_score = sum(
            normalize_result_score(r)
            for r in results
        )

        max_score = total * 10

        percentage = (
            (total_score / max_score) * 100
            if max_score
            else 0
        )

        # ----------------------------------------------------
        # SUMMARY METRICS
        # ----------------------------------------------------

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric(
                "Questions",
                total,
            )

        with c2:
            st.metric(
                "Correct",
                correct_count,
            )

        with c3:
            st.metric(
                "Partial",
                partial_count,
            )

        with c4:
            st.metric(
                "Incorrect",
                incorrect_count,
            )

        with c5:
            st.metric(
                "Overall Score",
                f"{percentage:.1f}%",
            )

        st.progress(
            int(max(0, min(100, percentage)))
        )

        # ----------------------------------------------------
        # PERFORMANCE SUMMARY
        # ----------------------------------------------------

        if percentage >= 80:
            summary_label = "Strong performance"
        elif percentage >= 60:
            summary_label = "Good foundation, but revision is needed"
        elif percentage >= 40:
            summary_label = "Several concepts need revision"
        else:
            summary_label = "Major revision recommended"

        st.markdown(
            f"""
            <div class="card">
                <h3>📌 Performance Summary</h3>
                <p><b>{summary_label}</b></p>
                <p>
                Score: <b>{total_score:.1f}/{max_score:.1f}</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # EVERY ANSWER ANALYSIS
        # ----------------------------------------------------

        st.markdown(
            "### 🔎 Answer-by-Answer Evaluation"
        )

        for result in results:

            classification = result.get(
                "classification",
                "Incorrect",
            )

            if classification == "Correct":
                css_class = "result-correct"
                icon = "✅"
                label = "CORRECT"
            elif classification == "Partial":
                css_class = "result-partial"
                icon = "🟡"
                label = "PARTIAL"
            else:
                css_class = "result-wrong"
                icon = "❌"
                label = "INCORRECT"

            st.markdown(
                f"""
                <div class="{css_class}">
                    <b>
                    {icon} Q{result.get('question_no')}
                    — {label}
                    </b>
                    &nbsp;&nbsp;
                    <b>
                    Score: {normalize_result_score(result):.1f}/10
                    </b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"### Q{result.get('question_no')}. "
                f"{result.get('question')}"
            )

            # ------------------------------------------------
            # User answer
            # ------------------------------------------------

            st.markdown("#### 👤 Your Answer")

            user_answer = clean_text(
                result.get("user_answer")
            )

            if user_answer:
                st.info(user_answer)
            else:
                st.warning(
                    "You did not provide an answer."
                )

            # ------------------------------------------------
            # Correct points
            # ------------------------------------------------

            correct_points = result.get(
                "correct_points",
                [],
            )

            if correct_points:
                st.markdown(
                    "#### ✅ What You Got Right"
                )

                for point in correct_points:
                    st.write(f"• {point}")

            # ------------------------------------------------
            # Missing points
            # ------------------------------------------------

            missing_points = result.get(
                "missing_points",
                [],
            )

            if missing_points:
                st.markdown(
                    "#### ⚠️ Missing / Incorrect Points"
                )

                for point in missing_points:
                    st.write(f"• {point}")

            # ------------------------------------------------
            # Feedback
            # ------------------------------------------------

            if result.get("feedback"):
                st.markdown("#### 💬 Feedback")
                st.markdown(
                    result.get("feedback")
                )

            # ------------------------------------------------
            # Correct / Ideal answer
            # ------------------------------------------------

            st.markdown(
                "#### 📖 Correct / Ideal Answer"
            )

            st.success(
                result.get(
                    "ideal_answer",
                    result.get(
                        "reference_answer",
                        "Not available",
                    ),
                )
            )

            st.divider()

        # ----------------------------------------------------
        # PREPARATION ANALYSIS
        # ----------------------------------------------------

        st.markdown(
            "## 📚 What Should You Prepare Now?"
        )

        weak_items = []

        for result in results:

            classification = result.get(
                "classification"
            )

            if classification != "Correct":

                missing = result.get(
                    "missing_points",
                    [],
                )

                if missing:
                    weak_items.extend(
                        [
                            str(x)
                            for x in missing
                        ]
                    )
                else:
                    weak_items.append(
                        result.get(
                            "question",
                            "",
                        )
                    )

        if weak_items:

            preparation_prompt = f"""
You are an expert viva preparation mentor.

Language: {st.session_state.language}

The student has just completed a viva.

Topics/questions requiring improvement:
{json.dumps(weak_items, ensure_ascii=False, indent=2)}

Create a complete preparation plan.

Include:
1. Concepts to revise first
2. Missing concepts
3. Questions the student should practice
4. How to answer viva questions better
5. Common mistakes to avoid
6. A short revision plan
7. A final self-test strategy

Do not invent facts that are not supported by the supplied information.
"""

            try:
                preparation = _invoke(
                    preparation_prompt,
                    temperature=0.3,
                )
            except Exception:
                preparation = (
                    "Revise every Partial/Incorrect question "
                    "and practice answering it again."
                )

            st.markdown(preparation)

        else:
            st.success(
                "All evaluated answers were classified as Correct. "
                "Regular revision is still recommended."
            )

        # ----------------------------------------------------
        # VIVA REPORT TEXT
        # ----------------------------------------------------

        report_lines = [
            "# Complete Viva Performance Report",
            "",
            f"Viva Topic: {viva_topic}",
            f"Total Questions: {total}",
            f"Correct: {correct_count}",
            f"Partial: {partial_count}",
            f"Incorrect: {incorrect_count}",
            f"Score: {total_score:.1f}/{max_score:.1f}",
            f"Percentage: {percentage:.1f}%",
            "",
            "## Answer-by-Answer Analysis",
            "",
        ]

        for result in results:

            report_lines.extend(
                [
                    f"### Q{result.get('question_no')}. "
                    f"{result.get('question')}",
                    "",
                    f"**Your Answer:** "
                    f"{result.get('user_answer') or 'Not Answered'}",
                    "",
                    f"**Result:** "
                    f"{result.get('classification')}",
                    "",
                    f"**Score:** "
                    f"{normalize_result_score(result):.1f}/10",
                    "",
                    "**Correct / Ideal Answer:**",
                    result.get(
                        "ideal_answer",
                        result.get(
                            "reference_answer",
                            "",
                        ),
                    ),
                    "",
                ]
            )

            correct_points = result.get(
                "correct_points",
                [],
            )

            if correct_points:

                report_lines.append(
                    "**Correct Points:**"
                )

                for point in correct_points:
                    report_lines.append(
                        f"- {point}"
                    )

                report_lines.append("")

            missing_points = result.get(
                "missing_points",
                [],
            )

            if missing_points:

                report_lines.append(
                    "**Missing / Incorrect Points:**"
                )

                for point in missing_points:
                    report_lines.append(
                        f"- {point}"
                    )

                report_lines.append("")

            report_lines.extend(
                [
                    "**Feedback:**",
                    result.get("feedback", ""),
                    "",
                    "---",
                    "",
                ]
            )

        viva_report = "\n".join(report_lines)

        save_feature_report(
            "Complete Viva Report",
            viva_report,
        )

        st.markdown("## 📥 Export Viva Report")

        export_buttons(
            "Complete Viva Performance Report",
            viva_report,
            "complete_viva_report",
        )

        if st.button(
            "🔄 Start New Viva",
            use_container_width=True,
        ):

            st.session_state.viva_data = []
            st.session_state.viva_results = []
            st.session_state.viva_started = False
            st.session_state.viva_finished = False

            st.rerun()


# ============================================================
# TAB 6 - PROJECT LAB
# ============================================================

with tabs[5]:

    st.markdown("## 🚀 Project Lab")

    project_idea = st.text_area(
        "Project / Software / Application Description",
        height=130,
        placeholder=(
            "Example:\n"
            "RAG Based AI Teaching Assistant using Streamlit, "
            "Groq, LangChain and FAISS."
        ),
        key="project_idea",
    )

    budget = st.selectbox(
        "Budget",
        [
            "low",
            "medium",
            "high",
        ],
    )

    project_actions = [
        "Complete Project Guide",
        "Architecture & Modules",
        "Code Explanation",
        "Debugging Strategy",
        "Feature Roadmap",
        "Testing Strategy",
        "Documentation",
        "Viva Preparation",
    ]

    selected_action = st.selectbox(
        "Project Action",
        project_actions,
    )

    if st.button(
        "🚀 Generate Project Output",
        type="primary",
        use_container_width=True,
    ):

        if not project_idea.strip():
            st.warning(
                "Project description enter karo."
            )
        else:

            with st.spinner(
                "Generating project support..."
            ):

                if selected_action == "Complete Project Guide":

                    result = build_project_guide(
                        project_idea,
                        budget=budget,
                        language=st.session_state.language,
                    )

                else:

                    project_prompt = f"""
You are an expert project mentor.

Language: {st.session_state.language}

Project:
{project_idea}

Requested Feature:
{selected_action}

{answer_length_instruction(st.session_state.answer_length)}

Provide a complete practical response.

If it is software:
- architecture
- modules
- technologies
- data flow
- implementation
- testing
- deployment
- security
- future enhancements

If it is hardware/IoT:
- components
- wiring
- working
- code structure
- testing
- troubleshooting
- safety
- future enhancements

If it is an academic project:
- objective
- methodology
- modules
- implementation
- results
- limitations
- future scope
- viva questions

Do not assume unsupported hardware details.
Clearly mark examples as examples.
"""

                    result = _invoke(
                        project_prompt,
                        temperature=0.4,
                    )

            st.session_state.project_outputs[
                selected_action
            ] = result

            save_feature_report(
                f"Project - {selected_action}",
                result,
            )

            st.markdown(result)

            export_buttons(
                f"Project {selected_action}",
                result,
                "project_output",
            )


# ============================================================
# TAB 7 - MEDIA LAB
# ============================================================

with tabs[6]:

    st.markdown("## 🎧 Media Lab")

    media_topic = st.text_input(
        "Topic for Media",
        placeholder="Example: DBMS Transaction Management",
        key="media_topic",
    )

    # --------------------------------------------------------
    # PODCAST
    # --------------------------------------------------------

    st.markdown("### 🎙️ Educational Podcast")

    if st.button(
        "Generate Podcast Script",
        use_container_width=True,
    ):

        if not media_topic.strip():
            st.warning("Topic enter karo.")
        else:

            with st.spinner(
                "Creating podcast script..."
            ):

                podcast = generate_podcast_script(
                    media_topic,
                    language=st.session_state.language,
                )

            save_feature_report(
                "Podcast Script",
                podcast,
            )

            st.markdown(podcast)

            audio_path = text_to_audio_file(
                podcast,
                language_name=st.session_state.language,
            )

            if audio_path and os.path.exists(audio_path):
                st.audio(
                    audio_path,
                    format="audio/mp3",
                )

    st.divider()

    # --------------------------------------------------------
    # VOICE INPUT
    # --------------------------------------------------------

    st.markdown("### 🎤 Voice Question")

    st.caption(
        "Voice input ke liye Streamlit ka audio recorder use karo."
    )

    try:
        audio_value = st.audio_input(
            "Record your question",
            key="voice_question",
        )
    except Exception:
        audio_value = None
        st.warning(
            "Your Streamlit version may not support audio_input."
        )

    if audio_value is not None:

        temp_audio = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        )

        temp_audio.write(
            audio_value.getvalue()
        )

        temp_audio.close()

        if st.button(
            "🧠 Transcribe & Ask",
            use_container_width=True,
        ):

            with st.spinner(
                "Transcribing voice..."
            ):

                transcription = transcribe_audio(
                    get_api_key(),
                    temp_audio.name,
                )

            if transcription:

                st.markdown(
                    f"**Transcription:** {transcription}"
                )

                with st.spinner(
                    "Generating answer..."
                ):

                    answer, sources = ask_question(
                        transcription,
                        k=st.session_state.retrieval_k,
                        mode="normal",
                        language=st.session_state.language,
                    )

                st.markdown("### 🤖 AI Answer")
                st.markdown(answer)

                if sources:

                    with st.expander(
                        "📚 Sources"
                    ):

                        for source in sources:
                            st.write(source)

            else:
                st.error(
                    "Voice transcription failed."
                )

    st.divider()

    # --------------------------------------------------------
    # PPT
    # --------------------------------------------------------

    st.markdown("### 📊 PPT Generator")

    ppt_topic = st.text_input(
        "PPT Topic",
        key="ppt_topic",
        placeholder="Example: Computer Networks",
    )

    ppt_count = st.slider(
        "Slides",
        5,
        20,
        10,
    )

    if st.button(
        "📊 Generate PPT",
        use_container_width=True,
    ):

        if not ppt_topic.strip():
            st.warning("PPT topic enter karo.")
        else:

            with st.spinner(
                "Creating presentation..."
            ):

                try:
                    ppt_path = create_ppt_file(
                        ppt_topic,
                        num_slides=ppt_count,
                        language=st.session_state.language,
                    )

                    if ppt_path and os.path.exists(
                        ppt_path
                    ):

                        with open(
                            ppt_path,
                            "rb",
                        ) as f:
                            ppt_data = f.read()

                        st.download_button(
                            "⬇️ Download PPTX",
                            data=ppt_data,
                            file_name=(
                                f"{re.sub(r'[^a-zA-Z0-9]+', '_', ppt_topic)}"
                                f".pptx"
                            ),
                            mime=(
                                "application/vnd.openxmlformats-officedocument."
                                "presentationml.presentation"
                            ),
                            use_container_width=True,
                        )

                except Exception as e:
                    st.error(
                        f"PPT generation error: {e}"
                    )

    st.divider()

    # --------------------------------------------------------
    # IMAGE EXPORT
    # --------------------------------------------------------

    st.markdown(
        "### 🖼️ Images → PDF / DOCX"
    )

    image_files = st.file_uploader(
        "Upload Images",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
        accept_multiple_files=True,
        key="media_images",
    )

    if image_files:

        ic1, ic2 = st.columns(2)

        with ic1:

            if st.button(
                "📕 Images → PDF",
                use_container_width=True,
            ):

                try:

                    pdf_buffer = images_to_pdf(
                        image_files
                    )

                    st.download_button(
                        "⬇️ Download PDF",
                        data=pdf_buffer.getvalue(),
                        file_name="images.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

                except Exception as e:
                    st.error(
                        f"Image PDF error: {e}"
                    )

        with ic2:

            if st.button(
                "📝 Images → DOCX",
                use_container_width=True,
            ):

                try:

                    docx_buffer = images_to_docx(
                        image_files
                    )

                    st.download_button(
                        "⬇️ Download DOCX",
                        data=docx_buffer.getvalue(),
                        file_name="images.docx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document"
                        ),
                        use_container_width=True,
                    )

                except Exception as e:
                    st.error(
                        f"Image DOCX error: {e}"
                    )


# ============================================================
# TAB 8 - REPORTS
# ============================================================

with tabs[7]:

    st.markdown("## 📊 Reports Center")

    st.markdown(
        """
        <div class="card">
        Yaha generated features ke reports ek jagah milenge.
        Viva aur Quiz ke complete answer-by-answer reports bhi yaha
        export kiye ja sakte hain.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # VIVA QUICK SUMMARY
    # --------------------------------------------------------

    if st.session_state.viva_results:

        results = st.session_state.viva_results

        total = len(results)

        correct = sum(
            1
            for r in results
            if r.get("classification") == "Correct"
        )

        partial = sum(
            1
            for r in results
            if r.get("classification") == "Partial"
        )

        incorrect = sum(
            1
            for r in results
            if r.get("classification") == "Incorrect"
        )

        total_score = sum(
            normalize_result_score(r)
            for r in results
        )

        percentage = (
            total_score / (total * 10) * 100
            if total
            else 0
        )

        st.markdown("### 🎤 Latest Viva")

        a, b, c, d = st.columns(4)

        with a:
            st.metric("Correct", correct)

        with b:
            st.metric("Partial", partial)

        with c:
            st.metric("Incorrect", incorrect)

        with d:
            st.metric(
                "Score",
                f"{percentage:.1f}%",
            )

    # --------------------------------------------------------
    # QUIZ QUICK SUMMARY
    # --------------------------------------------------------

    if st.session_state.quiz_results:

        results = st.session_state.quiz_results

        total = len(results)

        correct = sum(
            1
            for r in results
            if r.get("is_correct")
        )

        percentage = (
            correct / total * 100
            if total
            else 0
        )

        st.markdown("### 📝 Latest Quiz")

        a, b, c = st.columns(3)

        with a:
            st.metric(
                "Total",
                total,
            )

        with b:
            st.metric(
                "Correct",
                correct,
            )

        with c:
            st.metric(
                "Score",
                f"{percentage:.1f}%",
            )

    st.divider()

    # --------------------------------------------------------
    # COMPLETE REPORT
    # --------------------------------------------------------

    st.markdown(
        "### 📘 Complete Combined Report"
    )

    if st.button(
        "🧠 Generate Complete Report",
        type="primary",
        use_container_width=True,
    ):

        quiz_data_for_report = (
            st.session_state.quiz_results
        )

        viva_data_for_report = (
            st.session_state.viva_results
        )

        weak_topics = get_weak_topics()

        report_prompt = f"""
You are an academic performance analyst.

Language:
{st.session_state.language}

Generate a COMPLETE student performance report.

The report must cover all available data.

QUIZ RESULTS:
{json.dumps(quiz_data_for_report, ensure_ascii=False, indent=2)}

VIVA RESULTS:
{json.dumps(viva_data_for_report, ensure_ascii=False, indent=2)}

WEAK TOPICS:
{json.dumps(weak_topics, ensure_ascii=False, indent=2)}

FEATURE REPORTS:
{json.dumps(st.session_state.feature_reports, ensure_ascii=False, indent=2)}

Include:

1. Executive Summary
2. Quiz Performance
3. Viva Performance
4. Correct Answers / Strengths
5. Wrong Answers / Weaknesses
6. Partial Answers
7. Correct answers the student should learn
8. Missing concepts
9. Weak topics
10. Preparation recommendations
11. Revision plan
12. Practice strategy
13. Suggested next quiz/viva
14. Project/study improvement suggestions
15. Final action plan

For every wrong or partial answer, clearly explain:
- what the student answered
- what was correct
- what was wrong/missing
- what the correct answer should be
- how to prepare it

Do not hide mistakes.
Do not invent unavailable results.
If some data is unavailable, clearly say that.
"""

        with st.spinner(
            "Generating complete performance report..."
        ):

            try:
                complete_report = _invoke(
                    report_prompt,
                    temperature=0.25,
                )
            except Exception as e:
                complete_report = (
                    f"Report generation error: {e}"
                )

        save_feature_report(
            "Complete Combined Performance Report",
            complete_report,
        )

        st.markdown(complete_report)

        export_buttons(
            "Complete Student Performance Report",
            complete_report,
            "complete_student_report",
        )

    st.divider()

    # --------------------------------------------------------
    # SAVED FEATURE REPORTS
    # --------------------------------------------------------

    st.markdown(
        "### 🗂️ Generated Feature Reports"
    )

    if not st.session_state.feature_reports:

        st.info(
            "Abhi koi feature report generate nahi hui."
        )

    else:

        for name, item in reversed(
            list(
                st.session_state.feature_reports.items()
            )
        ):

            with st.expander(
                f"📄 {name} — {item.get('time', '')}"
            ):

                content = item.get(
                    "content",
                    "",
                )

                st.markdown(content)

                export_buttons(
                    name,
                    content,
                    re.sub(
                        r"[^a-zA-Z0-9]+",
                        "_",
                        name.lower(),
                    ),
                )

    # --------------------------------------------------------
    # ALL REPORTS EXPORT
    # --------------------------------------------------------

    if st.session_state.feature_reports:

        st.divider()

        st.markdown(
            "### 📦 Export All Generated Reports"
        )

        all_reports = get_all_feature_reports_text()

        export_buttons(
            "All AI Teaching Assistant Reports",
            all_reports,
            "all_teaching_assistant_reports",
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🎓 RAG Based AI Teaching Assistant • "
    "Study • Practice • Viva • Projects • Reports"
)
