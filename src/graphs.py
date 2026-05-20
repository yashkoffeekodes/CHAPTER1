from langgraph.graph import StateGraph,START,END
from src.schema import InputState, MainState, OutputState
from src.nodes import chatbot_node,semantic_search_node,tool_node,supervisor_node

def graph_builder():
    try:
        print("Graph is preparing.................")
        
        builder = StateGraph(MainState,input_schema=InputState,output_schema=OutputState)

        print("We will add nodes now.........")

        builder.add_node("worker_node",chatbot_node)
        builder.add_node("semantic_node",semantic_search_node)
        builder.add_node("tools_node",tool_node)
       
        print("Adding edges and conditional edges.")

        builder.add_edge(START,"semantic_node")
        builder.add_edge("semantic_node","worker_node")
        builder.add_conditional_edges("worker_node",supervisor_node)

        builder.add_edge("tools_node",'worker_node')

        graph = builder.compile()

        return graph


    except Exception as e:
        return f"Error in our graph builder {e}" 