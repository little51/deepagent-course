# minihermes.py —— 第 6 章：让它动手干活（执行代码/命令，危险动作先问人）
# 运行：uv run python chapter06/minihermes.py
import json
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_quickjs import CodeInterpreterMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from web_tools import fetch_url, web_search

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)

# git bash 的位置：优先读环境变量，其次在 PATH 里找（在 git bash 里跑时一定能找到）
BASH = os.environ.get("MINIHERMES_BASH") or shutil.which("bash")

# 第一道闸门：几条真会毁机器的命令，工具自己先拦掉
BLOCKED = ("rm -rf /", "rm -rf /*", "mkfs", "format ", "shutdown", "reboot", ":(){", "rd /s /q c:\\")


def run_bash(command: str) -> str:
    """在工作目录里用 git bash 执行一条命令，返回退出码和输出。

    什么时候用：需要跑脚本、看目录、算文件、装依赖时。
    命令已经在工作目录里执行了，所以**写相对路径就行**（例如 `python hello.py`）。
    不要写 /e/... 这类路径：文件工具看到的 "/" 和工作目录不是一回事，混用会找不到文件。
    命令超过 60 秒会被掐断。
    """
    low = command.lower()
    for bad in BLOCKED:
        if bad in low:
            return f"被安全策略拦下（命令里出现了「{bad}」）：{command}"
    if not BASH:
        return "找不到 bash：请在环境变量 MINIHERMES_BASH 里写上 git bash 的 bash.exe 路径"
    try:
        r = subprocess.run(
            [BASH, "-c", command],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return f"命令超过 60 秒，被掐断了：{command}"
    out = (r.stdout or "") + (r.stderr or "")
    return f"exit={r.returncode}\n{out[:2000]}"


SYSTEM = (
    "你是 minihermes，用中文回答，回答尽量简短。"
    "要动命令或跑代码之前，先用一两句话说明你要做什么。"
    "跑 shell 命令用 run_bash；只是想算点东西、处理点数据，用 eval 里的 JavaScript。"
    "注意：文件工具里的 / 就是工作目录，跑命令时用相对路径（例如 python hello.py），不要拼 /e/... 这类路径。"
)

agent = create_deep_agent(
    model=ChatOpenAI(model="deepseek-v4-flash"),
    system_prompt=SYSTEM,
    tools=[web_search, fetch_url, run_bash],
    middleware=[CodeInterpreterMiddleware()],   # 内存里的 JS 解释器：不碰系统、不联网
    backend=FilesystemBackend(root_dir=str(WORKSPACE)),
    interrupt_on={"run_bash": True},            # 第二道闸门：跑命令前必须问人
    checkpointer=InMemorySaver(),
)
config = {"configurable": {"thread_id": "minihermes"}}


def show(step) -> None:
    for update in step.values():
        for m in (update or {}).get("messages") or []:
            for tc in getattr(m, "tool_calls", None) or []:
                print("   →", tc["name"], str(tc["args"])[:90])
            if type(m).__name__ == "ToolMessage":
                print("   ←", str(m.content).replace("\n", " ")[:90])
            elif getattr(m, "content", ""):
                print("minihermes >", m.content, "\n")


def turn(text: str) -> None:
    inputs = {"messages": [HumanMessage(content=text)]}
    while True:
        pending = None
        for step in agent.stream(inputs, config=config, stream_mode="updates"):
            if "__interrupt__" in step:
                pending = step["__interrupt__"][0]
                continue
            show(step)
        if pending is None:
            return

        value = pending.value
        requests = value.get("action_requests", []) if isinstance(value, dict) else []
        print("\n⚠️  这一步要动你的机器，先给你看一眼：")
        for req in requests:
            print("   工具:", req.get("name") or req.get("action_name"))
            print("   参数:", json.dumps(req.get("args") or req.get("arguments"), ensure_ascii=False))
        answer = input("   同意执行吗？(y = 同意，其它 = 拒绝) > ").strip().lower()
        decision = {"type": "approve"} if answer == "y" else {"type": "reject", "message": "用户拒绝执行"}
        inputs = Command(resume={"decisions": [decision] * max(1, len(requests))})


if __name__ == "__main__":
    while (q := input("你 > ")).strip() not in ("", "exit", "quit"):
        turn(q)
    print("再见。")
