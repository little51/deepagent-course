# minihermes.py —— 第 4 章：给它一份技能（SKILL.md），让它按套路干活
# 运行：uv run python chapter04/minihermes.py
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, FilesystemBackend

from web_tools import fetch_url, web_search

HERE = Path(__file__).resolve().parent          # chapter04/
WORKSPACE = HERE.parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)

SYSTEM = (
    "你是 minihermes，用中文回答。工具和技能的说明都在你的上下文里，照着用。"
    "干活过程中不要输出「让我先看看……」这类说明，直接做，最后再给结论。"
)

model = ChatOpenAI(model="deepseek-v4-flash")
agent = create_deep_agent(
    model=model,
    system_prompt=SYSTEM,
    tools=[web_search, fetch_url],
    backend=CompositeBackend(
        default=FilesystemBackend(root_dir=str(WORKSPACE)),           # 干活的地方
        routes={"/skills/": FilesystemBackend(root_dir=str(HERE / "skills"))},   # 技能目录挂到 /skills/
    ),
    skills=["/skills/"],            # 技能只在需要时才加载（启动只读每个技能的 name 和 description）
    permissions=[
        FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    ],                              # 技能是"手艺"，只读，不许 agent 自己改
    checkpointer=InMemorySaver(),
)
config = {"configurable": {"thread_id": "minihermes"}}

while (q := input("你 > ")).strip() not in ("", "exit", "quit"):
    for step in agent.stream({"messages": [HumanMessage(content=q)]}, config=config, stream_mode="updates"):
        for update in step.values():
            for m in (update or {}).get("messages") or []:
                for tc in getattr(m, "tool_calls", None) or []:
                    print("   →", tc["name"], str(tc["args"])[:90])
                if type(m).__name__ == "ToolMessage":
                    print("   ←", str(m.content).replace("\n", " ")[:90])
                elif getattr(m, "content", ""):
                    print("minihermes >", m.content, "\n")
