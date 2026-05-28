from langchain_core.documents import Document

# ============================================================
# SIMPLE 6-TOOL REGISTRY
# This is routing/tool metadata only. It does NOT contain business data.
# Business data always comes from the Chapter-1 API.
# ============================================================

TOOL_INTENT_REGISTRY = {
    "get_customer": {
        "category": "customer",
        "description": "Search customers or parties and return id, name, opening balance and opening type.",
        "aliases": [
            "customer", "customers", "party", "parties", "client", "buyer", "grahak",
        ],
        "keywords": [
            "customer id", "party id", "customer name", "party name",
            "opening balance", "opening type", "find customer", "search customer",
        ],
        "fields": ["id", "name", "openingBalance", "openingType"],
        "field_aliases": {
            "id": ["customer id", "party id", "id"],
            "name": ["name", "customer name", "party name"],
            "openingBalance": ["opening balance", "opening"],
            "openingType": ["opening type"],
        },
    },

    "get_customer_ledger": {
        "category": "customer_ledger",
        "description": "Fetch customer ledger or account statement by customer_id; returns opening, current, closing balance and transactions.",
        "aliases": [
            "ledger", "account statement", "statement", "khata", "hisab",
        ],
        "keywords": [
            "customer ledger", "ledger balance", "closing balance", "current balance",
            "opening balance", "transactions", "transaction", "entries", "debit", "credit",
        ],
        "fields": [
            "ledgerName", "glName", "opening", "current", "closing", "period",
            "total_rows", "total_pages", "transactions",
        ],
        "field_aliases": {
            "ledgerName": ["ledger name"],
            "glName": ["gl name"],
            "opening": ["opening", "opening balance"],
            "current": ["current", "current balance"],
            "closing": ["closing", "closing balance"],
            "period": ["period", "from", "to"],
            "transactions": ["transaction", "transactions", "statement", "entry", "entries"],
        },
    },

    "get_stock_levels": {
        "category": "stock",
        "description": "Fetch stock and inventory levels using product name, SKU or HSN; returns closing quantity/value, low stock and out-of-stock details.",
        "aliases": [
            "stock", "inventory", "product", "products", "item", "items",
            "maal", "jaththo", "satha",
        ],
        "keywords": [
            "hsn", "hsn code", "sku", "closing quantity", "closing qty",
            "closing stock", "closing value", "closing rate", "low stock", "out of stock",
        ],
        "fields": [
            "id", "name", "sku", "hsnCode", "group", "uom", "openingQty", "openingRate",
            "openingValue", "inwardQty", "inwardValue", "outwardQty", "outwardValue",
            "closingQty", "closingRate", "closingValue", "isLowStock", "isOutOfStock",
        ],
        "field_aliases": {
            "name": ["name", "product name", "item name"],
            "sku": ["sku"],
            "hsnCode": ["hsn", "hsn code"],
            "closingQty": ["closing quantity", "closing qty", "quantity", "qty", "closing stock"],
            "closingValue": ["closing value", "value"],
            "closingRate": ["closing rate", "rate"],
            "isLowStock": ["low stock"],
            "isOutOfStock": ["out of stock"],
        },
    },

    "get_gst_summary": {
        "category": "gst_report",
        "description": "Fetch GST summary/report by date range; supports B2B, B2C, exports, nil/exempt, credit notes and grand total rows.",
        "aliases": ["gst", "gstr", "gst summary", "gst report"],
        "keywords": [
            "b2b", "b2c", "b2c large", "b2c small", "exports", "export",
            "nil rated", "exempt", "igst", "cgst", "sgst", "cess",
            "taxable amount", "invoice amount", "voucher count", "grand total", "total gst",
        ],
        "fields": [
            "category", "name", "voucherCount", "taxableAmount", "igst", "cgst",
            "sgst", "cess", "tax", "invoiceAmount",
        ],
        "field_aliases": {
            "category": ["category", "b2b", "b2c", "exports", "nil", "grand total"],
            "name": ["name"],
            "voucherCount": ["voucher count", "voucher"],
            "taxableAmount": ["taxable amount", "taxable"],
            "igst": ["igst"],
            "cgst": ["cgst"],
            "sgst": ["sgst"],
            "cess": ["cess"],
            "tax": ["total tax", "tax"],
            "invoiceAmount": ["invoice amount"],
        },
    },

    "get_tds_outstanding": {
        "category": "tds_report",
        "description": "Fetch TDS outstanding/payable report by date range; supports section filters like 194C, 194J and 194I.",
        "aliases": ["tds", "tds outstanding", "tds payable", "tds report"],
        "keywords": ["tds", "outstanding", "payable", "pending", "section", "194c", "194j", "194i"],
        "fields": [
            "recordType", "name", "section", "amount", "outstanding",
            "totalAmount", "totalOutstanding", "total_rows", "total_pages", "period",
        ],
        "field_aliases": {
            "section": ["section", "194c", "194j", "194i"],
            "amount": ["amount", "total amount"],
            "outstanding": ["outstanding", "pending", "payable", "total outstanding"],
            "period": ["period", "from", "to"],
        },
    },

    "get_tcs_outstanding": {
        "category": "tcs_report",
        "description": "Fetch TCS outstanding/payable report by date range; supports section filters like 206C.",
        "aliases": ["tcs", "tcs outstanding", "tcs payable", "tcs report"],
        "keywords": ["tcs", "outstanding", "payable", "pending", "section", "206c"],
        "fields": [
            "recordType", "name", "section", "amount", "outstanding",
            "totalAmount", "totalOutstanding", "total_rows", "total_pages", "period",
        ],
        "field_aliases": {
            "section": ["section", "206c"],
            "amount": ["amount", "total amount"],
            "outstanding": ["outstanding", "pending", "payable", "total outstanding"],
            "period": ["period", "from", "to"],
        },
    },
}


TOOL_DOCUMENTS = []

for tool_name, meta in TOOL_INTENT_REGISTRY.items():
    TOOL_DOCUMENTS.append(
        Document(
            page_content=f"""
Tool: {tool_name}
Category: {meta.get('category', '')}
Description: {meta.get('description', '')}
Aliases: {', '.join(meta.get('aliases', []))}
Keywords: {', '.join(meta.get('keywords', []))}
Fields: {', '.join(meta.get('fields', []))}
""".strip(),
            metadata={
                "tool_name": tool_name,
                "category": meta.get("category", ""),
            },
        )
    )