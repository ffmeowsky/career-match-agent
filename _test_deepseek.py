"""DeepSeek API 连通性测试 — 临时脚本，验证完成后可删除。"""
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# 强制 UTF-8，避免 Windows GBK 编码报错
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key or api_key == "your_key_here":
    print("[FAIL] 请先创建 .env 文件并填入真实的 DEEPSEEK_API_KEY")
    print("       cp .env.example .env  ->  然后编辑 .env，替换 your_key_here")
    exit(1)

client = OpenAI(
    api_key=api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME", "deepseek-chat"),
    messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
    max_tokens=100,
)

print("[OK] DeepSeek API 连接成功!")
print(f"[REPLY] {response.choices[0].message.content}")
