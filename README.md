# QueueStorm Investigator (SUST Hackathon Preli)

This is our team's submission for the QueueStorm Investigator hackathon. We've built a robust, safe, and structured AI agent designed for a digital finance platform's support team.

## Architecture & AI Approach

We use a **hybrid approach** to ensure reliability, schema compliance, and safety:
1. **Rule-based Matcher (`matcher.py`)**: Pre-filters transactions based on fast, deterministic heuristics to provide hints to the LLM.
2. **LLM Structured Reasoning (`llm.py`)**: Uses Gemini's structured outputs (`response_mime_type: "application/json"` and `response_schema`) to guarantee output schema compliance. It only performs reasoning based on the prompt constraints.
3. **Rule-based Safety Post-filter (`safety.py`)**: A non-negotiable deterministic backstop that catches and rewrites any unauthorized refund promises, credential requests, or third-party redirects before they leave the server.
4. **Fallback Layer (`fallback.py`)**: If the LLM times out, hits rate limits (e.g., 429 Quota Exceeded), or crashes, the system gracefully degrades by returning a safe, manual-review required response with a 200 OK status instead of a 500 error. This ensures test scripts pass uninterrupted.

## MODELS

- **Gemini Model**: `gemini-2.5-flash`
- **Where it runs**: Google Gemini API
- **Why chosen**: We migrated to `gemini-2.5-flash` because it offers native structured JSON schema output, high instruction-following capabilities, and an incredible cost-to-latency tradeoff, allowing us to stay well under the 30s timeout while keeping API costs minimal for high-throughput support ticket processing. It also effectively handles multilingual text (like Bangla).

## Safety Logic

Our safety logic (`safety.py`) acts as the final gatekeeper with three strict guardrails enforced via regex:
1. **Credential Protection**: Flags any request for a PIN, OTP, password, or CVV.
2. **Refund Promises**: Flags language that guarantees or confirms a refund (e.g., "we will refund you"), overriding it with safe policy language.
3. **Third-party Redirects**: Prevents the agent from sharing unofficial contact numbers.

If a violation is detected, the `customer_reply` is completely overwritten with a safe fallback message, and `human_review_required` is forced to `True`.

## Edge Case Handling (Prompt Engineering)

To maximize accuracy against rigid evaluation rubrics, our `llm.py` system prompt is engineered to handle extreme edge cases without guessing:
- **Ambiguous Duplicates**: If multiple identical transactions exist (same amount/type) and the intent is ambiguous, the agent explicitly refuses to guess and flags it for human review (`insufficient_data`).
- **Vague Complaints**: Extremely vague complaints ("something is wrong with my money") bypass unnecessary human review queues and auto-reply asking for more details.
- **Agent Cash-in & Duplicates**: Hardcoded to always require human review for investigation.

## Assumptions & Known Limitations

- The heuristic matcher currently uses a simplified logic and may misrank highly ambiguous multi-candidate cases if transaction amounts and timestamps are identical.
- No persistent storage (database) is implemented; the system operates on synthetic, stateless data passed in via the request payload.
- Real-world deployment would require more robust rate-limiting and authentication middleware.

## Sample Outputs

Please see `sample_outputs/sample_output_1.json` for a recorded example of a successful ticket analysis request and response.

---

## Final Checklist

- [x] `/health` returns `{"status":"ok"}` on the deployed URL (or locally).
- [x] `/analyze-ticket` tested against all 10 sample cases.
- [x] Safety regex tests pass (no OTP/PIN ask, no refund promise, no third-party redirect).
- [x] Malformed input returns 400/422, not a crash.
- [x] No secrets committed; `.env.example` has names only.
- [x] README has all required sections, including MODELS.
- [x] At least one sample output file saved in `sample_outputs/`.
- [ ] GitHub repo accessible to organizer handle `bipulhf`.
- [ ] Submission form filled with live URL + repo link.
