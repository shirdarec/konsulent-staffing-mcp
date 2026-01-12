from fastapi import FastAPI
from typing import List
from pydantic import BaseModel

app = FastAPI(title="Konsulent API", version="1.0.0")


class Ferdighet(BaseModel):
    navn: str
    nivå: str


class Konsulent(BaseModel):
    id: int
    navn: str
    ferdigheter: List[str]
    belastning_prosent: float


# Hardkodet liste med konsulenter
KONSULENTER = [
    Konsulent(
        id=1,
        navn="Anna K.",
        ferdigheter=["python", "fastapi", "docker"],
        belastning_prosent=40.0
    ),
    Konsulent(
        id=2,
        navn="Leo T.",
        ferdigheter=["python", "javascript", "react"],
        belastning_prosent=20.0
    ),
    Konsulent(
        id=3,
        navn="Mia S.",
        ferdigheter=["java", "spring", "kubernetes"],
        belastning_prosent=90.0
    ),
    Konsulent(
        id=4,
        navn="Erik L.",
        ferdigheter=["python", "django", "postgresql"],
        belastning_prosent=60.0
    ),
    Konsulent(
        id=5,
        navn="Sara M.",
        ferdigheter=["javascript", "node.js", "mongodb"],
        belastning_prosent=30.0
    ),
]


@app.get("/")
async def root():
    return {"message": "Konsulent API er oppe og kjører"}


@app.get("/konsulenter", response_model=List[Konsulent])
async def get_konsulenter():
    """Returnerer liste over alle konsulenter"""
    return KONSULENTER


@app.get("/health")
async def health():
    return {"status": "healthy"}

