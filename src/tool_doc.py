from langchain_core.documents import Document

tool_docs = [
    Document(
        page_content="""
        Tool: get_purchase_info

        Use this tool when the user asks about purchase information,
        purchase invoice, supplier, purchase date, purchase quantity,
        purchase amount, bill-to details, ship-to details, or purchased items.

        Example queries:
        - Show purchase details
        - What is purchase invoice PR-5?
        - Who was the purchase bill to?
        - Show purchased items
        """,
        metadata={"tool_name": "get_purchase_info"},
    ),

    Document(
        page_content="""
        Tool: get_sale_info

        Use this tool when the user asks about sales information,
        sale invoice, customer, buyer, sale amount, taxable amount,
        GST in sales, outstanding amount, bill-to details, ship-to details,
        or sold items.

        Example queries:
        - Show sales details
        - Who bought the item?
        - What is invoice SL-3?
        - What is the sale outstanding amount?
        """,
        metadata={"tool_name": "get_sale_info"},
    ),

    Document(
        page_content="""
        Tool: get_payment

        Use this tool when the user asks about payments made,
        payment voucher, payment amount, payment mode, online payment,
        account payment, particular person, payment date, or payment reference.

        Example queries:
        - Show payment details
        - What payments were made?
        - Show payment voucher PT-2
        - What is the payment mode?
        """,
        metadata={"tool_name": "get_payment"},
    ),

    Document(
        page_content="""
        Tool: get_receipt

        Use this tool when the user asks about receipts,
        received amount, receipt voucher, cash receipt, receipt date,
        reference number, money received, or receipt attachment.

        Example queries:
        - Show receipt details
        - What amount was received?
        - Show receipt SO-15
        - Which receipt was paid by cash?
        """,
        metadata={"tool_name": "get_receipt"},
    ),

    Document(
        page_content="""
        Tool: get_sale_return

        Use this tool when the user asks about sale return,
        credit note, returned sale invoice, returned item,
        return amount, customer return, due date, or sale return bill details.

        Example queries:
        - Show sale return details
        - Was any sale returned?
        - Show credit note CT-2
        - What is the sale return amount?
        """,
        metadata={"tool_name": "get_sale_return"},
    ),

    Document(
        page_content="""
        Tool: get_hsn

        Use this tool when the user asks about HSN code,
        GST rate, IGST, CGST, SGST, tax percentage, tax category,
        or product tax classification.

        Example queries:
        - What is the HSN code?
        - Show GST rate
        - What is IGST CGST SGST?
        - Show tax details
        """,
        metadata={"tool_name": "get_hsn"},
    ),

    Document(
        page_content="""
        Tool: get_bill_term

        Use this tool when the user asks about bill terms,
        invoice terms, payment terms, credit period, due days,
        terms and conditions, or billing condition.

        Example queries:
        - Show bill terms
        - What are the payment terms?
        - What is the credit period?
        - Show invoice terms
        """,
        metadata={"tool_name": "get_bill_term"},
    ),
]