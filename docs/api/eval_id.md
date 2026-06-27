# `eval_id` — Evaluation Identifier

Every governance evaluation is assigned a unique `eval_id` at storage time. This ID is used for lookup in reports, PDF download, and cross-referencing between evaluations.

## Format

```
eval_YYYYMMDD_HHMMSS_xxxxxx
```

- `YYYYMMDD` — date (UTC)
- `HHMMSS` — time (UTC)
- `xxxxxx` — first 6 hex chars of MD5 of `(timestamp + id(now))`

**Example**: `eval_20240601_120000_a1b2c3`

## Generation

Two places:

1. **`_evaluate_and_record()`** (`cgt_governor.py:377`) — called by `/cgt/govern`, `/cgt/govern/batch`, `/cgt/govern/report`, `/cgt/govern/auto-repair`
2. **`gateway_evaluate()`** (`cgt_governor.py:1086`) — called by `/cgt/govern/gateway/evaluate`

In both cases, `eval_id` is added to the entry **before** encryption, so the ID is cryptographically bound inside the ciphertext.

## Auto-generation Fallback

In `JsonlEvaluationStore.append()` (`storage.py:67-68`):

```python
if "eval_id" not in entry:
    entry["eval_id"] = self._generate_eval_id()
```

This ensures every stored entry has an `eval_id`, even if the caller forgot to set one.

## Usage

| Endpoint / Component | How `eval_id` Is Used |
|----------------------|----------------------|
| `POST /cgt/govern` | Returned in response body: `"eval_id": "eval_..."` |
| `POST /cgt/govern/gateway/evaluate` | Returned in response body |
| `GET /cgt/govern/reports/{eval_id}/pdf` | Looks up entry by `eval_id` and generates a PDF |
| Reports UI (`reports.js`) | Used as the key for row clicks, PDF/JSON download buttons |
| `PolicyActionRecord` | Stored as `eval_id: str` in policy engine history |
| `ContextMetadata.parent_eval_id` | Links child evaluations to parent |

## Lookup

PDF download endpoint (`cgt_governor.py:870`):

```python
for stored in reversed(eval_store.entries):
    entry = decrypt_log_entry(stored, _crypto_key)
    if entry.get("eval_id") == eval_id:
        pdf_bytes = generate_governance_pdf(entry, language=lang, signature=sig)
        return Response(content=pdf_bytes, media_type="application/pdf")

raise HTTPException(status_code=404, detail=f"Evaluation eval_id='{eval_id}' not found")
```

## Encryption Boundary

```
entry = { ..., "eval_id": "eval_..." }       ← set before encryption
ciphertext = encrypt_report(entry, key)       ← eval_id is encrypted
stored = canonical_json(ciphertext)           ← eval_id is opaque
decrypted = decrypt_report(ciphertext, key)   ← eval_id recovered after decryption
```
