from langchain.tools import tool
from src.dummy import prod_list, purchase_data, sales_data
import json
from typing import Optional, Any


def to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def text_match(value: Any, query: Optional[str]) -> bool:
    if not query:
        return True
    if value is None:
        return False
    return query.lower() in str(value).lower()


def exact_text_match(value: Any, query: Optional[str]) -> bool:
    if not query:
        return True
    if value is None:
        return False
    return str(value).strip().lower() == query.strip().lower()


def compact_invoice(record: dict) -> dict:
    return {
        "invoiceNo": record.get("invoiceNo"),
        "invoiceDate": record.get("invoiceDate"),
        "billToName": record.get("billToName"),
        "billToState": record.get("billToState"),
        "billToCity": record.get("billToCity"),
        "shipToName": record.get("shipToName"),
        "shipToState": record.get("shipToState"),
        "taxableAmount": record.get("taxableAmount"),
        "igstAmount": record.get("igstAmount"),
        "cgstAmount": record.get("cgstAmount"),
        "sgstAmount": record.get("sgstAmount"),
        "netAmount": record.get("netAmount"),
        "outstanding": record.get("outstanding"),
        "status": record.get("status"),
    }


def compact_product(record: dict) -> dict:
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "sku": record.get("sku"),
        "uom": record.get("uom"),
        "hsn": record.get("hsn"),
        "igst": record.get("igst"),
        "cgst": record.get("cgst"),
        "sgst": record.get("sgst"),
        "closingRate": record.get("closingRate"),
        "closingQty": record.get("closingQty"),
    }


@tool
def get_products_list(
    negative_stock: bool = False,
    positive_stock: bool = False,
    zero_stock: bool = False,
    product_name: Optional[str] = None,
    hsn: Optional[str] = None
):
    """
    Get filtered product/inventory records.

    Use negative_stock=True for products where closingQty < 0.
    Use positive_stock=True for products where closingQty > 0.
    Use zero_stock=True for products where closingQty == 0.
    Use product_name to filter by product/item name.
    Use hsn to filter by HSN code.
    """

    records = prod_list.get("data", []) if isinstance(prod_list, dict) else prod_list

    filtered = []

    for record in records:
        closing_qty = to_float(record.get("closingQty"))

        if negative_stock and not closing_qty < 0:
            continue

        if positive_stock and not closing_qty > 0:
            continue

        if zero_stock and not closing_qty == 0:
            continue

        if product_name and not text_match(record.get("name"), product_name):
            continue

        if hsn and not exact_text_match(record.get("hsn"), hsn):
            continue

        filtered.append(compact_product(record))

    return json.dumps(filtered)


@tool
def get_purchase_list(
    state: Optional[str] = None,
    invoice_no: Optional[str] = None,
    party_name: Optional[str] = None,
    outstanding_only: bool = False
):
    """
    Get filtered purchase invoice records.

    Use state to filter billToState or shipToState.
    Use invoice_no to filter exact purchase invoice number.
    Use party_name to filter supplier/vendor/billToName/shipToName.
    Use outstanding_only=True for purchase invoices where outstanding > 0.
    """

    records = purchase_data.get("data", []) if isinstance(purchase_data, dict) else purchase_data

    filtered = []

    for record in records:
        if state:
            bill_state = record.get("billToState")
            ship_state = record.get("shipToState")

            if not (
                exact_text_match(bill_state, state)
                or exact_text_match(ship_state, state)
            ):
                continue

        if invoice_no and not exact_text_match(record.get("invoiceNo"), invoice_no):
            continue

        if party_name:
            if not (
                text_match(record.get("billToName"), party_name)
                or text_match(record.get("shipToName"), party_name)
            ):
                continue

        if outstanding_only and not to_float(record.get("outstanding")) > 0:
            continue

        filtered.append(compact_invoice(record))

    return json.dumps(filtered)


@tool
def get_sales_list(
    state: Optional[str] = None,
    invoice_no: Optional[str] = None,
    party_name: Optional[str] = None,
    outstanding_only: bool = False
):
    """
    Get filtered sales invoice records.

    Use state to filter billToState or shipToState.
    Use invoice_no to filter exact sales invoice number.
    Use party_name to filter customer/billToName/shipToName.
    Use outstanding_only=True for sales invoices where outstanding > 0.
    """

    records = sales_data.get("data", []) if isinstance(sales_data, dict) else sales_data

    filtered = []

    for record in records:
        if state:
            bill_state = record.get("billToState")
            ship_state = record.get("shipToState")

            if not (
                exact_text_match(bill_state, state)
                or exact_text_match(ship_state, state)
            ):
                continue

        if invoice_no and not exact_text_match(record.get("invoiceNo"), invoice_no):
            continue

        if party_name:
            if not (
                text_match(record.get("billToName"), party_name)
                or text_match(record.get("shipToName"), party_name)
            ):
                continue

        if outstanding_only and not to_float(record.get("outstanding")) > 0:
            continue

        filtered.append(compact_invoice(record))

    return json.dumps(filtered)


tools = [get_products_list, get_purchase_list, get_sales_list]

tools_dict = {tool.name: tool for tool in tools}



# from langchain.tools import tool
# from src.dummy import prod_list,purchase_data,sales_data
# import json


# @tool
# def get_products_list():
#     """
#         Use this tool to get the list of products name,group,sku,uom,hsn,igst,cgst,sgst,cess,closingRate,closingQty,etc
#     """
#     if isinstance(prod_list, dict):
#         return json.dumps(prod_list.get("data",[]))
#     return json.dumps(prod_list)

# @tool
# def get_purchase_list():
#     """
#         Use this tool to get the list of purchase details like invoiceNo,invoiceDate,billToName,shipToName,etc
#     """
#     return json.dumps(purchase_data.get("data",[]))


# @tool
# def get_sales_list():
#     """
#         Use this tool to get the list of sales details like invoiceNo,invoiceDate,billToName,shipToName,etc
#     """
#     return json.dumps(sales_data.get("data",[]))


# tools = [get_products_list, get_purchase_list, get_sales_list]

# tools_dict = {tool.name: tool for tool in tools}