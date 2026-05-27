# CareerMatch Agent · Agent 引擎设计

> **创建日期**：2026-05-26
> **状态**：v0 设计稿
> **依赖**：`docs/PRD.md` §7（Agent 设计）、`docs/DEMO_v0.md`（输出格式参考）
> **关联**：`docs/DEVELOPMENT_PLAN.md`（实现路径）

---

## 1. 设计理念：5 大法则

Agent 工具设计的核心原则——每个工具都是一个"傻子都能用的函数"。

| # | 法则 | 含义 | 违反示例 |
|---|------|------|---------|
| 1 | **单一职责** | 一个工具只做一件事，做到极致 | `match_and_generate_report()`——又匹配又生成报告 |
| 2 | **傻瓜描述** | description 写到让没看过代码的人也能正确选择 | "分析技能匹配"——太模糊，应该写"逐项比对 JD 技能要求和简历技能列表" |
| 3 | **契约清晰** | 输入什么类型、输出什么类型，必须显式声明 | `skills: list`——应该写 `skills: list[ResumeSkill]` |
| 4 | **触发明确** | 什么情况用、什么情况不用，白纸黑字 | Agent 在"信息不足时"也调用 `generate_cover_letter`——浪费 |
| 5 | **独立可测** | 每个工具可以不依赖 Agent 引擎单独跑通 | 工具内部硬编码了对 Agent 状态的引用——拆不开 |

---

## 2. 工具清单

### 工具全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                        6 工具 · 3 层                             │
│                                                                 │
│  第 1 层：匹配分析（理解差距）                                     │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ score_skill_match │  │score_project_rel  │                    │
│  │ 8 维技能匹配打分   │  │ 项目相关性评估     │                    │
│  └────────┬─────────┘  └────────┬─────────┘                    │
│           │                     │                                │
│           └──────────┬──────────┘                                │
│                      ▼                                           │
│  第 2 层：洞察提炼（从数据到洞察）                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │identify_skill_gap │  │extract_unique_adv│                    │
│  │ 能力缺口 + 话术    │  │ 差异化优势 Top 3  │                    │
│  └────────┬─────────┘  └────────┬─────────┘                    │
│           │                     │                                │
│           └──────────┬──────────┘                                │
│                      ▼                                           │
│  第 3 层：输出生成（给用户看的）                                    │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │predict_interview_q│  │generate_cvr_ltr   │                    │
│  │ 面试题预测 ×5      │  │ 个性化求职信       │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                 │
│  调用顺序：第 1 层并行 → 第 2 层并行 → 第 3 层并行                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 score_skill_match —— 8 维技能匹配打分

```yaml
名称: score_skill_match
描述: >
  将简历与 JD 在 8 个维度上逐项比对，每个维度输出 0-100 分 +
  匹配程度（full_match/partial_match/no_match）+ 一句话证据。
  8 个维度：技能、经验、学历、项目、软素质、行业认知、产品方法论、成长潜力。

输入:
  resume:
    description: "解析后的简历结构化对象（Resume Pydantic 模型）"
    type: Resume
  jd:
    description: "解析后的 JD 结构化对象（JobDescription Pydantic 模型）"
    type: JobDescription

输出:
  type: MatchScore
  字段:
    overall:
      description: "综合评分 0-100，由 8 维加权计算"
      type: float
    dimensions:
      description: "8 个维度的逐项分析"
      type: list[MatchDimension]
      每项:
        dimension: DimensionName  # 维度枚举
        label: str                # 中文名，如"技能匹配"
        score: float              # 0-100
        level: MatchLevel         # full_match / partial_match / no_match
        evidence: str             # 一句证据
        details: list[str]        # 子项分析要点
    verdict:
      description: "一句话判定，如'建议投递，但需补强 2 个维度'"
      type: str

调用时机:
  使用: "任何时候——这是 Agent 分析的第一步，必须先知道差距在哪"
  不使用: "JD 信息不足（info_sufficient=false）且 Agent 已尝试补全但失败时，降级为部分维度评分"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

### 2.2 score_project_relevance —— 项目相关性评估

```yaml
名称: score_project_relevance
描述: >
  逐一评估简历中的每个项目与目标岗位的相关性。
  不是简单的"项目多不多"，而是判断项目的方向、深度、技术栈是否和 JD 对口。
  输出每个项目的相关性分（0-5）+ 一句点评。

输入:
  projects:
    description: "简历中的项目列表"
    type: list[ResumeProject]
  jd:
    description: "解析后的 JD 对象——用于提取岗位方向和关键技术栈"
    type: JobDescription

输出:
  type: list[ProjectRelevance]
  每项:
    project_name: str       # 项目名称
    relevance_score: float  # 0-5 相关性分（5=高度对口，0=完全不相关）
    direction_match: str    # 方向是否匹配 + 一句解释
    depth_assessment: str   # 深度评估：课程作业级 / Demo 级 / 可上线级
    key_evidence: str       # 项目中和 JD 最相关的 1-2 个亮点
    suggestion: str         # 如果相关性 < 3，给一条提升建议

调用时机:
  使用: "简历中有至少 1 个项目时"
  不使用: "简历项目列表为空（projects=[]）——跳过此工具，在报告中标注'无项目经历'"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

### 2.3 identify_skill_gap —— 能力缺口识别

```yaml
名称: identify_skill_gap
描述: >
  基于技能匹配和项目评估的结果，找出候选人最关键的 2-3 个能力缺口。
  每个缺口不仅描述"差什么"，还给出：
  - 这个缺口在面试中的影响（会不会被直接挂掉？还是可以补救？）
  - 应对策略：简历怎么改、面试怎么说（逐字稿级话术）
  - 置信度：这个缺口判断有多确定

输入:
  match_score:
    description: "score_skill_match 的输出——8 维匹配结果"
    type: MatchScore
  project_relevance:
    description: "score_project_relevance 的输出——项目相关性列表"
    type: list[ProjectRelevance]
  jd:
    description: "JD 对象——用于二次确认缺口是否真的是 JD 的要求"
    type: JobDescription
  resume:
    description: "简历对象——用于定位具体差距段落"
    type: Resume

输出:
  type: list[SkillGap]
  每项:
    gap: str              # 缺口描述——"JD 要什么、你差什么"
    impact: str           # 面试影响评估——"会不会被挂"
    talking_points: str   # 面试话术——逐字稿级模板
    confidence: Confidence # high / medium / low

调用时机:
  使用: "score_skill_match 完成后，且存在 no_match 或 partial_match 维度"
  不使用: "全部 8 维都是 full_match——无可识别缺口，跳过"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

### 2.4 extract_unique_advantages —— 差异化优势提取

```yaml
名称: extract_unique_advantages
描述: >
  从简历和匹配结果中挖掘候选人针对这个岗位的最强卖点。
  不是泛泛的"学习能力强"，而是有具体证据支撑的、面试官听完会记住的优势。
  输出 Top 3，每条包含：标题 + 证据 + 为什么这条优势对这个岗位重要。

输入:
  resume:
    description: "简历对象"
    type: Resume
  jd:
    description: "JD 对象"
    type: JobDescription
  match_score:
    description: "8 维匹配结果——优先从 full_match 维度中提炼优势"
    type: MatchScore
  project_relevance:
    description: "项目相关性——高相关性项目是优势的主要来源"
    type: list[ProjectRelevance]

输出:
  type: list[UniqueAdvantage]
  每项:
    title: str       # 优势标题，如"有自己的 AI 产品作品"
    detail: str      # 优势详细说明——具体做了什么、成果是什么
    why_matters: str  # 为什么这条优势对这个岗位很重要

调用时机:
  使用: "任何时候——即使匹配度低，也需要帮用户找到能打的牌"
  不使用: "几乎没有——即使整体匹配度 50%，也有相对优势可以挖掘"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

### 2.5 predict_interview_questions —— 面试题预测

```yaml
名称: predict_interview_questions
描述: >
  基于 JD 要求和候选人能力缺口，预测面试官最可能问的 5 道题。
  覆盖 4 种题型：技术基础、项目深挖、行为面试、行业认知。
  每道题附带：面试官为什么问（考察点分析）+ 参考回答框架与要点。
  题目按被问概率从高到低排序。

输入:
  jd:
    description: "JD 对象——提取面试官最关心的技术栈和软素质要求"
    type: JobDescription
  skill_gaps:
    description: "能力缺口列表——缺口是高概率出题点"
    type: list[SkillGap]
  advantages:
    description: "差异化优势——面试官会追问'你是怎么做出来的'"
    type: list[UniqueAdvantage]
  match_score:
    description: "8 维匹配结果——低分维度也是出题热点"
    type: MatchScore
  resume:
    description: "简历——用于生成'深挖项目'类题目"
    type: Resume

输出:
  type: list[InterviewQuestion]
  每项:
    question: str          # 面试题原文
    why_asked: str         # 面试官为什么问这个——考察点分析
    suggested_answer: str  # 参考回答框架与要点
    category: str          # 产品sense / 技术理解 / 行为 / 压力
    confidence: Confidence # 这道题被问到的概率

调用时机:
  使用: "匹配分析完成后——面试题应该基于真实差距生成，不是泛泛的'你最大的缺点是什么'"
  不使用: "JD 信息严重不足（info_sufficient=false 且补全失败）——此时生成的面试题质量不可控"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

### 2.6 generate_cover_letter —— 个性化求职信

```yaml
名称: generate_cover_letter
描述: >
  基于匹配结果和差异化优势，生成一封 ≤300 字的个性化求职信。
  结构：开头（对公司和岗位的了解）+ 中间（2-3 个匹配点 + 证据）+ 结尾（call to action）。
  语调默认自然专业（不说"我认为贵公司是行业领导者"这种套话）。

输入:
  resume:
    description: "简历对象——提取个人基本信息和关键经历"
    type: Resume
  jd:
    description: "JD 对象——提取公司名、岗位名、核心要求"
    type: JobDescription
  advantages:
    description: "差异化优势——求职信的核心卖点来源"
    type: list[UniqueAdvantage]
  match_score:
    description: "匹配结果——用于判断整体匹配度，决定求职信的自信程度"
    type: MatchScore

输出:
  type: CoverLetter
  字段:
    greeting: str     # 称呼，如"面试官你好，"
    body: str         # 正文 ≤300 字
    closing: str      # 署名
    word_count: int   # 正文字数

调用时机:
  使用: "用户主动请求时（P2 优先级）"
  不使用: "默认不自动生成——求职信是锦上添花，不是核心差异化"

内部 LLM: 是（1 次 deepseek-chat 调用）
```

---

## 3. Agent 主循环设计（ReAct）

### 3.1 循环流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                   Agent 主循环 · ReAct 模式                        │
│                                                                  │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │                      初始化                                  │ │
│   │  输入: Resume (Pydantic) + JobDescription (Pydantic)        │ │
│   │  状态: iteration=0, trace=[], results={}                    │ │
│   └───────────────────────────┬────────────────────────────────┘ │
│                               ▼                                   │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │                    1. THINK  我该做什么？                     │ │
│   │                                                            │ │
│   │  · 检查当前状态：已经完成了哪些分析？还缺什么？                │ │
│   │  · 选择路径：标准分析 / 信息补全 / 公司评估                   │ │
│   │  · 决定下一步：调用哪个工具？传入什么参数？                    │ │
│   │  · 输出：reasoning（为什么选这个）+ next_action（tool_name）  │ │
│   └───────────────────────────┬────────────────────────────────┘ │
│                               ▼                                   │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │                    2. ACT    执行工具调用                    │ │
│   │                                                            │ │
│   │  · 调用选定的工具，传入结构化参数                             │ │
│   │  · 设置超时：单次工具调用 ≤ 30s                              │ │
│   │  · 捕获异常：网络错误、LLM 返回异常、Pydantic 校验失败        │ │
│   └───────────────────────────┬────────────────────────────────┘ │
│                               ▼                                   │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │                    3. OBSERVE  分析结果                      │ │
│   │                                                            │ │
│   │  · 工具返回是否有效？（非空、字段完整、置信度标注存在）         │ │
│   │  · 结果是否与预期一致？（如匹配度 90% 但项目经验空白 → 可疑）  │ │
│   │  · 是否需要重试或换工具？（如 LLM 返回格式错误 → retry）       │ │
│   │  · 输出：observation（结果摘要）+ quality（ok/suspect/retry）│ │
│   └───────────────────────────┬────────────────────────────────┘ │
│                               ▼                                   │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │                    4. DECIDE  下一步？                       │ │
│   │                                                            │ │
│   │  判断条件（满足任一即终止）：                                  │ │
│   │  ✓ 全部 6 工具中已用的必要工具均完成                          │ │
│   │  ✓ Agent 自主判断"分析已足够完整"                            │ │
│   │  ✓ iteration >= max_iterations (15)                        │ │
│   │                                                            │ │
│   │  未满足 → 回到 THINK，iteration++                           │ │
│   │  已满足 → 组装 MatchReport，退出循环                         │ │
│   └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│   终止后:                                                         │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │  Pydantic 校验 MatchReport → 置信度标注 → 敏感信息过滤        │ │
│   │  → 保存 trace 到 outputs/traces/ → 返回报告给用户            │ │
│   └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 三个分析路径

Agent 不是固定流水线——根据 JD 质量自动切换路径。

```
JD + 简历输入
      │
      ▼
┌──────────────┐
│ THINK #1:    │
│ 判断 JD 质量  │
└──────┬───────┘
       │
       ├── JD 信息充足 + 公司名可识别
       │   → 路径 A：标准分析
       │   → score_skill_match → score_project_relevance
       │   → identify_skill_gap → extract_unique_advantages
       │   → predict_interview_questions
       │   → (可选) generate_cover_letter
       │
       ├── JD 信息不足 (info_sufficient=false)
       │   → 路径 B：降级分析
       │   → 提示用户"JD 信息不足"
       │   → 仅对可识别的维度做匹配
       │   → score_skill_match(部分维度) → extract_unique_advantages
       │   → 标注所有输出为"低置信度"
       │   → 不生成面试题（质量不可控）
       │
       └── JD 指向的公司存疑（初创、信息不透明）
           → 路径 C：预警分析
           → 先标注"公司信息有限，以下分析仅基于 JD 文本"
           → 按路径 A 执行，但不做公司评估（数据不足）
           → 报告中附加"公司信息有限"风险提示
```

### 3.3 Agent 决策 Prompt 结构

Agent 每一步 Think 通过 LLM 完成，Prompt 结构如下：

```yaml
System Prompt 层次:
  第 1 层 - 角色定义:
    "你是一个求职分析 Agent。你会收到一份简历和一份 JD 的结构化数据。
     你的任务是逐步调用工具完成分析，最终输出一份 MatchReport。"

  第 2 层 - 可用工具清单:
    列出 6 个工具的名称、一句话描述、输入/输出类型
    （从 §2 的工具描述生成，精简版）

  第 3 层 - 决策规则:
    - 第 1 步必须先判断 JD 信息是否充足
    - score_skill_match 和 score_project_relevance 可以并行调用（两者无依赖）
    - identify_skill_gap 必须在 score_skill_match 完成后调用（依赖匹配结果）
    - extract_unique_advantages 依赖 match_score + project_relevance
    - predict_interview_questions 依赖 skill_gaps + advantages
    - generate_cover_letter 只在用户明确请求时调用
    - 最多迭代 15 轮，达到上限时返回已有结果

  第 4 层 - 输出格式:
    "每次 Think 输出 JSON:
     {
       'reasoning': '为什么选择这一步',
       'next_action': 'tool_name | finish',
       'tool_args': {...}  # 仅当 next_action != finish 时需要
     }"

User Prompt:
  传入当前状态：已完成步骤、已有结果、剩余迭代次数
```

---

## 4. 关键决策

### 4.1 max_iterations = 15

```
15 轮分配（最坏情况）:

  路径 A（标准分析）理论最少 5 轮:
    轮 1: score_skill_match
    轮 2: score_project_relevance（可与轮 1 并行，但 Agent 串行执行）
    轮 3: identify_skill_gap
    轮 4: extract_unique_advantages（可与轮 3 并行）
    轮 5: predict_interview_questions
    轮 6: [可选] generate_cover_letter
    → 最多 6 轮

  路径 B（降级分析）理论最少 3 轮:
    轮 1: 判断信息不足 → 跳过大部分工具
    轮 2: score_skill_match（部分维度）
    轮 3: extract_unique_advantages
    → 最多 3 轮

  为什么设 15 而非 6?
    - 预留 LLM 返回异常时的重试（每个工具最多 retry 2 次 = +2 轮/工具）
    - 预留 Agent "多疑"情况（对结果不满意，换角度再分析）
    - 预留并行调用失败时串行 fallback
    - 实际运行中，90% 的 case 会在 6-8 轮内完成
    - 15 是安全上限，不是目标值
```

### 4.2 异常处理策略

```
异常分类与应对:

┌──────────────────┬──────────────────────┬──────────────────────┐
│ 异常类型          │ 表现                  │ Agent 应对            │
├──────────────────┼──────────────────────┼──────────────────────┤
│ 工具调用失败      │ LLM 返回非 JSON       │ 自动 retry（最多 2 次）│
│ (可恢复)          │ 网络超时              │ → 仍失败 → 跳过该工具 │
│                   │                      │ → 标注"此维度分析失败" │
├──────────────────┼──────────────────────┼──────────────────────┤
│ 工具返回异常      │ 置信度全是 low         │ 标记为 suspect       │
│ (可疑)           │ 8 维全部 full_match    │ → 不重试             │
│                   │ （对任何 JD 都不正常）  │ → 但在报告中降置信度   │
├──────────────────┼──────────────────────┼──────────────────────┤
│ Agent 死循环      │ 连续 3 轮调用同一工具  │ 强制终止             │
│ (需中断)          │ Think 输出不变         │ → 返回已有结果        │
│                   │                       │ → 标注"分析未完成"    │
├──────────────────┼──────────────────────┼──────────────────────┤
│ 超迭代上限        │ iteration=15 触发     │ 优雅终止             │
│ (需兜底)          │                       │ → 返回已有结果        │
│                   │                       │ → 标注"达分析上限"    │
├──────────────────┼──────────────────────┼──────────────────────┤
│ Pydantic 校验失败 │ MatchReport 字段缺失  │ 不返回给用户          │
│ (不可恢复)        │ 或类型错误             │ → 取已有结果中        │
│                   │                       │   校验通过的部分      │
│                   │                       │ → 缺失模块标注原因    │
└──────────────────┴──────────────────────┴──────────────────────┘
```

### 4.3 Trace 记录格式

每次 Agent 运行生成一份 trace 文件，保存到 `outputs/traces/{timestamp}_{jd_company}.json`。

```json
{
  "trace_id": "20260526-233000-bytedance",
  "input": {
    "resume_name": "秦俪萍",
    "jd_company": "字节跳动",
    "jd_role": "豆包 AI 产品经理（应届生）"
  },
  "analysis_path": "A",
  "iterations": [
    {
      "round": 1,
      "think": {
        "reasoning": "JD 信息充足，公司字节跳动可识别。采用标准分析路径。第一步先做技能匹配，这是后续所有分析的基礎。",
        "next_action": "score_skill_match"
      },
      "act": {
        "tool": "score_skill_match",
        "args": {
          "resume": "Resume(name=秦俪萍, ...)",
          "jd": "JobDescription(company=字节跳动, ...)"
        },
        "timestamp": "2026-05-26T23:30:01",
        "elapsed_ms": 4320
      },
      "observe": {
        "status": "ok",
        "summary": "8 维匹配完成，综合分 74/100。skill=76, experience=52, education=90, project=82, soft_skill=78, industry=75, pm_method=62, growth=80",
        "quality": "ok"
      },
      "decide": {
        "decision": "continue",
        "reason": "匹配结果合理。experience=52 和 pm_method=62 是两个低分维度，需要继续分析缺口和优势。"
      }
    }
  ],
  "final_result": "success",
  "total_iterations": 6,
  "total_elapsed_ms": 18500,
  "warnings": []
}
```

**Trace 设计原则**：

- **可复现**：每轮记录完整的 tool args，后期可单独重跑任一工具
- **可诊断**：reasoning 和 decision 用自然语言写，人可读
- **可量化**：每轮耗时、token 消耗、总耗时全部记录
- **不冗余**：tool 返回的完整 JSON 不塞进 trace（太大），只存 summary 摘要

---

## 5. 输出校验层

Agent 输出进入用户视野前，走三层校验：

```
Agent 输出 (dict)
     │
     ▼
┌─────────────────────┐
│ 第 1 层: Pydantic   │  字段类型、必填项、数值范围
│ MatchReport 校验     │  失败 → 标记缺失模块，不阻断
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 第 2 层: 置信度标注  │  每维标注 high/medium/low
│                     │  低分维度 + JD 信息不足 → 自动 low
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 第 3 层: 内容安全    │  过滤可能的敏感信息
│                     │  联网搜索结果只展示 Agent 摘要
└─────────┬───────────┘
          ▼
    用户可见报告
```

---

## 6. 与现有文档的关系

| 文档 | 关系 | 本设计变更 |
|------|------|-----------|
| `docs/PRD.md` §7 | 原始 Agent 设计（7 工具） | 工具从 7 → 6：移除 `translate_jd`（JD 解析器已做）、移除 `evaluate_company`（v0 不做公司评估）、移除 `web_search`（v0 不做联网）、移除 `suggest_resume_fix`（合并到 `identify_skill_gap` 的 talking_points）。新增 `score_project_relevance`（项目相关性独立评估）、`extract_unique_advantages`（优势提炼独立化） |
| `docs/DEVELOPMENT_PLAN.md` §3阶段2 | 工具实现顺序 | 6 工具替代原来的 T1-T7，实现顺序见 §7 |
| `docs/DEMO_v0.md` | 输出格式参考 | 输出模块不变（8 维匹配 + 优势 + 缺口 + 面试题 + 求职信） |
| `src/models.py` | 数据模型 | 无需修改——现有 Pydantic 模型已覆盖所有工具输入输出 |

---

## 7. 实现顺序

```
Phase 2a: 匹配层（最先实现——后续所有工具依赖它们）
  → score_skill_match
  → score_project_relevance

Phase 2b: 洞察层（依赖匹配层输出）
  → identify_skill_gap
  → extract_unique_advantages

Phase 2c: 输出层（依赖洞察层输出）
  → predict_interview_questions
  → generate_cover_letter

Phase 3: Agent 引擎
  → src/agent/engine.py（ReAct 循环，调度上述 6 工具）
```

---

*本文档与 `docs/PRD.md` §7 互补——PRD 描述"为什么是 Agent"，本文档描述"Agent 怎么设计"。*
