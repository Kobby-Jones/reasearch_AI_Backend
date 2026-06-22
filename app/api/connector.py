from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.http import ConnectorError
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.connector import (
    GoogleFormsImportRequest,
    GoogleSheetsImportRequest,
    KoboForm,
    KoboFormsRequest,
    KoboImportRequest,
    SurveyCtoImportRequest,
)
from app.schemas.dataset import DatasetOut
from app.schemas.questionnaire import QuestionnaireOut
from app.services.connector_service import ConnectorService

router = APIRouter(prefix="/connector", tags=["connector"])


def _guard(fn):
    """Translate connector failures into a clean 400 with the user-facing message."""
    try:
        return fn()
    except ConnectorError as exc:
        raise HTTPException(400, str(exc))


@router.post("/kobo/forms", response_model=list[KoboForm])
def kobo_forms(
    payload: KoboFormsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KoboForm]:
    forms = _guard(lambda: ConnectorService(db).kobo_forms(user.id, payload.base_url, payload.token))
    return [KoboForm(**f) for f in forms]


@router.post("/kobo/import", response_model=DatasetOut, status_code=201)
def kobo_import(
    payload: KoboImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    ds = _guard(lambda: ConnectorService(db).kobo_import(
        user.id, payload.project_id, payload.base_url, payload.token, payload.form_uid, payload.form_name))
    return DatasetOut.model_validate(ds)


@router.post("/google-sheets/import", response_model=DatasetOut, status_code=201)
def google_sheets_import(
    payload: GoogleSheetsImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    ds = _guard(lambda: ConnectorService(db).google_import(user.id, payload.project_id, payload.url))
    return DatasetOut.model_validate(ds)


@router.post("/surveycto/import", response_model=DatasetOut, status_code=201)
def surveycto_import(
    payload: SurveyCtoImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    ds = _guard(lambda: ConnectorService(db).surveycto_import(
        user.id, payload.project_id, payload.server, payload.username, payload.password, payload.form_id))
    return DatasetOut.model_validate(ds)


@router.post("/google-forms/import", response_model=QuestionnaireOut, status_code=201)
def google_forms_import(
    payload: GoogleFormsImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuestionnaireOut:
    """Import an existing public Google Form as an editable questionnaire."""
    q = _guard(lambda: ConnectorService(db).google_forms_import(user.id, payload.project_id, payload.url))
    return QuestionnaireOut.model_validate(q)
