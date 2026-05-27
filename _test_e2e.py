"""E2E 端到端测试：字节豆包 JD + 我的简历 → ReAct 引擎 → MatchReport + Trace。

用法:
    python _test_e2e.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from src.parsers.resume_parser import parse_resume
from src.parsers.jd_parser import parse_jd
from src.agent.engine import AgentEngine
from src.renderer import render_to_file
from src.models import RequirementType

# ============================================================
# 准备数据
# ============================================================

print("=" * 60)
print("加载数据")
print("=" * 60)

resume = parse_resume("data/sample_resumes/my_resume.pdf")
print(f"[OK] 简历: {resume.name} | {resume.education[0].school} | 技能={len(resume.skills)}项 | 项目={len(resume.projects)}项")

jd_text = Path("data/sample_jds/jd_1_bytedance_ai_pm.txt").read_text(encoding="utf-8")
jd = parse_jd(jd_text)
must = sum(1 for r in jd.requirements if r.type == RequirementType.MUST_HAVE)
nice = sum(1 for r in jd.requirements if r.type == RequirementType.NICE_TO_HAVE)
print(f"[OK] JD: {jd.company} | {jd.role} | must={must} nice={nice} | info_sufficient={jd.info_sufficient}")

# ============================================================
# ReAct 引擎
# ============================================================

print("\n" + "=" * 60)
print("ReAct 引擎运行中...")
print("=" * 60)

engine = AgentEngine(resume, jd, max_iterations=15)
report, trace = engine.run()

# ============================================================
# 1. ReAct Trace
# ============================================================

print("\n" + "=" * 60)
print("ReAct Trace")
print("=" * 60)

for t in trace:
    r = t["round"]
    think = t["think"]
    act = t["act"]
    obs = t["observe"]
    decide = t["decide"]
    print(f"\n[Round {r}]")
    print(f"  Think: {think['reasoning']}")
    if think["next_action"] != "finish" and act["tool"]:
        print(f"  Act: {act['tool']} ({act['elapsed_ms']}ms)")
        print(f"  Observe: {obs['quality']}")
        print(f"  Decide: {decide['decision']}")

# ============================================================
# 2. 匹配度
# ============================================================

print("\n" + "=" * 60)
print("匹配度报告")
print("=" * 60)

ms = report.match_score
print(f"\n  综合评分: {ms.overall}/100")
print(f"  判定: {ms.verdict}")
print(f"\n  8 维详情:")
for d in ms.dimensions:
    bar = "█" * int(d.score / 10) + "░" * (10 - int(d.score / 10))
    print(f"  {d.label} {bar} {d.score:.0f}/100  [{d.level.value}]")

# ============================================================
# 3. 差异化优势
# ============================================================

print(f"\n{'='*60}")
print(f"差异化优势 ({len(report.advantages)} 条)")
print("=" * 60)
for i, adv in enumerate(report.advantages, 1):
    print(f"\n  {i}. {adv.title}")
    print(f"     {adv.detail[:100]}...")

# ============================================================
# 4. 能力缺口
# ============================================================

print(f"\n{'='*60}")
print(f"能力缺口 ({len(report.skill_gaps)} 个)")
print("=" * 60)
for i, gap in enumerate(report.skill_gaps, 1):
    print(f"\n  缺口 {i}: {gap.gap[:80]}...")
    print(f"  影响: {gap.impact[:80]}...")

# ============================================================
# 5. 面试题
# ============================================================

print(f"\n{'='*60}")
print(f"面试预测题 ({len(report.interview_questions)} 道)")
print("=" * 60)
for i, q in enumerate(report.interview_questions, 1):
    print(f"\n  Q{i} [{q.category}][{q.confidence.value}]")
    print(f"  {q.question[:80]}...")

# ============================================================
# 6. 下一步建议
# ============================================================

print(f"\n{'='*60}")
print(f"下一步建议 ({len(report.next_steps)} 条)")
print("=" * 60)
for step in report.next_steps:
    print(f"\n  [{step.timing}] {step.action}")
    print(f"  {step.detail[:100]}...")

# ============================================================
# 汇总
# ============================================================

print("\n" + "=" * 60)
print("E2E 测试汇总")
print("=" * 60)
print(f"""
  ReAct 轮次: {len(trace)}
  综合匹配度: {ms.overall}/100
  优势: {len(report.advantages)} 条
  缺口: {len(report.skill_gaps)} 个
  面试题: {len(report.interview_questions)} 道
  下一步: {len(report.next_steps)} 条
  模型: {report.model_used}
  生成时间: {report.generated_at}

  >>> E2E 通过！Agent 引擎完成首次完整分析。
""")

# ============================================================
# 渲染 Markdown 报告
# ============================================================

output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)
output_path = output_dir / "report_e2e.md"
render_to_file(report, str(output_path))
print(f"\n[OK] Markdown 报告已写入: {output_path}")
