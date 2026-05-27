from langchain_core.documents import Document


TOOL_DOCUMENTS = [

    Document(
        page_content="""
        Tool: get_purchase_list

        Use this tool to fetch purchase records from the ERP purchaseList API.

        Supported arguments:
        - page
        - limit
        - term
        - ledger_id
        - from_date
        - to_date

        Use term for supplier name, purchase invoice number, reference number,
        keyword search, GST keyword, or general purchase search.

        Use this tool for purchase invoices, supplier bills, vendor bills,
        purchase amounts, purchase dates, outstanding purchases, purchase GST,
        and purchase records.
        """,
        metadata={
            "tool_name": "get_purchase_list",
            "category": "purchase",
            "data_source": "erp_api.purchaseList",
        },
    ),

    Document(
        page_content="""
        Tool: get_sales_list

        Use this tool to fetch sales records from the ERP salesList API.

        Supported arguments:
        - page
        - limit
        - term
        - ledger_id
        - from_date
        - to_date

        Use term for customer name, sales invoice number, reference number,
        keyword search, GST keyword, or general sales search.

        Use this tool for sales invoices, customer bills, sale bills,
        sales amounts, sales dates, outstanding sales, sales GST,
        and sales records.
        """,
        metadata={
            "tool_name": "get_sales_list",
            "category": "sales",
            "data_source": "erp_api.salesList",
        },
    ),

    Document(
        page_content="""
        Tool: get_product_list

        Use this tool to fetch products from the ERP productList API.

        Supported arguments:
        - page
        - limit
        - term

        Use term for product name, item name, SKU, HSN, GST keyword,
        inventory keyword, or general product search.

        Use this tool for products, inventory, item master, stock,
        SKU, HSN, GST rates, closing quantity, and product details.
        """,
        metadata={
            "tool_name": "get_product_list",
            "category": "inventory",
            "data_source": "erp_api.productList",
        },
    ),
]

TOOL_INTENT_REGISTRY = {
    "get_sales_list": {
        "category": "invoice",
        "domain": "sales",
        "description": "Fetch sales invoices, sales bills, customer bills, sold items, customer amount, outstanding, status, GST and sales invoice details.",
        "aliases": [
            "sales invoice",
            "sale invoice",
            "sales bill",
            "sale bill",
            "customer bill",
            "customer invoice",
            "sold",
            "sell",
            "selling",
            "bikri",
            "customer",
            "customers",
            "grahak",
            "khareedaar",
            "party sold to",
        ],
        "field_aliases": {
            "invoiceNo": ["invoice number", "bill number", "bill no", "invoice no"],
            "billToName": ["customer", "customer name", "party", "grahak", "khareedaar"],
            "netAmount": ["amount", "net amount", "total", "rakam", "paisa"],
            "outstanding": ["pending", "baki", "baqaya", "due", "outstanding"],
            "status": ["status", "stithi", "sthiti", "paid", "unpaid"],
            "invoiceDate": ["date", "bill date", "invoice date"],
            "taxableAmount": ["taxable", "taxable amount"],
            "igstAmount": ["igst"],
            "cgstAmount": ["cgst"],
            "sgstAmount": ["sgst"],
        },
        "default_fields": ["invoiceNo", "billToName", "netAmount", "status"],
    },

    "get_purchase_list": {
        "category": "invoice",
        "domain": "purchase",
        "description": "Fetch purchase invoices, purchase bills, vendor bills, supplier bills, purchase amount, outstanding, status, GST and purchase invoice details.",
        "aliases": [
            "purchase invoice",
            "purchase bill",
            "vendor bill",
            "supplier bill",
            "bought",
            "buy",
            "purchase",
            "purchased",
            "kharidi",
            "khareedi",
            "kharid",
            "vendor",
            "vendors",
            "supplier",
            "suppliers",
            "vikreta",
            "aapurti",
            "jinse kharidi",
        ],
        "field_aliases": {
            "invoiceNo": ["invoice number", "bill number", "bill no", "invoice no"],
            "billToName": ["vendor", "vendor name", "supplier", "supplier name", "vikreta", "aapurti karta"],
            "netAmount": ["amount", "net amount", "total", "rakam", "paisa", "kul rakam"],
            "outstanding": ["pending", "baki", "baqaya", "due", "outstanding"],
            "status": ["status", "stithi", "sthiti", "paid", "unpaid"],
            "invoiceDate": ["date", "bill date", "invoice date"],
            "taxableAmount": ["taxable", "taxable amount"],
            "igstAmount": ["igst"],
            "cgstAmount": ["cgst"],
            "sgstAmount": ["sgst"],
        },
        "default_fields": ["invoiceNo", "billToName", "netAmount"],
    },

    "get_product_list": {
        "category": "inventory",
        "domain": "product",
        "description": "Fetch products, items, goods, inventory, stock, HSN, GST rate, closing quantity and product details.",
        "aliases": [
            "product",
            "products",
            "item",
            "items",
            "goods",
            "maal",
            "saman",
            "inventory",
            "stock",
            "closing stock",
            "negative stock",
            "minus stock",
            "hsn",
            "gst rate",
            "tax rate",
        ],
        "field_aliases": {
            "name": ["product name", "item name", "goods name", "naam"],
            "sku": ["sku", "code"],
            "hsn": ["hsn", "hsn code"],
            "closingQty": ["stock", "quantity", "qty", "closing quantity", "matra", "bacha hua stock"],
            "closingRate": ["rate", "closing rate"],
            "igst": ["igst", "gst"],
            "cgst": ["cgst"],
            "sgst": ["sgst"],
        },
        "default_fields": ["name", "sku", "hsn"],
    },
}