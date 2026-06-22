from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetOut
from app.services.research_service import ResearchService
from app.utils.dataset_loader import clean_dataframe, detect_schema, load_dataframe

router = APIRouter(prefix="/dataset", tags=["dataset"])

_ALLOWED = {".csv", ".xlsx", ".xls", ".tsv", ".txt"}


def _store_upload(file: UploadFile) -> tuple[str, dict, dict, int, int]:
    """Save, load, clean and profile an uploaded tabular file.

    Returns (cleaned_csv_path, schema, cleaning_report, row_count, col_count).
    Shared by the initial upload and the revise (new-version) flow.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED:
        raise HTTPException(422, f"Unsupported file type '{ext}'. Use CSV or Excel.")

    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, stored)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with open(path, "wb") as fh:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                os.remove(path)
                raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit.")
            fh.write(chunk)
    if size == 0:
        os.remove(path)
        raise HTTPException(422, "Uploaded file is empty.")

    df = load_dataframe(path)
    schema = detect_schema(df)
    cleaned, report = clean_dataframe(df)
    cleaned_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.csv")
    cleaned.to_csv(cleaned_path, index=False)
    return cleaned_path, schema, report, int(cleaned.shape[0]), int(cleaned.shape[1])


@router.post("/upload", response_model=DatasetOut, status_code=201)
def upload(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    project = ResearchService(db).get_owned(project_id, user.id)
    cleaned_path, schema, report, rows, cols = _store_upload(file)
    dataset = Dataset(
        project_id=project.id,
        filename=file.filename or os.path.basename(cleaned_path),
        storage_path=cleaned_path,
        row_count=rows,
        column_count=cols,
        schema_info=schema,
        cleaning_report=report,
    )
    DatasetRepository(db).add(dataset)
    db.commit()
    from app.services.audit_service import audit
    audit(db, user.id, "dataset.upload", target_type="dataset", target_id=dataset.id,
          summary=f"Uploaded {dataset.filename} ({dataset.row_count} rows)")
    return DatasetOut.model_validate(dataset)


@router.post("/{dataset_id}/revise", response_model=DatasetOut, status_code=201)
def revise(
    dataset_id: int,
    file: UploadFile = File(...),
    rerun: bool = Form(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    """Upload a corrected file as a NEW version of an existing dataset.

    The new version supersedes the old one. By default, every analysis that was
    run on the previous version is re-run against the new data (using the same
    parameters), so corrections propagate without redoing the work by hand.
    """
    old = DatasetRepository(db).get(dataset_id)
    if not old or old.project.user_id != user.id:
        raise HTTPException(404, "Dataset not found.")

    cleaned_path, schema, report, rows, cols = _store_upload(file)
    new = Dataset(
        project_id=old.project_id,
        filename=file.filename or old.filename,
        storage_path=cleaned_path,
        row_count=rows,
        column_count=cols,
        schema_info=schema,
        cleaning_report=report,
        version=(old.version or 1) + 1,
        supersedes_id=old.id,
    )
    DatasetRepository(db).add(new)
    db.flush()  # assign new.id

    if rerun:
        from app.analytics.engine import AnalyticsEngine

        engine = AnalyticsEngine()
        df = load_dataframe(new.storage_path)
        prior = AnalysisRepository(db).list_for_dataset(old.id, limit=200, offset=0)
        for rec in prior:
            if rec.analysis_type not in AnalyticsEngine.SUPPORTED:
                continue
            try:
                results = engine.run(rec.analysis_type, df, **(rec.parameters or {}))
            except Exception:
                # a column may no longer exist in the revised data; skip quietly
                continue
            db.add(AnalysisResult(
                dataset_id=new.id,
                analysis_type=rec.analysis_type,
                parameters=rec.parameters,
                results=results,
                interpretation=None,
            ))

    db.commit()
    db.refresh(new)
    from app.services.audit_service import audit
    audit(db, user.id, "dataset.revise", target_type="dataset", target_id=new.id,
          summary=f"Created v{new.version} of {new.filename}")
    return DatasetOut.model_validate(new)


@router.get("/{dataset_id}/pii-scan")
def pii_scan(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Flag columns that likely contain personally identifying information."""
    from app.services.anonymize_service import AnonymizeService

    return AnonymizeService(db).scan(user.id, dataset_id)


@router.post("/{dataset_id}/anonymize", response_model=DatasetOut, status_code=201)
def anonymize(
    dataset_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    """Create an anonymised copy: drop and/or hash the selected PII columns."""
    from app.services.anonymize_service import AnonymizeService
    from app.services.audit_service import audit

    new = AnonymizeService(db).anonymize(
        user.id, dataset_id, payload.get("drop") or [], payload.get("hash") or []
    )
    audit(db, user.id, "dataset.anonymize", target_type="dataset", target_id=new.id,
          summary=f"Anonymised dataset (from #{dataset_id})")
    return DatasetOut.model_validate(new)


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    project_id: int = Query(..., description="List datasets for this project"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DatasetOut]:
    # Ownership is enforced by resolving the project for the current user first.
    ResearchService(db).get_owned(project_id, user.id)
    datasets = DatasetRepository(db).list_for_project(project_id, limit=limit, offset=offset)
    return [DatasetOut.model_validate(d) for d in datasets]
