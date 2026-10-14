"""Versioned public resume schema. Every professional claim carries evidence."""

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(StrictModel):
    text: str = Field(max_length=4000)
    fact_ids: list[str] = Field(max_length=30)


class Basics(StrictModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""


class ResumeSection(StrictModel):
    heading: str = Field(max_length=600)
    fact_ids: list[str] = Field(max_length=30)
    bullets: list[Claim] = Field(max_length=30)


class ResumeContent(StrictModel):
    basics: Basics
    summary: Claim
    education: list[ResumeSection] = Field(max_length=20)
    experience: list[ResumeSection] = Field(max_length=30)
    skills: list[Claim] = Field(max_length=50)
    interests: list[Claim] = Field(max_length=30)
