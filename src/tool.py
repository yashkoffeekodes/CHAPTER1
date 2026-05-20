import json
from langchain.tools import tool

# FIX 1: Alias the imports so they don't collide with your function names!
from src.dummy import (
    get_purch as dummy_purch, 
    get_sale as dummy_sale, 
    get_paym as dummy_paym, 
    get_recp as dummy_recp, 
    get_sale_retrn as dummy_sale_retrn, 
    get_hsn as dummy_hsn, 
    billterm as dummy_billterm
)

@tool
def get_purchase_info(search_query: str) -> str:
    """
    Use this tool to find purchase information, purchase amount, invoice date, ledger details, and transaction history for items.
    """
    # FIX 2: Return a JSON string so the LLM can easily read the data
    return json.dumps(dummy_purch)


@tool
def get_sale_info(search_query: str) -> str:
    """
    Use this tool when the user asks about sale information, sale amounts, selling dates, or customer billing details.
    """
    return json.dumps(dummy_sale)


@tool
def get_payment(search_query: str) -> str:
    """
    Use this tool when the user asks about payment information, payment dates, reference numbers, or paid amounts.
    """
    return json.dumps(dummy_paym)


@tool
def get_receipt(search_query: str) -> str:
    """
    Use this tool when the user asks about receipt information, received amounts, cash modes, or narration.
    """
    return json.dumps(dummy_recp)


@tool
def get_sale_return(search_query: str) -> str:
    """
    Use this tool when the user asks about sale return information, canceled sales, or returned items.
    """
    return json.dumps(dummy_sale_retrn)


@tool
def get_hsn(search_query: str) -> str:
    """
    Use this tool when the user asks about HSN code, GST, CGST, SGST, cess, or tax rates for specific items.
    """
    return json.dumps(dummy_hsn)


@tool
def get_bill_term(search_query: str) -> str:
    """
    Use this tool when the user asks about bill terms, payment terms, due days, credit terms, or billing rules.
    """
    return json.dumps(dummy_billterm)


tools = [
    get_purchase_info,
    get_sale_info,
    get_payment,
    get_receipt,
    get_sale_return,
    get_hsn,
    get_bill_term,
]

tools_dict = {tool.name: tool for tool in tools}







# from langchain.tools import tool

# from src.dummy import get_purch, get_sale, get_paym, get_recp, get_sale_retrn, get_hsn, billterm
# @tool
# def get_purchase_info(item: str):
#     """
#     Use this tool when the user asks about purchase information.
#     """
#     return get_purch


# @tool
# def get_sale_info(item: str):
#     """
#     Use this tool when the user asks about sale information.
#     """
#     return get_sale


# @tool
# def get_payment(item: str):
#     """
#     Use this tool when the user asks about payment information.
#     """
#     return get_paym


# @tool
# def get_receipt(item: str):
#     """
#     Use this tool when the user asks about receipt information.
#     """
#     return get_recp


# @tool
# def get_sale_return(item: str):
#     """
#     Use this tool when the user asks about sale return information.
#     """
#     return get_sale_retrn


# @tool
# def get_hsn(item: str):
#     """
#     Use this tool when the user asks about HSN code, GST, CGST, SGST, or tax rate.
#     """
#     return get_hsn


# @tool
# def get_bill_term(item: str):
#     """
#     Use this tool when the user asks about bill terms, payment terms, due days, or credit terms.
#     """
#     return billterm


# tools = [
#     get_purchase_info,
#     get_sale_info,
#     get_payment,
#     get_receipt,
#     get_sale_return,
#     get_hsn,
#     get_bill_term,
# ]

# tools_dict = {tool.name: tool for tool in tools}