from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetOut
from app.services.research_service import ResearchService
from app.utils.dataset_loader import clean_dataframe, detect_schema, load_dataframe

router = APIRouter(prefix="/dataset", tags=["dataset"])

_ALLOWED = {".csv", ".xlsx", ".xls", ".tsv", ".txt"}


@router.post("/upload", response_model=DatasetOut, status_code=201)
def upload(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    project = ResearchService(db).get_owned(project_id, user.id)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED:
        raise HTTPException(422, f"Unsupported file type '{ext}'. Use CSV or Excel.")

    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, stored)

    # Read in bounded chunks so an oversized upload is rejected before it can
    # exhaust memory, rather than slurping the whole body first.
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

    # Persist the cleaned frame in a canonical CSV so downstream analysis can
    # reload it deterministically regardless of the original upload format.
    cleaned_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.csv")
    cleaned.to_csv(cleaned_path, index=False)

    dataset = Dataset(
        project_id=project.id,
        filename=file.filename or stored,
        storage_path=cleaned_path,
        row_count=int(cleaned.shape[0]),
        column_count=int(cleaned.shape[1]),
        schema_info=schema,
        cleaning_report=report,
    )
    DatasetRepository(db).add(dataset)
    db.commit()
    return DatasetOut.model_validate(dataset)


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
