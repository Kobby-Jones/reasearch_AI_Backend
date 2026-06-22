from __future__ import annotations

import hashlib
import os
import re
import uuid

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset import Dataset
from app.repositories.dataset_repository import DatasetRepository
from app.utils.dataset_loader import detect_schema, load_dataframe

# Column-name signals for personally identifying information.
_NAME_HINTS = (
    "name", "surname", "firstname", "lastname", "fullname", "email", "mail",
    "phone", "tel", "mobile", "msisdn", "contact", "address", "street",
    "gps", "latitude", "longitude", "lat", "lng", "coordinates", "location",
    "dob", "birth", "ssn", "nid", "passport", "national_id", "nationalid",
    "ip", "device", "respondent", "participant_name", "household_head",
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{7,}$")


def _looks_like_pii_values(series: pd.Series) -> str | None:
    sample = series.dropna().astype(str).head(25)
    if sample.empty:
        return None
    emails = sum(bool(_EMAIL_RE.match(v.strip())) for v in sample)
    if emails >= max(2, len(sample) // 3):
        return "values look like email addresses"
    phones = sum(bool(_PHONE_RE.match(v.strip())) for v in sample)
    if phones >= max(2, len(sample) // 3):
        return "values look like phone numbers"
    return None


def scan_dataframe(df: pd.DataFrame) -> list[dict]:
    """Flag columns that likely contain PII, with a reason and a recommendation."""
    findings: list[dict] = []
    for col in df.columns:
        lower = str(col).lower()
        reason = None
        if any(h in lower for h in _NAME_HINTS):
            reason = f"column name suggests identifying data ('{col}')"
        if reason is None:
            reason = _looks_like_pii_values(df[col])
        if reason:
            # location/contact data is best dropped; identifiers can be hashed
            recommend = "drop" if any(k in lower for k in ("gps", "lat", "lng", "coordinate", "address", "location", "email", "phone", "mobile", "tel")) else "hash"
            findings.append({"column": str(col), "reason": reason, "recommend": recommend})
    return findings


def _hash_value(v) -> str:
    if pd.isna(v):
        return ""
    return hashlib.sha256(str(v).encode("utf-8")).hexdigest()[:12]


class AnonymizeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)

    def _owned(self, dataset_id: int, user_id: int) -> Dataset:
        ds = self.datasets.get(dataset_id)
        if not ds or ds.project.user_id != user_id:
            raise NotFoundError("Dataset not found.")
        return ds

    def scan(self, user_id: int, dataset_id: int) -> list[dict]:
        ds = self._owned(dataset_id, user_id)
        return scan_dataframe(load_dataframe(ds.storage_path))

    def anonymize(
        self, user_id: int, dataset_id: int, drop: list[str], hash_: list[str]
    ) -> Dataset:
        ds = self._owned(dataset_id, user_id)
        df = load_dataframe(ds.storage_path)
        drop = [c for c in (drop or []) if c in df.columns]
        hash_ = [c for c in (hash_ or []) if c in df.columns and c not in drop]
        if not drop and not hash_:
            raise ValidationError("Select at least one column to remove or hash.")

        out = df.drop(columns=drop)
        for c in hash_:
            out[c] = out[c].map(_hash_value)

        os.makedirs(settings.upload_dir, exist_ok=True)
        path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.csv")
        out.to_csv(path, index=False)

        base = os.path.splitext(ds.filename)[0]
        new = Dataset(
            project_id=ds.project_id,
            filename=f"{base} (anonymised).csv",
            storage_path=path,
            row_count=int(out.shape[0]),
            column_count=int(out.shape[1]),
            schema_info=detect_schema(out),
            cleaning_report={
                "source": "anonymisation",
                "from_dataset_id": ds.id,
                "dropped": drop,
                "hashed": hash_,
            },
        )
        self.datasets.add(new)
        self.db.commit()
        self.db.refresh(new)
        return new
