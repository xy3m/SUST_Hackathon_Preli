# QueueStorm Investigator — SUST CSE Carnival 2026 (Preliminary)

An AI/API "support copilot" for a digital finance platform. It reads one
customer/merchant/agent complaint plus a short snippet of that person's recent
transactions, **investigates** what actually happened against the evidence, and
returns a single structured JSON response that classifies, routes, escalates,
and drafts a **safe** reply for a human support agent.

The service exposes two HTTP endpoints:

| Method | Path              | Purpose                                                   |
| ------ | ----------------- | --------------------------------------------------------- |
| `GET`  | `/health`         | Readiness probe — returns `{"status":"ok"}`.              |
| `POST` | `/analyze-ticket` | Analyze one ticket and return the structured response.    |

---

## Architecture & AI Approach

We use a **"LLM proposes, deterministic rules enforce"** pipeline. The LLM does
the open-ended reasoning; small deterministic layers guarantee the parts of the
contract that must never drift (routing, the evidence invariant, escalation, and
safety). Each request flows through:

1. **Heuristic matcher — [`app/matcher.py`](app/matcher.py)**
   Pre-filters the transaction history with fast, deterministic scoring (amount
   match ±5%, transaction-type keywords, recency) and passes the top candidates
   to the LLM as hints.

2. **LLM structured reasoning — [`app/llm.py`](app/llm.py)**
   Calls Gemini with a strict system prompt and `response_mime_type:
   "application/json"`. The LLM picks the relevant transaction, judges the
   evidence, classifies the case, and drafts the summaries and customer reply.

3. **Deterministic normalizer — [`app/normalize.py`](app/normalize.py)**
   Corrects the LLM output against rules that are fully deterministic:
   - `department` is derived strictly from `case_type` (Problem Statement §7.2).
   - A verdict of `consistent`/`inconsistent` **requires** a matched transaction;
     a `null` `relevant_transaction_id` is forced to `insufficient_data`.
   - `duplicate_payment` with two identical payments points to the **later**
     duplicate with verdict `consistent` (it is confirming evidence, not ambiguity).
   - A `wrong_transfer` to a counterparty that appears **2+ times** in history is
     forced to `inconsistent` (a known/established recipient contradicts the claim).
   - `human_review_required` is set by a deterministic escalation policy.
   - `confidence` is never `null` or `0` on a real analysis.

4. **Safety post-filter — [`app/safety.py`](app/safety.py)**
   A non-negotiable backstop that scans `customer_reply` and
   `recommended_next_action` for unsafe language and rewrites the reply if needed.

5. **Graceful fallback — [`app/fallback.py`](app/fallback.py)**
   If the LLM times out (20s cap), is rate-limited (429), or errors, the service
   returns a safe, `human_review_required: true` response with **200 OK** instead
   of crashing — so the judge harness is never interrupted.

Orchestration, the per-request timeout, and the `422`/`500` handlers live in
[`app/main.py`](app/main.py).

---

## MODELS

| Item            | Value                                                            |
| --------------- | --------------------------------------------------------------- |
| Model           | `gemini-2.5-flash` (configurable via `MODEL_NAME`)              |
| Where it runs   | Google Gemini API (external, called over HTTPS)                |
| Why chosen      | Native JSON output, strong instruction-following, low latency/cost (stays well under the 30s timeout), and solid multilingual handling including **Bangla**. |

No model weights are bundled in the image; the model is called at runtime.

---

## Setup

**Prerequisites:** Python 3.11+ and a Google Gemini API key.

```bash
# 1. Clone and enter the project
cd "SUST Hackathon"

# 2. (Recommended) create a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets — copy the template and add your key
cp .env.example .env
#   then edit .env and set GEMINI_API_KEY=...
```

`.env` keys (see [`.env.example`](.env.example)):

| Variable         | Required | Default            | Notes                          |
| ---------------- | -------- | ------------------ | ------------------------------ |
| `GEMINI_API_KEY` | yes      | —                  | Your Google Gemini API key.    |
| `MODEL_NAME`     | no       | `gemini-2.5-flash` | Any Gemini model id.           |
| `PORT`           | no       | `8000`             | Port for local runs.           |

> Secrets are loaded from `.env` via `python-dotenv`. Never commit `.env`;
> only `.env.example` (names only) is tracked.

---

## Run

### Locally (uvicorn)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# health check:
curl http://localhost:8000/health      # -> {"status":"ok"}
```

### With Docker

```bash
docker build -t queuestorm .
docker run -p 8000:8000 --env-file .env queuestorm
```

### Run the sample test suite

With the server running in one terminal:

```bash
python tests/run_sample_cases.py
```

This POSTs all 10 cases from `Preliminary Questions and Resources/SUST_Preli_Sample_Cases.json`
and diffs the core fields against the expected outputs.

---

## Sample Request

`POST /analyze-ticket`

```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today. The number was supposed to be 01712345678 but I think I typed it wrong. The person isn't responding to my call. Please help me get my money back.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "campaign_context": "boishakh_bonanza_day_1",
  "transaction_history": [
    {
      "transaction_id": "TXN-9101",
      "timestamp": "2026-04-14T14:08:22Z",
      "type": "transfer",
      "amount": 5000,
      "counterparty": "+8801719876543",
      "status": "completed"
    },
    {
      "transaction_id": "TXN-9087",
      "timestamp": "2026-04-13T18:12:00Z",
      "type": "cash_in",
      "amount": 10000,
      "counterparty": "AGENT-512",
      "status": "completed"
    }
  ]
}
```

Only `ticket_id` and `complaint` are required; everything else is optional.
`transaction_history` may be empty (e.g. for phishing/safety reports).

## Sample Response

`200 OK`

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to +8801719876543, which they now believe was the wrong recipient. Recipient is unresponsive.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Our dispute team will review the case and contact you through official support channels. Please do not share your PIN or OTP with anyone.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer", "transaction_match", "dispute_initiated"]
}
```

A recorded example is also saved at
[`sample_outputs/sample_output_1.json`](sample_outputs/sample_output_1.json).

### HTTP status codes

| Code  | Meaning                                                                 |
| ----- | ---------------------------------------------------------------------- |
| `200` | Successful analysis; body conforms to the response schema.             |
| `422` | Schema-valid but semantically invalid input (e.g. missing `complaint`).|
| `500` | Internal error; body carries a non-sensitive message (no stack traces).|

The service never crashes on malformed input — it returns `422`/`500`, never an
exit.

---

## Safety Logic

Safety rules are enforced **after** the LLM, as a deterministic gatekeeper in
[`app/safety.py`](app/safety.py). It scans both `customer_reply` and
`recommended_next_action`:

1. **No unauthorized refund/reversal promises** — phrases like "we will refund
   you" or "your money will be returned" are flagged. The model is steered to use
   non-committal language such as *"any eligible amount will be returned through
   official channels."*
2. **No third-party redirects** — directing the customer to an outside number or
   unofficial channel is flagged.
3. **Credential protection (context-aware)** — asking the customer to *share* a
   PIN/OTP/password/CVV is flagged, **but a defensive warning** like *"do **not**
   share your PIN or OTP"* is explicitly allowed (a negation guard prevents the
   warning from being misread as a request). Warning customers is encouraged.

If any real violation is found, the `customer_reply` is overwritten with a safe
template, `human_review_required` is forced to `true`, and a `safety_override`
reason code is appended.

Independently, the prompt instructs the model to **ignore instructions embedded
in the complaint text** (prompt-injection defense) — the complaint is treated as
untrusted input, never as system instructions.

---

## Assumptions & Known Limitations

- **External LLM dependency.** The service requires a reachable Gemini API and a
  valid key. The free tier is rate-limited (~5 req/min for `gemini-2.5-flash`),
  which is why the sample runner sleeps between cases and the service degrades to
  a safe fallback on `429`/timeout.
- **Non-determinism is bounded, not eliminated.** Free-text fields
  (`agent_summary`, `recommended_next_action`, `customer_reply`) and `severity`
  still depend on the model. The deterministic layer only guarantees
  `department`, the verdict/`relevant_transaction_id` invariant, the
  duplicate/known-recipient verdicts, `human_review_required`, and a non-null
  `confidence`.
- **Heuristic matcher is simple.** Candidate scoring uses amount/type/recency and
  may misrank highly ambiguous multi-candidate cases; for genuinely ambiguous
  different-recipient matches the system intentionally returns
  `insufficient_data` rather than guessing.
- **Stateless & synthetic.** No database or persistence; the service operates only
  on the data passed in each request. All data is synthetic per the problem spec.
- **Not production-hardened.** Real deployment would add authentication, request
  rate-limiting, structured logging/metrics, and per-tenant quotas.

---

## Project Layout

```
app/
  main.py        # FastAPI app, orchestration, timeout, error handlers
  schemas.py     # Pydantic request/response models (enum validation)
  matcher.py     # Heuristic transaction candidate pre-filter
  llm.py         # Gemini call + system prompt
  normalize.py   # Deterministic enforcement of contract rules
  safety.py      # Post-hoc safety guardrails
  fallback.py    # Safe degraded response
tests/
  run_sample_cases.py   # Hits /analyze-ticket with the 10 sample cases
sample_outputs/
  sample_output_1.json  # Recorded sample response
Dockerfile
requirements.txt
.env.example
```

---

## Deliverables Checklist

- [x] `/health` returns `{"status":"ok"}`.
- [x] `/analyze-ticket` validated against all 10 sample cases.
- [x] Safety guardrails: no PIN/OTP request, no refund promise, no third-party redirect.
- [x] Malformed input returns `422`/`500`, never a crash.
- [x] No secrets committed; `.env.example` lists names only.
- [x] README covers setup, run, sample request/response, models, safety, and limitations.
- [x] Sample output saved in `sample_outputs/`.
- [ ] GitHub repo shared with organizer handle `bipulhf`.
- [ ] Submission form filled with live URL + repo link.
