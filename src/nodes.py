from src.retriever import retriever
from src.schema import MainState,InputState,OutputState,SupervisorState
from src.config import llm
from src.tool import tools_dict,tools
import asyncio
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage,ToolMessage
from langgraph.prebuilt import ToolNode


# 1. our semantic search node

async def semantic_search_node(state:MainState):
    try:
        query = state['user_query']
        print(f"Semantic search node activated and is analysing the user's query : {query}")

        retrieved_tools = await retriever(query, k=7)
        retrieved_tools_names = [tool.name for tool in retrieved_tools]
        print(f"Retrieved tools : {retrieved_tools_names}")
        return {
            "retrieved_tools": retrieved_tools_names
        }
    except Exception as e:
        print(f"Error in semantic search node: {e}")


#2. our worker node the chatbot node

async def chatbot_node(state:MainState):
    """Binds the active tools to the LLM and generates a response or tool calls."""
    try:
        print("\n Chatbot Node is activated..........")
        messages = state["messages"]
        loop_count = state.get("loop_count",0)
        retrieved_tools = state.get("retrieved_tools", [])
        tools_list = [tools_dict[name] for name in retrieved_tools if name in tools_dict]
        if tools_list:
            print("Binding the tools with LLM................")
            llm_with_tools = llm.bind_tools(tools_list)
            print("LLM with tools bound successfully")
        available_tool_names = [tool.name for tool in tools_list]   
        # sys_prompt = SystemMessage(
        #     content=(
        #     #    "You are an advanced ERP & Accounting Assistant.\n"
        #     #     "Use the provided tools to find the data required to answer the user's query.\n\n"
        #     #     f"THE USER'S EXACT QUERY IS: '{state['user_query']}'\n\n"
        #     #     "CRITICAL INSTRUCTIONS:\n"
        #     #     "1. If the user asks for multiple pieces of data, call multiple tools in parallel.\n"
        #     #     "2. NEVER hallucinate or change tool arguments.\n"
        #     #     "3. ONLY answer exactly what the user explicitly asked for based on the tool data.\n"
        #     #     "4. Be extremely concise and direct. Do not make up dates or names."
            
        #     )
        # )
        sys_prompt = SystemMessage(
            content=(
        "You are an advanced ERP & Accounting Assistant.\n"
        "You answer ERP/accounting questions using ONLY the JSON data returned by tools.\n\n"

        f"THE USER'S EXACT QUERY IS: '{state['user_query']}'\n\n"
        f"TOOLS AVAILABLE TO YOU RIGHT NOW: {available_tool_names}\n\n"

        "CORE BEHAVIOR:\n"
        "1. If the user asks for ERP/accounting records, call the relevant available tools first.\n"
        "2. If the user asks for multiple modules, call multiple relevant tools.\n"
        "3. Never answer ERP data questions from memory.\n"
        "4. Use only the JSON returned by tools.\n"
        "5. Never invent invoice numbers, voucher numbers, dates, names, amounts, cities, states, GST rates, or payment modes.\n"
        "6. Never change the user's filters.\n"
        "7. If the user asks for data but the matching records are not present in the tool output, return an empty list for that section.\n"
        "8. If a needed tool is not available in TOOLS AVAILABLE TO YOU RIGHT NOW, do not invent that section.\n\n"

        "STRICT FILTERING RULES:\n"
        "1. Apply every filter from the user's query exactly.\n"
        "2. For customer/person filters, match fields such as billToName, shipToName, account.name, particular.name, customer_name, supplier_name, or name.\n"
        "3. For city filters, match fields such as billToCity, shipToCity, city, or place.\n"
        "4. For payment/receipt mode filters, match fields such as referenceMode, paymentMode, mode, or reference_mode.\n"
        "5. For item/HSN/bill-term filters like pen00001, match fields such as code, name, itemName, item_code, or description.\n"
        "6. Do not include records just because they came from the correct tool.\n"
        "7. Include only records that satisfy the user's exact filter.\n"
        "8. Example: if the user asks for sale returns for Account, do not include sale returns for ABC Ltd.\n"
        "9. Example: if the user asks for CASH, do not include records where referenceMode is empty, ONLINE, null, or anything other than CASH.\n\n"

        "FEW-SHOT TOOL CALLING EXAMPLES:\n\n"

        "Example 1:\n"
        "User query: Find all sales invoices where customer city is Silvassa, and show receipt vouchers where payment mode is CASH.\n"
        "Correct tools to call: get_sale_info, get_receipt\n"
        "Final JSON data keys: sales_invoices, receipt_vouchers\n"
        "Filtering rule: sales_invoices must have city Silvassa. receipt_vouchers must have referenceMode CASH.\n\n"

        "Example 2:\n"
        "User query: Show sale returns for Account, sales invoices for Account, receipt vouchers with CASH mode, and bill terms for pen00001.\n"
        "Correct tools to call: get_sale_return, get_sale_info, get_receipt, get_bill_term\n"
        "Final JSON data keys: sale_returns, sales_invoices, receipt_vouchers, bill_terms\n"
        "Filtering rule: sale_returns and sales_invoices must match Account. receipts must match CASH. bill_terms must match pen00001.\n\n"

        "Example 3:\n"
        "User query: Get HSN code, GST rate, CGST, SGST for pen00001 and also show its bill term.\n"
        "Correct tools to call: get_hsn, get_bill_term\n"
        "Final JSON data keys: hsn_tax_details, bill_terms\n"
        "Filtering rule: hsn_tax_details must match code/name pen00001. bill_terms must match name pen00001.\n\n"

        "Example 4:\n"
        "User query: Show purchase invoices for Dddsdss and payments made to rohan using ONLINE mode.\n"
        "Correct tools to call: get_purchase_info, get_payment\n"
        "Final JSON data keys: purchase_invoices, payment_vouchers\n"
        "Filtering rule: purchase_invoices must match Dddsdss. payment_vouchers must match rohan and ONLINE.\n\n"

        "Example 5:\n"
        "User query: Customer rohan ke naam par jitni bhi sales invoices hain wo dikhao, aur sath me check karo ki unse total kitna paisa receipt vouchers me receive hua hai.\n"
        "Correct tools to call: get_sale_info, get_receipt\n"
        "Final JSON data keys: sales_invoices, receipt_vouchers, totals\n"
        "Filtering rule: both sales_invoices and receipt_vouchers must match rohan. totals should be calculated only from matching receipt records.\n\n"

        "FINAL ANSWER FORMAT:\n"
        "After tool results are available, return ONLY valid raw JSON.\n"
        "Do not return markdown.\n"
        "Do not use bullet points.\n"
        "Do not wrap JSON inside ```json or ```.\n"
        "Do not add explanation before or after JSON.\n"
        "Use double quotes for JSON keys and string values.\n"
        "Use null for missing values.\n"
        "Convert numeric strings to JSON numbers when possible.\n"
        "Examples: \"20000\" should become 20000, \"1111\" should become 1111, \"122221\" should become 122221.\n\n"

        "FINAL JSON STRUCTURE:\n"
        "{\n"
        '  "success": true,\n'
        '  "query": "original user query",\n'
        '  "data": {\n'
        '    "dynamic_section_name": [\n'
        "      {\n"
        '        "field_name": "field_value"\n'
        "      }\n"
        "    ]\n"
        "  },\n"
        '  "summary": "short factual summary of what was found"\n'
        "}\n\n"

        "DYNAMIC DATA KEY RULES:\n"
        "1. The keys inside data must be based on the user's query.\n"
        "2. Use clear snake_case names.\n"
        "3. Common section names are:\n"
        "   - sales_invoices\n"
        "   - receipt_vouchers\n"
        "   - purchase_invoices\n"
        "   - payment_vouchers\n"
        "   - sale_returns\n"
        "   - hsn_tax_details\n"
        "   - bill_terms\n"
        "   - totals\n"
        "4. Only include sections relevant to the user's query.\n"
        "5. Do not include unrelated empty sections.\n"
        "6. If a requested relevant section has no matching records, include that section as an empty list.\n\n"

        "FIELD SELECTION RULES:\n"
        "1. Do not dump full raw tool responses unless the user explicitly asks for raw data.\n"
        "2. Include only useful fields needed to answer the user.\n"
        "3. Prefer clean API-friendly names.\n"
        "4. Example field mappings:\n"
        "   - invoiceNo -> invoice_no\n"
        "   - invoiceDate -> invoice_date\n"
        "   - billToName -> customer_name or supplier_name depending on context\n"
        "   - billToCity -> city\n"
        "   - billToState -> state\n"
        "   - netAmount or amount -> amount\n"
        "   - referenceMode -> reference_mode\n"
        "   - code -> hsn_code\n"
        "   - igst -> igst\n"
        "   - cgst -> cgst\n"
        "   - sgst -> sgst\n\n"

        "SUMMARY RULES:\n"
        "1. Summary must be short and factual.\n"
        "2. Mention counts from the filtered final data only.\n"
        "3. Do not claim records were found if the matching list is empty.\n"
    )
)
        response = await llm_with_tools.ainvoke([sys_prompt] + messages)
        print("Response has been generated sucessfully")
        return {
            "messages": [response],
            "loop_count" : loop_count + 1
        }
    except Exception as e:
        print(f"Error in our worker node is {e}")
        return {
            "messages" : [AIMessage(content=f"An internal error occured : {str(e)}")]
        }

tool_node = ToolNode(tools)

async def supervisor_node(state:MainState):
    """
      This node will be used for routing logic and guide the llm in choosing whether 
      the chatbot should continue with the task,try again or end it.
    """
    try:
            
        print("\nThe supervisor  node has been activated anb is evaluating..............")
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message,"tool_calls") and last_message.tool_calls:
            print("Tool call action is detected routing to TOOLS NODE>>>>>>>>>>>>.")
            return "tools_node"
        if state.get("loop_count", 0) > 10:
            print("Maximum loop count reached, ending the conversation.")
            return "__end__"
        system_prompt = SystemMessage(
            content=(
                "You are a Quality Assurance Supervisor for an ERP AI.\n"
                "Review the conversation history. Did the worker fully and accurately "
                "answer the user's original query?\n"
                "- If YES, route to 'FINISH'.\n"
                "- If NO (the worker hallucinated, gave an incomplete answer, or needs "
                "to try a different approach), route back to 'worker_node'."
            )
        )
        supervisor_llm = llm.with_structured_output(SupervisorState)
        print("Supervisor LLM initiated.........")
        response = await supervisor_llm.ainvoke([system_prompt] + messages)
        print("Supervisor response received.........")
        if response.next_node == "FINISH":
            return "__end__"

        return response.next_node
    except Exception as e:
        print(f"Exception of routing  node  is {e}")
        print("↳ Routing to '__end__' to prevent graph crash.")
        return "__end__"
