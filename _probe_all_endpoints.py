"""
Probe script: calls all 19 API endpoints with minimal bodies,
captures actual response shapes, field names, timing, and filter behavior.
Also tests specific bug scenarios.
"""
import asyncio
import json
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv(override=True)

import httpx

CHP1_API_BASE_URL = os.getenv("CHP1_API_BASE_URL", "")
CHP1_API_TOKEN = os.getenv("CHP1_API_TOKEN", "")
CHP1_API_TIMEOUT = int(os.getenv("CHP1_API_TIMEOUT", "30"))
COMPANY_ID = int(os.getenv("COMPANY_ID", "0"))

HEADERS = {"Authorization": f"{CHP1_API_TOKEN}"}

ENDPOINTS = {
    "get_customer":                   "/customers",
    "get_customer_ledger":            "/customers/ledger",
    "get_stock_levels":               "/inventory/stock",
    "get_gst_summary":                "/reports/gst-summary",
    "get_tds_outstanding":            "/reports/tds-outstanding",
    "get_tcs_outstanding":            "/reports/tcs-outstanding",
    "get_top_products":               "/top-products",
    "get_popular_products":           "/popular-products",
    "get_slow_moving_products":       "/slow-moving-products",
    "get_sales_summary":              "/sales-summary",
    "get_sales_trend":                "/sales-trends",
    "get_top_customer":               "/top-customers",
    "get_top_vendor":                 "/top-vendors",
    "get_purchase_summary":           "/purchase-summary",
    "get_search_ledgers":             "/ledgers/search",
    "get_search_vendors":             "/vendors",
    "get_outstanding_sales_invoices": "/reports/outstanding-sales-invoices",
    "get_outstanding_purchase_invoices": "/reports/outstanding-purchase-invoices",
    "get_overdue_invoices":           "/reports/overdue-invoices",
}

# Minimal body per endpoint (based on tool definitions)
MINIMAL_BODIES = {
    "get_customer":                   {"companyId": COMPANY_ID, "search": "", "limit": 2},
    "get_customer_ledger":            {"companyId": COMPANY_ID, "customerId": 815, "from": "", "to": "", "page": 1, "limit": 2},
    "get_stock_levels":               {"companyId": COMPANY_ID, "from": "", "to": "", "lowStockOnly": False, "page": 1, "limit": 2, "term": ""},
    "get_gst_summary":                {"companyId": COMPANY_ID, "from": "", "to": ""},
    "get_tds_outstanding":            {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 2},
    "get_tcs_outstanding":            {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 2},
    "get_top_products":               {"companyId": COMPANY_ID, "from": "", "to": "", "sortBy": "revenue", "limit": 2},
    "get_popular_products":           {"companyId": COMPANY_ID, "period": "this_month", "limit": 2},
    "get_slow_moving_products":       {"companyId": COMPANY_ID, "period": "current_fy", "limit": 2},
    "get_sales_summary":              {"companyId": COMPANY_ID, "from": "", "to": "", "groupBy": "day", "vendorId": None, "productId": None},
    "get_sales_trend":                {"companyId": COMPANY_ID, "period": "this_month", "compareWith": "last_year"},
    "get_top_customer":               {"companyId": COMPANY_ID, "period": "current_fy", "sortBy": "revenue", "limit": 2},
    "get_top_vendor":                 {"companyId": COMPANY_ID, "period": "current_fy", "limit": 2},
    "get_purchase_summary":           {"companyId": COMPANY_ID, "from": "", "to": "", "vendorId": None, "productId": None},
    "get_search_ledgers":             {"companyId": COMPANY_ID, "searchTerm": "", "groupType": None, "page": 1, "limit": 2},
    "get_search_vendors":             {"companyId": COMPANY_ID, "search": "", "limit": 2},
    "get_outstanding_sales_invoices": {"companyId": COMPANY_ID, "from": "", "to": "", "asOfDate": "", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc"},
    "get_outstanding_purchase_invoices": {"companyId": COMPANY_ID, "from": "", "to": "", "asOfDate": "", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc"},
    "get_overdue_invoices":           {"companyId": COMPANY_ID, "invoiceType": "BOTH", "asOfDate": "", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc"},
}

# Bug-specific probe calls
BUG_PROBE_CALLS = [
    # Issue 1: City search - does /customers return city field?
    ("customer_city_search", "/customers", {"companyId": COMPANY_ID, "search": "Kolkata", "limit": 5}),
    # Issue 2: B2C_PUNJAB - what category values does GST summary use?
    ("gst_summary_categories", "/reports/gst-summary", {"companyId": COMPANY_ID, "from": "", "to": ""}),
    # Issue 3: GST with b2cSmall filter
    ("gst_summary_b2cSmall", "/reports/gst-summary", {"companyId": COMPANY_ID, "from": "", "to": "", "filters": {"category": "b2cSmall"}}),
    # Issue 4: GST with b2cLarge filter
    ("gst_summary_b2cLarge", "/reports/gst-summary", {"companyId": COMPANY_ID, "from": "", "to": "", "filters": {"category": "b2cLarge"}}),
    # Issue 5: Outstanding sales invoices with limited date range (to test timeout)
    ("outstanding_sales_limited", "/reports/outstanding-sales-invoices", {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc"}),
    # Issue 6: Outstanding sales invoices with empty dates (to test timeout)
    ("outstanding_sales_empty", "/reports/outstanding-sales-invoices", {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc"}),
    # Issue 7: Ledger search with city
    ("ledger_search_kolkata", "/ledgers/search", {"companyId": COMPANY_ID, "searchTerm": "Kolkata", "groupType": None, "page": 1, "limit": 5}),
    # Issue 8: Search vendors with city
    ("vendor_search_kolkata", "/vendors", {"companyId": COMPANY_ID, "search": "Kolkata", "limit": 5}),
    # Issue 9: Customer with specific city filter in API body
    ("customer_name_contains_kolkata", "/customers", {"companyId": COMPANY_ID, "search": "", "limit": 5, "filters": {"name": {"contains": "KOLKATA"}}}),
    # Issue 10: Invoice lookup with ledgerId filter (test if ledgerId exists in response)
    ("outstanding_sales_ledgerId_check", "/reports/outstanding-sales-invoices", {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 2, "sortBy": "daysOverdue", "sortOrder": "desc", "filters": {"ledgerId": {"contains": "b2cSmall"}}}),
    # Issue 11: Outstanding sales invoices with invoiceNo filter  
    ("outstanding_sales_invoiceNo_filter", "/reports/outstanding-sales-invoices", {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 5, "sortBy": "daysOverdue", "sortOrder": "desc", "filters": {"invoiceNo": "SI-001"}}),
]


async def call_endpoint(name: str, endpoint: str, body: dict, timeout: int = CHP1_API_TIMEOUT) -> dict:
    url = f"{CHP1_API_BASE_URL.rstrip('/')}/{endpoint.strip('/')}"
    print(f"\n{'='*70}")
    print(f"[{name}] POST {url}")
    print(f"[{name}] BODY: {json.dumps(body, default=str)}")
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body, headers=HEADERS)
        duration = time.perf_counter() - start
        print(f"[{name}] TIME: {duration:.3f}s")
        print(f"[{name}] STATUS: {resp.status_code}")
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text[:1000]}
        # Show first record fully to see ALL field names
        if isinstance(data, dict):
            payload_data = data.get("data", data)
            if isinstance(payload_data, dict):
                print(f"[{name}] DATA KEYS: {list(payload_data.keys()) if isinstance(payload_data, dict) else 'N/A'}")
            elif isinstance(payload_data, list) and payload_data:
                print(f"[{name}] FIELD NAMES: {list(payload_data[0].keys())}")
                print(f"[{name}] FIRST RECORD: {json.dumps(payload_data[0], ensure_ascii=False, default=str)[:500]}")
                print(f"[{name}] RECORD COUNT: {len(payload_data)}")
            else:
                print(f"[{name}] DATA: {json.dumps(data, ensure_ascii=False, default=str)[:1000]}")
        print(f"[{name}] RESPONSE OK: {resp.is_success}")
        return {"name": name, "success": resp.is_success, "duration": duration, "data": data}
    except httpx.TimeoutException:
        duration = time.perf_counter() - start
        print(f"[{name}] TIMEOUT after {duration:.3f}s")
        return {"name": name, "success": False, "duration": duration, "error": "timeout"}
    except Exception as e:
        duration = time.perf_counter() - start
        print(f"[{name}] ERROR: {e}")
        return {"name": name, "success": False, "duration": duration, "error": str(e)}


async def main():
    print("=" * 70)
    print("PHASE 1: Call all 19 endpoints with minimal bodies")
    print("=" * 70)
    results = {}
    for tool_name, endpoint in ENDPOINTS.items():
        body = MINIMAL_BODIES[tool_name]
        result = await call_endpoint(tool_name, endpoint, body)
        results[tool_name] = result
        await asyncio.sleep(0.3)  # rate limit
    
    print("\n" + "=" * 70)
    print("PHASE 2: Bug-specific probe calls")
    print("=" * 70)
    bug_results = {}
    for name, endpoint, body in BUG_PROBE_CALLS:
        result = await call_endpoint(name, endpoint, body)
        bug_results[name] = result
        await asyncio.sleep(0.3)
    
    # Summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    all_ok = []
    timeouts = []
    errors = []
    for name, r in results.items():
        if r.get("success") and r.get("duration", 0) < 5:
            all_ok.append(name)
        elif r.get("error") == "timeout":
            timeouts.append(name)
        else:
            errors.append(f"{name}: {r.get('error', 'unknown')}")
    for name, r in bug_results.items():
        if r.get("error") == "timeout":
            timeouts.append(name)
        elif not r.get("success"):
            errors.append(f"{name}: {r.get('error', 'unknown')}")
    
    print(f"OK ({len(all_ok)}): {', '.join(all_ok)}")
    print(f"TIMEOUTS ({len(timeouts)}): {', '.join(timeouts)}")
    print(f"ERRORS ({len(errors)}): {'; '.join(errors)}")
    
    return results, bug_results

if __name__ == "__main__":
    asyncio.run(main())
