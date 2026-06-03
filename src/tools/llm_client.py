"""LLM 调用封装——统一入口，含 retry、日志、错误处理。

替代 resume_parser 和 jd_parser 中各自内联的 _call_llm()。

用法:
    from src.tools.llm_client import chat_json

    data = chat_json(system_prompt, user_prompt)
"""

import json
import os
import time

import httpx
from loguru import logger
from openai import OpenAI

from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME

# ============================================================
# 配置
# ============================================================

MAX_RETRIES = 3  # 最多重试次数（总共 4 次尝试）

# 从环境变量读取代理配置
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "") or os.getenv("https_proxy", "")
HTTP_PROXY = os.getenv("HTTP_PROXY", "") or os.getenv("http_proxy", "")


# ============================================================
# 底层调用
# ============================================================

def _call_api(messages: list[dict], temperature: float = 0.1) -> str:
    """单次 API 调用（不含 retry 逻辑）。

    Args:
        messages: OpenAI 格式的消息列表。
        temperature: 生成温度，解析类任务建议 0.1。

    Returns:
        LLM 返回的原始文本内容。

    Raises:
        openai 相关异常：网络、认证、限流等。
    """
    # 构造带代理的 httpx 客户端
    http_kwargs: dict = {}
    if HTTPS_PROXY:
        http_kwargs["proxy"] = HTTPS_PROXY
        logger.debug(f"使用代理: {HTTPS_PROXY}")
    else:
        logger.debug("未检测到代理，直连 API")

    http_client = httpx.Client(**http_kwargs)
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        http_client=http_client,
    )

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    elapsed = time.perf_counter() - t0

    usage = response.usage
    if usage:
        logger.info(
            f"LLM 调用完成 | model={MODEL_NAME} | "
            f"prompt_tokens={usage.prompt_tokens} | "
            f"completion_tokens={usage.completion_tokens} | "
            f"elapsed={elapsed:.2f}s"
        )

    return response.choices[0].message.content or ""


# ============================================================
# 公开 API
# ============================================================

def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """调用 LLM 并返回解析后的 JSON dict。

    内含自动 retry：遇到网络错误或 JSON 解析失败时，指数退避重试。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        temperature: 生成温度。
        max_retries: 最多重试次数，默认 3（总共 4 次尝试）。

    Returns:
        LLM 返回的 JSON dict。

    Raises:
        RuntimeError: 重试耗尽后仍失败。
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):  # +2 因为 range 不含上界
        try:
            content = _call_api(messages, temperature=temperature)
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(
                f"LLM 返回非 JSON | attempt={attempt}/{max_retries + 1} | "
                f"原始内容前 200 字符: {content[:200]}"
            )
            last_error = ValueError(f"LLM 返回的内容不是合法 JSON: {e}")

        except Exception as e:
            logger.error(
                f"LLM 调用失败 | attempt={attempt}/{max_retries + 1} | "
                f"错误类型: {type(e).__name__} | 错误: {e}"
            )
            last_error = e

            if attempt > max_retries:
                break

            # 指数退避：1s → 2s → 4s
            backoff = 2 ** (attempt - 1)
            logger.info(f"指数退避 {backoff}s 后重试...")
            time.sleep(backoff)

    raise RuntimeError(
        f"DeepSeek API 调用失败（已重试 {max_retries} 次）。"
        f"请检查 API Key 是否有效、网络是否可达。"
        f"原始错误: {last_error}"
    ) from last_error


# ============================================================
# 自检入口
# ============================================================

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    # 用简单的 JD 解析测试连通性
    result = chat_json(
        system_prompt="你是一个 JSON 输出器。只输出 JSON，不要其他文字。",
        user_prompt='请输出 {"status": "ok", "message": "LLM 客户端自检通过"}',
    )
    print(f"[OK] LLM 客户端自检通过: {result}")
