import os
import asyncio
import logging
import re
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf
from pymupdf import Rect

from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    HTTPException,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from dotenv import load_dotenv

import openai
from openai import OpenAI

from python_backend.prompts import get_prompt

load_dotenv()

# ---------------------------------------------------------------------------
# Environment handling
# ---------------------------------------------------------------------------


def get_env_or_raise(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required but not set.")
    return value


SRC_PATH = Path(get_env_or_raise("SRC_PATH"))
DEST_PATH = Path(get_env_or_raise("DEST_PATH"))

MODEL_ID = os.getenv("MODEL_ID", "")

SRC_PATH.mkdir(parents=True, exist_ok=True)
DEST_PATH.mkdir(parents=True, exist_ok=True)

# FIXME: 
# LLM_SERVER_URL = get_env_or_raise("LLM_SERVER_URL")
# llm_client = openai.OpenAI(base_url=LLM_SERVER_URL, api_key="dummy")


# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------

app = FastAPI()
logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# {job_id: {"status": ..., "result": ..., "error": ...}}
JOBS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def ensure_pdf(up: UploadFile) -> None:
    """
    Ensure the uploaded file is a PDF, otherwise raise HTTPException.
    """
    content_type = (up.content_type or "").lower()
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail=f"{up.filename} is not a PDF")


def sanitize_filename(name: str) -> str:
    """
    Sanitize filename to avoid directory traversal and weird chars.
    """
    name = name or "document.pdf"
    name = os.path.basename(name)
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def chunk_doc(document_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Use pdfminer to extract text per text box and keep an index map.
    Returns:
        - text_chunks: list of {content, start, end}
        - full_text: concatenated text
    """
    text_chunks: List[Dict[str, Any]] = []
    full_text = ""

    for page_layout in extract_pages(document_path):
        for text_container in page_layout:
            if isinstance(text_container, LTTextContainer):
                text_to_anonymize = text_container.get_text()
                start = 0 if len(text_chunks) == 0 else text_chunks[-1]["end"] + 1
                end = start + len(text_to_anonymize) - 1
                text_chunks.append(
                    {"content": text_to_anonymize, "start": start, "end": end}
                )
                full_text += text_to_anonymize

    return text_chunks, full_text


def query_llm(
    llm,
    model_name: str,
    system_prompt: str,
    document_text: str,
) -> str:
    """
    Generic helper to query an LLM and strip <think>...</think> blocks.
    Not used by default; get_sensitive_texts is currently stubbed.
    """
    response = llm.chat.completions.create(
        model=model_name,
        stream=False,
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": document_text},
        ],
        temperature=1,
        max_tokens=4096,
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("LLM did not generate text")

    trimmed = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return trimmed


def get_sensitive_texts(full_text: str, categories: List[str]) -> List[str]:
    """
    Build the prompt for the LLM and parse its JSON output.
    Currently stubbed with a constant response.
    """
    system_prompt, document_text = get_prompt(full_text, categories)

    # TODO: placeholder
    # res = query_llm(llm_client, MODEL_ID, system_prompt, document_text)

    res = '["Johnathan A. Reynolds"]'
    sensitive_texts = json.loads(res)

    if not isinstance(sensitive_texts, list) or not all(
        isinstance(s, str) for s in sensitive_texts
    ):
        raise ValueError("LLM output must be a JSON array of strings")

    return sensitive_texts


def redact_texts(
    document_path: str, sensitive_texts: List[str], save_path: str
) -> List[Dict[str, Any]]:
    """
    Use PyMuPDF to search for each sensitive text occurrence and redact it.
    Returns a list of rects + page indices for the redactions.
    """
    pymupdf_doc = pymupdf.open(document_path)
    inst_list: List[Dict[str, Any]] = []

    for page_index in range(len(pymupdf_doc)):
        page = pymupdf_doc.load_page(page_index)

        for s in sensitive_texts:
            instances = page.search_for(s)

            redaction_obj = {
                "text": s,
                "rects": [],
                "page": page_index,
            }

            for inst in instances:
                page.add_redact_annot(inst, fill=(0, 0, 0))
                redaction_obj["rects"].append([inst.x0, inst.y0, inst.x1, inst.y1])

            inst_list.append(redaction_obj)
        page.apply_redactions()

    pymupdf_doc.save(save_path)
    return inst_list


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------


async def redact_by_llm(
    job_id: str,
    file_paths: List[str],
    categories: List[str],
) -> None:
    try:
        if not isinstance(categories, list) or not all( isinstance(c, str) for c in categories):
            raise ValueError("categories must be a list of strings")
        if not file_paths:
            raise ValueError("No files received")

        saved_paths: List[Dict[str, Any]] = []
        for fp in file_paths:
            chunks, full_text = chunk_doc(fp)
            _ = chunks  # TODO: chunks currently unused
            await asyncio.sleep(4)
            sensitive_texts = get_sensitive_texts(full_text, categories)

            in_path = Path(fp) 
            stem = in_path.stem
            ts = int(time.time())
            out_name = f"{stem}_redacted_{ts}.pdf"
            out_path = DEST_PATH / out_name

            rects = redact_texts(str(in_path), sensitive_texts, str(out_path))

            saved_paths.append({
                "path": str(out_path.resolve()),
                "redactions": rects,
            })
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["result"] = saved_paths
        JOBS[job_id]["error"] = None

    except Exception as exc:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["result"] = None
        JOBS[job_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.post("/redact", status_code=202)
async def create_job(
    bg: BackgroundTasks,
    files: List[UploadFile] = File(..., description="PDF files"),
    categories: str = Form(
        ..., description='JSON array of categories, e.g. ["name", "address"]'
    ),
):
    try:
        cats = json.loads(categories)
        if not isinstance(cats, list) or not all(isinstance(c, str) for c in cats):
            raise ValueError
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="`categories` must be a JSON array of strings (e.g. [\"name\"]).",
        )

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "processing", "result": None, "error": None}

    file_paths = []
    for up in files: 
        ensure_pdf(up)

        sanitized_name = sanitize_filename(up.filename or "document.pdf")
        in_path = SRC_PATH / sanitized_name
        file_paths.append(in_path)
        content = await up.read()
        with open(in_path, "wb") as f:
            f.write(content)

    bg.add_task(redact_by_llm, job_id, file_paths, cats)

    return {"job_id": job_id}

# TODO: add get file, check cookie,

@app.get("/jobs/{job_id}")
async def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

