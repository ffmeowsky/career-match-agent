"""Agent 工具 Schema 注册表——OpenAI function calling 格式。

Day 12：只定义 Schema，不实现。每个工具的 name/description/parameters
是 LLM 选择工具的唯一依据——description 必须写到"傻瓜也能正确选择"的程度。

用法:
    from src.agent.tool_schemas import TOOL_SCHEMAS

    # 传给 LLM 的 tools 参数
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

注意：所有工具的 parameters 为空——参数由 Agent 引擎根据当前状态注入，
LLM 只负责选择"调用哪个工具"，不负责传参。
"""

# ============================================================
# 单个 Schema 定义
# ============================================================

SCHEMA_SCORE_SKILL_MATCH = {
    "type": "function",
    "function": {
        "name": "score_skill_match",
        "description": (
            "将简历与 JD 在 8 个维度上逐项比对并打分（0-100）。"
            "8 个维度：技能、经验、学历、项目、软素质、行业认知、产品方法论、成长潜力。"
            "每维输出：分数 + full_match/partial_match/no_match + 一句证据。"
            "最后输出综合分 + 一句话判定（如'建议投递，但需补强 2 个维度'）。"
            "什么时候用：所有分析的第一步——必须先知道差距在哪。"
            "什么时候不用：JD 信息严重不足且补全失败时——降级为部分维度评分。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SCHEMA_SCORE_PROJECT_RELEVANCE = {
    "type": "function",
    "function": {
        "name": "score_project_relevance",
        "description": (
            "逐一评估简历中的每个项目与目标岗位的相关性（0-5 分）。"
            "判断维度：方向是否对口、深度（课程作业级/Demo 级/可上线级）、"
            "技术栈是否匹配 JD 关键词。每个项目输出相关性分 + 一句点评 + 提升建议。"
            "什么时候用：简历中有至少 1 个项目时——对 PM 岗尤其重要，"
            "因为产品岗的项目相关性比技能关键词匹配更能说明问题。"
            "什么时候不用：简历项目列表为空——跳过，标注'无项目经历'。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SCHEMA_IDENTIFY_SKILL_GAP = {
    "type": "function",
    "function": {
        "name": "identify_skill_gap",
        "description": (
            "基于技能匹配和项目评估结果，找出候选人最关键的 2-3 个能力缺口。"
            "每个缺口输出：① 缺口描述（JD 要什么、你差什么）"
            "② 面试影响评估（会不会被直接挂？还是可以补救？）"
            "③ 逐字稿级面试话术（面试时怎么说）"
            "④ 置信度（high/medium/low）。"
            "什么时候用：score_skill_match 完成后，且存在 no_match 或 partial_match 维度。"
            "什么时候不用：全部 8 维都是 full_match——无可识别缺口，跳过。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SCHEMA_EXTRACT_UNIQUE_ADVANTAGES = {
    "type": "function",
    "function": {
        "name": "extract_unique_advantages",
        "description": (
            "从简历和匹配结果中挖掘候选人针对这个岗位的最强卖点（Top 3）。"
            "不是泛泛的'学习能力强'，而是有具体证据支撑的、面试官听完会记住的优势。"
            "每条输出：标题 + 详细说明（具体做了什么、成果是什么）"
            "+ 为什么这条优势对这个岗位重要。"
            "什么时候用：匹配分析完成后——即使整体匹配度 50%，"
            "也需要帮用户找到能打的牌。"
            "什么时候不用：几乎没有——总有相对优势可以挖掘。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SCHEMA_PREDICT_INTERVIEW_QUESTIONS = {
    "type": "function",
    "function": {
        "name": "predict_interview_questions",
        "description": (
            "基于 JD 要求和候选人能力缺口，预测面试官最可能问的 5 道题。"
            "覆盖 4 种题型：产品 sense、技术理解、行为面试、情景题。"
            "每道题输出：题目原文 + 面试官为什么问（考察点分析）"
            "+ 参考回答框架与要点 + 被问概率（high/medium/low）。"
            "题目按被问概率从高到低排序。"
            "什么时候用：缺口分析和优势提炼都完成后——面试题应该基于真实差距生成。"
            "什么时候不用：JD 信息严重不足——此时生成的面试题质量不可控，不生成。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SCHEMA_GENERATE_COVER_LETTER = {
    "type": "function",
    "function": {
        "name": "generate_cover_letter",
        "description": (
            "生成一封 ≤300 字的个性化求职信。"
            "结构：开头（对公司和岗位的了解）+ 中间（2-3 个匹配点 + 证据）"
            "+ 结尾（call to action）。语调自然专业，不说套话。"
            "什么时候用：用户明确请求时（P2 优先级）。"
            "什么时候不用：默认不自动生成——求职信是锦上添花，不是核心差异化。"
            "注意：这个工具不自动触发，只有当 Agent 判断'用户已请求'时才调用。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

# ============================================================
# 汇总
# ============================================================

SCHEMA_SUGGEST_RESUME_EDITS = {
    "type": "function",
    "function": {
        "name": "suggest_resume_edits",
        "description": (
            "针对目标 JD，给出简历的逐条定制优化建议（原文→改写→理由）。"
            "只基于简历已有事实做重组/突出/换措辞，绝不编造经历。"
            "什么时候用：用户主动请求'优化简历/针对这个岗位改简历'时。"
            "什么时候不用：默认不自动触发——这是用户主动操作的功能。"
            "依赖：需要先有 match_score 和 skill_gaps（即先跑完匹配分析）。"
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_SCHEMAS: list[dict] = [
    SCHEMA_SCORE_SKILL_MATCH,
    SCHEMA_SCORE_PROJECT_RELEVANCE,
    SCHEMA_IDENTIFY_SKILL_GAP,
    SCHEMA_EXTRACT_UNIQUE_ADVANTAGES,
    SCHEMA_PREDICT_INTERVIEW_QUESTIONS,
    SCHEMA_GENERATE_COVER_LETTER,
    SCHEMA_SUGGEST_RESUME_EDITS,
]

# 工具名 → Schema 映射（engine 快速查找）
TOOL_BY_NAME: dict[str, dict] = {
    schema["function"]["name"]: schema for schema in TOOL_SCHEMAS
}


# ============================================================
# 自检入口
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    print(f"工具 Schema 注册表")
    print(f"共 {len(TOOL_SCHEMAS)} 个工具:\n")

    for schema in TOOL_SCHEMAS:
        func = schema["function"]
        name = func["name"]
        desc = func["description"]
        # 取第一行（"什么时候用"之前的简述）
        short = desc.split("。")[0] if "。" in desc else desc[:80]
        print(f"  [{name}]")
        print(f"    {short}。")
        print()

    # 验证：每个 schema 必须有 name/description/parameters
    for schema in TOOL_SCHEMAS:
        assert "function" in schema, "缺少 function 键"
        func = schema["function"]
        assert "name" in func, "缺少 name"
        assert "description" in func, "缺少 description"
        assert len(func["description"]) > 50, f"{func['name']} 的 description 太短"
        assert "parameters" in func, "缺少 parameters"

    print("[OK] 全部 Schema 校验通过！")
    print(f"\nLLM 视角（tools 参数）:\n")
    print(json.dumps(TOOL_SCHEMAS, indent=2, ensure_ascii=False))
