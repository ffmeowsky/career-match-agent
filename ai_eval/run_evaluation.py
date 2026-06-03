"""
CareerMatch Agent 评估脚本
================================
对比两种方案在 30 条 JD 上的表现：
  - v1 (baseline): 单次 LLM 调用直接打匹配分（无 Agent、无工具、无结构化）
  - v2 (Agent):    完整 CareerMatch Agent（ReAct + 6 工具 + Pydantic）

用 LLM-as-a-Judge (deepseek-reasoner) 盲评两者，并校准期望区间。

运行方式（在项目根目录）：
    python ai_eval/run_evaluation.py
    python ai_eval/run_evaluation.py --limit 5      # 只跑前 5 条快速验证
    python ai_eval/run_evaluation.py --skip-v2      # 只测 baseline（调试用）

输出：ai_eval/results/eval_report_<时间戳>.md
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 让脚本能 import 项目 src
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from src.tools.llm_client import chat_json  # noqa: E402
from src.parsers.resume_parser import parse_resume_with_llm  # noqa: E402
from src.parsers.jd_parser import parse_jd  # noqa: E402
from src.agent.engine import AgentEngine  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

JUDGE_MODEL_HINT = "deepseek-reasoner"  # Judge 模型（避免裁判=选手）


# ============================================================
# v1 baseline：没有 Agent 的朴素做法
# ============================================================

V1_SYSTEM = """你是一个简单的简历-JD 匹配打分器。
给定简历和 JD，直接输出一个匹配分和简短说明。不要做深度分析。
只输出 JSON：{"overall": <0-100整数>, "summary": "<50字内一句话>"}"""


def run_v1_baseline(resume_text: str, jd_text: str) -> dict:
    """v1：单次 LLM 调用，朴素打分（模拟没有 Agent 的做法）。"""
    user = f"【简历】\n{resume_text[:3000]}\n\n【JD】\n{jd_text}\n\n输出匹配 JSON。"
    try:
        result = chat_json(V1_SYSTEM, user, temperature=0.3)
        return {
            "overall": float(result.get("overall", 0)),
            "summary": result.get("summary", ""),
            "advantages": [],   # baseline 没有这些
            "skill_gaps": [],
            "interview_questions": [],
            "ok": True,
        }
    except Exception as e:
        logger.error(f"v1 baseline 失败: {e}")
        return {"overall": 0, "summary": f"失败: {e}", "ok": False}


# ============================================================
# v2：完整 CareerMatch Agent
# ============================================================

def run_v2_agent(resume_obj, jd_obj) -> dict:
    """v2：完整 Agent 流程。"""
    try:
        engine = AgentEngine(resume=resume_obj, jd=jd_obj, max_iterations=15)
        report, trace = engine.run()
        return {
            "overall": float(report.match_score.overall),
            "summary": report.match_score.verdict,
            "advantages": [a.title for a in report.advantages],
            "skill_gaps": [g.gap for g in report.skill_gaps],
            "interview_questions": [q.question for q in report.interview_questions],
            "n_tool_calls": len([
                t for t in trace
                if t.get("act", {}).get("tool") not in (None, "finish", "")
            ]),
            "ok": True,
        }
    except Exception as e:
        logger.error(f"v2 Agent 失败: {e}")
        return {"overall": 0, "summary": f"失败: {e}", "ok": False}


# ============================================================
# LLM-as-a-Judge
# ============================================================

JUDGE_SYSTEM = """你是资深 AI 产品/招聘评估专家。
你将看到同一份简历对同一个 JD 的两份匹配分析（A 和 B，已匿名打乱），
请盲评哪份质量更高，并各打分。

评分维度（每项 1-5 分）：
1. 匹配准确性——综合分是否落在合理区间、判断是否站得住脚
2. 分析深度——是否给出差异化优势、能力缺口、面试题等可操作内容（只给一个数字=深度低）
3. 覆盖率——是否覆盖 JD 关键要求
4. 可操作性——结论能否指导候选人下一步行动

同时判断：综合分是否落在「期望区间」内（这是人工标注的合理范围）。

只输出 JSON（不要 markdown 代码块）：
{
  "A": {"准确性":N,"深度":N,"覆盖率":N,"可操作性":N},
  "B": {"准确性":N,"深度":N,"覆盖率":N,"可操作性":N},
  "winner": "A" | "B" | "tie",
  "A_in_range": true/false,
  "B_in_range": true/false,
  "comment": "<60字内点评>"
}"""


def judge(jd_text, expected_range, out_a, out_b):
    """盲评 A vs B。返回 judge 结果 dict。"""
    user = f"""【JD】
{jd_text}

【期望综合分区间】{expected_range[0]} - {expected_range[1]}

【分析 A】
综合分: {out_a['overall']}
说明: {out_a['summary']}
差异化优势: {out_a.get('advantages', [])}
能力缺口: {out_a.get('skill_gaps', [])}
面试题: {out_a.get('interview_questions', [])}

【分析 B】
综合分: {out_b['overall']}
说明: {out_b['summary']}
差异化优势: {out_b.get('advantages', [])}
能力缺口: {out_b.get('skill_gaps', [])}
面试题: {out_b.get('interview_questions', [])}

请盲评，输出 JSON。"""
    try:
        return chat_json(JUDGE_SYSTEM, user, temperature=0.0)
    except Exception as e:
        logger.error(f"Judge 失败: {e}")
        return None


# ============================================================
# 主流程
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全部）")
    ap.add_argument("--skip-v2", action="store_true", help="只跑 baseline")
    args = ap.parse_args()

    # 加载测试集和简历
    test_set = json.loads((EVAL_DIR / "test_set.json").read_text(encoding="utf-8"))
    resume_text = (EVAL_DIR / "sample_resume.txt").read_text(encoding="utf-8")
    cases = test_set["cases"]
    if args.limit:
        cases = cases[:args.limit]

    logger.info(f"加载 {len(cases)} 条测试用例")

    # 简历只解析一次（所有 case 共用）
    logger.info("解析简历...")
    resume_obj = parse_resume_with_llm(resume_text)
    logger.info(f"简历解析完成: {resume_obj.name}")

    results = []
    t_start = time.perf_counter()

    for i, case in enumerate(cases, 1):
        cid = case["id"]
        logger.info(f"[{i}/{len(cases)}] {cid} - {case['company']} {case['position']}")
        jd_text = case["jd_text"]
        exp_range = case["expected_overall_range"]

        # v1 baseline
        v1 = run_v1_baseline(resume_text, jd_text)

        # v2 Agent
        if args.skip_v2:
            v2 = {"overall": 0, "summary": "(skipped)", "ok": False}
        else:
            try:
                jd_obj = parse_jd(jd_text)
                v2 = run_v2_agent(resume_obj, jd_obj)
            except Exception as e:
                logger.error(f"{cid} JD 解析/Agent 失败: {e}")
                v2 = {"overall": 0, "summary": f"失败: {e}", "ok": False}

        # 盲评（打乱 A/B 顺序：偶数轮 A=v1，奇数轮 A=v2，消除位置偏差）
        if i % 2 == 0:
            a, b, a_is = v1, v2, "v1"
        else:
            a, b, a_is = v2, v1, "v2"

        j = judge(jd_text, exp_range, a, b) if not args.skip_v2 else None

        # 解析 judge 结果，映射回 v1/v2
        rec = {
            "id": cid, "category": case["category"], "type": case["type"],
            "company": case["company"], "position": case["position"],
            "expected_range": exp_range,
            "v1_overall": v1["overall"], "v2_overall": v2["overall"],
            "v1_summary": v1["summary"], "v2_summary": v2["summary"],
            "v2_advantages": v2.get("advantages", []),
            "v2_gaps": v2.get("skill_gaps", []),
        }
        if j:
            winner_raw = j.get("winner", "tie")
            # 把 A/B 映射回 v1/v2
            if winner_raw == "tie":
                rec["winner"] = "tie"
            elif (winner_raw == "A" and a_is == "v2") or (winner_raw == "B" and a_is == "v1"):
                rec["winner"] = "v2"
            else:
                rec["winner"] = "v1"
            # 维度分映射
            a_scores = j.get("A", {})
            b_scores = j.get("B", {})
            rec["v1_scores"] = b_scores if a_is == "v2" else a_scores
            rec["v2_scores"] = a_scores if a_is == "v2" else b_scores
            rec["v1_in_range"] = (j.get("B_in_range") if a_is == "v2" else j.get("A_in_range"))
            rec["v2_in_range"] = (j.get("A_in_range") if a_is == "v2" else j.get("B_in_range"))
            rec["comment"] = j.get("comment", "")
        results.append(rec)

        logger.info(f"  v1={v1['overall']:.0f} v2={v2['overall']:.0f} "
                    f"winner={rec.get('winner','?')}")

    elapsed = time.perf_counter() - t_start
    write_report(results, elapsed, args)


def _avg(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else 0.0


def write_report(results, elapsed, args):
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = RESULTS_DIR / f"eval_report_{ts}.md"

    n = len(results)
    v2_win = sum(1 for r in results if r.get("winner") == "v2")
    v1_win = sum(1 for r in results if r.get("winner") == "v1")
    tie = sum(1 for r in results if r.get("winner") == "tie")

    dims = ["准确性", "深度", "覆盖率", "可操作性"]
    v1_dim = {d: _avg([r.get("v1_scores", {}).get(d) for r in results]) for d in dims}
    v2_dim = {d: _avg([r.get("v2_scores", {}).get(d) for r in results]) for d in dims}

    v2_in_range = sum(1 for r in results if r.get("v2_in_range"))
    v1_in_range = sum(1 for r in results if r.get("v1_in_range"))

    lines = []
    lines.append("# CareerMatch Agent 评估报告\n")
    lines.append(f"**评估时间**：{ts}  |  **耗时**：{elapsed:.0f} 秒")
    lines.append(f"**测试用例**：{n} 条  |  **Judge 模型**：{JUDGE_MODEL_HINT}")
    lines.append(f"**对比**：v1 (单次 LLM 朴素打分) vs v2 (完整 ReAct Agent)\n")
    lines.append("---\n")
    lines.append("## 总览\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| v2 (Agent) 获胜 | {v2_win} |")
    lines.append(f"| v1 (baseline) 获胜 | {v1_win} |")
    lines.append(f"| 平局 | {tie} |")
    lines.append(f"| **v2 胜率** | **{v2_win/n*100:.0f}%** |")
    lines.append(f"| v2 评分落在期望区间 | {v2_in_range}/{n} ({v2_in_range/n*100:.0f}%) |")
    lines.append(f"| v1 评分落在期望区间 | {v1_in_range}/{n} ({v1_in_range/n*100:.0f}%) |\n")

    lines.append("## 各维度平均分（1-5）\n")
    lines.append("| 维度 | v1 | v2 | 提升 |")
    lines.append("|------|----|----|------|")
    for d in dims:
        lines.append(f"| {d} | {v1_dim[d]:.1f} | {v2_dim[d]:.1f} | +{v2_dim[d]-v1_dim[d]:.1f} |")
    v1_overall_avg = _avg([sum(v1_dim.values())/len(dims)])
    v2_overall_avg = _avg([sum(v2_dim.values())/len(dims)])
    lines.append(f"| **综合** | **{sum(v1_dim.values())/len(dims):.2f}** | "
                 f"**{sum(v2_dim.values())/len(dims):.2f}** | "
                 f"**+{(sum(v2_dim.values())-sum(v1_dim.values()))/len(dims):.2f}** |\n")

    # 按类别
    lines.append("## 按类别 v2 胜率\n")
    lines.append("| 类别 | v2 胜 | v1 胜 | 平 |")
    lines.append("|------|-------|-------|----|")
    for cat in ["happy", "edge", "adversarial"]:
        sub = [r for r in results if r["category"] == cat]
        if sub:
            w2 = sum(1 for r in sub if r.get("winner") == "v2")
            w1 = sum(1 for r in sub if r.get("winner") == "v1")
            t = sum(1 for r in sub if r.get("winner") == "tie")
            lines.append(f"| {cat} | {w2} | {w1} | {t} |")
    lines.append("")

    # 明细
    lines.append("## 逐条明细\n")
    lines.append("| ID | 类别 | 公司/岗位 | 期望区间 | v1分 | v2分 | 胜者 | 点评 |")
    lines.append("|----|------|----------|---------|------|------|------|------|")
    for r in results:
        lines.append(f"| {r['id']} | {r['category']} | {r['company']}/{r['position'][:12]} | "
                     f"{r['expected_range'][0]}-{r['expected_range'][1]} | "
                     f"{r['v1_overall']:.0f} | {r['v2_overall']:.0f} | "
                     f"{r.get('winner','?')} | {r.get('comment','')[:30]} |")
    lines.append("")
    lines.append("---")
    lines.append(f"*报告由 ai_eval/run_evaluation.py 自动生成，Judge 模型 {JUDGE_MODEL_HINT}*")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"✅ 报告已生成: {path}")
    print(f"\n{'='*50}")
    print(f"✅ 评估完成！v2 胜率 {v2_win/n*100:.0f}%，报告: {path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
