# minihermes.py —— 第 5 章：让它记住你（跨进程的长期记忆）
# 运行：uv run python chapter05/minihermes.py
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from web_tools import fetch_url, web_search

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent / "workspace"
MEM_FILE = WORKSPACE / "memories" / "AGENTS.md"      # 长期记忆就住在这个文件里
MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
if not MEM_FILE.exists():
    MEM_FILE.write_text("# 关于用户的长期事实\n", encoding="utf-8")

SYSTEM = (
    "你是 minihermes，用中文回答，回答尽量简短。"
    "/memories/AGENTS.md 里记的关于用户的长期事实，每次回答前先看一眼；"
    "用户说了值得长期记住的信息，就用 edit_file 写进去。"
)

agent = create_deep_agent(
    model=ChatOpenAI(model="deepseek-v4-flash"),
    system_prompt=SYSTEM,
    tools=[web_search, fetch_url],
    backend=FilesystemBackend(root_dir=str(WORKSPACE)),
    memory=["/memories/AGENTS.md"],       # 启动时读进来，干活时可以改
    checkpointer=InMemorySaver(),
)
config = {"configurable": {"thread_id": "minihermes"}}


def turn(text: str) -> None:
    for step in agent.stream({"messages": [HumanMessage(content=text)]}, config=config, stream_mode="updates"):
        for update in step.values():
            for m in (update or {}).get("messages") or []:
                for tc in getattr(m, "tool_calls", None) or []:
                    print("   →", tc["name"], str(tc["args"])[:90])
                if type(m).__name__ == "ToolMessage":
                    print("   ←", str(m.content).replace("\n", " ")[:90])
                elif getattr(m, "content", ""):
                    print("minihermes >", m.content, "\n")


if __name__ == "__main__":
    while (q := input("你 > ")).strip() not in ("", "exit", "quit"):
        turn(q)
    print("\n=== 它现在记着这些（memories/AGENTS.md）===")
    print(MEM_FILE.read_text(encoding="utf-8").strip())
