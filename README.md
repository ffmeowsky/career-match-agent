# CareerMatch Agent

> AI 驱动的求职匹配助手 — 上传简历 + 粘贴 JD，3 分钟获得完整匹配报告、能力缺口分析、面试题预测。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-deployed-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

---

## 功能

- **JD 智能解析**：自动过滤福利/公司介绍等无关内容，提取 must_have / nice_to_have 要求
- **简历解析**：支持 PDF 上传，自动提取教育、技能、项目经历
- **ReAct Agent 分析引擎**：多轮思考-行动-观察循环，自主决定分析路径
- **8 维技能匹配**：技能、经验、学历、项目、软素质、行业认知、产品方法论、成长潜力
- **能力缺口 + 话术**：精准定位短板，给出面试时应对话术
- **面试题预测**：基于缺口 × 优势生成 5 道高概率面试题
- **差异化优势提炼**：从项目中提炼让面试官记住的记忆点
- **求职信生成**（可选）：一键生成定制化求职信

---

## 快速开始

```bash
# 1. 克隆仓库
git clone git@github.com:ffmeowsky/career-match-agent.git
cd career-match-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 4. 启动 Web 界面
streamlit run web_app.py

# 或者命令行模式
python main.py
```

---

## 项目结构

```
career-match-agent/
├── main.py                  # CLI 入口
├── web_app.py               # Streamlit Web 界面（主入口）
├── requirements.txt
├── .env.example
├── CLAUDE.md                # AI 协作代码规范
├── AGENTS.md                # AI 协作项目说明
│
├── docs/                    # 产品文档
│   ├── PRD.md               # 产品需求文档（11 章）
│   ├── AGENT_DESIGN.md      # Agent 架构设计
│   ├── DEVELOPMENT_PLAN.md  # 开发计划 + DoD
│   ├── ITERATION_LOG.md     # 迭代记录
│   ├── DECISIONS.md         # 决策记录
│   ├── EVALUATION.md        # 评估报告
│   ├── DEMO_v0.md           # Demo 报告样例
│   ├── DEMO_JD_PARSER.md    # JD 解析器 Demo
│   └── DEMO_AGENT_TRACE.md  # Agent 运行 Trace Demo
│
├── assets/                  # 视觉素材
│   └── design/              # UI 设计稿
│
├── notes/                   # 学习笔记
│   ├── techniques.md        # 技术笔记
│   ├── pitfalls.md          # 踩坑记录
│   └── insights.md          # AI 协作心得
│
├── src/                     # 源代码
│   ├── config.py            # 环境配置（从 .env 读取）
│   ├── models.py            # Pydantic 数据模型（14 模型 + 6 枚举）
│   ├── renderer.py          # 报告渲染（MatchReport → Markdown）
│   ├── parsers/
│   │   ├── jd_parser.py     # JD 解析器
│   │   └── resume_parser.py # 简历解析器（PDF）
│   ├── tools/
│   │   └── llm_client.py    # LLM 客户端（DeepSeek OpenAI 兼容）
│   └── agent/
│       ├── engine.py        # ReAct Agent 主循环
│       ├── prompts.py       # 系统提示词
│       ├── tools.py         # 工具函数（技能匹配/缺口分析等）
│       └── tool_schemas.py  # Tool/JsonSchema 定义
│
├── data/                    # 测试数据
│   ├── sample_jds/          # 5 份不同风格 JD 样本
│   └── sample_resumes/      # 简历样本
│
├── outputs/                 # 分析输出（不提交 git）
├── tests/                   # 测试代码
└── .streamlit/              # Streamlit 配置
    ├── config.toml
    └── secrets.toml.example
```

---

## 部署

Web 应用已部署在 **Streamlit Cloud**，推送即自动部署。

本地部署时复制 secrets 模板并填入真实值：

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

---

## 技术栈

| 用途 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | Streamlit |
| AI 模型 | DeepSeek V4 Pro（OpenAI 兼容 API） |
| 数据校验 | Pydantic v2 |
| PDF 解析 | pypdf |
| 日志 | loguru |
| 配置管理 | python-dotenv + pydantic-settings |

---

## 作者

**ffmeowsky**

---

## 许可

MIT
