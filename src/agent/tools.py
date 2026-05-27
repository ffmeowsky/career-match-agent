"""Agent 工具实现——6 个工具，每个独立可测。

每个工具的接口：输入 Pydantic 对象 → LLM 调用 → 输出 Pydantic 对象。
工具之间不互相调用（单一职责），由 engine.py 统一调度。
Prompt 定义在 src/agent/prompts.py 中。

测试方式：每个工具可单独 import 并传入 mock 数据验证输出结构。
"""

import json

from loguru import logger

from src.agent.prompts import (
    EXTRACT_UNIQUE_ADVANTAGES_PROMPT,
    GENERATE_COVER_LETTER_PROMPT,
    IDENTIFY_SKILL_GAP_PROMPT,
    PREDICT_INTERVIEW_QUESTIONS_PROMPT,
    SCORE_PROJECT_RELEVANCE_PROMPT,
    SCORE_SKILL_MATCH_PROMPT,
)
from src.models import (
    Confidence,
    CoverLetter,
    DimensionName,
    InterviewQuestion,
    JobDescription,
    MatchDimension,
    MatchLevel,
    MatchScore,
    ProjectRelevance,
    Resume,
    SkillGap,
    UniqueAdvantage,
)
from src.tools.llm_client import chat_json

# LLM 生成的维度名 → 枚举值映射（容错）
_DIMENSION_ALIASES: dict[str, str] = {
    "soft_quality": "soft_skill",
    "soft": "soft_skill",
    "skill_match": "skill",
    "experience_match": "experience",
    "education_match": "education",
    "project_match": "project",
    "industry_insight": "industry",
    "pm": "pm_method",
    "product_methodology": "pm_method",
    "growth_potential": "growth",
    "potential": "growth",
}


def _normalize_dimension(name: str) -> str:
    """将 LLM 可能返回的变体维度名标准化为 DimensionName 枚举值。"""
    name = name.strip().lower()
    if name in _DIMENSION_ALIASES:
        return _DIMENSION_ALIASES[name]
    # 检查是否为合法枚举值
    try:
        DimensionName(name)
        return name
    except ValueError:
        # 模糊匹配：包含关键字的映射
        for alias, target in _DIMENSION_ALIASES.items():
            if alias in name or name in alias:
                return target
        # 兜底：标记为 skill
        return "skill"


# ============================================================
# Tool 1: score_skill_match
# ============================================================

def score_skill_match(resume: Resume, jd: JobDescription) -> MatchScore:
    """8 维技能匹配打分。

    Args:
        resume: 简历结构化对象。
        jd: JD 结构化对象。

    Returns:
        MatchScore: 综合分 + 8 维逐项分析。
    """
    logger.info(f"工具调用: score_skill_match | 候选人={resume.name} | 岗位={jd.role}")

    user_prompt = (
        "请对以下 JD 和简历进行 8 维匹配打分：\n\n"
        f"<jd>\n{jd.model_dump_json(indent=2, ensure_ascii=False)}\n</jd>\n\n"
        f"<resume>\n{resume.model_dump_json(indent=2, ensure_ascii=False)}\n</resume>"
    )

    data = chat_json(SCORE_SKILL_MATCH_PROMPT, user_prompt)

    try:
        dimensions = []
        for d in data.get("dimensions", []):
            dim_name = _normalize_dimension(d.get("dimension", "skill"))
            dimensions.append(MatchDimension(
                dimension=DimensionName(dim_name),
                label=d.get("label", ""),
                score=float(d.get("score", 0)),
                level=MatchLevel(d.get("level", "partial_match")),
                evidence=d.get("evidence", ""),
                details=d.get("details", []),
            ))

        result = MatchScore(
            overall=float(data.get("overall", 0)),
            dimensions=dimensions,
            verdict=data.get("verdict", ""),
        )
        logger.info(
            f"score_skill_match 完成 | overall={result.overall} | "
            f"维度数={len(result.dimensions)}"
        )
        return result

    except Exception as e:
        logger.error(f"score_skill_match Pydantic 校验失败: {e}")
        raise ValueError(f"技能匹配结果格式异常: {e}") from e


# ============================================================
# Tool 2: score_project_relevance
# ============================================================

def score_project_relevance(
    projects: list, jd: JobDescription
) -> list[ProjectRelevance]:
    """项目相关性评估。

    Args:
        projects: 简历中的项目列表（list[ResumeProject]）。
        jd: JD 结构化对象。

    Returns:
        list[ProjectRelevance]: 每个项目的相关性评估。
    """
    logger.info(
        f"工具调用: score_project_relevance | 项目数={len(projects)} | 岗位={jd.role}"
    )

    projects_json = []
    for p in projects:
        projects_json.append({
            "name": p.name,
            "role": p.role,
            "duration": p.duration,
            "description": p.description,
            "highlights": p.highlights,
        })

    user_prompt = (
        "请评估以下项目与 JD 的相关性：\n\n"
        f"<jd>\n{jd.model_dump_json(indent=2, ensure_ascii=False)}\n</jd>\n\n"
        f"<projects>\n{json.dumps(projects_json, indent=2, ensure_ascii=False)}"
        f"\n</projects>"
    )

    data = chat_json(SCORE_PROJECT_RELEVANCE_PROMPT, user_prompt)

    try:
        results = []
        for item in data:
            results.append(ProjectRelevance(
                project_name=item.get("project_name", ""),
                relevance_score=float(item.get("relevance_score", 0)),
                direction_match=item.get("direction_match", ""),
                depth_assessment=item.get("depth_assessment", ""),
                key_evidence=item.get("key_evidence", ""),
                suggestion=item.get("suggestion", ""),
            ))
        logger.info(f"score_project_relevance 完成 | 评估 {len(results)} 个项目")
        return results

    except Exception as e:
        logger.error(f"score_project_relevance Pydantic 校验失败: {e}")
        raise ValueError(f"项目相关性评估结果格式异常: {e}") from e


# ============================================================
# Tool 3: identify_skill_gap
# ============================================================

def identify_skill_gap(
    match_score: MatchScore,
    project_relevance: list[ProjectRelevance],
    jd: JobDescription,
    resume: Resume,
) -> list[SkillGap]:
    """能力缺口识别。

    Args:
        match_score: 8 维匹配结果。
        project_relevance: 项目相关性列表。
        jd: JD 对象。
        resume: 简历对象。

    Returns:
        list[SkillGap]: 2-3 个关键缺口。
    """
    logger.info(f"工具调用: identify_skill_gap | 候选人={resume.name}")

    low_dims = [
        f"{d.label}: {d.score}分 ({d.level.value}) - {d.evidence}"
        for d in match_score.dimensions
        if d.score < 75
    ]

    context = {
        "match_overall": match_score.overall,
        "verdict": match_score.verdict,
        "low_dimensions": low_dims,
        "project_relevance": [
            {"name": p.project_name, "score": p.relevance_score,
             "key": p.key_evidence}
            for p in project_relevance
        ],
        "jd_requirements": [
            {"content": r.content, "type": r.type.value, "category": r.category}
            for r in jd.requirements
        ],
        "candidate_name": resume.name,
        "candidate_projects": [p.name for p in resume.projects],
        "candidate_skills": [s.name for s in resume.skills],
    }

    user_prompt = (
        "请基于以下匹配结果找出候选人的关键能力缺口（2-3 个）：\n\n"
        f"<context>\n{json.dumps(context, indent=2, ensure_ascii=False)}\n</context>"
    )

    data = chat_json(IDENTIFY_SKILL_GAP_PROMPT, user_prompt)

    try:
        results = []
        for item in data:
            conf = item.get("confidence", "medium")
            if conf not in {"high", "medium", "low"}:
                conf = "medium"
            results.append(SkillGap(
                gap=item.get("gap", ""),
                impact=item.get("impact", ""),
                talking_points=item.get("talking_points", ""),
                confidence=Confidence(conf),
            ))
        logger.info(f"identify_skill_gap 完成 | 识别 {len(results)} 个缺口")
        return results

    except Exception as e:
        logger.error(f"identify_skill_gap Pydantic 校验失败: {e}")
        raise ValueError(f"能力缺口分析结果格式异常: {e}") from e


# ============================================================
# Tool 4: extract_unique_advantages
# ============================================================

def extract_unique_advantages(
    resume: Resume,
    jd: JobDescription,
    match_score: MatchScore,
    project_relevance: list[ProjectRelevance],
) -> list[UniqueAdvantage]:
    """差异化优势提取。

    Args:
        resume: 简历对象。
        jd: JD 对象。
        match_score: 8 维匹配结果。
        project_relevance: 项目相关性列表。

    Returns:
        list[UniqueAdvantage]: Top 3 差异化优势。
    """
    logger.info(f"工具调用: extract_unique_advantages | 候选人={resume.name}")

    high_dims = [
        f"{d.label}: {d.score}分 - {d.evidence}"
        for d in match_score.dimensions
        if d.score >= 75
    ]
    top_projects = [
        {"name": p.project_name, "score": p.relevance_score,
         "evidence": p.key_evidence}
        for p in project_relevance
        if p.relevance_score >= 3
    ]

    education_str = (
        f"{resume.education[0].school} {resume.education[0].major}"
        if resume.education else ""
    )

    context = {
        "candidate_name": resume.name,
        "target_role": resume.target_role,
        "education": education_str,
        "skills": [s.name for s in resume.skills],
        "projects": [
            {"name": p.name, "description": p.description,
             "highlights": p.highlights}
            for p in resume.projects
        ],
        "jd_company": jd.company,
        "jd_role": jd.role,
        "high_dimensions": high_dims,
        "top_projects": top_projects,
        "verdict": match_score.verdict,
    }

    user_prompt = (
        "请基于以下信息提炼候选人的差异化优势 Top 3：\n\n"
        f"<context>\n{json.dumps(context, indent=2, ensure_ascii=False)}\n</context>"
    )

    data = chat_json(EXTRACT_UNIQUE_ADVANTAGES_PROMPT, user_prompt)

    try:
        results = []
        for item in data:
            results.append(UniqueAdvantage(
                title=item.get("title", ""),
                detail=item.get("detail", ""),
                why_matters=item.get("why_matters", ""),
            ))
        logger.info(f"extract_unique_advantages 完成 | 提取 {len(results)} 条优势")
        return results

    except Exception as e:
        logger.error(f"extract_unique_advantages Pydantic 校验失败: {e}")
        raise ValueError(f"差异化优势提取结果格式异常: {e}") from e


# ============================================================
# Tool 5: predict_interview_questions
# ============================================================

def predict_interview_questions(
    jd: JobDescription,
    skill_gaps: list[SkillGap],
    advantages: list[UniqueAdvantage],
    match_score: MatchScore,
    resume: Resume,
) -> list[InterviewQuestion]:
    """面试题预测。

    Args:
        jd: JD 对象。
        skill_gaps: 能力缺口列表。
        advantages: 差异化优势列表。
        match_score: 8 维匹配结果。
        resume: 简历对象。

    Returns:
        list[InterviewQuestion]: 5 道面试预测题。
    """
    logger.info(f"工具调用: predict_interview_questions | 岗位={jd.role}")

    context = {
        "jd_company": jd.company,
        "jd_role": jd.role,
        "jd_requirements": [
            {"content": r.content, "type": r.type.value, "category": r.category}
            for r in jd.requirements
        ],
        "gaps": [{"gap": g.gap, "impact": g.impact} for g in skill_gaps],
        "advantages": [{"title": a.title, "detail": a.detail} for a in advantages],
        "low_dimensions": [
            f"{d.label}: {d.score}分"
            for d in match_score.dimensions if d.score < 75
        ],
        "candidate_projects": [p.name for p in resume.projects],
    }

    user_prompt = (
        "请基于以下信息预测 5 道面试题：\n\n"
        f"<context>\n{json.dumps(context, indent=2, ensure_ascii=False)}\n</context>"
    )

    data = chat_json(PREDICT_INTERVIEW_QUESTIONS_PROMPT, user_prompt)

    try:
        results = []
        for item in data:
            conf = item.get("confidence", "medium")
            if conf not in {"high", "medium", "low"}:
                conf = "medium"
            results.append(InterviewQuestion(
                question=item.get("question", ""),
                why_asked=item.get("why_asked", ""),
                suggested_answer=item.get("suggested_answer", ""),
                category=item.get("category", "产品sense"),
                confidence=Confidence(conf),
            ))
        logger.info(f"predict_interview_questions 完成 | 生成 {len(results)} 道题")
        return results

    except Exception as e:
        logger.error(f"predict_interview_questions Pydantic 校验失败: {e}")
        raise ValueError(f"面试题预测结果格式异常: {e}") from e


# ============================================================
# Tool 6: generate_cover_letter
# ============================================================

def generate_cover_letter(
    resume: Resume,
    jd: JobDescription,
    advantages: list[UniqueAdvantage],
    match_score: MatchScore,
) -> CoverLetter:
    """个性化求职信生成。

    Args:
        resume: 简历对象。
        jd: JD 对象。
        advantages: 差异化优势列表。
        match_score: 匹配结果——决定求职信的自信程度。

    Returns:
        CoverLetter: 求职信。
    """
    logger.info(
        f"工具调用: generate_cover_letter | 候选人={resume.name} | 岗位={jd.role}"
    )

    education_str = (
        f"{resume.education[0].school} {resume.education[0].degree.value} "
        f"{resume.education[0].major}" if resume.education else ""
    )
    top_project = (
        {"name": resume.projects[0].name,
         "description": resume.projects[0].description}
        if resume.projects else None
    )

    context = {
        "candidate_name": resume.name,
        "target_role": resume.target_role,
        "education": education_str,
        "skills": [s.name for s in resume.skills],
        "top_project": top_project,
        "jd_company": jd.company,
        "jd_role": jd.role,
        "advantages": [{"title": a.title, "detail": a.detail} for a in advantages],
        "match_overall": match_score.overall,
    }

    user_prompt = (
        "请基于以下信息生成一封个性化求职信：\n\n"
        f"<context>\n{json.dumps(context, indent=2, ensure_ascii=False)}\n</context>"
    )

    data = chat_json(GENERATE_COVER_LETTER_PROMPT, user_prompt)

    try:
        result = CoverLetter(
            greeting=data.get("greeting", "面试官你好，"),
            body=data.get("body", ""),
            closing=data.get("closing", "秦俪萍"),
            word_count=int(data.get("word_count", 0)),
        )
        logger.info(f"generate_cover_letter 完成 | 字数={result.word_count}")
        return result

    except Exception as e:
        logger.error(f"generate_cover_letter Pydantic 校验失败: {e}")
        raise ValueError(f"求职信生成结果格式异常: {e}") from e
