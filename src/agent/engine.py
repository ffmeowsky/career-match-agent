"""Agent 引擎——ReAct 主循环，调度 6 工具完成匹配分析。

链路: Resume + JobDescription → Think→Act→Observe→Decide 循环 → MatchReport

用法:
    from src.agent.engine import AgentEngine
    engine = AgentEngine(resume, jd)
    report, trace = engine.run()
"""

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone

from loguru import logger

from src.agent.tool_schemas import TOOL_SCHEMAS
from src.agent.tools import (
    extract_unique_advantages,
    generate_cover_letter,
    identify_skill_gap,
    predict_interview_questions,
    score_project_relevance,
    score_skill_match,
)
from src.models import (
    CoverLetter,
    InterviewQuestion,
    JobDescription,
    MatchReport,
    MatchScore,
    NextStep,
    ProjectRelevance,
    Resume,
    SkillGap,
    UniqueAdvantage,
)
from src.tools.llm_client import chat_json

# ============================================================
# Agent Think Prompt
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一个求职分析 Agent 的决策中枢。你会收到一份简历和 JD 的结构化摘要，以及当前的分析进度。你的任务是决定下一步应该调用哪个工具。

## 可用工具

1. score_project_relevance — 评估简历项目的相关性（0-5分）
2. score_skill_match — 8 维度技能匹配打分（输出综合分 + 逐维证据）
3. identify_skill_gap — 基于匹配结果识别 2-3 个关键能力缺口 + 面试话术
4. extract_unique_advantages — 提炼候选人的 Top 3 差异化优势
5. predict_interview_questions — 预测 5 道面试题 + 答法要点
6. generate_cover_letter — 生成个性化求职信（可选，不自动调用）

## 决策规则（优先级从高到低）

1. 如果 JD 是产品/PM 岗位且还没做项目评估 → 先调 score_project_relevance
2. 如果没做技能匹配 → 调 score_skill_match（必须先做，后续工具依赖它）
3. 如果技能匹配已完成 + 还没做缺口分析 → 调 identify_skill_gap
4. 如果技能匹配已完成 + 还没做优势提取 → 调 extract_unique_advantages
5. 如果缺口和优势都已完成 + 还没预测面试题 → 调 predict_interview_questions
6. 如果以上都完成 + JD 信息充足 → 输出 next_action="finish"
7. generate_cover_letter 不自动调用——除非用户明确请求
8. 最多 15 轮迭代，达到上限时输出 finish

## 输出格式

只输出一个 JSON 对象：
{
  "reasoning": "简短说明为什么选择这一步（中文，30字以内）",
  "next_action": "score_project_relevance | score_skill_match | identify_skill_gap | extract_unique_advantages | predict_interview_questions | generate_cover_letter | finish"
}

不要输出其他文字。"""

# ============================================================
# 引擎
# ============================================================


class AgentEngine:
    """ReAct Agent 引擎——接收解析后的简历和 JD，调度工具完成分析。"""

    def __init__(
        self,
        resume: Resume,
        jd: JobDescription,
        max_iterations: int = 15,
        user_wants_cover_letter: bool = False,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self.resume = resume
        self.jd = jd
        self.max_iterations = max_iterations
        self.user_wants_cover_letter = user_wants_cover_letter
        self.progress_callback = progress_callback

        # 状态
        self.iteration: int = 0
        self.trace: list[dict] = []
        self.completed_tools: set[str] = set()
        self.results: dict[str, object] = {}

        # 中间结果（有类型标注，方便 dispatch 使用）
        self._match_score: MatchScore | None = None
        self._project_relevance: list[ProjectRelevance] = []
        self._skill_gaps: list[SkillGap] = []
        self._advantages: list[UniqueAdvantage] = []
        self._interview_questions: list[InterviewQuestion] = []
        self._cover_letter: CoverLetter | None = None

    # ============================================================
    # 主循环
    # ============================================================

    def run(self) -> tuple[MatchReport, list[dict]]:
        """运行 Agent 直到完成或达到迭代上限。

        Returns:
            (MatchReport, trace) 元组。trace 为每轮 Think/Act/Observe/Decide 的记录。
        """
        t_start = time.perf_counter()

        while self.iteration < self.max_iterations:
            self.iteration += 1
            round_start = time.perf_counter()

            # 1. Think
            reasoning, next_action = self._think()
            if self.progress_callback:
                self.progress_callback("think", f"正在思考下一步... ({reasoning[:30]})")

            # 2. Decide: finish?
            if next_action == "finish":
                self._record_trace(self.iteration, reasoning, next_action,
                                   "", "ok", "finish", round_start)
                logger.info(f"Agent 决策完成 | 共 {self.iteration} 轮 | 决策=finish")
                break

            # 3. Act
            act_status, act_summary = self._act(next_action)
            if self.progress_callback:
                self.progress_callback(next_action, act_status)

            # 4. Observe
            obs_status, obs_summary = self._observe(next_action, act_status)

            # 5. Decide
            decision = self._decide(next_action, obs_status)
            self._record_trace(self.iteration, reasoning, next_action,
                               act_summary, obs_status, decision, round_start)

            if decision == "finish":
                logger.info(f"Agent 判定分析已足够完整 | 共 {self.iteration} 轮")
                break

            # 循环检测：连续 3 次调用同一工具
            if self._detect_loop():
                logger.warning("检测到循环调用，强制终止")
                break

        # 达到上限
        if self.iteration >= self.max_iterations:
            logger.warning(f"达到最大迭代次数 {self.max_iterations}，返回已有结果")

        total_elapsed = time.perf_counter() - t_start
        logger.info(f"Agent 运行结束 | 总耗时={total_elapsed:.1f}s | 轮次={self.iteration}")

        report = self._assemble_report()
        return report, self.trace

    # ============================================================
    # Step 1: Think
    # ============================================================

    def _think(self) -> tuple[str, str]:
        """调用 LLM 决定下一步动作。

        Returns:
            (reasoning, next_action) 元组。
        """
        state = self._build_state()

        user_prompt = (
            "请基于当前分析进度决定下一步：\n\n"
            f"<state>\n{json.dumps(state, indent=2, ensure_ascii=False)}\n</state>"
        )

        data = chat_json(AGENT_SYSTEM_PROMPT, user_prompt)
        reasoning = data.get("reasoning", "")
        next_action = data.get("next_action", "finish")

        # 合法性校验
        valid_actions = {
            "score_project_relevance", "score_skill_match",
            "identify_skill_gap", "extract_unique_advantages",
            "predict_interview_questions", "generate_cover_letter", "finish",
        }
        if next_action not in valid_actions:
            logger.warning(f"LLM 返回非法 action: {next_action}，降级为 finish")
            next_action = "finish"

        # 不允许在没有 match_score 的情况下调用依赖工具
        deps = {"identify_skill_gap", "extract_unique_advantages",
                "predict_interview_questions", "generate_cover_letter"}
        if next_action in deps and self._match_score is None:
            logger.warning(f"LLM 尝试在无 match_score 时调 {next_action}，重定向到 score_skill_match")
            next_action = "score_skill_match"

        return reasoning, next_action

    def _build_state(self) -> dict:
        """构造当前状态的摘要给 LLM 做决策。"""
        return {
            "candidate": self.resume.name,
            "target_role": self.resume.target_role,
            "jd_company": self.jd.company,
            "jd_role": self.jd.role,
            "jd_info_sufficient": self.jd.info_sufficient,
            "completed_tools": sorted(self.completed_tools),
            "has_project_relevance": len(self._project_relevance) > 0,
            "has_skill_match": self._match_score is not None,
            "has_gaps": len(self._skill_gaps) > 0,
            "has_advantages": len(self._advantages) > 0,
            "has_interview_questions": len(self._interview_questions) > 0,
            "has_cover_letter": self._cover_letter is not None,
            "user_wants_cover_letter": self.user_wants_cover_letter,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }

    # ============================================================
    # Step 2: Act
    # ============================================================

    def _act(self, tool_name: str) -> tuple[str, str]:
        """执行工具调用。

        Returns:
            (status, summary) 元组。status: ok/failed/skipped
        """
        try:
            t0 = time.perf_counter()
            result = self._dispatch(tool_name)
            elapsed = time.perf_counter() - t0

            self.completed_tools.add(tool_name)
            self.results[tool_name] = result

            return "ok", (
                f"{tool_name} 完成 | elapsed={elapsed:.2f}s"
            )

        except Exception as e:
            logger.error(f"工具 {tool_name} 调用失败: {e}")
            return "failed", str(e)[:100]

    def _dispatch(self, tool_name: str) -> object:
        """根据工具名分发到对应的函数，自动注入参数。"""
        if tool_name == "score_project_relevance":
            result = score_project_relevance(self.resume.projects, self.jd)
            self._project_relevance = result
            return result

        elif tool_name == "score_skill_match":
            result = score_skill_match(self.resume, self.jd)
            self._match_score = result
            return result

        elif tool_name == "identify_skill_gap":
            result = identify_skill_gap(
                self._match_score,  # type: ignore[arg-type]
                self._project_relevance,
                self.jd,
                self.resume,
            )
            self._skill_gaps = result
            return result

        elif tool_name == "extract_unique_advantages":
            result = extract_unique_advantages(
                self.resume,
                self.jd,
                self._match_score,  # type: ignore[arg-type]
                self._project_relevance,
            )
            self._advantages = result
            return result

        elif tool_name == "predict_interview_questions":
            result = predict_interview_questions(
                self.jd,
                self._skill_gaps,
                self._advantages,
                self._match_score,  # type: ignore[arg-type]
                self.resume,
            )
            self._interview_questions = result
            return result

        elif tool_name == "generate_cover_letter":
            result = generate_cover_letter(
                self.resume,
                self.jd,
                self._advantages,
                self._match_score,  # type: ignore[arg-type]
            )
            self._cover_letter = result
            return result

        else:
            raise ValueError(f"未知工具: {tool_name}")

    # ============================================================
    # Step 3: Observe
    # ============================================================

    def _observe(self, tool_name: str, act_status: str) -> tuple[str, str]:
        """分析工具返回结果。

        Returns:
            (quality, summary) 元组。quality: ok/suspect/retry/skip
        """
        if act_status == "failed":
            return "skip", f"{tool_name} 执行失败，跳过"

        # 对 match_score 做合理性检查
        if tool_name == "score_skill_match" and self._match_score is not None:
            ms = self._match_score
            if ms.overall < 0 or ms.overall > 100:
                return "suspect", f"综合分异常: {ms.overall}"
            if len(ms.dimensions) < 5:
                return "suspect", f"维度数不完整: {len(ms.dimensions)}"

        return "ok", f"{tool_name} 结果正常"

    # ============================================================
    # Step 4: Decide
    # ============================================================

    def _decide(self, tool_name: str, obs_status: str) -> str:
        """判断是否应该终止循环。

        Returns:
            "continue" 或 "finish"
        """
        # 核心分析链路已完整 → 终止
        core_done = (
            self._match_score is not None
            and len(self._skill_gaps) > 0
            and len(self._advantages) > 0
            and len(self._interview_questions) > 0
        )
        if core_done:
            # 如果用户要求职信且还没生成，继续
            if self.user_wants_cover_letter and self._cover_letter is None:
                return "continue"
            return "finish"

        # 工具执行失败 → 尝试下个工具
        if obs_status in ("failed", "skip"):
            return "continue"

        # 已经做了 match 但缺口/优势/面试题都还没做 → 继续
        return "continue"

    # ============================================================
    # 辅助
    # ============================================================

    def _detect_loop(self) -> bool:
        """检测是否连续 3 轮调用同一工具。"""
        if len(self.trace) < 3:
            return False
        last_three = [t["act"]["tool"] for t in self.trace[-3:]]
        return len(set(last_three)) == 1

    def _record_trace(
        self,
        round_num: int,
        reasoning: str,
        next_action: str,
        act_summary: str,
        obs_status: str,
        decision: str,
        round_start: float,
    ) -> None:
        """记录一轮完整 trace。"""
        self.trace.append({
            "round": round_num,
            "think": {
                "reasoning": reasoning,
                "next_action": next_action,
            },
            "act": {
                "tool": next_action,
                "summary": act_summary,
                "elapsed_ms": int((time.perf_counter() - round_start) * 1000),
            },
            "observe": {
                "quality": obs_status,
            },
            "decide": {
                "decision": decision,
            },
        })

    # ============================================================
    # 组装最终报告
    # ============================================================

    def _assemble_report(self) -> MatchReport:
        """将所有工具结果组装为 MatchReport。"""

        now_iso = datetime.now(timezone.utc).isoformat()

        # 补齐可能缺失的结果
        match_score = self._match_score or MatchScore(
            overall=0, dimensions=[], verdict="分析未完成"
        )
        skill_gaps = self._skill_gaps or []
        advantages = self._advantages or []
        interview_questions = self._interview_questions or []
        cover_letter = self._cover_letter

        # 生成下一步建议
        next_steps = self._build_next_steps()

        return MatchReport(
            resume=self.resume,
            jd=self.jd,
            match_score=match_score,
            advantages=advantages,
            skill_gaps=skill_gaps,
            interview_questions=interview_questions,
            cover_letter=cover_letter,
            next_steps=next_steps,
            model_used="deepseek-chat",
            generated_at=now_iso,
        )

    def _build_next_steps(self) -> list[NextStep]:
        """基于分析结果生成下一步行动建议。"""
        steps: list[NextStep] = []

        if self._match_score and self._match_score.overall >= 70:
            steps.append(NextStep(
                action="投递简历",
                detail="匹配度较高，建议投递。投递前将 CareerMatch Agent 项目链接加入简历。",
                timing="投递前",
            ))

        if self._skill_gaps:
            gap_topics = [g.gap[:30] for g in self._skill_gaps[:2]]
            steps.append(NextStep(
                action="准备面试话术",
                detail=f"针对缺口重点准备: {'; '.join(gap_topics)}",
                timing="面试前",
            ))

        if self._interview_questions:
            steps.append(NextStep(
                action="模拟面试",
                detail=f"找同学或 AI 模拟面试，逐题练习 {len(self._interview_questions)} 道预测题。",
                timing="面试前 1-2 天",
            ))

        if self.jd.info_sufficient:
            steps.append(NextStep(
                action="深度使用产品",
                detail=f"面试前至少使用 {self.jd.company} 的核心产品 3 天，准备一份体验分析。",
                timing="面试前",
            ))
        else:
            steps.append(NextStep(
                action="补全 JD 信息",
                detail="当前 JD 信息不足，建议搜索该公司其他岗位 JD 或联系 HR 了解详情。",
                timing="投递前",
            ))

        return steps


# ============================================================
# 自检入口（需 mock LLM，这里只验证导入和初始化）
# ============================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    from src.models import EducationLevel, ResumeEducation

    # 构造最小测试数据
    test_resume = Resume(
        name="测试用户",
        email="test@example.com",
        education=[
            ResumeEducation(
                school="CityU", degree=EducationLevel.MASTER,
                major="工程管理", start_date="2025.09", end_date="2026.07",
            )
        ],
    )
    test_jd = JobDescription(
        company="测试公司", role="AI PM",
        requirements=[],
    )

    engine = AgentEngine(test_resume, test_jd, max_iterations=15)
    print(f"[OK] AgentEngine 初始化成功")
    print(f"  max_iterations={engine.max_iterations}")
    print(f"  可用工具数={len(TOOL_SCHEMAS)}")
    print(f"  [注意] 运行 run() 需要调 LLM，请用 E2E 测试脚本验证。")
