"""
Reproduce the "right tool, wrong fields, prints nothing" bug.
Tests the local apply_filters + project_fields logic with real API responses.
"""
import asyncio, json, sys, os
from dotenv import load_dotenv
load_dotenv(override=True)
sys.path.insert(0, os.path.dirname(__file__))

# Simulate what tools_api.py does: call API then project_result
from src.tools_api import (
    cached_api_post, project_result, flatten_gst_summary_result,
    append_report_summary_row, flatten_sales_summary_result,
    CUSTOMER_ENDPOINT, GST_SUMMARY_ENDPOINT,
    OUTSTANDING_SALES_INVOICES_ENDPOINT, STOCK_LEVELS_ENDPOINT
)
from src.config import COMPANY_ID

# Clear cache for fresh results
from src.tools_api import api_cache
api_cache.clear()

async def test_scenario(label, tool_name, endpoint, body, fields, filters):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"  endpoint: {endpoint}")
    print(f"  fields requested: {fields}")
    print(f"  filters requested: {filters}")
    print(f"  body sent to API: {json.dumps(body, default=str)[:200]}")
    
    result = await cached_api_post(endpoint, body=body)
    
    api_success = result.get("success", False)
    api_data = result.get("data", [])
    print(f"  API success: {api_success}")
    if isinstance(api_data, list):
        print(f"  API returned {len(api_data)} records")
        if api_data:
            print(f"  Actual field names: {list(api_data[0].keys()) if isinstance(api_data[0], dict) else 'N/A'}")
    elif isinstance(api_data, dict):
        print(f"  API returned dict with keys: {list(api_data.keys())}")
    
    # Apply flatteners specific to the endpoint
    if endpoint == "/reports/gst-summary":
        result = flatten_gst_summary_result(result)
    elif "outstanding" in endpoint:
        report_type = "outstandingSalesInvoices" if "sales" in endpoint else "outstandingPurchaseInvoices"
        result = append_report_summary_row(result, report_type)
    
    # Now project_result — this is where the bug manifests
    projected = project_result(result, fields=fields, filters=filters)
    projected_data = projected.get("data", [])
    print(f"  AFTER project_result: {len(projected_data)} records")
    if projected_data:
        print(f"  Projected field names: {list(projected_data[0].keys()) if isinstance(projected_data[0], dict) else 'N/A'}")
        print(f"  First record: {json.dumps(projected_data[0], ensure_ascii=False, default=str)[:300]}")
    elif not projected_data and api_success and (isinstance(api_data, (list, dict)) and api_data):
        print(f"  *** BUG: API returned data but project_result returned empty! ***")
        # Check why: trace apply_filters
        from src.tools_api import apply_filters
        filtered = apply_filters(api_data if isinstance(api_data, list) else [], filters)
        print(f"  apply_filters returned {len(filtered)} records")
        if not filtered and filters:
            # Check if filter field exists in data
            data_records = api_data if isinstance(api_data, list) else []
            if data_records:
                actual_fields = set()
                for r in data_records:
                    if isinstance(r, dict):
                        actual_fields.update(r.keys())
                for fk in filters:
                    if fk not in actual_fields:
                        print(f"  >>> Filter key '{fk}' NOT IN actual fields {actual_fields}")
                    else:
                        print(f"  >>> Filter key '{fk}' IS in actual fields — but value comparison failed")
    print(f"{'='*60}")

async def main():
    print("="*60)
    print("FIELD PROJECTION BUG REPRODUCTION")
    print("="*60)
    
    # === SCENARIO 1: Correct tool (get_outstanding_sales_invoices) with wrong filter ===
    # This is what happened with "B2C_PUNJAB ka invoice number?"
    print("\n--- Scenario 1: outstanding_sales_invoices + wrong filter (ledgerId.contains b2cSmall) ---")
    await test_scenario(
        "outstanding_sales + wrong filter",
        "get_outstanding_sales_invoices",
        OUTSTANDING_SALES_INVOICES_ENDPOINT,
        {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 10, "sortBy": "daysOverdue", "sortOrder": "desc"},
        fields=["invoiceNo", "invoiceDate", "ledgerName", "outstanding"],
        filters={"ledgerId": {"contains": "b2cSmall"}}  # LLM invented this
    )
    
    # === SCENARIO 2: Correct filter but wrong field names in fields ===
    print("\n--- Scenario 2: Correct entity but field name mismatch ---")
    await test_scenario(
        "customer + correct search but wrong field names",
        "get_customer",
        CUSTOMER_ENDPOINT,
        {"companyId": COMPANY_ID, "search": "Nykaa", "limit": 5},
        fields=["customer_id", "party_name", "balance"],  # LLM invented names
        filters=None
    )
    
    # === SCENARIO 3: GST summary with wrong filter category ===
    print("\n--- Scenario 3: GST summary with nillRated vs nilRated mismatch ---")
    await test_scenario(
        "gst_summary + category filter (map mismatch: nilRated vs nillRated)",
        "get_gst_summary",
        GST_SUMMARY_ENDPOINT,
        {"companyId": COMPANY_ID, "from": "", "to": ""},
        fields=["category", "name", "voucherCount", "taxableAmount"],
        filters={"category": "nilRated"}  # Code expects nilRated but API returns nillRated
    )
    
    # === SCENARIO 4: Correct filter value but wrong field name ===
    print("\n--- Scenario 4: Outstanding invoices with ledgerName (correct) filter ---")
    await test_scenario(
        "outstanding_sales + correct ledgerName filter",
        "get_outstanding_sales_invoices",
        OUTSTANDING_SALES_INVOICES_ENDPOINT,
        {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 10, "sortBy": "daysOverdue", "sortOrder": "desc"},
        fields=["invoiceNo", "invoiceDate", "ledgerName", "outstanding"],
        filters={"ledgerName": {"contains": "MAHARASHTRA"}}  # known to exist
    )
    
    # === SCENARIO 5: Customer search with city filter ===
    print("\n--- Scenario 5: Customer search - trying to filter by city via filters.name ---")
    await test_scenario(
        "customer + filters.name.contains Kolkata",
        "get_customer",
        CUSTOMER_ENDPOINT,
        {"companyId": COMPANY_ID, "search": "", "limit": 10},
        fields=["id", "name", "city"],
        filters={"name": {"contains": "KOLKATA"}}
    )
    
    # === SCENARIO 6: The exact B2C_PUNJAB scenario with the correct approach ===
    print("\n--- Scenario 6: B2C_PUNJAB - correct approach (ledgerName contains PUNJAB) ---")
    await test_scenario(
        "outstanding_sales + ledgerName contains PUNJAB",
        "get_outstanding_sales_invoices",
        OUTSTANDING_SALES_INVOICES_ENDPOINT,
        {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 10, "sortBy": "daysOverdue", "sortOrder": "desc"},
        fields=["invoiceNo", "invoiceDate", "ledgerName", "netAmount", "outstanding"],
        filters={"ledgerName": {"contains": "PUNJAB"}}
    )

    # === SCENARIO 7: Customer search with empty search but API body filter (test if API respects filter) ===
    print("\n--- Scenario 7: Customer search - filters in API body vs local ---")
    body = {"companyId": COMPANY_ID, "search": "", "limit": 10, "filters": {"name": {"contains": "NYKAA"}}}
    result = await cached_api_post(CUSTOMER_ENDPOINT, body=body)
    data = result.get("data", [])
    print(f"  API returned {len(data) if isinstance(data, list) else 'N/A'} records")
    if isinstance(data, list) and data:
        print(f"  API ignored the filters.name.contains - got {len(data)} unfiltered records")
        # But local filtering should still work
        projected = project_result(result, fields=["id", "name"], filters={"name": {"contains": "NYKAA"}})
        proj_data = projected.get("data", [])
        print(f"  After local project_result: {len(proj_data)} records")
        if proj_data:
            print(f"  Local filter WORKS: found {len(proj_data)} records matching NYKAA")
        else:
            print(f"  Local filter FAILED: 0 records even though API returned data")

if __name__ == "__main__":
    asyncio.run(main())
