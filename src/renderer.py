"""报告渲染器——MatchReport → Markdown 字符串。

用法:
    from src.renderer import render_report
    md = render_report(report)
    Path("outputs/report.md").write_text(md, encoding="utf-8")
"""

from src.models import (
    CoverLetter,
    InterviewQuestion,
    JobDescription,
    MatchDimension,
    MatchReport,
    MatchScore,
    NextStep,
    Resume,
    SkillGap,
    UniqueAdvantage,
)


def render_report(report: MatchReport) -> str:
    """将 MatchReport 渲染为 Markdown 报告，返回完整字符串。"""
    sections: list[str] = []

    sections.append(_render_header(report))
    sections.append(_render_input_overview(report.resume, report.jd))
    sections.append(_render_match_score(report.match_score))
    sections.append(_render_dimensions(report.match_score.dimensions))
    sections.append(_render_advantages(report.advantages))
    sections.append(_render_skill_gaps(report.skill_gaps))
    if report.cover_letter:
        sections.append(_render_cover_letter(report.cover_letter))
    sections.append(_render_interview_questions(report.interview_questions))
    sections.append(_render_next_steps(report.next_steps))
    sections.append(_render_footer(report))

    return "\n\n".join(sections) + "\n"


# ============================================================
# Section helpers
# ============================================================


def _render_header(report: MatchReport) -> str:
    return (
        f"# CareerMatch Agent · 匹配分析报告\n\n"
        f"> 模型：{report.model_used} | 生成时间：{report.generated_at[:19]}"
    )


def _render_input_overview(resume: Resume, jd: JobDescription) -> str:
    lines = ["## 一、输入概览", "", "### JD 信息", ""]
    lines.append(f"| 字段 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 公司 | {jd.company} |")
    lines.append(f"| 岗位 | {jd.role} |")
    lines.append(f"| 地点 | {jd.location} |")
    if jd.summary:
        lines.append(f"| 摘要 | {jd.summary} |")
    lines.append(f"| 信息充足 | {'是' if jd.info_sufficient else '否'} |")

    must = [r for r in jd.requirements if r.type.value == "must_have"]
    nice = [r for r in jd.requirements if r.type.value == "nice_to_have"]
    lines.append(f"| must_have | {len(must)} 条 |")
    lines.append(f"| nice_to_have | {len(nice)} 条 |")

    if jd.responsibilities:
        lines.append("")
        lines.append("**岗位职责：**")
        for resp in jd.responsibilities:
            lines.append(f"- {resp}")

    if jd.requirements:
        lines.append("")
        lines.append("**任职要求：**")
        for req in jd.requirements:
            tag = "[必须]" if req.type.value == "must_have" else "[加分]"
            lines.append(f"- {tag} {req.content}")

    lines.append("")
    lines.append("### 简历摘要")
    lines.append("")
    lines.append(f"| 维度 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 姓名 | {resume.name} |")
    lines.append(f"| 求职方向 | {resume.target_role} |")

    if resume.education:
        edu = resume.education[0]
        lines.append(f"| 教育 | {edu.school} {edu.major} {edu.degree.value} |")

    lines.append(f"| 技能 | {len(resume.skills)} 项 |")
    lines.append(f"| 项目 | {len(resume.projects)} 项 |")
    lines.append(f"| 实习 | {len(resume.internships)} 段 |")

    return "\n".join(lines)


def _render_match_score(ms: MatchScore) -> str:
    lines = ["## 二、综合匹配度", ""]
    bar = _score_bar(ms.overall)
    lines.append(f"```")
    lines.append(f"{bar}  {ms.overall:.0f}/100")
    lines.append(f"```")
    lines.append("")
    lines.append(f"**{ms.overall:.0f}/100 · {ms.verdict}**")
    return "\n".join(lines)


def _render_dimensions(dimensions: list[MatchDimension]) -> str:
    lines = ["## 三、8 维度逐项分析", ""]

    for d in dimensions:
        bar = _score_bar(d.score)
        label_map = {
            "full_match": "完全匹配",
            "partial_match": "部分匹配",
            "no_match": "不匹配",
        }
        level_cn = label_map.get(d.level.value, d.level.value)
        lines.append(f"### {d.label} {bar} {d.score:.0f}/100 · {level_cn}")
        lines.append("")
        lines.append(f"> {d.evidence}")
        lines.append("")
        if d.details:
            for detail in d.details:
                lines.append(f"- {detail}")
            lines.append("")

    return "\n".join(lines)


def _render_advantages(advantages: list[UniqueAdvantage]) -> str:
    lines = [f"## 四、差异化优势（Top {len(advantages)}）", ""]
    for i, adv in enumerate(advantages, 1):
        lines.append(f"### {i}. {adv.title}")
        lines.append("")
        lines.append(f"{adv.detail}")
        lines.append("")
        lines.append(f"**为什么重要：**{adv.why_matters}")
        lines.append("")
    return "\n".join(lines)


def _render_skill_gaps(gaps: list[SkillGap]) -> str:
    lines = [f"## 五、能力缺口 & 面试话术（{len(gaps)} 个）", ""]
    confidence_cn = {"high": "高", "medium": "中", "low": "低"}

    for i, gap in enumerate(gaps, 1):
        cf = confidence_cn.get(gap.confidence.value, gap.confidence.value)
        lines.append(f"### 缺口 {i}：{gap.gap}")
        lines.append("")
        lines.append(f"**面试影响：**{gap.impact}")
        lines.append("")
        lines.append(f"**面试话术：**")
        lines.append("")
        lines.append(f"> {gap.talking_points}")
        lines.append("")
        lines.append(f"*置信度：{cf}*")
        lines.append("")
    return "\n".join(lines)


def _render_cover_letter(cl: CoverLetter) -> str:
    lines = ["## 六、求职信草稿", ""]
    lines.append(f"{cl.greeting}")
    lines.append("")
    lines.append(cl.body)
    lines.append("")
    lines.append(cl.closing)
    lines.append("")
    lines.append(f"*（正文 {cl.word_count} 字）*")
    return "\n".join(lines)


def _render_interview_questions(questions: list[InterviewQuestion]) -> str:
    lines = [f"## 七、面试预测题（Top {len(questions)}）", ""]
    confidence_cn = {"high": "高频", "medium": "中频", "low": "低频"}

    for i, q in enumerate(questions, 1):
        cf = confidence_cn.get(q.confidence.value, q.confidence.value)
        lines.append(f"### 题 {i}：{q.question}")
        lines.append("")
        lines.append(f"**面试官为什么问这个：**{q.why_asked}")
        lines.append("")
        lines.append(f"**参考回答：**")
        lines.append("")
        lines.append(q.suggested_answer)
        lines.append("")
        lines.append(f"*题型：{q.category} | 被问概率：{cf}*")
        lines.append("")
    return "\n".join(lines)


def _render_next_steps(steps: list[NextStep]) -> str:
    lines = [f"## 八、下一步建议", ""]
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. **[{step.timing}] {step.action}**")
        lines.append(f"   {step.detail}")
        lines.append("")
    return "\n".join(lines)


def _render_footer(report: MatchReport) -> str:
    return (
        "---\n\n"
        f"*本报告由 CareerMatch Agent 自动生成 | 模型：{report.model_used}"
        f" | 生成时间：{report.generated_at[:19]}*"
    )


def _score_bar(score: float) -> str:
    """生成 10 格的分数条，如 ████████░░。"""
    filled = int(score / 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty


# ============================================================
# 便捷函数：渲染并写入文件
# ============================================================


def render_to_file(report: MatchReport, output_path: str) -> None:
    """渲染报告并写入文件（UTF-8）。"""
    md = render_report(report)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
