from langchain.tools import tool

from src.dummy import get_purch, get_sale, get_paym, get_recp, get_sale_retrn, get_hsn, billterm
@tool
def get_purchase_info(item: str):
    """
    Use this tool when the user asks about purchase information.
    """
    return get_purch


@tool
def get_sale_info(item: str):
    """
    Use this tool when the user asks about sale information.
    """
    return get_sale


@tool
def get_payment(item: str):
    """
    Use this tool when the user asks about payment information.
    """
    return get_paym


@tool
def get_receipt(item: str):
    """
    Use this tool when the user asks about receipt information.
    """
    return get_recp


@tool
def get_sale_return(item: str):
    """
    Use this tool when the user asks about sale return information.
    """
    return get_sale_retrn


@tool
def get_hsn(item: str):
    """
    Use this tool when the user asks about HSN code, GST, CGST, SGST, or tax rate.
    """
    return get_hsn


@tool
def get_bill_term(item: str):
    """
    Use this tool when the user asks about bill terms, payment terms, due days, or credit terms.
    """
    return billterm


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