from langchain_core.messages import HumanMessage
from src.tool import tools_dict
from src.retriever import retriever
from src.graphs import graph_builder
import asyncio


async def main():
    try:
        print("Starting the application...")
        chatbot_graph = graph_builder()
        # query = "How many sales have we done in silvasa"
        # query = "What is the HSN code and GST rate for pen00001, and what are the total sales we have done for 'rohan'?"
        # query = "What are our total purchase amounts for 'Dddsdss', have we made any payments to 'rohan' via ONLINE mode, and what is the billing term name in our system?"
        # query = "Find all sales invoices where the customer city is 'Silvassa', and also show me the receipt vouchers where the payment mode was 'CASH'."
        # query = "Customer 'rohan' ke naam par jitni bhi sales invoices hain wo dikhao, aur sath me check karo ki unse total kitna paisa receipt vouchers me receive hua hai."
        query = "ભાઈ, 'Silvassa' city na jetla bhee sales invoices chhe ae to batavo, and sath ma e bhee check karo ke 'ABC Ltd' na ketla sale return thaya chhe?"
        initial_state = {
            "user_query": query,
            "messages": [HumanMessage(content=query)],
            "retrieved_tools": []
        }
        async for chunk in chatbot_graph.astream(initial_state,stream_mode="updates"):
            for node_name,state_update in chunk.items():
                if node_name == "worker_node" and "messages" in state_update:
                    last_msg = state_update["messages"][-1]
                    if not getattr(last_msg, "tool_calls", None):
                        print(f"\nCHAPTER1 AI ASSISTANT's Final Answer:\n{last_msg.content}\n")
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())