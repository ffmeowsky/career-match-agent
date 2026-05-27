# 迭代记录

> 记录每次功能的迭代变更、原因与影响。

---

## 格式约定

每条记录包含：
- **日期**：YYYY-MM-DD
- **类型**：新增 / 修改 / 删除 / 修复
- **描述**：改了什么，为什么
- **影响范围**：涉及的文件或模块

---

## 迭代记录

| 日期 | 类型 | 描述 | 影响范围 |
|------|------|------|----------|
| 2026-05-22 | 新增 | 项目初始化，创建工作区结构 | 全局 |
| 2026-05-22 | 新增 | AGENTS.md + CLAUDE.md 编写完成 | 全局 |
| 2026-05-22 | 新增 | 开发环境检查通过（Python 3.12.10 + DeepSeek API 连通） | 全局 |
| 2026-05-23 | 新增 | PRD v0 完成（10 章完整版） | docs/PRD.md |
| 2026-05-23 | 新增 | DEMO_v0 假报告（基于字节豆包 AI PM JD） | docs/DEMO_v0.md |
| 2026-05-23 | 新增 | 开发计划（自顶向下拆解 + 自底向上排序 + DoD） | docs/DEVELOPMENT_PLAN.md |
| 2026-05-26 | 新增 | Pydantic 模型全部定义（14 模型 + 6 枚举） | src/models.py |
| 2026-05-26 | 新增 | 简历解析器（PDF → Resume）完成 + 3 风格兼容测试 | src/parsers/resume_parser.py |
| 2026-05-26 | 新增 | 技术笔记 T001：Few-shot 提升简历解析鲁棒性 | notes/techniques.md |
| 2026-05-26 | 修改 | PRD 补充 JD 解析子模块章节（用户故事 + 风险 + 黑话表） | docs/PRD.md |
| 2026-05-26 | 新增 | Agent 引擎设计文档（6 工具 + ReAct 循环 + 异常处理 + Trace 格式） | docs/AGENT_DESIGN.md |
| 2026-05-26 | 新增 | Agent ReAct Trace 模拟 Demo（字节豆包 JD × 秦俪萍简历，6 轮完整运行） | docs/DEMO_AGENT_TRACE.md |
| 2026-05-26 | 修改 | 开发计划更新：工具从 7→6，Agent 引擎拆为 Day 12-14 三步 | docs/DEVELOPMENT_PLAN.md |
| 2026-05-26 | 新增 | Agent 工具 Schema 注册表（6 工具 OpenAI function calling 格式） | src/agent/tool_schemas.py |
| 2026-05-26 | 新增 | Agent 工具实现（6 工具各含 Prompt + 构造逻辑 + Pydantic 校验） | src/agent/tools.py, src/agent/prompts.py |
| 2026-05-26 | 新增 | models.py 补充 ProjectRelevance 模型 | src/models.py |
| 2026-05-27 | 新增 | Agent ReAct 引擎（Think→Act→Observe→Decide 循环 + 工具调度 + Trace 记录 + MatchReport 组装） | src/agent/engine.py |
| 2026-05-27 | 新增 | E2E 端到端测试脚本（字节豆包 JD + 简历 → Agent → 完整报告 + Trace） | _test_e2e.py |
| 2026-05-27 | 新增 | 报告渲染器（MatchReport → Markdown，8 模块对应 DEMO_v0 结构） | src/renderer.py |
| 2026-05-27 | 修改 | 简历/JD 解析器改用统一 llm_client.chat_json()，删除各自内联 _call_llm（去重 + retry 升级 2→3 次 + 指数退避） | src/parsers/resume_parser.py, src/parsers/jd_parser.py |
| 2026-05-27 | 新增 | PRD 第 11 章：Web 前端与部署方案（Streamlit vs React 选型、用户路径、UI 元素清单、部署方案） | docs/PRD.md |
| 2026-05-27 | 新增 | UI 设计稿 v0：Streamlit ASCII 布局 + 4 种状态 + 组件树 + 状态流转图 | assets/design/ui_mockup_v0.md |
| 2026-05-27 | 新增 | Streamlit Web 前端 web_app.py（两栏布局 + 解析预览 + 进度指示 + 报告渲染 + 下载 + 错误处理） | web_app.py |
| 2026-05-27 | 修改 | AgentEngine 增加 progress_callback 参数，Streamlit 可实时显示 ReAct 步骤 | src/agent/engine.py |
| 2026-05-27 | 新增 | 部署配置文件（requirements.txt 补 streamlit、.streamlit/config.toml、secrets.toml.example） | requirements.txt, .streamlit/ |
| 2026-05-27 | 修改 | .gitignore 补 .streamlit/secrets.toml | .gitignore |
