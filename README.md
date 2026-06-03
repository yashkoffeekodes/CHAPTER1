# Chapter1-Assist

A FastAPI + LangGraph based ERP/accounting assistant that answers business-data queries by selecting the correct ERP tool, calling the backend API, and returning clean Hinglish/English conversational responses.

**Author:** Yash Sheth

---

## Overview

Chapter1-Assist connects to the Chapter-1 ERP backend and answers natural language queries about:

- Customer lookup by brand and city
- Customer ledger balance and transactions
- Stock levels by product, HSN, SKU, or low-stock status
- GST summary reports (B2B, B2C, exports, nil-rated, credit notes, grand total)
- TDS outstanding reports
- TCS outstanding reports

The system uses three local LLMs: a small translator (1024 ctx) for query normalization, a full-size worker (4096 ctx) for tool-call generation, and a dedicated summary LLM (4096 ctx) that writes the final Hinglish/English response from real API output. This reduces hallucination, keeps responses predictable, and avoids external API costs.

For a deeper look at how each component works, see [ARCHITECTURE.md](./ARCHITECTURE.md). For what changed in the latest iteration, see [CHANGES.md](./CHANGES.md) and [DIFF.md](./DIFF.md).

---

## Architecture

```text
START
  -> translator_node       (Ollama qwen3:latest — Hinglish→English, language detection)
  -> semantic_search       (bge-m3 embedding + cross-encoder rerank + keyword fallback + city-name routing)
  -> chat_model_node       (Ollama qwen3:latest with bind_tools — native tool calling)
  -> _apply_repair         (registry-driven fixup: param aliases, dates, filters,
  |                         generic corrections, strict-marker, min/max→limit, name)
  -> tools_node            (executes backend APIs)
  -> generate_llm_summary  (Ollama qwen3:latest — Hinglish/English response from real data)
  -> END
```

### Node Responsibilities

| Node | Responsibility |
|---|---|---|
| `translator_node` | Translates Hinglish/Hindi/Gujarati to English, detects source language |
| `semantic_search` | Selects relevant ERP tools via embedding recall + cross-encoder reranking + keyword fallback + city-name routing |
| `chat_model_node` | Generates tool calls from query + available tools (Ollama native `bind_tools`); includes internal retry loop when multiple tools are needed (qwen3 emits 1 call per response) |
| `_apply_repair` | Fixes LLM tool call args: param aliases, category map, dates, value filters, malformed filter normalization, generic corrections (min/max→limit=1, "which entity"→ensure name), positive/negative value injection |
| `tools_node` | Executes the ERP tool functions against the Chapter-1 backend API |
| `deterministic_final_node` | Builds final JSON from tool output, runs `generate_llm_summary` for the response text, falls back to Python `make_summary` on LLM failure |

---

## Supported Tools

| Tool | Purpose |
|---|---|
| `get_customer` | Search customers by brand/city, return ID, name, opening balance |
| `get_customer_ledger` | Fetch ledger opening, current, closing balance, and transactions |
| `get_stock_levels` | Fetch stock levels by product, HSN, SKU, quantity, low/out-of-stock; local sort when API ignores sort params |
| `get_gst_summary` | Fetch GST summary (B2B, B2C, export, nil-rated, credit notes, grand total) |
| `get_tds_outstanding` | Fetch TDS outstanding summary and section-wise details |
| `get_tcs_outstanding` | Fetch TCS outstanding summary and section-wise details |

---

## Key Features

### Local LLM, No External API

Worker and translator are both `qwen3:latest` (8B) running locally via Ollama with `reasoning=False` (disables qwen3 thinking tokens). No Groq/OpenAI keys, no rate limits, no per-query cost. RTX 3070 (8GB VRAM) is sufficient.

### Embedding + Cross-Encoder Tool Routing

Tool selection uses a 3-stage pipeline:
1. **Embedding recall** (`bge-m3`) over pre-computed tool embeddings
2. **Cross-encoder reranking** (`cross-encoder/ms-marco-MiniLM-L-6-v2`) — eager-loaded at startup
3. **Keyword fallback** with word-boundary regex against the registry's `keywords`/`aliases` — handles short Hinglish queries

### Native Tool Calling (No JSON Parsing)

Worker LLM uses `llm.bind_tools(available_tools).ainvoke()`. Ollama's tool-calling API handles schema validation, so no JSON text parsing and no truncation bugs. Internal retry loop re-invokes the LLM when multiple tools are needed (qwen3 emits only 1 tool call per response).

### LLM's Fields Authoritative + Trigger Safety Net

The LLM's explicit `fields` choice is always respected (`overwrite=True` preserves LLM field names). `field_triggers` act as a safety net — they add fields the user asked for but the LLM missed. A strict marker (`sirf`/`only`/`just`/`bas`) in the query disables triggers globally, making the LLM's field choice authoritative.

### Generic Cross-Tool Corrections

Applied in `_apply_repair` after all tool-specific logic, so they never interfere with existing repair rules:

- **Min/max → limit=1**: "sabse kam/jyada", "least/most/lowest/highest" → forces `limit=1` (unless an explicit count like "top 3" exists)
- **"Which entity?" → ensure name**: "kis product ka", "kaunsa customer", "which party" → prepends `name` to fields if missing

### Malformed Filter Normalization

LLMs sometimes generate malformed filter syntax like `{"closingQty gt": "2"}` or `{"name.contains": "Bangalore"}`. The repair layer normalizes these:
- `"closingQty gt": "2"` → `{"closingQty": {"gt": 2.0}}`
- `"name.contains": "Bangalore"` → `{"name": {"contains": "Bangalore"}}`

Filters with `.`, spaces, `$`, `>`, `<`, `=` in keys are skipped entirely (prevents API crashes from hallucinated formats).

### Numeric Comparison Fix

`match_filter` uses `float()` equality when both record values and filter values parse as numbers. This prevents falsematches like `"0"` matching `"-64894.05"`.

### Local Sort for Stock Levels

The stock API ignores `sortField`/`sortOrder`. `get_stock_levels` fetches 200 records, sorts locally by the requested field, and truncates to the requested limit.

### LLM-Generated Final Response

The worker LLM chooses tool calls, but the final response text is generated by a **dedicated summary LLM** that receives the raw API data, projected records, and the original user query. This allows the response to match the user's language (Hinglish/Hindi/English) while staying grounded in real data:

```text
Worker LLM chooses tool calls → Tools fetch real ERP data → Python builds compact data + raw_response
→ Summary LLM writes conversational response from actual values (no hallucination)
```

Key design:
- **Raw data section** in the prompt contains the REAL API values with all fields — the LLM uses these, not the projected records
- **Record counts section** shows only counts and first 10 samples of the projected data
- **Language instruction** dynamically adapts based on `detected_language` (Hinglish → Roman-script Hindi + English ERP terms, English → plain English)
- Falls back to deterministic Python `make_summary` if the LLM call fails

This prevents hallucinated records, amounts, customer IDs, GST values, stock quantities, or ledger balances.

### Config-Driven Repair System

Tool argument repair uses `TOOL_INTENT_REGISTRY` in `src/tool_doc.py` rather than hardcoded if/elif chains:

- **`param_aliases`** — maps LLM param names to real params (e.g., `"name"` → `"term"`)
- **`category_map`** — maps category aliases (e.g., `"b2csmall"` → `"b2cSmall"`) with auto-generated no-space variants
- **`prefix expansion`** — generic: any single-word keyword prefixing multi-word keywords auto-expands (e.g., "b2c" → both b2cLarge + b2cSmall)
- **`parent-keyword dedup`** — when parent and child keywords map to same value, the value is kept (not deduped away)
- **`category_to_filter`** — converts GST category keywords to API filters
- **`low_stock_only_keywords`** — forces `low_stock_only=False` unless query mentions "low stock"
- **`field_triggers`** (from `repair.field_triggers`, not `field_aliases`) — curated per tool, high precision, maps user phrases to field names
- **`strict marker`** — `sirf`/`only`/`just`/`bas` disables all field_triggers, making LLM's field choice authoritative

Adding a new tool or category keyword requires zero code changes — just add to the registry.

### Generic Value-Comparison Filters (Positive + Negative)

The repair layer automatically injects value-comparison filters when the query mentions negative/positive values:

| Query phrase | Auto-injected filter |
|---|---|
| "negative closing qty" / "less than 0" / "0 se kam" / "< 0" | `{<field>: {lt: 0}}` |
| "positive closing qty" / "greater than 0" / "0 se jyada" / "0 se upar" / "> 0" | `{<field>: {gt: 0}}` |

Only applies to fields whose names contain Qty/Value/Rate/Amount/Balance/Count/Gst/St. Injects the filter only when the LLM has not already set `filters`. Both English and Hinglish patterns are supported.

### Multi-Identifier Queries

Queries with multiple identifiers (e.g., "49090090 aur id 349") are split into separate tool calls:

```text
"49090090 aur id 349 dono ka stock status kya hai?"
  -> Call 1: get_stock_levels(filters={"hsnCode": "49090090"})
  -> Call 2: get_stock_levels(filters={"id": 349})
```

### GST Category Filtering

GST summary API returns all categories. The system filters based on the user query using the same generic prefix-expansion logic as the repair layer:

| User asks | Returned categories |
|---|---|
| B2B GST | `b2b` only |
| Grand total GST | `grandTotal` only |
| B2B + grand total | `b2b`, `grandTotal` |
| Generic "B2C" | `b2cLarge` + `b2cSmall` (both) |
| "B2C Small" specifically | `b2cSmall` only |
| Full GST summary | All categories |

### Field Projection Fallback

When the LLM requests fields that don't match actual API field names (e.g., `customer_id` vs `id`, `city` vs no such per-customer field), `project_fields` returns the original records instead of silently dropping all data. This prevents empty results from name mismatches while preserving projection behavior when field names are correct.

### Search Sanitization for Customer Lookup

The LLM often treats `search` as a semantic filter rather than a name substring match. `get_customer` automatically sanitizes bad search terms:
- **Fetch-all keywords** (`"all"`, `"all customers"`, `"everyone"`, etc.) → empty search (return all)
- **Comma-separated lists** (`"kolkata,punjab,bangalore"`) → empty search (not a real customer name)

### City-Name Routing

When the semantic search node splits a query into parts (e.g., `"how many customers in kolkata and punjab?"` → `"how many customers in kolkata"` + `"punjab?"`), lone city names that fail tool matching now route to `get_customer` via the `CITY_WORDS` list from `config.yaml`. Adding a new city to the config automatically makes it routeable.

---

## Tech Stack

| Component | Technology |
|---|---|---|
| Framework | FastAPI |
| Graph Engine | LangGraph |
| Worker LLM | `qwen3:latest` (8B) via Ollama (`reasoning=False`, `num_predict=2048`, `num_ctx=4096`) |
| Translator LLM | `qwen3:latest` (8B) via Ollama (`reasoning=False`, `num_predict=512`, `num_ctx=1024`) |
| Summary LLM | `qwen3:latest` (8B) via Ollama (`reasoning=False`, `num_predict=2048`, `num_ctx=4096`) |
| Embeddings | `bge-m3` via Ollama |
| Cross-encoder reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Backend | Chapter-1 ERP API |
| HTTP client | `requests` (sync, planned migration to `httpx.AsyncClient`) |

---

## Project Structure

```text
CHAPTER1-ASSIST/
├── fast_main.py              # FastAPI entry point, cache, session management, response format
├── config.yaml               # All pipeline config (cities, thresholds, words, field names)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not committed)
├── ARCHITECTURE.md           # Detailed architecture of each pipeline stage
├── CHANGES.md                # Chronological list of changes in this iteration
├── DIFF.md                   # Old vs new architecture comparison
│
├── src/
│   ├── config.py             # LLM setup (qwen3, reasoning=False), API env vars, YAML loader
│   ├── schema.py             # State/schema definitions (MainState, InputState)
│   ├── api_client.py         # HTTP client with timeout/error handling
│   ├── tools_api.py          # API-backed ERP tool functions (project_result, match_filter, local sort)
│   ├── tool_doc.py           # Tool descriptions, intent registry, repair configs, field aliases
│   ├── nodes.py              # LangGraph nodes, repair logic, query processing, semantic search
│   └── graph.py              # LangGraph graph builder
│
└── README.md
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
CHP1_API_BASE_URL=https://dev.chapter1.finance/aiAnalytics/
CHP1_API_TOKEN=your_api_token_here
COMPANY_ID=355
CHP1_API_TIMEOUT=10
```

The auth header is currently hardcoded to a test value in `api_client.py` and will become dynamic when the production API URL is finalized.

---

## Installation

Clone the repository:

```bash
git clone <your-repo-url>
cd CHAPTER1-ASSIST
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Make sure Ollama is running and required models are available:

```bash
ollama list
```

Pull models if needed:

```bash
ollama pull qwen3:latest
ollama pull bge-m3
```

The cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) downloads automatically on first startup.

---

## Running

Start the FastAPI server:

```bash
python fast_main.py
```

Server starts at:

```text
http://127.0.0.1:8000
```

First startup takes ~5-10s for cross-encoder model load. Subsequent startups are faster (model cache).

---

## API Usage

**Endpoint:** `POST /chat`

**Example Request:**

```json
{
  "query": "HSN 48211090 ka stock name and closing quantity dikhao"
}
```

**Example Response:**

```json
{
  "response": {
    "success": true,
    "status": "success",
    "query": "HSN 48211090 ka stock name and closing quantity dikhao",
    "tools_used": ["get_stock_levels"],
    "data": {
      "get_stock_levels": [
        {
          "name": "Office Products 48211090 @ 18",
          "hsnCode": "48211090",
          "closingQty": -43
        }
      ]
    },
    "summary": "get_stock_levels: found 1 record",
    "errors": []
  }
}
```

---

## Test Queries

### Customer Lookup

```json
{
  "query": "Nykaa Bangalore customer id, name and opening balance batao"
}
```

### Min/ Max Stock Query

```json
{
  "query": "jo sabse kam closing quantity wala product hai uska value aur name chaia"
}
```

### Customer Ledger

```json
{
  "query": "Customer id 814 ka opening, current and closing balance bata from 2024-04-01 to 2024-12-31"
}
```

### Stock by HSN

```json
{
  "query": "Show stock levels for HSN 48211090"
}
```

### Multi-Product Stock Query

```json
{
  "query": "49090090 aur id 349 dono ka stock status kya hai?"
}
```

### GST B2B + Grand Total

```json
{
  "query": "Show B2B GST taxable amount, IGST, CGST, SGST and invoice amount, also show grand total GST from 2024-04-01 to 2024-04-30"
}
```

### Multi-tool Query (Hinglish)

```json
{
  "query": "b2c and b2b and grandtotal ka info chaia for april 2024?"
}
```

### TDS + TCS Outstanding

```json
{
  "query": "Show TDS outstanding and TCS outstanding from 2024-04-01 to 2024-12-31"
}
```

### Negative / Positive Stock Query

```json
{
  "query": "negative closing quantity wale products dikhao"
}
```

### Strict Fields Query

```json
{
  "query": "sirf closing quantity batao"
}
```

---

## Performance

Typical local timings (qwen3:8b on RTX 3070):

| Stage | Approx Time |
|---|---|
| translator_node (cold) | ~7s |
| translator_node (warm) | ~3s |
| semantic_search | ~0.5s |
| chat_model_node | ~4.4s |
| tools_node (1 call) | ~0.25s |
| deterministic_final + format | <50ms |
| **Total single-tool (cold)** | **~12s** |
| **Total single-tool (warm)** | **~5-6s** |

Multi-tool queries currently run tools sequentially (~500ms for 2 calls). Future async + httpx refactor would cut this to ~250ms.

---

## Security

Before pushing to GitHub, ensure secrets are not committed:

```bash
grep -R "Authorization\|API_TOKEN\|SECRET\|KEY" .
```

Do not commit `.env`, `venv/`, `__pycache__/`, or `chroma_db/`.

---

## Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Detailed walkthrough of each pipeline component
- **[CHANGES.md](./CHANGES.md)** — Chronological list of code/architecture changes
- **[DIFF.md](./DIFF.md)** — Old vs new architecture, with rationale for each change

---

## License

This project is currently a prototype/portfolio ERP assistant. Add a license file before public distribution if required.

---

**Author:** Yash Sheth
