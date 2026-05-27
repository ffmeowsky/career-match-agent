"""JD 解析器——纯文本 JD → JobDescription Pydantic 对象。

与 resume_parser 的核心差异：
- 简历：信息提取              → JD：信息提取 + 去噪 + 黑话翻译 + must/nice 归类
- 简历：结构化程度高          → JD：格式高度不统一
- 简历：Few-shot 辅助          → JD：Few-shot 是关键

链路：parse_jd() → chat_json() → _build_requirements() → Pydantic 校验
"""

from loguru import logger

from src.models import JDRequirement, JobDescription, RequirementType
from src.tools.llm_client import chat_json

# ============================================================
# Prompt
# ============================================================

JD_PARSE_SYSTEM_PROMPT = """你是一个 JD（Job Description）解析器。你的任务是将招聘文案解析为结构化 JSON。

## 你的三个核心任务

1. **提取**：从 JD 中提取公司名、岗位名、地点、职责、任职要求
2. **去噪**：过滤掉与"这个岗位要求候选人具备什么"无关的内容
3. **归类**：区分硬性要求（must_have）和加分项（nice_to_have）

## JSON 结构

{
  "company": "公司名（没有填'未知'）",
  "role": "岗位名",
  "location": "工作地点（没有填'未知'）",
  "summary": "一句话岗位摘要——这个岗位的核心职责是什么",
  "responsibilities": ["职责1", "职责2"],
  "requirements": [
    {
      "content": "要求原文（保留措辞，不要改写）",
      "type": "must_have | nice_to_have",
      "category": "学历 | 技能 | 经验 | 项目 | 软素质 | 其他"
    }
  ],
  "info_sufficient": true
}

## 去噪规则（以下内容不要提取到 requirements 中）

- 公司介绍（"我们是XX行业的领导者"）
- 团队描述（"团队由算法、工程、产品组成"）
- 福利待遇（"一日三餐、健身房、期权、六险一金"）
- 薪资描述（"薪资 open""上不封顶""有竞争力的薪酬"）
- 价值观口号（"改变世界""极致追求""用科技让生活更美好"）
- 应聘流程（"请将简历发送至...""面试共三轮"）

## must_have vs nice_to_have 归类规则

按以下优先级判断（先匹配到的规则胜出）：

1. 在"加分项""优先条件""nice to have""加分"小标题下的要求 → nice_to_have
2. 句子含"优先""加分""更好""更佳""plus""preferred" → nice_to_have
3. 句子含"必须""需要""要求""should have""must have" → must_have
4. 以上都不满足 → 默认 must_have（宁可严格，不误投）

## category 归类规则

- 提到学位、专业、学校、应届/往届 → "学历"
- 提到具体技术、工具、编程语言、框架 → "技能"
- 提到工作年限、行业背景、管理经验 → "经验"
- 提到作品集、项目经历、开源贡献 → "项目"
- 提到沟通、逻辑、抗压、自驱、协作 → "软素质"
- 不符合以上 → "其他"

## info_sufficient 判断规则

- JD 文本 < 50 字 且 提取到的 requirements < 2 条 → false
- JD 几乎全是公司介绍，无实质要求 → false
- 其他情况 → true
- 注意：即使 info_sufficient=false，也要尽力提取已有信息，不要返回空对象

## 互联网黑话辅助表（不改写原文，只帮助正确归类）

| 原文 | 含义提示 |
|------|---------|
| "皮实""能扛事" | 情绪稳定、抗压能力 → 软素质 |
| "有创业精神" | 能身兼多职、职责不固定 → 软素质 |
| "快速成长""学习能力强" | 入职即上手、自学能力 → 软素质 |
| "owner 意识" | 主动负责、不推诿 → 软素质 |
| "扁平化管理" | 可能是公司描述，不是候选人要求 → 过滤 |

## Few-shot 示例

示例 1 —— 去噪：
输入 JD 片段：「我们能提供一日三餐 + 无限零食 + 健身房 + 六险一金」
→ 这段不提取到 requirements 中，因为属于福利待遇。

示例 2 —— 黑话归类：
输入要求：「希望你皮实，能承担快节奏的迭代压力」
→ {"content": "皮实，能承担快节奏的迭代压力", "type": "must_have", "category": "软素质"}

示例 3 —— 加分识别：
输入要求：「有 AI 产品作品优先」
→ {"content": "有 AI 产品作品", "type": "nice_to_have", "category": "项目"}

示例 4 —— 技术术语（不需要理解术语含义）：
输入 JD 片段：「熟悉 Transformer 架构，有 CUDA 编程经验优先，掌握 vLLM 推理框架」
→ [
  {"content": "熟悉 Transformer 架构", "type": "must_have", "category": "技能"},
  {"content": "有 CUDA 编程经验", "type": "nice_to_have", "category": "技能"},
  {"content": "掌握 vLLM 推理框架", "type": "must_have", "category": "技能"}
]
（"优先"→nice_to_have，其余默认→must_have）

示例 5 —— 信息不足：
输入 JD：「招 AI PM，坐标北京，感兴趣私聊。」
→ info_sufficient=false（< 50 字且无实质 requirements），但仍提取已有信息。

## 输出要求

只输出一个 JSON 对象，不要包含任何其他文字或 markdown 标记。"""


def build_jd_prompt(raw_text: str) -> tuple[str, str]:
    """构造 JD 解析的 system + user prompt。

    Args:
        raw_text: JD 纯文本。

    Returns:
        (system_prompt, user_prompt) 元组。
    """
    user_prompt = (
        "请解析以下 JD 文本，输出 JSON：\n\n"
        f"<jd_text>\n{raw_text}\n</jd_text>"
    )
    return JD_PARSE_SYSTEM_PROMPT, user_prompt


# ============================================================
# LLM 输出 → JobDescription 对象
# ============================================================

def _build_requirements(raw_list: list[dict]) -> list[JDRequirement]:
    """将 LLM 返回的 requirements 列表转为 JDRequirement 对象列表。

    做类型容错：requirement type 不在枚举范围内时默认 must_have。
    """
    result: list[JDRequirement] = []
    for item in raw_list:
        req_type = item.get("type", "must_have")
        # 容错：LLM 可能返回中文或变体
        if req_type not in {"must_have", "nice_to_have"}:
            req_type = "must_have"
        result.append(
            JDRequirement(
                content=item.get("content", ""),
                type=RequirementType(req_type),
                category=item.get("category", "技能"),
            )
        )
    return result


def parse_jd_with_llm(raw_text: str) -> JobDescription:
    """调用 DeepSeek 将 JD 纯文本解析为 JobDescription 对象。

    Args:
        raw_text: JD 纯文本。

    Returns:
        经过 Pydantic 校验的 JobDescription 对象。

    Raises:
        RuntimeError: LLM 调用失败。
        ValueError: Pydantic 校验失败。
    """
    system_prompt, user_prompt = build_jd_prompt(raw_text)
    logger.info(f"开始 LLM 解析 JD | 文本长度: {len(raw_text)} 字符")

    data = chat_json(system_prompt, user_prompt)

    try:
        requirements = _build_requirements(data.get("requirements", []))

        jd = JobDescription(
            company=data.get("company", "未知"),
            role=data.get("role", ""),
            location=data.get("location", "未知"),
            summary=data.get("summary", ""),
            responsibilities=data.get("responsibilities", []),
            requirements=requirements,
            raw_text=raw_text,
            info_sufficient=data.get("info_sufficient", True),
        )
        logger.info(
            f"JD 解析完成 | 公司={jd.company} | 岗位={jd.role} | "
            f"must_have={sum(1 for r in jd.requirements if r.type == RequirementType.MUST_HAVE)}项 | "
            f"nice_to_have={sum(1 for r in jd.requirements if r.type == RequirementType.NICE_TO_HAVE)}项 | "
            f"info_sufficient={jd.info_sufficient}"
        )
        return jd

    except Exception as e:
        logger.error(f"Pydantic 校验失败，LLM 输出与模型不匹配: {e}")
        raise ValueError(
            f"JD 解析结果与预期结构不匹配，可能是 LLM 输出格式异常。"
            f"原始错误: {e}"
        ) from e


# ============================================================
# 入口
# ============================================================

def parse_jd(jd_text: str) -> JobDescription:
    """主入口：JD 纯文本 → JobDescription 对象。

    Args:
        jd_text: JD 完整文本。

    Returns:
        完整的 JobDescription Pydantic 对象（含 raw_text）。
    """
    text = jd_text.strip()

    if len(text) < 30:
        logger.warning(f"JD 文本过短 ({len(text)} 字符)，解析结果可能不完整")

    logger.info(f"开始解析 JD | 文本长度: {len(text)} 字符")
    jd = parse_jd_with_llm(text)
    return jd


# ============================================================
# 自检入口
# ============================================================

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    # 用 DEMO_JD_PARSER.md 里的豆包 JD 做自检
    test_jd = """【字节跳动】豆包 AI 产品经理（应届生）

我们是谁
豆包是字节跳动旗下的 AI 智能助手，目前国内用户规模最大的大模型 C 端产品之一。

你会做什么
- 参与豆包 C 端核心功能的需求定义与版本迭代
- 通过用户访谈、数据分析发现产品机会，独立输出 PRD 并推动落地
- 跟踪国内外 AI 产品动态，定期输出竞品分析

我们希望你
- 2026 届应届生，计算机/AI 相关背景优先
- 理解大模型基本概念（LLM、Prompt Engineering、RAG）
- 逻辑清晰，能把模糊问题拆成可执行步骤
- 皮实，能承担快节奏的迭代压力

加分项
- 有自己的 AI 产品作品
- 写过 prompt 或搭过 AI workflow

我们能提供
- 和国内最优秀的 AI 产品团队一起工作
- 一日三餐 + 健身房 + 无限零食
"""

    try:
        result = parse_jd(test_jd)
        print(f"\n[OK] JD 解析成功!")
        print(f"  公司: {result.company}")
        print(f"  岗位: {result.role}")
        print(f"  地点: {result.location}")
        print(f"  摘要: {result.summary}")
        print(f"  职责 ({len(result.responsibilities)}):")
        for r in result.responsibilities:
            print(f"    - {r}")
        print(f"  要求 ({len(result.requirements)} 条):")
        for req in result.requirements:
            type_label = "[硬性]" if req.type == RequirementType.MUST_HAVE else "[加分]"
            print(f"    {type_label} [{req.category}] {req.content}")
        print(f"  信息充足: {result.info_sufficient}")
        # 验证去噪效果
        has_benefit = any("食堂" in r.content or "零食" in r.content for r in result.requirements)
        if has_benefit:
            print(f"  [WARN] 福利内容未被过滤!")
        else:
            print(f"  [OK] 福利内容已正确过滤")
    except Exception as e:
        logger.error(f"自检失败: {e}")
        print(f"\n[FAIL] JD 解析失败: {e}")
