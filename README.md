# CareerMatch Agent

> AI 驱动的求职匹配助手 — 分析 JD 与简历的匹配度，提供优化建议。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 3. 运行
python main.py
```

---

## 项目结构

```
career-match-agent/
├── docs/            # 产品文档（PRD、迭代记录、决策记录、评估报告）
├── assets/          # 视觉素材
├── notes/           # 学习笔记（踩坑、技术、AI 协作心得）
├── src/             # 源代码
│   ├── parsers/     # JD/简历解析器
│   ├── tools/       # 工具函数
│   ├── agent/       # LLM Agent 核心逻辑
│   ├── models.py    # Pydantic 数据模型
│   └── config.py    # 环境配置
├── data/            # 测试数据（JD、简历样本）
├── outputs/         # 分析输出
├── tests/           # 测试代码
├── main.py          # 入口
└── requirements.txt
```

---

## 作者

ffmeowsky

## 许可

MIT
