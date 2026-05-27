"""逐工具测试 Agent 6 个工具——每个工具单独验证，失败不阻塞后续。

用法:
    python _test_agent_tools.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from src.parsers.resume_parser import parse_resume
from src.parsers.jd_parser import parse_jd
from src.agent.tools import (
    score_skill_match,
    score_project_relevance,
    identify_skill_gap,
    extract_unique_advantages,
    predict_interview_questions,
    generate_cover_letter,
)
from src.models import RequirementType

ok_count = 0
fail_count = 0

# ============================================================
# 准备数据
# ============================================================

print("=" * 60)
print("准备数据: 加载简历 + JD")
print("=" * 60)

resume = parse_resume("data/sample_resumes/my_resume.pdf")
print(f"[OK] 简历: {resume.name} | 教育={resume.education[0].school} | 技能={len(resume.skills)}项 | 项目={len(resume.projects)}项")

jd_text = Path("data/sample_jds/jd_1_bytedance_ai_pm.txt").read_text(encoding="utf-8")
jd = parse_jd(jd_text)
must = sum(1 for r in jd.requirements if r.type == RequirementType.MUST_HAVE)
nice = sum(1 for r in jd.requirements if r.type == RequirementType.NICE_TO_HAVE)
print(f"[OK] JD: {jd.company} | {jd.role} | must={must} nice={nice}")

# 初始化所有可能被赋值但未赋值的变量
match_result = None
project_results = []
gaps = []
advantages = []
questions = []
letter = None

# ============================================================
# Tool 1: score_project_relevance
# ============================================================

print("\n" + "=" * 60)
print("[Tool 1/6] score_project_relevance — 项目相关性评估")
print("=" * 60)

try:
    project_results = score_project_relevance(resume.projects, jd)
    for i, pr in enumerate(project_results, 1):
        print(f"  项目 {i}: {pr.project_name}")
        print(f"    相关性: {pr.relevance_score}/5")
        print(f"    方向匹配: {pr.direction_match[:80]}...")
        print(f"    深度: {pr.depth_assessment}")
        print(f"    证据: {pr.key_evidence[:80]}...")
    print(f"\n[OK] score_project_relevance 通过 ✅")
    ok_count += 1
except Exception as e:
    print(f"[FAIL] score_project_relevance 失败: {e}")
    fail_count += 1

# ============================================================
# Tool 2: score_skill_match
# ============================================================

print("\n" + "=" * 60)
print("[Tool 2/6] score_skill_match — 8 维匹配打分")
print("=" * 60)

try:
    match_result = score_skill_match(resume, jd)
    print(f"  综合分: {match_result.overall}/100")
    print(f"  判定: {match_result.verdict}")
    print(f"  8 维详情:")
    for d in match_result.dimensions:
        bar = "█" * int(d.score / 10) + "░" * (10 - int(d.score / 10))
        print(f"    {d.label} {bar} {d.score:.0f}/100  {d.level.value}  {d.evidence[:50]}...")
    print(f"\n[OK] score_skill_match 通过 ✅")
    ok_count += 1
except Exception as e:
    print(f"[FAIL] score_skill_match 失败: {e}")
    fail_count += 1

# ============================================================
# Tool 3: identify_skill_gap
# ============================================================

print("\n" + "=" * 60)
print("[Tool 3/6] identify_skill_gap — 能力缺口识别")
print("=" * 60)

if match_result is None:
    print("[SKIP] 依赖的 score_skill_match 未通过，跳过此工具")
    fail_count += 1
else:
    try:
        gaps = identify_skill_gap(match_result, project_results, jd, resume)
        for i, g in enumerate(gaps, 1):
            print(f"  缺口 {i}: {g.gap[:80]}...")
            print(f"    影响: {g.impact[:60]}...")
            print(f"    话术: {g.talking_points[:80]}...")
            print(f"    置信度: {g.confidence.value}")
        print(f"\n[OK] identify_skill_gap 通过 ✅ (识别 {len(gaps)} 个缺口)")
        ok_count += 1
    except Exception as e:
        print(f"[FAIL] identify_skill_gap 失败: {e}")
        fail_count += 1

# ============================================================
# Tool 4: extract_unique_advantages
# ============================================================

print("\n" + "=" * 60)
print("[Tool 4/6] extract_unique_advantages — 差异化优势提取")
print("=" * 60)

if match_result is None:
    print("[SKIP] 依赖的 score_skill_match 未通过，跳过此工具")
    fail_count += 1
else:
    try:
        advantages = extract_unique_advantages(
            resume, jd, match_result, project_results
        )
        for i, adv in enumerate(advantages, 1):
            print(f"  优势 {i}: {adv.title}")
            print(f"    详情: {adv.detail[:80]}...")
            print(f"    为什么重要: {adv.why_matters[:80]}...")
        print(f"\n[OK] extract_unique_advantages 通过 ✅ (提取 {len(advantages)} 条)")
        ok_count += 1
    except Exception as e:
        print(f"[FAIL] extract_unique_advantages 失败: {e}")
        fail_count += 1

# ============================================================
# Tool 5: predict_interview_questions
# ============================================================

print("\n" + "=" * 60)
print("[Tool 5/6] predict_interview_questions — 面试题预测")
print("=" * 60)

if match_result is None:
    print("[SKIP] 依赖的 score_skill_match 未通过，跳过此工具")
    fail_count += 1
else:
    try:
        questions = predict_interview_questions(
            jd, gaps, advantages, match_result, resume
        )
        for i, q in enumerate(questions, 1):
            print(f"  Q{i} [{q.category}][{q.confidence.value}]: {q.question[:70]}...")
            print(f"     考察点: {q.why_asked[:60]}...")
        print(f"\n[OK] predict_interview_questions 通过 ✅ (生成 {len(questions)} 道题)")
        ok_count += 1
    except Exception as e:
        print(f"[FAIL] predict_interview_questions 失败: {e}")
        fail_count += 1

# ============================================================
# Tool 6: generate_cover_letter
# ============================================================

print("\n" + "=" * 60)
print("[Tool 6/6] generate_cover_letter — 个性化求职信")
print("=" * 60)

if match_result is None:
    print("[SKIP] 依赖的 score_skill_match 未通过，跳过此工具")
    fail_count += 1
else:
    try:
        letter = generate_cover_letter(resume, jd, advantages, match_result)
        print(f"  称呼: {letter.greeting}")
        print(f"  正文 ({letter.word_count} 字):")
        print(f"    {letter.body[:200]}...")
        print(f"  署名: {letter.closing}")
        print(f"\n[OK] generate_cover_letter 通过 ✅")
        ok_count += 1
    except Exception as e:
        print(f"[FAIL] generate_cover_letter 失败: {e}")
        fail_count += 1

# ============================================================
# 汇总
# ============================================================

print("\n" + "=" * 60)
print("测试汇总")
print("=" * 60)
print(f"  通过: {ok_count}/6 | 失败: {fail_count}/6")

if match_result is not None:
    print(f"  匹配度: {match_result.overall}/100 → {match_result.verdict}")
if project_results:
    print(f"  项目相关性: {project_results[0].project_name} = {project_results[0].relevance_score}/5")
if gaps:
    print(f"  能力缺口: {len(gaps)} 个")
if advantages:
    print(f"  差异化优势: {len(advantages)} 条")
if questions:
    print(f"  面试题: {len(questions)} 道")
if letter is not None:
    print(f"  求职信: {letter.word_count} 字")

if fail_count == 0:
    print("\n  >>> 6/6 工具全部跑通！进入 Day 14: ReAct 引擎。")
else:
    print(f"\n  >>> {fail_count} 个失败，先修再继续。")
