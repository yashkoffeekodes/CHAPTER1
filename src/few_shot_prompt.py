from langchain_core.documents import Document

few_shot_examples = [

    Document(
        page_content="Show all purchase invoices for Dddsdss",
        metadata={
            "section": "purchase_invoices",
            "scenario": "match",
            "output": '{"success":true,"query":"Show all purchase invoices for Dddsdss","status":"success","data":{"purchase_invoices":[{"invoiceNo":"PR-5","billToName":"Dddsdss"},{"invoiceNo":"PR-4","billToName":"Dddsdss"}]}}'
        }
    ),

    Document(
        page_content="Show sale returns for Account",
        metadata={
            "section": "sale_returns",
            "scenario": "no_match",
            "output": '{"success":false,"query":"Show sale returns for Account","status":"no_data_found","data":{"sale_returns":[]}}'
        }
    ),

    Document(
        page_content="Show bill terms for ABC Ltd",
        metadata={
            "section": "bill_terms",
            "scenario": "no_entity_field",
            "output": '{"success":false,"query":"Show bill terms for ABC Ltd","status":"no_data_found","data":{"bill_terms":[]}}'
        }
    ),

    Document(
        page_content="Show payment vouchers for ABC Ltd",
        metadata={
            "section": "payment_vouchers",
            "scenario": "tool_unavailable",
            "output": '{"success":false,"query":"Show payment vouchers for ABC Ltd","status":"partial_success","data":{"payment_vouchers":[]}}'
        }
    ),

    Document(
        page_content="Give me invoiceNo of all sale returns for ABC Ltd",
        metadata={
            "section": "sale_returns",
            "scenario": "specific_fields",
            "output": '{"success":true,"query":"Give me invoiceNo of all sale returns for ABC Ltd","status":"success","data":{"sale_returns":[{"invoiceNo":"CT-2"},{"invoiceNo":"CT-1"}]}}'
        }
    ),

]