# Chapter1 AI Assistant

An asynchronous **ERP & Accounting AI Assistant** built with **LangGraph**, **LangChain**, **NVIDIA AI Endpoints**, and **ChromaDB**.

The assistant understands a user's ERP/accounting query, semantically retrieves only the relevant tools, binds those tools to the LLM, executes the needed tool calls, and returns a concise answer based on structured ERP data.

---

## Features

- **LangGraph workflow** for structured agent execution
- **Semantic tool retrieval** using ChromaDB vector search
- **Dynamic tool binding** so the LLM only receives relevant tools
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

Instead of giving all tools to the LLM every time, the system first performs **semantic search over tool descriptions** and only binds the tools that match the user's query.

---

## Architecture

```text
User Query
   |
   v
Initial State
   |
   v
Semantic Search Node
   |  - Searches ChromaDB tool cards
   |  - Returns relevant tool names
   v
Worker / Chatbot Node
   |  - Binds selected tools to the LLM
   |  - Generates answer or tool calls
   v
Supervisor Node
   |  - If tool calls exist -> route to Tools Node
   |  - If answer is complete -> END
   |  - If incomplete -> route back to Worker Node
   v
Tools Node
   |  - Executes selected ERP tools
   v
Worker Node
   |
   v
Final Answer
```

---

## Graph Flow

The LangGraph workflow contains three main nodes:

| Node | Purpose |
|---|---|
| `semantic_node` | Retrieves the most relevant tools based on the user query |
| `worker_node` | Binds retrieved tools to the LLM and generates tool calls or final response |
| `tools_node` | Executes LangChain tools through `ToolNode` |

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
- LangChain
- LangGraph
- LangGraph Prebuilt `ToolNode`
- LangChain Chroma
- ChromaDB
- NVIDIA AI Endpoints
- Pydantic
- python-dotenv

---

## Folder Structure

Recommended structure for this project:

```text
chapter1_assist/
│
├── main.py
├── .env
├── requirements.txt
├── README.md
│
├── chroma_db/                 # Auto-created vector database
│
└── src/
    ├── __init__.py
    ├── config.py              # LLM and embedding model setup
    ├── dummy.py               # Dummy ERP/accounting data
    ├── graphs.py              # LangGraph builder
    ├── nodes.py               # Semantic search, chatbot, and supervisor nodes
    ├── retriever.py           # Semantic tool retriever
    ├── schema.py              # TypedDict and Pydantic state schemas
    ├── tool.py                # LangChain tool definitions
    ├── tool_doc.py            # Tool cards used for semantic search
    └── vectorstore.py         # Chroma vector store setup
```

> Note: Make sure your local filenames match the imports. For example, use `main.py`, `graphs.py`, `nodes.py`, and `schema.py` instead of files with names like `main(2).py` or `graphs(2).py`.

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

You can replace the model name with any supported NVIDIA AI Endpoint model that supports tool calling and instruction following.

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

### 3. Retriever selects tools

`retriever.py` performs async similarity search:

```python
retriver_tools = await vectore_store.asimilarity_search(query, k=k)
```

Then it maps matched tool cards back to actual LangChain tool objects.

### 4. Worker node binds only selected tools

The chatbot node gets the retrieved tool names and binds only those tools:

```python
llm_with_tools = llm.bind_tools(tools_list)
```

This keeps the LLM focused and reduces unnecessary tool confusion.

### 5. Supervisor controls routing

The supervisor checks whether:

- the model requested tool calls,
- the response is complete,
- the worker should retry,
- or the graph should end.

---

## Running the Project

Run the application:

```bash
python main.py
```

The current `main.py` contains a sample query:

```python
query = "ભાઈ, 'Silvassa' city na jetla bhee sales invoices chhe ae to batavo, and sath ma e bhee check karo ke 'ABC Ltd' na ketla sale return thaya chhe?"
```

You can replace it with your own query:

```python
query = "Show sales invoices from Silvassa and receipt vouchers paid by CASH."
```

---

## Example Queries

```text
What is the HSN code and GST rate for pen00001?
```

```text
Show me all sales invoices where the customer city is Silvassa.
```

```text
Have we made any payments to rohan through ONLINE mode?
```

```text
Show receipt vouchers where payment mode was CASH.
```

```text
Customer rohan ke naam par jitni bhi sales invoices hain wo dikhao aur receipts bhi check karo.
```

```text
Find all sale returns for ABC Ltd.
```

---

## Important Implementation Notes

### Dynamic tool binding

The project does not bind all tools every time. It retrieves only the most relevant tools first, then binds those tools to the model.

This improves:

- tool selection accuracy,
- prompt efficiency,
- model focus,
- and multi-tool query handling.

### Async-first design

The graph uses async execution:

```python
async for chunk in chatbot_graph.astream(initial_state, stream_mode="updates"):
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

### 1. `ModuleNotFoundError: No module named 'src'`

Make sure you run the project from the root directory:

```bash
cd chapter1_assist
python main.py
```

Also make sure `src/__init__.py` exists.

---

### 2. NVIDIA API key not found

Check that your `.env` file exists and contains:

```env
NVIDIA_API_KEY=your_key_here
```

---

### 3. ChromaDB not loading correctly

Delete the existing `chroma_db` folder and run the app again:

```bash
rm -rf chroma_db
python main.py
```

The vector store will be recreated.

---

### 4. Tool is not selected correctly

Improve the descriptions in `tool_doc.py`. Semantic retrieval depends heavily on how clearly each tool card describes when that tool should be used.

---

## Future Improvements

- Replace dummy ERP data with real database/API calls
- Add SQLite checkpointing with `AsyncSqliteSaver`
- Add conversation memory and message summarization
- Add human-in-the-loop approval for sensitive operations
- Add authentication for ERP users
- Add FastAPI backend
- Add Streamlit or React frontend
- Add unit tests for retriever, tools, and graph routing
- Add Docker support
- Add logging with structured traces
- Add LangSmith tracing

---

## Learning Goals Covered

This project helps practice:

- LangGraph state management
- Conditional routing
- ToolNode execution
- LLM tool calling
- Semantic search
- ChromaDB vector stores
- NVIDIA LLM and embedding integration
- Async agent workflows
- Multi-tool retrieval
- ERP/accounting assistant design

---

## Disclaimer

This project currently uses dummy ERP/accounting data for learning and prototyping purposes. It is not intended for production financial decision-making without proper validation, authentication, logging, and real backend integration.

---

## Author

Built by **Yash Sheth** as a LangChain + LangGraph ERP assistant project.
