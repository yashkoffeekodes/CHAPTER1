# CHapter1-assist Version 4

CHapter1-assist Version 4 is a FastAPI + LangGraph based ERP/accounting assistant prototype. It is designed to answer business-data queries by selecting the correct ERP tool, calling the backend API, and returning clean deterministic JSON responses.

This version focuses on stability, low latency, deterministic final output, and safer handling of unsupported queries.

---

## Overview

The assistant can answer questions related to:

- Customer lookup
- Customer opening balance
- Customer ledger balance
- Customer ledger transactions
- Stock and HSN-based inventory lookup
- GST summary reports
- TDS outstanding reports
- TCS outstanding reports

The project uses a local LLM mainly for tool-call generation, while the final response is built deterministically from real API output. This reduces hallucination and keeps the response predictable.

---

## Current Version Focus

Version 4 moves back to the stable compact deterministic approach after testing a fully metadata-driven version.

The current version prioritizes:

- Correct tool routing
- Stable multi-tool queries
- Compact final JSON
- No raw API dumps
- No hallucinated business values
- Fast rejection of unsupported invoice/voucher queries
- Better latency with caching

---

## Supported Tools

| Tool | Purpose |
|---|---|
| `get_customer` | Search customers and return customer ID, name, opening balance, and opening type |
| `get_customer_ledger` | Fetch customer ledger opening, current, closing balance, and transactions |
| `get_stock_levels` | Fetch stock levels by product, HSN, SKU, quantity, low stock, or out-of-stock state |
| `get_gst_summary` | Fetch GST summary such as B2B, B2C, export, nil-rated, credit notes, and grand total |
| `get_tds_outstanding` | Fetch TDS outstanding summary and section-wise details |
| `get_tcs_outstanding` | Fetch TCS outstanding summary and section-wise details |

---

## Unsupported in Current Scope

The following are intentionally not supported in this version:

- Sales invoice lookup
- Purchase invoice lookup
- Receipt voucher lookup
- Payment voucher lookup
- Sale return lookup
- Purchase return lookup

Unsupported queries should return a safe response instead of calling a wrong tool.

Example unsupported query:

```json
{
  "query": "Show sales invoice A/0326/C0077 customer and amount"
}
```

Expected behavior:

```json
{
  "success": false,
  "status": "unsupported",
  "tools_used": [],
  "data": {},
  "summary": "This query needs invoice/voucher tools, which are not enabled in the current 6-tool scope.",
  "errors": []
}
```

---

## Architecture

The current stable flow is:

```text
START
  -> translator_node       (granite4.1:8b — Hinglish→English)
  -> semantic_search       (keyword + metadata tool routing)
  -> chat_model_node       (Groq llama-3.3-70b — generates tool calls as JSON text)
  -> routing_node          (conditional: tool_calls? → tools : → end)
  -> ToolNode              (executes backend APIs)
  -> deterministic_final   (builds JSON from API data)
  -> END
```

### Node Responsibilities

| Node | Responsibility |
|---|---|
| `translator_node` | Translates Hinglish/Hindi queries to English (granite4.1:8b) |
| `semantic_search` | Selects relevant ERP tools using keyword + metadata rules |
| `chat_model_node` | Generates tool calls from query + tools (Groq llama-3.3-70b) |
| `routing_node` | Routes to tools if tool calls exist, else ends |
| `ToolNode` | Executes backend API tools |
| `deterministic_final_node` | Builds final JSON from tool output — no hallucination |

---

## Key Design Decisions

### 1. Deterministic Final Response

The LLM does not write the final business answer directly.

Instead:

```text
LLM chooses tool calls
Tools fetch real ERP data
Python builds final JSON deterministically
```

This helps prevent hallucinated records, amounts, customer IDs, GST values, stock quantities, or ledger balances.

### 2. Compact Output Projection

The final node only returns the fields requested by the user or the safest default fields for that tool.

Example:

If the user asks:

```text
HSN 48211090 ka stock name, HSN and closing quantity dikhao
```

The response should include:

```json
{
  "name": "Office Products 48211090 @ 18",
  "hsnCode": "48211090",
  "closingQty": -43
}
```

### 3. Ledger Transaction Compaction

Ledger API responses can contain very large nested `items` arrays.

Version 4 removes the full nested item dump and replaces it with:

```json
{
  "itemCount": 70
}
```

This keeps the response useful without returning huge raw payloads.

### 4. GST Category Filtering

GST summary API may return all categories, but the final node filters rows according to the user query.

Examples:

| User asks | Returned categories |
|---|---|
| B2B GST | `b2b` only |
| Grand total GST | `grandTotal` only |
| B2B + grand total | `b2b`, `grandTotal` |
| Full GST summary | All GST categories |

### 5. Deterministic Repair Layer

Groq/llama-3.3-70b generates tool calls as JSON text. A repair layer inside `chat_model_node` (`_apply_repair`) normalizes and corrects tool arguments using metadata from `TOOL_INTENT_REGISTRY[]["repair"]` — no `if/elif` chains:

**Tool name aliases**: `tds_report`→`get_tds_outstanding`, `tcs_report`→`get_tcs_outstanding`, `stock_report`→`get_stock_levels`

**Date alias normalization** (`_repair_tool_call`): Worker outputs `startDate`/`endDate` — these are normalized to canonical `from_date`/`to_date` before repair runs. Also handles `date_from`/`date_to`, `start_date`/`end_date`.

**Worker date preservation** (`_apply_repair`): Worker (Groq) produces correct date ranges. The repair layer captures `from_date`/`to_date` from worker output BEFORE applying overwrite args, then restores them. `date_keywords` only fires when both dates are still missing after all repair steps.

**Segment-based date assignment**: The old "first/last date range" approach broke when query order changed. `extract_date_range_for_tool()` splits the query into per-tool segments bounded by the next major tool keyword, then extracts the first date range from each segment.

**GST repair** (`overwrite=True`): Hard overwrites with `base_args` (empty dates), fills dates via `date_keywords` (only if worker omitted them), removes filters, applies `category_map`, appends keyword-matched fields.

**Stock strict override**: When an 8-digit HSN is found, worker's bad filters are discarded entirely. Args replaced with `{term: HSN, filters: {hsnCode: HSN}, fields: [name, id, hsnCode, closingQty]}`.

**Customer arg override** (`overwrite=True`): Brand (`Nykaa`), city, and requested fields extracted deterministically from query. Multi-city queries create one call per city via `expand_customer_city_calls()`. Unknown location after "Nykaa" (e.g., "Mars") is used as filter.

**Customer ledger arg override** (`overwrite=False`): Forces `customer_id` from regex, segment-based date extraction, fixed fields. `strict_field_keywords` ("sirf"/"only") restricts to `["closing"]`.

**TDS/TCS arg override** (`overwrite=True`): Hard overwrites with `base_args` + `date_keywords` (only if worker omitted dates).

**TCS injection**: If query mentions "tcs" and the tool was selected but missing, injects the call.

**Deduplication**: Two passes — `(name, args)` JSON-key dedup, then safety dedup (keeps first call per tool name for non-customer tools).

**Tolerant JSON parser**: The parser (`parse_planner_json_blocks` + `normalize_planner_blocks`) handles multi-block output, markdown fences, missing `args`/`arguments` keys, and malformed `=` suffixes.

**unsupported_parts**: Invoice/voucher parts are checked per-part. Supported parts proceed; unsupported parts tracked in `state["unsupported_parts"]` (must be in `MainState` TypedDict or langgraph drops it silently) and reported in final response with `status: "partial_success"`.

### 6. Groq JSON Text Planner

The worker LLM (Groq llama-3.3-70b) outputs tool calls as a JSON text array. The system prompt includes concrete examples for each tool:

**Customer lookup**: brand+city → `search="Nykaa"`, `filters={"name":{"contains":"BANGALORE"}}`
**Ledger**: `customer_id` must be int, dates in YYYY-MM-DD
**Stock**: HSN → `term="48211090"`, low/out stock via filters
**GST**: Category mapping (b2b, b2cLarge, etc.), date range
**TDS/TCS**: Section filter (194C, 206C)

Response text is parsed as JSON, converted to LangChain `tool_calls`, and executed via ToolNode. This approach gives ~0.7s LLM latency.

### 7. Token Usage Logging

Every LLM invocation logs token counts to the console:
```
[TOKENS] translator   | model=granite4.1:8b | input=245 | output=48 | total=293
[TOKENS] chat_model   | provider=groq | model=llama-3.3-70b-versatile | input=375 | output=175 | total=550
```

Supports both Groq format (`response_metadata.token_usage`) and Ollama format (`prompt_eval_count`/`eval_count`).

No separate router LLM — tool selection is handled directly by the worker.

### 5. Unsupported Query Guard

Queries for tools not enabled in this version should not trigger random API calls.

For example, a sales invoice query should not call `get_customer` just because it contains the word `customer`.

---

## Tech Stack

- Python
- FastAPI
- LangGraph
- LangChain
- Ollama (translator + embeddings)
- Groq (worker via `llama-3.3-70b-versatile`)
- Worker LLM: `llama-3.3-70b-versatile` (via Groq API — JSON text tool-calling)
- Translator LLM: `granite4.1:8b` (via Ollama — Hinglish→English)
- Embedding model: `bge-m3`
- Backend ERP API

---

## Project Structure

```text
CHAPTER1-ASSIST/
│
├── fast_main.py          # FastAPI entry point
├── main.py               # Local testing entry point, if used
├── requirements.txt      # Python dependencies
├── langgraph.json        # LangGraph config, if used
│
├── src/
│   ├── config.py         # Runtime configuration
│   ├── api_client.py     # Backend API client
│   ├── tools_api.py      # API-backed ERP tool functions
│   ├── tools.py          # LangChain tool definitions
│   ├── tool_doc.py       # Tool descriptions and routing docs
│   ├── schema.py         # State/schema definitions
│   ├── retriever.py      # Tool retriever logic
│   ├── vector_store.py   # Vector store handling
│   ├── nodes.py          # LangGraph nodes and deterministic final response logic
│   └── graph.py          # LangGraph graph builder
│
└── README.md
```

---

## Environment Variables

Create a `.env` file or export environment variables before running the project.

```env
CHP1_API_BASE_URL=https://dev.chapter1.finance/aiAnalytics/
COMPANY_ID=355
CHP1_API_TOKEN=your_api_token_here
GROQ_API_KEY=your_groq_api_key_here
WORKER_LLM=llama-3.3-70b-versatile
TRANSLATOR_LLM=granite4.1:8b
EMBED_MODEL=bge-m3
```

Do not hardcode private API tokens before pushing to GitHub.

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

If needed, pull models:

```bash
ollama pull granite4.1:8b
ollama pull bge-m3
```

You also need a [Groq API key](https://console.groq.com) set as `GROQ_API_KEY` in `.env`.

---

## Run the FastAPI Server

```bash
python fast_main.py
```

Server should start at:

```text
http://127.0.0.1:8000
```

---

## API Usage

Endpoint:

```text
POST /chat
```

Example request:

```json
{
  "query": "Nykaa Bangalore customer id batao aur HSN 48211090 ka product name, HSN and closing quantity dikhao"
}
```

Example response:

```json
{
  "response": {
    "success": true,
    "status": "success",
    "query": "Nykaa Bangalore customer id batao aur HSN 48211090 ka product name, HSN and closing quantity dikhao",
    "tools_used": [
      "get_customer",
      "get_stock_levels"
    ],
    "data": {
      "get_customer": [
        {
          "id": 814,
          "name": "NYKAA E- RETAIL PRIVATE LIMITED BANGALORE"
        }
      ],
      "get_stock_levels": [
        {
          "name": "Office Products 48211090 @ 18",
          "hsnCode": "48211090",
          "closingQty": -43
        }
      ]
    },
    "summary": "get_customer: found 1 record; get_stock_levels: found 1 record",
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

### Customer Ledger

```json
{
  "query": "Customer id 814 ka opening, current and closing balance bata from 2024-04-01 to 2024-12-31"
}
```

### Ledger Transactions

```json
{
  "query": "Customer id 814 ka ledger opening, current, closing balance and transactions dikhao from 2024-04-01 to 2024-12-31"
}
```

### Stock by HSN

```json
{
  "query": "Show stock levels for HSN 48211090"
}
```

### GST B2B + Grand Total

```json
{
  "query": "Show B2B GST taxable amount, IGST, CGST, SGST and invoice amount, also show grand total GST from 2024-04-01 to 2024-04-30"
}
```

### TDS + TCS Outstanding

```json
{
  "query": "Show TDS outstanding and TCS outstanding from 2024-04-01 to 2024-12-31"
}
```

### Multi-tool Query

```json
{
  "query": "Nykaa Bangalore customer id batao, HSN 48211090 ka stock name and closing quantity dikhao, aur B2B GST taxable amount and invoice amount dikhao from 2024-04-01 to 2024-04-30"
}
```

### Unsupported Query

```json
{
  "query": "Show sales invoice A/0326/C0077 customer and amount"
}
```

---

## Known Stable Behaviors

Version 4 has been tested for:

- Customer lookup by brand + city
- Ledger lookup by customer ID
- HSN stock lookup
- Customer + stock multi-tool query
- GST B2B + grand total filtering
- Ledger transaction compaction
- TDS + TCS combined query
- Unsupported sales invoice query guard

---

## Example Successful Results

### Customer Lookup

```json
{
  "id": 814,
  "name": "NYKAA E- RETAIL PRIVATE LIMITED BANGALORE",
  "openingBalance": "0"
}
```

### Ledger Balance

```json
{
  "opening": -26838.61,
  "current": -29938.32,
  "closing": -56776.93
}
```

### Stock by HSN

```json
{
  "name": "Office Products 48211090 @ 18",
  "hsnCode": "48211090",
  "closingQty": -43
}
```

### GST B2B + Grand Total

```json
[
  {
    "category": "b2b",
    "name": "B2B Invoices (Registered)",
    "taxableAmount": 246261.38,
    "igst": 44327.27,
    "cgst": 22163.54,
    "sgst": 22163.54,
    "invoiceAmount": 290587.84
  },
  {
    "category": "grandTotal",
    "name": "Grand Total",
    "taxableAmount": 276633.43,
    "igst": 49794.27,
    "cgst": 24896.65,
    "sgst": 24896.65,
    "invoiceAmount": 326426.71
  }
]
```

---

## Performance Notes

Typical local timings observed during testing:

| Query Type | Approx Time |
|---|---:|
| Customer lookup | 1.2s - 1.5s |
| Ledger balance | 1.3s - 1.5s |
| Stock HSN lookup | 1.2s - 1.4s |
| GST summary | 2.0s - 2.3s |
| TDS + TCS | 1.7s - 2.0s |
| Unsupported query | under 0.1s |

Backend API latency may vary. Cached API responses are faster.

---

## Security Notes

Before pushing to GitHub, check that secrets are not hardcoded:

```bash
grep -R "Authorization\|API_TOKEN\|SECRET\|KEY" .
```

Do not commit:

```text
.env
venv/
__pycache__/
.langgraph_api/
```

Recommended `.gitignore` entries:

```gitignore
venv/
__pycache__/
*.pyc
.env
.langgraph_api/
.DS_Store
```

---

## Git Push Commands

```bash
git status
git add README.md src/config.py src/tool_doc.py src/nodes.py
git commit -m "Release CHapter1-assist version 4"
git push origin <your-branch-name>
```

---

## Future Improvements

Planned improvements:

- Add sales invoice tool
- Add purchase invoice tool
- Add receipt/payment voucher tools
- Add better section-wise TDS/TCS filtering
- Add stronger test suite
- Add proper `.env` support for all secrets
- Add request/response logging controls
- Add optional fully deterministic data node for known ERP intents
- Add invoice-level tools (get_sales_invoice, get_purchase_invoice) and handle doc_type splitting

---

## License

This project is currently intended as a prototype/portfolio ERP assistant. Add a license file before public distribution if required.
