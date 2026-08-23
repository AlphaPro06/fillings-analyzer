from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.models import Analysis, Document, User
from app.schemas.schemas import AnalysisCreate, AnalysisOut
from app.services.llm_service import LLMError, analyze

router = APIRouter(prefix="/documents", tags=["analyses"])


@router.post(
    "/{document_id}/analyses",
    response_model=AnalysisOut,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis(
    document_id: int,
    payload: AnalysisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_owned_document(document_id, current_user, db)
    question = payload.question.strip()

    # Cache: if this exact question was already answered for this document,
    # return the stored answer instead of paying for another LLM call.
    cached = (
        db.query(Analysis)
        .filter(Analysis.document_id == document.id, Analysis.question == question)
        .order_by(Analysis.created_at.desc())
        .first()
    )
    if cached:
        return cached

    try:
        answer = analyze(question=question, document_text=document.extracted_text)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Analysis failed: {exc}",
        )

    analysis = Analysis(document_id=document.id, question=question, answer=answer)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{document_id}/analyses", response_model=list[AnalysisOut])
def list_analyses(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = _get_owned_document(document_id, current_user, db)
    return (
        db.query(Analysis)
        .filter(Analysis.document_id == document.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )


def _get_owned_document(document_id: int, user: User, db: Session) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == user.id)
        .first()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document
