"""
Probe all 19 API endpoints with minimal bodies to confirm data returns correctly
without the removed project_fields/apply_filters layer.
"""
import asyncio, json, sys, os
from dotenv import load_dotenv
load_dotenv(override=True)
sys.path.insert(0, os.path.dirname(__file__))

from src.tools_api import (
    cached_api_post,
    CUSTOMER_ENDPOINT, CUSTOMER_LEDGER_ENDPOINT, STOCK_LEVELS_ENDPOINT,
    GST_SUMMARY_ENDPOINT, TDS_OUTSTANDING_ENDPOINT, TCS_OUTSTANDING_ENDPOINT,
    TOP_PRODUCTS_ENDPOINT, POPULAR_PRODUCTS_ENDPOINT, SLOW_MOVING_PRODUCTS_ENDPOINT,
    SALES_SUMMARY_ENDPOINT, SALES_TRENDS_ENDPOINT, TOP_CUSTOMER_ENDPOINT, TOP_VENDOR_ENDPOINT,
    PURCHASE_SUMMARY_ENDPOINT, OUTSTANDING_SALES_INVOICES_ENDPOINT,
    OUTSTANDING_PURCHASE_INVOICES_ENDPOINT, OVERDUE_INVOICES_ENDPOINT,
    LEDGERS_SEARCH_ENDPOINT, VENDORS_SEARCH_ENDPOINT,
    flatten_gst_summary_result, flatten_sales_summary_result, flatten_sales_trend_result,
    flatten_purchase_summary_result, append_report_summary_row,
)
from src.config import COMPANY_ID

from src.tools_api import api_cache
api_cache.clear()

passed = 0
failed = 0

async def probe(label, endpoint, body, post_fn=None):
    global passed, failed
    print(f"\n--- {label} ---")
    print(f"  endpoint: {endpoint}")
    print(f"  body: {json.dumps(body, default=str)[:200]}")
    try:
        result = await cached_api_post(endpoint, body=body)
    except Exception as e:
        print(f"  CRASHED: {e}")
        failed += 1
        return

    success = result.get("success", False)
    data = result.get("data", [])

    if post_fn:
        result = post_fn(result)
        data = result.get("data", [])

    if isinstance(data, list):
        count = len(data)
        print(f"  success={success} | records={count}")
        if count > 0 and isinstance(data[0], dict):
            print(f"  fields: {list(data[0].keys())[:12]}")
    elif isinstance(data, dict):
        count = len(data)
        print(f"  success={success} | dict keys={list(data.keys())[:12]}")
    else:
        count = 0
        print(f"  success={success} | type={type(data).__name__}")

    if success and (isinstance(data, (list, dict))):
        passed += 1
        print(f"  PASS")
    elif success and not data:
        passed += 1
        print(f"  PASS (empty data — valid)")
    else:
        failed += 1
        print(f"  FAIL")

async def main():
    print("=" * 60)
    print("PROBE: ALL 19 ENDPOINTS")
    print("=" * 60)

    # 1. get_customer
    await probe("get_customer(search=Nykaa)", CUSTOMER_ENDPOINT,
                {"companyId": COMPANY_ID, "search": "Nykaa", "limit": 3})

    # 2. get_customer_ledger
    await probe("get_customer_ledger(id=814, empty dates)", CUSTOMER_LEDGER_ENDPOINT,
                {"companyId": COMPANY_ID, "customerId": 814, "from": "", "to": "", "page": 1, "limit": 5})

    # 3. get_stock_levels
    await probe("get_stock_levels(empty)", STOCK_LEVELS_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": "", "lowStockOnly": False, "page": 1, "limit": 3, "term": ""})

    # 4. get_gst_summary
    await probe("get_gst_summary(empty dates) + flatten", GST_SUMMARY_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": ""},
                post_fn=flatten_gst_summary_result)

    # 5. get_tds_outstanding
    await probe("get_tds_outstanding(empty) + summary_row", TDS_OUTSTANDING_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 5},
                post_fn=lambda r: append_report_summary_row(r, "tdsOutstanding"))

    # 6. get_tcs_outstanding
    await probe("get_tcs_outstanding(empty) + summary_row", TCS_OUTSTANDING_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": "", "page": 1, "limit": 5},
                post_fn=lambda r: append_report_summary_row(r, "tcsOutstanding"))

    # 7. get_top_products
    await probe("get_top_products(defaults)", TOP_PRODUCTS_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": "", "sortBy": "revenue", "limit": 3})

    # 8. get_popular_products
    await probe("get_popular_products(this_month)", POPULAR_PRODUCTS_ENDPOINT,
                {"companyId": COMPANY_ID, "period": "this_month", "limit": 3})

    # 9. get_slow_moving_products
    await probe("get_slow_moving_products(current_fy)", SLOW_MOVING_PRODUCTS_ENDPOINT,
                {"companyId": COMPANY_ID, "period": "current_fy", "limit": 3})

    # 10. get_sales_summary
    await probe("get_sales_summary(empty) + flatten", SALES_SUMMARY_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": "", "groupBy": "day"},
                post_fn=flatten_sales_summary_result)

    # 11. get_sales_trend
    await probe("get_sales_trend(this_month/last_year) + flatten", SALES_TRENDS_ENDPOINT,
                {"companyId": COMPANY_ID, "period": "this_month", "compareWith": "last_year"},
                post_fn=flatten_sales_trend_result)

    # 12. get_top_customer
    await probe("get_top_customer(current_fy)", TOP_CUSTOMER_ENDPOINT,
                {"companyId": COMPANY_ID, "period": "current_fy", "sortBy": "revenue", "limit": 3})

    # 13. get_top_vendor
    await probe("get_top_vendor(current_fy)", TOP_VENDOR_ENDPOINT,
                {"companyId": COMPANY_ID, "period": "current_fy", "limit": 3})

    # 14. get_purchase_summary
    await probe("get_purchase_summary(empty) + flatten", PURCHASE_SUMMARY_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "", "to": ""},
                post_fn=flatten_purchase_summary_result)

    # 15. get_search_ledgers
    await probe("get_search_ledgers(empty)", LEDGERS_SEARCH_ENDPOINT,
                {"companyId": COMPANY_ID, "searchTerm": "", "page": 1, "limit": 3})

    # 16. get_search_vendors
    await probe("get_search_vendors(empty)", VENDORS_SEARCH_ENDPOINT,
                {"companyId": COMPANY_ID, "search": "", "limit": 3})

    # 17. get_outstanding_sales_invoices
    await probe("get_outstanding_sales_invoices(Jan 2025) + summary", OUTSTANDING_SALES_INVOICES_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 3,
                 "sortBy": "daysOverdue", "sortOrder": "desc"},
                post_fn=lambda r: append_report_summary_row(r, "outstandingSalesInvoices"))

    # 18. get_outstanding_purchase_invoices
    await probe("get_outstanding_purchase_invoices(Jan 2025) + summary", OUTSTANDING_PURCHASE_INVOICES_ENDPOINT,
                {"companyId": COMPANY_ID, "from": "2025-01-01", "to": "2025-01-31", "page": 1, "limit": 3,
                 "sortBy": "daysOverdue", "sortOrder": "desc"},
                post_fn=lambda r: append_report_summary_row(r, "outstandingPurchaseInvoices"))

    # 19. get_overdue_invoices
    await probe("get_overdue_invoices(BOTH) + summary", OVERDUE_INVOICES_ENDPOINT,
                {"companyId": COMPANY_ID, "invoiceType": "BOTH", "asOfDate": "2025-06-10",
                 "page": 1, "limit": 3, "sortBy": "daysOverdue", "sortOrder": "desc"},
                post_fn=lambda r: append_report_summary_row(r, "overdueInvoices"))

    print(f"\n{'='*60}")
    print(f"RESULT: {passed} passed, {failed} failed out of {passed+failed}")
    print(f"{'='*60}")
    if failed:
        sys.exit(1)

asyncio.run(main())
