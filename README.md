# Chapter1 AI Assistant

An asynchronous **ERP & Accounting AI Assistant** built with **LangGraph**, **LangChain**, **FastAPI**, **NVIDIA AI Endpoints**, and **ChromaDB**.

The assistant understands ERP/accounting queries, breaks multi-intent questions into smaller semantic parts, retrieves relevant ERP tools, binds only those tools to the LLM, executes tool calls, and returns a structured **dynamic JSON response** suitable for API/frontend usage.

---

## Features

- **LangGraph workflow** for structured agent execution
- **FastAPI backend** with a `/chat` endpoint
- **Dynamic JSON API responses** instead of markdown text
- **Semantic tool retrieval** using ChromaDB vector search
- **Multi-intent query decomposition** before semantic retrieval
- **Dynamic tool binding** so the LLM only receives relevant tools
- **Few-shot worker prompt** for better multi-tool calling and filtering
- **Strict filtering rules** to avoid returning unrelated ERP records
- **Async execution** using `async` / `await`
- **Supervisor routing node** to decide whether to finish, retry, or call tools
- **ToolNode integration** for executing LangChain tools
- **NVIDIA ChatNVIDIA model** for reasoning and tool calling
- **NVIDIA embeddings** for tool-card vector search
- **Dummy ERP dataset** for purchases, sales, payments, receipts, sale returns, GST/HSN, and bill terms
- Supports **multi-intent ERP queries**, including mixed English, Hindi, and Gujarati-style prompts

---

## Project Idea

This project acts like an ERP assistant that can answer questions such as:

- Show purchase details for a supplier
- Find sales invoices from a city
- Show payments made through online mode
- Get receipt vouchers paid by cash
- Check sale returns for a customer
- Find HSN, GST, CGST, SGST, and IGST details
- Show bill/payment terms
- Answer multiple ERP questions in a single query

Instead of giving all tools to the LLM every time, the system first retrieves relevant tools from ChromaDB and binds only those tools to the model.

---

## Updated Architecture

```text
User / Postman / Frontend
   |
   v
FastAPI /chat endpoint
   |
   v
Initial LangGraph State
   |
   v
Semantic Search Node
   |  - Splits multi-intent query into smaller parts
   |  - Searches ChromaDB tool cards for each part
   |  - Returns relevant tool names
   v
Worker / Chatbot Node
   |  - Binds selected tools to the LLM
   |  - Uses few-shot prompt for tool calling + JSON output
   |  - Generates tool calls or final JSON response
   v
Supervisor Node
   |  - If tool calls exist -> route to Tools Node
   |  - If answer is complete -> END
   |  - If incomplete -> route back to Worker Node
   v
Tools Node
   |  - Executes selected ERP tools
   |  - Tools return JSON strings from dummy ERP data
   v
Worker Node
   |
   v
Structured Dynamic JSON Response
```

---

## Graph Flow

The LangGraph workflow contains these main nodes:

| Node | Purpose |
|---|---|
| `semantic_node` | Retrieves the most relevant tools based on the user query |
| `worker_node` | Binds retrieved tools to the LLM and generates tool calls or final JSON response |
| `tools_node` | Executes LangChain tools through `ToolNode` |
| `supervisor_node` | Routes between worker, tools, retry, and finish |

The flow is:

```text
START -> semantic_node -> worker_node -> supervisor_node
```

The supervisor decides:

```text
worker_node -> tools_node -> worker_node
worker_node -> END
worker_node -> worker_node
```

---

## Available Tools

| Tool Name | Purpose |
|---|---|
| `get_purchase_info` | Purchase invoices, supplier info, purchase amount, purchase items |
| `get_sale_info` | Sales invoices, customer info, sale amount, GST in sales, outstanding amount |
| `get_payment` | Payment vouchers, payment mode, paid amount, payment reference |
| `get_receipt` | Receipt vouchers, received amount, cash receipts, receipt attachments |
| `get_sale_return` | Sale returns, credit notes, returned invoices, returned items |
| `get_hsn` | HSN code, GST rate, IGST, CGST, SGST, tax classification |
| `get_bill_term` | Bill terms, payment terms, credit period, due days |

---

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- LangChain
- LangGraph
- LangGraph Prebuilt `ToolNode`
- LangChain Chroma
- ChromaDB
- NVIDIA AI Endpoints
- NVIDIA Embeddings
- Pydantic
- python-dotenv

---

## Folder Structure

Recommended structure:

```text
chapter1_assist/
│
├── fast_main.py              # FastAPI backend
├── main.py                   # Optional terminal runner
├── .env
├── requirements.txt
├── README.md
│
├── chroma_db/                # Auto-created vector database
│
└── src/
    ├── __init__.py
    ├── config.py             # LLM and embedding model setup
    ├── dummy.py              # Dummy ERP/accounting data
    ├── graphs.py             # LangGraph builder
    ├── nodes.py              # Semantic search, chatbot, and supervisor nodes
    ├── retriever.py          # Multi-intent semantic tool retriever
    ├── schema.py             # TypedDict and Pydantic state schemas
    ├── tool.py               # LangChain tool definitions
    ├── tool_doc.py           # Tool cards used for semantic search
    └── vectorstore.py        # Chroma vector store setup
```

> Note: Make sure your local filenames match the imports. For example, use `fast_main.py`, `graphs.py`, `nodes.py`, and `schema.py` instead of files with names like `fast_main(2).py` or `graphs(2).py`.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/chapter1-assist.git
cd chapter1-assist
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If you do not have a `requirements.txt` yet, create one with:

```txt
fastapi
uvicorn
langchain
langchain-core
langchain-community
langchain-nvidia-ai-endpoints
langchain-chroma
langgraph
langgraph-prebuilt
chromadb
python-dotenv
pydantic
```

Install again:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
NVIDIA_API_KEY=your_nvidia_api_key_here
```

The project loads this key in `src/config.py` using `python-dotenv`.

---

## Model Configuration

The current configuration uses:

```python
llm = ChatNVIDIA(
    model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
    api_key=NVIDIA_API_KEY,
    max_tokens=4096
)
```

Embedding model:

```python
embedding_model = NVIDIAEmbeddings(
    model="nvidia/nv-embedqa-e5-v5",
    api_key=NVIDIA_API_KEY
)
```

Important: avoid calling `llm.invoke()` inside `config.py`. `config.py` should only create model and embedding objects. Test the model from a separate test file to avoid import-time crashes.

---

## How It Works

### 1. Tool cards are created

Each tool has a natural-language description stored as a LangChain `Document` in `tool_doc.py`.

Example:

```python
Document(
    page_content="""
    Tool: get_sale_info

    Use this tool when the user asks about sales information,
    sale invoice, customer, buyer, sale amount, taxable amount,
    GST in sales, outstanding amount, bill-to details, ship-to details,
    or sold items.
    """,
    metadata={"tool_name": "get_sale_info"},
)
```

### 2. ChromaDB stores the tool cards

`vectorstore.py` creates a vector store from the tool documents:

```python
vectore_store = Chroma.from_documents(
    documents=tool_docs,
    embedding=emb_model,
    persist_directory="./chroma_db",
    collection_name="tool_cards"
)
```

### 3. Retriever splits multi-intent queries

The retriever now breaks a query into smaller parts before semantic search.

Example query:

```text
Show sales invoices for Account, receipt vouchers with CASH mode, and bill terms for pen00001.
```

Detected parts:

```python
[
    "Show sales invoices for Account",
    "receipt vouchers with CASH mode",
    "bill terms for pen00001"
]
```

Each part is searched separately in ChromaDB. This improves multi-tool retrieval compared to searching the full query only once.

### 4. Worker node binds selected tools

The chatbot node receives retrieved tool names and binds only those tools:

```python
llm_with_tools = llm.bind_tools(tools_list)
```

If no tools are retrieved, the node safely falls back to the plain LLM:

```python
llm_with_tools = llm
```

### 5. Worker prompt uses few-shot examples

The worker prompt includes examples such as:

```text
User query: Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH.
Correct tools to call: get_sale_info, get_receipt
Final JSON data keys: sales_invoices, receipt_vouchers
```

This improves:

- multi-tool calling,
- exact filtering,
- dynamic JSON structure,
- and avoiding markdown responses.

### 6. Final output is dynamic JSON

The assistant returns structured JSON instead of markdown text.

General structure:

```json
{
  "response": {
    "success": true,
    "query": "original user query",
    "data": {
      "dynamic_section_name": []
    },
    "summary": "short factual summary"
  }
}
```

The keys inside `data` are dynamic and depend on the user query, such as:

```text
sales_invoices
receipt_vouchers
purchase_invoices
payment_vouchers
sale_returns
hsn_tax_details
bill_terms
totals
```

---

## Running the FastAPI Backend

Run:

```bash
python fast_main.py
```

Or:

```bash
uvicorn fast_main:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

Health check:

```text
GET http://127.0.0.1:8000/
```

Chat endpoint:

```text
POST http://127.0.0.1:8000/chat
```

---

## Testing with Postman

Use:

```text
POST http://127.0.0.1:8000/chat
```

Headers:

```text
Content-Type: application/json
```

Body → raw → JSON:

```json
{
  "query": "Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH."
}
```

Example response:

```json
{
  "response": {
    "success": true,
    "query": "Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH.",
    "data": {
      "sales_invoices": [
        {
          "invoice_no": "SL-3",
          "invoice_date": "2025-07-10",
          "customer_name": "Account",
          "city": "Silvassa",
          "net_amount": 1111
        }
      ],
      "receipt_vouchers": [
        {
          "invoice_no": "SO-12",
          "date": "2025-06-30",
          "amount": 20000,
          "reference_mode": "CASH"
        }
      ]
    },
    "summary": "Found matching sales invoices and receipt vouchers."
  }
}
```

---

## FastAPI Response Model

The API uses a dynamic response model:

```python
from typing import Any
from pydantic import BaseModel, Field

class DynamicERPResponse(BaseModel):
    success: bool = True
    query: str
    data: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None

class ChatResponse(BaseModel):
    response: DynamicERPResponse
```

Do not use this for the final JSON version:

```python
class ChatResponse(BaseModel):
    response: str
```

That will cause a validation error because the response is now a dictionary, not a string.

---

## Example Multi-Tool Queries

### 2-tool queries

```json
{
  "query": "Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH."
}
```

```json
{
  "query": "Get HSN code, GST rate, CGST and SGST for pen00001, and also show its bill term."
}
```

```json
{
  "query": "Show purchase invoices for Dddsdss and payment vouchers made to rohan."
}
```

### 3-tool queries

```json
{
  "query": "Show sales invoices for Account, receipt vouchers with CASH mode, and bill terms for pen00001."
}
```

```json
{
  "query": "Find sales invoices for rohan, receipt vouchers from rohan, and payment vouchers related to rohan."
}
```

### 4-tool queries

```json
{
  "query": "Show sale returns for Account, sales invoices for Account, receipt vouchers with CASH mode, and bill terms for pen00001."
}
```

```json
{
  "query": "Show purchase invoices for Dddsdss, sales invoices for Account, payment vouchers for rohan, and receipt vouchers with CASH mode."
}
```

### Stress test

```json
{
  "query": "Show purchase invoices for Dddsdss, sales invoices for Account, receipt vouchers with CASH mode, payment vouchers for rohan, HSN details for pen00001, and bill terms for pen00001."
}
```

### Hindi/Gujarati mixed queries

```json
{
  "query": "Account ke naam par jitni sales invoices hain wo dikhao, aur CASH mode ke receipt vouchers bhi show karo."
}
```

```json
{
  "query": "pen00001 ka HSN, GST, CGST, SGST dikhao aur uska bill term bhi batao."
}
```

```json
{
  "query": "Silvassa city na sales invoices batavo ane CASH mode na receipt vouchers pan show karo."
}
```

---

## Important Implementation Notes

### Dynamic tool binding

The project does not bind all tools every time. It retrieves relevant tools first, then binds those tools to the model.

This improves:

- tool selection accuracy,
- prompt efficiency,
- model focus,
- and multi-tool query handling.

### Multi-intent retrieval

The retriever splits long queries into smaller parts and searches each part separately.

This helps the assistant retrieve tools for queries such as:

```text
sales invoices + receipts + bill terms
```

instead of only retrieving the strongest single matching tool.

### Dynamic JSON output

The final answer is designed for APIs and frontends.

The worker prompt forces the final response to be:

- valid raw JSON,
- no markdown,
- no bullet points,
- no code fences,
- dynamic `data` keys,
- and strict filtering based on the user's query.

### Async-first design

The graph uses async execution:

```python
async for chunk in chatbot_graph.astream(
    initial_state,
    config=config,
    stream_mode="updates"
):
```

This makes the architecture easier to extend later with real APIs, databases, or external ERP services.

### Dummy data

Currently, all tools return data from `dummy.py`.

For production, replace the dummy data with:

- REST API calls,
- SQL database queries,
- ERP backend services,
- or authenticated business APIs.

---

## Common Issues

### 1. `422 Unprocessable Entity`

This usually means the Postman body is wrong.

Correct request body:

```json
{
  "query": "Show sales invoices for Account."
}
```

Make sure Postman uses:

```text
Body -> raw -> JSON
Content-Type: application/json
```

---

### 2. Pydantic validation error: response should be a string

If you see:

```text
Input should be a valid string
```

then your FastAPI response model is still:

```python
class ChatResponse(BaseModel):
    response: str
```

Change it to:

```python
class ChatResponse(BaseModel):
    response: DynamicERPResponse
```

---

### 3. NVIDIA `502 Bad Gateway`

This is usually an upstream NVIDIA endpoint/provider issue.

Avoid calling:

```python
llm.invoke("Hello")
```

inside `config.py`, because that can break app startup during imports.

Use a separate test file instead.

---

### 4. `ImportError: cannot import name 'embedding_model'`

This can happen if `config.py` fails before creating `embedding_model`.

Keep `config.py` simple:

```python
llm = ChatNVIDIA(...)
embedding_model = NVIDIAEmbeddings(...)
```

Do not make live model calls inside `config.py`.

---

### 5. ChromaDB not loading correctly

Delete the existing `chroma_db` folder and run the app again:

```bash
rm -rf chroma_db
python fast_main.py
```

The vector store will be recreated.

---

### 6. Tool is not selected correctly

Improve the descriptions in `tool_doc.py`. Semantic retrieval depends heavily on how clearly each tool card describes when that tool should be used.

For multi-intent queries, also check terminal logs:

```text
Query parts detected: [...]
Final retrieved tool names: [...]
```

---

### 7. Model returns markdown instead of JSON

Strengthen the worker prompt with:

```text
Return ONLY valid raw JSON.
Do not return markdown.
Do not wrap JSON inside ```json or ```.
```

Also parse the final output in FastAPI using `json.loads()`.

---

## Future Improvements

- Replace dummy ERP data with real database/API calls
- Add SQLite/Postgres checkpointing
- Add conversation memory and message summarization
- Add human-in-the-loop approval for sensitive operations
- Add authentication for ERP users
- Add role-based ERP access control
- Add Streamlit or React frontend
- Add unit tests for retriever, tools, and graph routing
- Add Docker support
- Add structured logging
- Add LangSmith tracing
- Add retry handling for temporary NVIDIA endpoint failures
- Move filtering from the LLM layer into the API/database layer for production reliability

---

## Learning Goals Covered

This project helps practice:

- LangGraph state management
- Conditional routing
- ToolNode execution
- LLM tool calling
- Semantic search
- ChromaDB vector stores
- FastAPI backend development
- Dynamic JSON API design
- NVIDIA LLM and embedding integration
- Async agent workflows
- Multi-tool retrieval
- Few-shot prompting
- ERP/accounting assistant design

---

## Disclaimer

This project currently uses dummy ERP/accounting data for learning and prototyping purposes. It is not intended for production financial decision-making without proper validation, authentication, logging, and real backend integration.

---

## Author

Built by **Yash Sheth** as a LangChain + LangGraph ERP assistant project.