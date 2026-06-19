"""Streamlit UI for the AI Data Copilot.   streamlit run ui.py"""
from __future__ import annotations

import os

import streamlit as st

from app.config import settings
from app.copilot import Copilot
from app.seed import create

st.set_page_config(page_title="AI Data Copilot", layout="centered")


@st.cache_resource
def get_copilot() -> Copilot:
    if not os.path.exists(settings.db_path):
        create(settings.db_path)
    return Copilot()


copilot = get_copilot()

st.title("AI Data Copilot")
st.caption("Ask questions about the student database in plain English. "
           "Every query is validated; unsafe or unanswerable ones are refused, not run.")

with st.sidebar:
    st.subheader("Schema")
    st.code(copilot.schema, language="sql")
    st.subheader("Try")
    st.write("- How many students are there?\n- What is the average score per city?\n"
             "- Top student in each subject?\n- Average score by hometown? *(self-corrects)*\n"
             "- Delete all grades *(blocked)*")

question = st.text_input("Your question", placeholder="e.g., What is the average score per city?")

if question:
    res = copilot.ask(question)
    st.subheader("Generated SQL")
    st.code(res.sql or "(none)", language="sql")
    if res.attempts > 1:
        st.info(f"Self-corrected after {res.attempts} attempts.")

    if res.status == "success":
        st.subheader("Result")
        st.dataframe(res.rows, use_container_width=True)
        st.caption(f"{res.to_dict()['row_count']} row(s)")
    elif res.status == "refused":
        st.warning(res.error)
    elif res.status == "blocked":
        st.error(f"Blocked: {res.error}")
    else:
        st.error(f"Could not run after retries: {res.error}")
