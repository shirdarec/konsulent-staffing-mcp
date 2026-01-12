from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx

app = FastAPI(title="LLM Verktøy API", version="1.0.0")

# URL til konsulent-api (vil bli satt via miljøvariabel eller default)
# Bruker localhost for lokal kjøring, konsulent-api for Docker (satt via miljøvariabel)
import os
KONSULENT_API_URL = os.getenv("KONSULENT_API_URL", "http://localhost:8000")


class Konsulent(BaseModel):
    id: int
    navn: str
    ferdigheter: List[str]
    belastning_prosent: float


class SammendragResponse(BaseModel):
    sammendrag: str


async def hent_konsulenter() -> List[Konsulent]:
    """Henter alle konsulenter fra konsulent-api"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{KONSULENT_API_URL}/konsulenter", timeout=5.0)
            response.raise_for_status()
            return [Konsulent(**k) for k in response.json()]
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Kunne ikke koble til konsulent-api: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Konsulent-api returnerte feil: {e.response.status_code}"
            )


def beregn_tilgjengelighet(belastning_prosent: float) -> float:
    """Beregner tilgjengelighet basert på belastning"""
    return 100.0 - belastning_prosent


def filtrer_konsulenter(
    konsulenter: List[Konsulent],
    min_tilgjengelighet_prosent: float,
    påkrevd_ferdighet: str
) -> List[Konsulent]:
    """Filtrerer konsulenter basert på tilgjengelighet og ferdighet"""
    filtrerte = []
    for konsulent in konsulenter:
        tilgjengelighet = beregn_tilgjengelighet(konsulent.belastning_prosent)
        har_ferdighet = påkrevd_ferdighet.lower() in [
            f.lower() for f in konsulent.ferdigheter
        ]
        
        if tilgjengelighet >= min_tilgjengelighet_prosent and har_ferdighet:
            filtrerte.append(konsulent)
    
    return filtrerte


def generer_sammendrag(konsulenter: List[Konsulent], min_tilgjengelighet_prosent: float, påkrevd_ferdighet: str) -> str:
    """Genererer menneskeleselig sammendrag av filtrerte konsulenter"""
    if not konsulenter:
        return f"Fant ingen konsulenter med minst {min_tilgjengelighet_prosent}% tilgjengelighet og ferdigheten '{påkrevd_ferdighet}'."
    
    antall = len(konsulenter)
    sammendrag = f"Fant {antall} konsulent{'er' if antall > 1 else ''} med minst {min_tilgjengelighet_prosent}% tilgjengelighet og ferdigheten '{påkrevd_ferdighet}'."
    
    detaljer = []
    for konsulent in konsulenter:
        tilgjengelighet = beregn_tilgjengelighet(konsulent.belastning_prosent)
        detaljer.append(f"{konsulent.navn} har {tilgjengelighet:.0f}% tilgjengelighet")
    
    sammendrag += " " + ". ".join(detaljer) + "."
    
    return sammendrag


@app.get("/")
async def root():
    return {"message": "LLM Verktøy API er oppe og kjører"}


@app.get("/tilgjengelige-konsulenter/sammendrag", response_model=SammendragResponse)
async def get_tilgjengelige_konsulenter_sammendrag(
    min_tilgjengelighet_prosent: float = Query(..., description="Minimum tilgjengelighet i prosent"),
    påkrevd_ferdighet: str = Query(..., description="Påkrevd ferdighet")
):
    """
    Henter konsulenter fra konsulent-api, filtrerer basert på tilgjengelighet og ferdighet,
    og returnerer et menneskeleselig sammendrag.
    """
    # Hent alle konsulenter
    konsulenter = await hent_konsulenter()
    
    # Filtrer konsulenter
    filtrerte = filtrer_konsulenter(
        konsulenter,
        min_tilgjengelighet_prosent,
        påkrevd_ferdighet
    )
    
    # Generer sammendrag
    sammendrag = generer_sammendrag(
        filtrerte,
        min_tilgjengelighet_prosent,
        påkrevd_ferdighet
    )
    
    return SammendragResponse(sammendrag=sammendrag)


@app.get("/health")
async def health():
    return {"status": "healthy"}

