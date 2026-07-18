"""API — Single Document Review runs (Mode spec §12.2).

POST /review-runs                 upload text + assessment date -> locked run
GET  /review-runs/{id}            state + locked report
POST /review-runs/{id}/questions  explainer chat (bounded to the locked run)
POST /review-runs/{id}/export     the locked report JSON
POST /review-runs/{id}/rerun      NEW run (old result never changes)
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from api.auth import CurrentUser, require_authenticated

from backend.app.review import explainer
from backend.app.review import service

router = APIRouter(tags=["review-runs"])


@router.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...), user: CurrentUser = Depends(require_authenticated)
) -> dict:
    """Trích xuất text từ PDF/DOCX/TXT cho mode Nhận xét tài liệu (PyMuPDF cho PDF).

    File chỉ dùng để lấy text (REVIEW_TARGET) — KHÔNG lưu vào kho pháp lý, không
    index. Trả 422 rõ ràng nếu là PDF scan/ảnh (không có lớp text) cần OCR.
    """
    import os
    import tempfile

    data = await file.read()
    name = (file.filename or "").lower()
    text = ""
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        suffix, fn = ".pdf", "extract_text_blocks_from_pdf"
    elif name.endswith(".docx"):
        suffix, fn = ".docx", "extract_text_blocks_from_docx"
    else:
        suffix = None

    if suffix:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            import backend.app.ingestion.extractors.pdf as ext
            blocks = getattr(ext, fn)(path)
            text = "\n".join(b.get("text", "") for b in blocks)
        except Exception as e:  # PyMuPDF thiếu / PDF scan / file hỏng
            raise HTTPException(status_code=422, detail={"error": {
                "code": "EXTRACT_FAILED",
                "message": f"Không đọc được nội dung ({e}). Có thể là PDF scan (ảnh) cần OCR."}})
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    else:
        text = data.decode("utf-8", errors="replace")

    text = text.replace("\x00", "").strip()
    if not text:
        raise HTTPException(status_code=422, detail={"error": {
            "code": "NEEDS_TEXT_EXTRACTION",
            "message": "Không trích xuất được text (PDF scan/ảnh cần OCR)."}})
    return {"filename": file.filename, "text": text}


class CreateReviewRunRequest(BaseModel):
    filename: str
    text: str
    assessment_date: Optional[date] = None
    conversation_id: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str
    claim_id: Optional[str] = None


class RerunRequest(BaseModel):
    assessment_date: Optional[date] = None


@router.post("/review-runs")
def create_review_run(
    req: CreateReviewRunRequest, user: CurrentUser = Depends(require_authenticated)
) -> dict:
    return service.create_review_run(
        owner_id=user.username, filename=req.filename, text=req.text,
        assessment_date=req.assessment_date, conversation_id=req.conversation_id)


@router.get("/review-runs/{run_id}")
def get_review_run(run_id: str, user: CurrentUser = Depends(require_authenticated)) -> dict:
    return service.get_review_run(user.username, run_id)


@router.post("/review-runs/{run_id}/questions")
def ask_question(
    run_id: str, req: QuestionRequest,
    user: CurrentUser = Depends(require_authenticated),
) -> dict:
    return explainer.answer(user.username, run_id, req.question, req.claim_id)


@router.post("/review-runs/{run_id}/export")
def export_report(run_id: str, user: CurrentUser = Depends(require_authenticated)) -> dict:
    data = service.get_review_run(user.username, run_id)
    return data["report"] or {"review_run_id": run_id, "state": data["state"]}


@router.post("/review-runs/{run_id}/rerun")
def rerun(
    run_id: str, req: RerunRequest,
    user: CurrentUser = Depends(require_authenticated),
) -> dict:
    return service.rerun(user.username, run_id, req.assessment_date)
