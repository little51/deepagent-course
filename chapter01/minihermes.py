# minihermes.py —— 第 1 章：10 行以内的命令行智能体   运行：uv run python minihermes.py
from dotenv import load_dotenv; load_dotenv()
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="deepseek-v4-flash")               # 读 .env 里的 OPENAI_API_KEY / OPENAI_BASE_URL
history = []                                            # 会话上下文：一问一答都追加到这里
while (q := input("你 > ")).strip() not in ("", "exit", "quit"):
    history.append({"role": "user", "content": q})      # 记住用户说了什么
    reply = model.invoke(history).content               # 连历史一起发给模型
    history.append({"role": "assistant", "content": reply})
    print("minihermes >", reply, "\n")
