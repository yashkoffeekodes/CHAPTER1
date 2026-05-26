from langchain.tools import tool
import json
from typing import Optional, Any
from src.api_client import api_post
from src.config import COMPANY_ID


def normalize_fields(fields):
    if fields is None:
        return []

    if fields == "":
        return []

    if isinstance(fields, list):
        return [
            str(field).strip()
            for field in fields
            if str(field).strip()
        ]

    if isinstance(fields, dict):
        return [
            str(field).strip()
            for field, enabled in fields.items()
            if enabled in [1, True, "1", "true", "True"]
        ]

    if isinstance(fields, str):
        return [
            field.strip()
            for field in fields.split(",")
            if field.strip()
        ]

    return []


def normalize_value(value):
    if value is None:
        return ""

    return str(value).strip().lower()


def to_number(value):
    try:
        if value is None or value == "":
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def match_filter(actual, expected):
    if isinstance(expected, dict):
        for operator, value in expected.items():
            operator = str(operator).lower().strip()

            if operator == "eq":
                if normalize_value(actual) != normalize_value(value):
                    return False

            elif operator == "contains":
                if normalize_value(value) not in normalize_value(actual):
                    return False

            elif operator == "in":
                if not isinstance(value, list):
                    return False

                allowed_values = [normalize_value(v) for v in value]

                if normalize_value(actual) not in allowed_values:
                    return False

            elif operator in ["gt", "gte", "lt", "lte"]:
                actual_num = to_number(actual)
                expected_num = to_number(value)

                if actual_num is None or expected_num is None:
                    return False

                if operator == "gt" and not actual_num > expected_num:
                    return False

                if operator == "gte" and not actual_num >= expected_num:
                    return False

                if operator == "lt" and not actual_num < expected_num:
                    return False

                if operator == "lte" and not actual_num <= expected_num:
                    return False

            else:
                return False

        return True

    return normalize_value(actual) == normalize_value(expected)


def apply_filters(records, filters=None):
    if not filters:
        return records

    filtered_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        matched = True

        for field, expected in filters.items():
            actual = record.get(field)

            if not match_filter(actual, expected):
                matched = False
                break

        if matched:
            filtered_records.append(record)

    return filtered_records


def project_fields(records, fields=None):
    selected_fields = normalize_fields(fields)

    if not selected_fields:
        return records

    projected_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        projected_records.append({
            field: record.get(field)
            for field in selected_fields
            if field in record
        })

    return projected_records


def project_result(result: dict, fields=None, filters=None) -> dict:
    if not isinstance(result, dict):
        return {
            "success": False,
            "data": [],
            "count": 0,
            "error": "API result is not a dictionary"
        }

    if not result.get("success", False):
        return result

    data = result.get("data", [])

    if data is None:
        data = []

    if not isinstance(data, list):
        data = [data]

    data = apply_filters(data, filters)
    data = project_fields(data, fields)

    result["data"] = data
    result["count"] = len(data)

    return result
def make_purchase_sales_body(
    page: int,
    limit: int,
    term: str,
    ledger_id: int,
    from_date: str,
    to_date: str
) -> dict:
    return {
        "companyId": COMPANY_ID,
        "page": page,
        "limit": limit,
        "term": term or "",
        "ledgerId": ledger_id,
        "from": from_date or "",
        "to": to_date or "",
    }




@tool
def get_product_list(
    page: int = 1,
    limit: int = 10,
    term: Optional[str] = "",
    fields: Optional[Any] = None,
    filters: Optional[dict[str, Any]] = None  
):
    """
    Get product/inventory list from Chapter-1 API.

    Use this tool when the user asks about products, inventory, items,
    stock, SKU, HSN, GST rate, product name, or item details.

    Args:
        page: Page number. Default is 1.
        limit: Number of records to fetch. Default is 10.
        term: Search keyword for product name, SKU, HSN, or item keyword.
    """
    body = {
        "companyId": COMPANY_ID,
        "page": page,
        "limit": limit,
        "term": term or ""
    }
    result = api_post("/productList",body=body)
    result = project_result(result, fields=fields, filters=filters)
    print("[TOOL OUTPUT]", result)
    return json.dumps(result,ensure_ascii=False)

@tool
def get_purchase_list(
page: int = 1,
    limit: int = 10,
    term: Optional[str] = "",
    ledger_id: int = 0,
    from_date: Optional[str] = "",
    to_date: Optional[str] = "",
    fields: Optional[Any] = None,
    filters: Optional[dict[str, Any]] = None
    ):
    """
        Get purchase invoice/list records from ERP API.

    Use this tool when the user asks about purchases, purchase invoices,
    vendor bills, supplier bills, purchase amount, purchase date,
    purchase invoice number, purchase ledger, or purchase records.

    Args:
        page: Page number. Default is 1.
        limit: Number of records to fetch. Default is 10.
        term: Search keyword such as invoice number, supplier name, reference number, or keyword.
        ledger_id: Ledger ID filter. Use 0 when no specific ledger is provided.
        from_date: Start date filter. Use empty string when not provided.
        to_date: End date filter. Use empty string when not provided.
    """
    body = {
        "companyId": COMPANY_ID,
        "page": page,
        "limit": limit,
        "term": term or "",
        "ledgerId": ledger_id,
        "from": from_date or "",
        "to": to_date or "",
    }
    result = api_post("/purchaseList",body=body)
    result = project_result(result, fields=fields, filters=filters)
    print("[TOOL OUTPUT]", result)
    return json.dumps(result,ensure_ascii=False)

@tool
def get_sales_list(
    page: int = 1,
    limit: int = 10,
    term: Optional[str] = "",
    ledger_id: int = 0,
    from_date: Optional[str] = "",
    to_date: Optional[str] = "",
    fields: Optional[Any] = None,
    filters: Optional[dict[str, Any]] = None
):
    """
    Get sales invoice/list records from ERP API.

    Use this tool when the user asks about sales, sales invoices,
    customer invoices, sale bills, customer bills, sales amount,
    sales date, sales invoice number, sales ledger, or sales records.

    Args:
        page: Page number. Default is 1.
        limit: Number of records to fetch. Default is 10.
        term: Search keyword such as invoice number, customer name, reference number, or keyword.
        ledger_id: Ledger ID filter. Use 0 when no specific ledger is provided.
        from_date: Start date filter. Use empty string when not provided.
        to_date: End date filter. Use empty string when not provided.
    """

    body = {
        "companyId": COMPANY_ID,
        "page": page,
        "limit": limit,
        "term": term or "",
        "ledgerId": ledger_id,
        "from": from_date or "",
        "to": to_date or "",
    }
    result = api_post("/salesList",body=body)
    result = project_result(result, fields=fields, filters=filters)
    print("[TOOL OUTPUT]", result)
    return json.dumps(result,ensure_ascii=False)

tools = [get_product_list, get_purchase_list, get_sales_list]

tools_dict = {tool.name : tool for tool in tools}