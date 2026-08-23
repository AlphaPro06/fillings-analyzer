from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- Auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Documents ----
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    created_at: datetime


# ---- Analyses ----
class AnalysisCreate(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    question: str
    answer: str
    created_at: datetime
