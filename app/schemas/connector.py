from __future__ import annotations

from pydantic import BaseModel, Field


class KoboFormsRequest(BaseModel):
    base_url: str = Field(min_length=3)
    token: str = Field(min_length=3)


class KoboForm(BaseModel):
    uid: str
    name: str
    submission_count: int = 0


class KoboImportRequest(BaseModel):
    project_id: int
    base_url: str
    token: str
    form_uid: str
    form_name: str | None = None


class GoogleSheetsImportRequest(BaseModel):
    project_id: int
    url: str = Field(min_length=5)


class SurveyCtoImportRequest(BaseModel):
    project_id: int
    server: str
    username: str
    password: str
    form_id: str


class GoogleFormsImportRequest(BaseModel):
    project_id: int
    url: str
