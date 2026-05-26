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
# TOOL_DOCUMENTS = [

#     Document(
#         page_content="""
#         Tool: get_purchase_list

#         Category: purchase, purchase invoice, supplier purchase, vendor bill

#         Use this tool when the user asks about purchase information,
#         purchase invoices, purchase bills, supplier bills, vendor bills,
#         bought items, purchase date, purchase invoice number, reference number,
#         supplier name, bill-to party, ship-to party, bill-to state, bill-to city,
#         GST number, taxable amount, IGST amount, CGST amount, SGST amount,
#         cess amount, discount, round off, net amount, outstanding amount,
#         taxability, purchase status, or purchase records.

#         Important fields this tool can return:
#         id, invoiceType, voucherId, invoiceNo, invoiceDate, referenceNo,
#         billToName, billToAddress, billToCountry, billToState, billToCity,
#         billToPincode, billTogstNumber, shipToName, shipToAddress,
#         shipToCountry, shipToState, shipToCity, shipToPincode,
#         shipTogstNumber, currencyCode, taxableAmount, igstAmount,
#         cgstAmount, sgstAmount, cessAmount, discountAmount,
#         roundOffAmount, netAmount, outstanding, taxability, status,
#         createAt, updateAt.

#         Match this tool for words like:
#         purchase, purchases, purchase invoice, purchase bill, supplier,
#         vendor, bought, purchase amount, purchase date, PR invoice,
#         bill to, ship to, GST number, taxable amount, net amount,
#         outstanding purchase, purchase tax, purchase GST.

#         Example queries:
#         - Show purchase invoices
#         - Show purchase details
#         - Find purchase invoice PR-32
#         - Show purchases from Amazon Seller Services
#         - Show purchase invoices from Maharashtra
#         - Show purchase bills where bill-to state is Karnataka
#         - Show purchase taxable amount and GST
#         - Show purchase invoice net amount
#         - Show outstanding purchase invoices
#         - Get bill-to and ship-to details for purchase invoice PR-23
#         """,
#         metadata={
#             "tool_name": "get_purchase_list",
#             "category": "purchase",
#             "data_source": "purchase_data",
#         },
#     ),

#     Document(
#         page_content="""
#         Tool: get_sales_list

#         Category: sales, sales invoice, customer invoice, sale bill

#         Use this tool when the user asks about sales information,
#         sales invoices, sale bills, customer invoices, sold items,
#         sales date, sales invoice number, customer name, bill-to customer,
#         ship-to customer, bill-to state, bill-to city, customer GST number,
#         taxable amount, IGST amount, CGST amount, SGST amount,
#         cess amount, discount, round off, net amount, outstanding amount,
#         e-way bill, e-invoice, share link, taxability, sales status,
#         or sales records.

#         Important fields this tool can return:
#         id, invoiceType, voucherId, invoiceNo, invoiceDate, narration,
#         billToName, billToAddress, billToCountry, billToState, billToCity,
#         billToPincode, billTogstNumber, shipToName, shipToAddress,
#         shipToCountry, shipToState, shipToCity, shipToPincode,
#         shipTogstNumber, currencyCode, taxableAmount, igstAmount,
#         cgstAmount, sgstAmount, cessAmount, discountAmount,
#         roundOffAmount, netAmount, outstanding, taxability, eWayBill,
#         eInvoice, shareLink, status, createAt, updateAt.

#         Match this tool for words like:
#         sale, sales, sales invoice, sale bill, customer invoice,
#         customer, sold, invoice amount, sales date, bill to customer,
#         ship to customer, customer state, customer city, sales GST,
#         taxable amount, net amount, outstanding sales, e invoice,
#         e-way bill.

#         Example queries:
#         - Show sales invoices
#         - Show sales details
#         - Find sales invoice A/0326/C0077
#         - Show sales for B2CMAHARASHTRA
#         - Show sales invoices from Gujarat
#         - Show sales where bill-to state is Maharashtra
#         - Show sales taxable amount and GST
#         - Show sales invoice net amount
#         - Show outstanding sales invoices
#         - Get e-invoice details for a sales invoice
#         """,
#         metadata={
#             "tool_name": "get_sales_list",
#             "category": "sales",
#             "data_source": "sales_data",
#         },
#     ),

#     Document(
#         page_content="""
#         Tool: get_products_list

#         Category: inventory, product list, stock, item master

#         Use this tool when the user asks about inventory information,
#         product list, item list, stock details, item details, product details,
#         item name, product name, SKU, UOM, unit of measurement,
#         alternate UOM, HSN code, GST rate, IGST, CGST, SGST,
#         cess, closing rate, closing quantity, closing stock,
#         current stock, negative stock, product rate, or item tax details.

#         Important fields this tool can return:
#         id, name, group, sku, uom, altUom, hsn, igst, cgst,
#         sgst, cess, closingRate, closingQty.

#         Match this tool for words like:
#         inventory, product, products, item, items, stock, goods,
#         material, product list, item list, SKU, UOM, unit, HSN,
#         GST, IGST, CGST, SGST, cess, closing quantity, closing qty,
#         current stock, negative stock, closing rate, product rate,
#         item rate.

#         Example queries:
#         - Show inventory items
#         - Show product list
#         - Show stock details
#         - Find product BIC pen
#         - Find item ASA CX 3 Flight Computer
#         - Show items with HSN 48211090
#         - Show GST details for Books
#         - Show IGST CGST SGST for an item
#         - Show products with negative stock
#         - Show products where closing quantity is less than 0
#         - Show item name, HSN and closing quantity
#         - Show closing rate of BIC Cristal pen
#         """,
#         metadata={
#             "tool_name": "get_products_list",
#             "category": "inventory",
#             "data_source": "prod_list",
#         },
#     ),
# ]