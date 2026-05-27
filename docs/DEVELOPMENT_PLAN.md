# CareerMatch Agent · 开发计划

> **基于**：`docs/DEMO_v0.md` 反推实现路径  
> **创建日期**：2026-05-23  
> **原则**：自顶向下拆解，自底向上开发。先简单后复杂，先独立后耦合。

---

## 1. 模块层级（自顶向下拆解）

```
Level 1（用户可见）
  └─ 完整匹配报告（Markdown）
       ↑ 依赖 MatchReport 对象 + 报告渲染器
       
Level 2（数据结构）
  └─ MatchReport = {scores[], advantages[], gaps[], cover_letter, interview_qs[]}
       ↑ 依赖 Agent 引擎输出
       
Level 3（核心引擎）
  └─ Agent（ReAct 模式：Think → Act → Observe → Decide）
       ↑ 依赖 7 个工具 + LLM 客户端 + Pydantic 校验层
       
Level 4（基础模块）
  └─ JD 解析器 + 简历解析器 + 7 个工具 + LLM 封装层
```

### Level 4 展开

| 模块 | 输入 | 输出 | 依赖 |
|------|------|------|------|
| **简历解析器** | PDF / DOCX / 纯文本 | `Resume` (Pydantic) | pypdf |
| **JD 解析器** | 纯文本 / URL | `JobDescription` (Pydantic) | LLM |
| **LLM 封装层** | messages + model | response (str) | openai SDK, config.py |
| **T1 translate_jd** | `JobDescription` | 岗位画像摘要 | LLM |
| **T2 match_skills** | `Resume` + `JobDescription` | 8 维匹配结果 | LLM |
| **T3 evaluate_company** | 公司名 | PMF/融资/Leader/方向 评估 | LLM + web_search |
| **T4 web_search** | 搜索 query | 搜索结果摘要 | httpx / openai web tool |
| **T5 suggest_resume_fix** | 差距分析 + `Resume` | 修改建议（定位→问题→改法→示例） | LLM |
| **T6 predict_interview_qs** | `JobDescription` + 差距 | 5 道面试题 + 答法 | LLM |
| **T7 generate_cover_letter** | `Resume` + `JobDescription` | 求职信 ≤300 字 | LLM |

---

## 2. Pydantic 数据模型（`src/models.py`）

在写任何逻辑之前，先把数据结构定下来。

```python
# 核心模型清单
Resume           # 简历结构化对象
JobDescription   # JD 结构化对象
MatchDimension   # 单个匹配维度（技能/经验/学历...）
MatchResult      # 8 维度匹配结果
SkillGap         # 能力缺口 + 面试话术
Advantage        # 差异化优势
InterviewQ       # 面试题 + 答法
CoverLetter      # 求职信
MatchReport      # 完整报告 = 以上全部之和
CompanyBrief     # 公司评估简报
```

---

## 3. 开发顺序（自底向上）

### 阶段 1：数据模型 + 解析器 [Day 3-5]

| 序号 | 模块 | 预计 | 依赖 | 独立可测？ |
|------|------|------|------|-----------|
| 1.1 | `src/models.py` — 所有 Pydantic 模型定义 | Day 3 | 无 | ✅ |
| 1.2 | `src/config.py` — 补全 LLM 配置 + 日志 | Day 3 | .env | ✅ |
| 1.3 | `src/parsers/resume_parser.py` | Day 3-4 | 1.1, 1.2, pypdf | ✅ |
| 1.4 | `src/parsers/jd_parser.py` | Day 4-5 | 1.1, 1.2, LLM | ✅ |
| 1.5 | `tests/test_parsers.py` | Day 5 | 1.3, 1.4 | — |
| 1.6 | 准备 5 条真实 JD + 3 份测试简历到 `data/` | Day 5 | 无 | — |

### 阶段 2：LLM 封装 + Schema 注册 [Day 8]

| 序号 | 模块 | 预计 | 依赖 | 独立可测？ |
|------|------|------|------|-----------|
| 2.1 | `src/tools/llm_client.py` — LLM 调用封装（含 retry + 日志 + 错误处理） | Day 8 | 1.2 | ✅ |
| 2.2 | `src/agent/tool_schemas.py` — 6 工具 Schema 定义（OpenAI function calling 格式，仅注册不实现） | Day 8 | 1.1 | ✅ |

> **变更说明（2026-05-26）**：原 T1-T7 的 7 工具已废弃，改用 `docs/AGENT_DESIGN.md` 中的 6 工具设计。工具实现移入阶段 3。

### 阶段 3：Agent 引擎 [Day 12-14]

| 序号 | 模块 | 预计 | 依赖 | 独立可测？ |
|------|------|------|------|-----------|
| 3.1 | `src/agent/tools.py` — 6 工具实现（score_skill_match / score_project_relevance / identify_skill_gap / extract_unique_advantages / predict_interview_questions / generate_cover_letter） | Day 13 | 2.1, 2.2 | ✅（每工具独立 mock LLM 测试） |
| 3.2 | `src/agent/engine.py` — ReAct 主循环（Think→Act→Observe→Decide，含路径选择 + Pydantic 校验 + 置信度标注） | Day 14 | 3.1 | 需 mock |
| 3.3 | `src/renderer.py` — MatchReport → Markdown 报告 | Day 14 | 1.1 | ✅ |
| 3.4 | 端到端联调：1 份 JD（字节豆包）+ 我的简历 → 完整报告，Trace 记录 | Day 14 晚 | 3.2, 3.3 | — |

**Day 12 详细**：定义 TOOL_SCHEMAS——6 个工具的 name/description/parameters，格式遵循 OpenAI function calling 规范。写完即用 `python -c "import json; from src.agent.tool_schemas import TOOL_SCHEMAS; print(json.dumps(TOOL_SCHEMAS, indent=2, ensure_ascii=False))"` 目视检查——确认 LLM 看到这些描述后会做出正确的工具选择。

**Day 13 详细**：每个工具是一个函数（输入 Pydantic → LLM 调用 → 输出 Pydantic）。工具之间不允许互相调用（单一职责），由 engine 统一调度。每个工具单独写单元测试（mock LLM 响应），通过后再进入 Day 14。

**Day 14 详细**：`engine.py` 是核心——实现 ReAct 循环。Think 调用 LLM（传入当前状态 + 可用工具列表）→ 解析 LLM 返回的 tool_call → Act 调用对应工具 → Observe 校验结果 → Decide 判断继续/终止。下午联调 `renderer.py`，晚上用字节豆包 JD + 用户简历端到端跑通，Trace 格式参照 `docs/DEMO_AGENT_TRACE.md`。

**设计参考**：`docs/AGENT_DESIGN.md`（工具设计 + 异常处理策略）和 `docs/DEMO_AGENT_TRACE.md`（6 轮 Trace 模拟）。

### 阶段 4：端到端联调 [Day 12-14]

| 序号 | 模块 | 预计 | 依赖 |
|------|------|------|------|

| 4.1 | `main.py` — CLI 入口：传入 JD + 简历路径 → 输出报告 | Day 12 | 全部 |
| 4.2 | `tests/test_agent.py` — Agent 集成测试（mock LLM） | Day 12-13 | 4.1 |
| 4.3 | 10 条 Happy Case 首轮评估，记入 `docs/EVALUATION.md` | Day 13-14 | 4.1 |

### 阶段 5：评估迭代 [Day 15-17]

| 序号 | 模块 | 预计 | 依赖 |
|------|------|------|------|
| 5.1 | 30 条全量测试 + Judge 打分 | Day 15 | 4.1 |
| 5.2 | Bad Case 修复，目标 ≥ 90% | Day 16 | 5.1 |
| 5.3 | 回归测试 + EVALUATION.md 更新 | Day 17 | 5.2 |

### 阶段 6：Web 前端 [Day 18-19]

| 序号 | 模块 | 预计 | 依赖 |
|------|------|------|------|
| 6.1 | `app.py` — Streamlit 界面（上传简历 + 粘贴 JD → 报告） | Day 18 | 4.1 |
| 6.2 | UI 打磨：加载态、空态、错误友好提示 | Day 19 | 6.1 |

### 阶段 7：部署 + 包装 [Day 20-21]

| 序号 | 模块 | 预计 | 依赖 |
|------|------|------|------|
| 7.1 | Streamlit Cloud 部署 | Day 20 | 6.2 |
| 7.2 | README 完善 + 输出样本准备 + Demo 视频 | Day 20 | 7.1 |
| 7.3 | 全流程走通 + 代码整理 + PRD 对齐 | Day 21 | 全部 |

---

## 4. 每个模块的完成标准（DoD）

### 4.1 简历解析器 `resume_parser.py`

- [ ] 能解析 PDF 文件 → `Resume` Pydantic 对象（字段无遗漏）
- [ ] 支持纯文本输入作为降级路径
- [ ] 通过 3 份不同风格简历的测试（简洁版 / 详细版 / 多页版）
- [ ] 解析失败时抛出明确错误（不是静默返回空对象）
- [ ] `notes/pitfalls.md` 记录 ≥ 1 个踩坑（如中文编码、特殊字符、非标准格式）

### 4.2 JD 解析器 `jd_parser.py`

#### Prompt 策略

JD 解析比简历解析多两个任务——**去噪**和**翻译**，Prompt 需要分层设计。

**第一层：结构化角色定义**

```
你是一个 JD 解析器。你的任务：
1. 从 JD 文本中提取岗位信息，过滤掉与岗位要求无关的内容
2. 将营销语言翻译为可分析的结构化要求
3. 区分硬性要求（must_have）和加分项（nice_to_have）
```

**第二层：去噪规则（明确列出要过滤的内容）**

| 过滤内容 | 示例 | 原因 |
|---------|------|------|
| 公司介绍 | "我们是中国最大的…" | 雇主品牌，非岗位要求 |
| 团队描述 | "团队由算法、工程、产品组成" | 组织信息，非要求 |
| 福利待遇 | "一日三餐、健身房、期权" | 福利，非要求 |
| 薪资描述 | "薪资 open，上不封顶" | 薪资，非要求 |
| 价值观口号 | "改变世界""极致追求" | 文化描述，非要求 |

**第三层：黑话翻译表（内置对照，不改写原文，只帮助正确归类）**

| JD 黑话 | 帮助 LLM 理解为 |
|---------|---------------|
| "皮实" | 情绪稳定、能抗压 |
| "扁平化管理" | 组织层级少（非候选人的要求，可过滤） |
| "薪资 open" | 薪资结构偏绩效（可过滤） |
| "有创业精神" | 身兼多职、职责范围不固定 |
| "快速成长" | 入职即上手，培训资源有限 |

**第四层：must_have vs nice_to_have 归类规则**

```
判断逻辑（按优先级）：
1. 在"加分项""优先条件""nice to have"小标题下 → nice_to_have
2. 句子含"优先""加分""更好""plus" → nice_to_have
3. 句子含"必须""需要""要求""should have" → must_have
4. 都不满足 → 默认 must_have（宁可严格，不误投）
```

**第五层：Few-shot 示例（每个场景 1 个短示例）**

| 示例场景 | 输入片段 | 期望输出 |
|---------|---------|---------|
| 去噪 | "我们能提供一日三餐 + 无限零食 + 健身房" | → 不提取到 requirements 中 |
| 黑话归类 | "希望你皮实，能扛事" | → `{content: "皮实，能扛事", type: "must_have", category: "软素质"}` |
| 加分识别 | "有 AI 产品作品优先" | → `{type: "nice_to_have"}` |
| 信息不足 | "招 AI PM，坐标北京" | → `info_sufficient: false` |

**为什么不选 CoT**：
- 去噪和归类的逻辑可以用明确的规则表达（if-this-then-that），不需要推理链
- CoT 增加 token 消耗（约 +30%），且本任务不需要多步推理
- Few-shot 已足够引导 LLM 在陌生场景下遵循规则

#### 边界 Case 处理矩阵

参考 `docs/DEMO_JD_PARSER.md` 第四节的场景分类，每个边界 case 对应一种处理策略：

| # | 场景 | 输入特征 | 处理策略 | 期望输出 |
|---|------|---------|---------|---------|
| C1 | 极简 JD | 文本 < 50 字，无 requirements 可提取 | 不拒绝请求，正常解析 + `info_sufficient=false` | 返回部分结果 + 标注"信息不足" |
| C2 | 技术术语密集 | JD 含 Transformer/CUDA/vLLM 等术语 | LLM 不需要理解术语含义，只根据句式判断 must/nice | 术语原样保留在 requirements 中 |
| C3 | 中英混杂 | JD 中英文混写（外企常见） | Prompt 要求保留原文措辞，禁止翻译 | content 字段保持原始语言混搭 |
| C4 | 无公司名 | JD 文本没有公司标识 | company 字段填"未知"，不影响解析 | 正常解析 |
| C5 | 全篇营销文 | JD 全是公司宣传，无实质要求 | 设置较低的 requirements 提取阈值 | 提取到的 requirements < 2 条 → `info_sufficient=false` |
| C6 | 隐性歧视 | JD 含"男性优先""35 岁以下"等 | Prompt 内置敏感词提示（不加拒绝逻辑，只保留原文） | 正常提取，由上层 Agent 标注风险 |

#### 完成标准（DoD）

**功能类**：

- [ ] 能解析纯文本 JD → `JobDescription` Pydantic 对象，字段无遗漏
- [ ] 正确过滤福利/公司介绍/团队描述（过滤率 ≥ 90%）
- [ ] 区分 must_have / nice_to_have，与人工标注对比准确率 ≥ 90%
- [ ] JD < 50 字时自动标记 `info_sufficient=false`
- [ ] requirements 中每条记录的 content 保留原文措辞

**鲁棒性类**：

- [ ] 通过 6 类 JD 测试，覆盖率 100%：

  | 类型 | 测试 JD | 通过标准 |
  |------|--------|---------|
  | 大厂校招 | 字节豆包 AI PM | 去噪正确 + must/nice 区分 ≥ 90% |
  | 初创口语 | 某初创 AI 公司（含大量口语文案） | 过滤率 ≥ 80% |
  | 极简 | < 50 字 JD | info_sufficient=false |
  | 技术术语多 | 含 10+ 技术栈名的 JD | 术语原样保留 + 归类正确 |
  | 中英混杂 | 外企 AI PM JD | content 保留原文语言 |
  | 全篇营销 | 几乎无实质要求的 JD | requirements < 2 条 + insufficient |

- [ ] 非标准 JD 不崩溃——返回部分结果，不抛异常

**工程类**：

- [ ] LLM 调用走统一的 `_call_llm()`（与 resume_parser 共用，后续迁移到 `llm_client.py`）
- [ ] 中文 docstring（每个函数）
- [ ] loguru 日志（输入长度、token 消耗、解析耗时、info_sufficient 判断）
- [ ] 解析失败时抛出 `RuntimeError`（含排查线索），不是静默返回空对象
- [ ] `notes/pitfalls.md` 记录 ≥ 2 个踩坑

### 4.3 LLM 封装层 `llm_client.py`

- [ ] 封装 `chat()` 方法：输入 messages → 输出 str
- [ ] 支持 `response_format={"type": "json_object"}` 模式
- [ ] 失败自动 retry（最多 3 次，指数退避）
- [ ] 每次调用 loguru 记录：模型名、token 消耗、耗时
- [ ] try/except 包住所有调用，错误信息包含排查线索

### 4.4 每个工具（T1-T7）

- [ ] 输入/输出类型明确（Pydantic 或 dataclass）
- [ ] 独立可测：不依赖 Agent 引擎，可单独调用验证
- [ ] 输出包含置信度标注（高 / 中 / 低）
- [ ] LLM 调用走统一的 `llm_client.chat()`，不自己裸调 openai

### 4.5 Agent 引擎 `engine.py`

- [ ] ReAct 循环正确运行：Think → Act → Observe → Decide，直到完成或达到 max_iterations
- [ ] `max_iterations=15`，超限时优雅终止（返回已有结果 + 标注"分析未完成"）
- [ ] 三个分析路径（标准/补全/可疑）能自动切换
- [ ] 通过 3 条不同 JD 类型的端到端测试（标准 JD / 极简 JD / 技术 JD）

### 4.6 报告渲染器 `renderer.py`

- [ ] 输入 `MatchReport` → 输出 Markdown 字符串
- [ ] 输出格式与 `docs/DEMO_v0.md` 一致（8 个模块不缺）
- [ ] 中文无乱码、编码为 UTF-8

### 4.7 主入口 `main.py`

- [ ] CLI 调用：`python main.py --resume path/to/resume.pdf --jd "JD文本"`
- [ ] 输出报告到 `outputs/` 目录，文件名含时间戳
- [ ] 无参数时打印 help

### 4.8 Streamlit 前端 `app.py`

- [ ] 两个输入区：文件上传（简历）+ 文本框（JD）
- [ ] 一个"开始分析"按钮
- [ ] 三种状态：等待输入 / 分析中（loading spinner）/ 报告展示
- [ ] 错误状态友好提示（不是 traceback）

---

## 5. 风险与依赖

| # | 风险 | 概率 | 影响 | 预防措施 | 发生时的应对 |
|---|------|------|------|---------|------------|
| R1 | DeepSeek JSON 输出格式不稳定（缺字段、多字段、非 JSON） | 中 | 解析器/工具输出无法校验 | 所有 LLM 调用加 `response_format` 参数 + Pydantic 校验兜底 | retry 3 次 → 降级（去掉校验，标注"低置信度"） |
| R2 | Agent 死循环（反复调用同一工具） | 中 | 烧 token + 卡死 | `max_iterations=15` + 检测连续 3 次相同调用 → 强制终止 | 返回已有结果 + 标注"分析未完成，请手动检查" |
| R3 | pypdf 对某些 PDF 格式解析失败（扫描版、加密、非标准字体） | 中 | 简历解析失败 | 支持纯文本输入作为降级路径 | 提示用户"请提供文本版简历或可搜索的 PDF" |
| R4 | web_search 工具返回低质量或不相关结果 | 高 | 公司评估不准确 | 搜索结果不直接展示，只展示 Agent 摘要 + 标注来源 | 降级为"信息不足，建议手动核实" |
| R5 | DeepSeek API 大规模故障 | 低 | 全部功能不可用 | `config.py` 预留备选模型切换（2 行改动） | 切换到备选 OpenAI 兼容接口 |
| R6 | Agent 工具调用选择错误（该搜不搜、不该搜乱搜） | 中 | 分析质量下降 | 工具描述写得足够清晰 + Judge 抽检 | Day 12 早验证，修 prompt |
| R7 | 21 天排期某一模块超时 | 高 | 挤占后续阶段 | 每个阶段最后 1 天为 buffer | 砍 P2 功能（T7 求职信），保 P0+P1 |

---

## 6. 文件结构（开发完成后）

```
src/
├── __init__.py
├── models.py              # 所有 Pydantic 模型
├── config.py              # 环境配置 + loguru 初始化
├── renderer.py            # MatchReport → Markdown
├── parsers/
│   ├── __init__.py
│   ├── resume_parser.py   # PDF → Resume
│   └── jd_parser.py       # 文本 → JobDescription
├── tools/
│   ├── __init__.py
│   └── llm_client.py      # LLM 调用封装（chat_json + retry + 日志）
└── agent/
    ├── __init__.py
    ├── tool_schemas.py    # 6 工具 Schema 定义（OpenAI function calling 格式）
    ├── tools.py           # 6 工具实现（每个工具独立可测）
    └── engine.py          # ReAct 主循环（Think→Act→Observe→Decide）
```

---

*本计划基于 DEMO_v0.md 反推，开发过程中如有调整，同步更新本文档和 docs/ITERATION_LOG.md。*
