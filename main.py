from fastapi import FastAPI
from src.graph import graph_builder
import asyncio
import json
import re

app = FastAPI()


def parse_llm_json(text: str):
    if not text:
        return None

    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def main():
    graph = graph_builder()

    query = "Show me all purchase invoices from Maharashtra."
    print("Executing query: ", query)

    initial_state = {
        "user_query": query,
        "messages": [],
        "retrieved_tools": [],
        "loop_count": 0,
        "final_response": "",
        "tools_utilized": [],
        "step_timings": []
    }

    async for chunks in graph.astream(initial_state, stream_mode="updates"):
        for node_name, state_update in chunks.items():
            print(f"Finished running: {node_name}")

            if "step_timings" in state_update:
                for timing in state_update["step_timings"]:
                    print(
                        f"[STEP TIME] {timing['node']} = {timing['duration_sec']}s"
                    )

            if node_name == "chat_model":
                messages = state_update.get("messages", [])

                if not messages:
                    print("\n")
                    continue

                last_message = messages[-1]

                # First chat_model call usually returns tool calls, not final content.
                if last_message.tool_calls:
                    print("Tool calls requested:")
                    for tool_call in last_message.tool_calls:
                        print(f"- {tool_call['name']} args={tool_call.get('args', {})}")

                    print("\n")
                    continue

                # Final chat_model call should return JSON content.
                if last_message.content:
                    print("Final Response:")

                    result = parse_llm_json(last_message.content)

                    if result is not None:
                        print(json.dumps(result, indent=2))
                    else:
                        print("Non-JSON response:")
                        print(last_message.content)

            print("\n")


if __name__ == "__main__":
    asyncio.run(main())