from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .schemas import TicketRequest, TicketResponse
from .fallback import safe_fallback
from .safety import enforce_safety
from .matcher import find_candidates
from .llm import analyze_with_llm

app = FastAPI(title="QueueStorm Investigator")
executor = ThreadPoolExecutor(max_workers=10)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the exception internally here if needed, but do not leak it to the client.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Return 422 for semantically invalid inputs or missing required fields
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request schema"}
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze-ticket", response_model=TicketResponse)
async def analyze_ticket(payload: TicketRequest):
    ticket_id = payload.ticket_id
    try:
        # Step 1: Pre-filter candidates
        history = [txn.model_dump() for txn in payload.transaction_history] if payload.transaction_history else []
        candidates = find_candidates(payload.complaint, history)
        
        # Step 2: Call LLM with a strict 20-second timeout
        loop = asyncio.get_running_loop()
        raw = await asyncio.wait_for(
            loop.run_in_executor(executor, analyze_with_llm, payload.model_dump(), candidates),
            timeout=20.0
        )
        
        # Always echo the ticket_id exactly as given, never trust LLM here
        raw["ticket_id"] = ticket_id
        
    except Exception as e:
        raw = safe_fallback(ticket_id)

    # Step 3: Enforce safety rules
    raw, violations = enforce_safety(raw)

    # Step 4: Validate against Pydantic model
    try:
        # Returning standard Pydantic model forces schema validation
        return TicketResponse(**raw)
    except Exception:
        # If the LLM returned invalid enums/schema, fall back
        return TicketResponse(**safe_fallback(ticket_id))
