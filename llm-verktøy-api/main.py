from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
from openai import OpenAI
import os
import logging

app = FastAPI(title="LLM Verktøy API", version="1.0.0")

# Konfigurasjon
KONSULENT_API_URL = os.getenv("KONSULENT_API_URL", "http://localhost:8000")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")  # Kostnadseffektiv modell

# Sett opp OpenRouter klient
openrouter_client = None
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def generer_sammendrag_fallback(konsulenter: List[Konsulent], min_tilgjengelighet_prosent: float, påkrevd_ferdighet: str) -> str:
    """Fallback: Genererer sammendrag uten LLM hvis OpenRouter ikke er tilgjengelig"""
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


async def generer_sammendrag_med_llm(
    konsulenter: List[Konsulent], 
    min_tilgjengelighet_prosent: float, 
    påkrevd_ferdighet: str
) -> str:
    """Genererer menneskeleselig sammendrag ved hjelp av OpenRouter LLM"""
    
    # Hvis ingen konsulenter, returner umiddelbart
    if not konsulenter:
        return f"Fant ingen konsulenter med minst {min_tilgjengelighet_prosent}% tilgjengelighet og ferdigheten '{påkrevd_ferdighet}'."
    
    # Hvis OpenRouter ikke er konfigurert, bruk fallback
    if not openrouter_client:
        logger.warning("OpenRouter ikke konfigurert, bruker fallback")
        return generer_sammendrag_fallback(konsulenter, min_tilgjengelighet_prosent, påkrevd_ferdighet)
    
    # Bygg konsulent-data for prompt
    konsulent_info = []
    for konsulent in konsulenter:
        tilgjengelighet = beregn_tilgjengelighet(konsulent.belastning_prosent)
        konsulent_info.append(
            f"- {konsulent.navn}: {tilgjengelighet:.0f}% tilgjengelighet, "
            f"ferdigheter: {', '.join(konsulent.ferdigheter)}"
        )
    
    # Bygg prompt
    prompt = f"""Du er en assistent som hjelper med konsulent-staffing. 

Basert på følgende filtrerte konsulenter, generer et kort og menneskeleselig sammendrag på norsk.

Krav:
- Minimum tilgjengelighet: {min_tilgjengelighet_prosent}%
- Påkrevd ferdighet: {påkrevd_ferdighet}

Konsulenter som matcher kriteriene:
{chr(10).join(konsulent_info)}

Generer et kort sammendrag som oppsummerer antall funnet konsulenter og deres tilgjengelighet. 
Hold det profesjonelt og konsist."""
    
    try:
        # Kall OpenRouter API
        response = openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "Du er en hjelpsom assistent som genererer profesjonelle sammendrag på norsk."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lavere temperatur for mer konsistente resultater
            max_tokens=200
        )
        
        sammendrag = response.choices[0].message.content.strip()
        logger.info(f"Generert sammendrag med LLM: {OPENROUTER_MODEL}")
        return sammendrag
        
    except Exception as e:
        logger.error(f"Feil ved kall til OpenRouter: {str(e)}")
        # Fallback til enkel tekst-generering hvis LLM feiler
        return generer_sammendrag_fallback(konsulenter, min_tilgjengelighet_prosent, påkrevd_ferdighet)


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
    
    # Generer sammendrag med LLM via OpenRouter
    sammendrag = await generer_sammendrag_med_llm(
        filtrerte,
        min_tilgjengelighet_prosent,
        påkrevd_ferdighet
    )
    
    return SammendragResponse(sammendrag=sammendrag)


@app.get("/health")
async def health():
    return {"status": "healthy"}

