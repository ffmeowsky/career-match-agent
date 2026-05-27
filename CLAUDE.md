# CareerMatch Agent · 代码规范

> 写代码前扫一眼。每一条都是硬约束，不是建议。

---

## 1. 编程语言规则

```yaml
Python 版本: "3.11+"
Type Hints:  "必须，所有函数参数和返回值"
字符串引号:  "双引号"
缩进:        "4 空格，禁用 tab"
行长:        "≤ 100 字符"
函数体:      "≤ 50 行，超过必须拆分"
文件行数:    "≤ 300 行，超过必须拆模块"
```

### Type Hints 示例

```python
# ✅ 正确
def parse_resume(file_path: str) -> dict[str, str]:
    ...

# ❌ 错误
def parse_resume(file_path):
    ...
```

---

## 2. 命名规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 函数 | `snake_case` | `parse_resume()` |
| 类 | `PascalCase` | `ResumeParser` |
| 常量 | `UPPER_SNAKE` | `MAX_RETRIES` |
| 私有成员 | 前缀 `_` | `_internal_helper()` |
| 布尔变量 | `is_` / `has_` 前缀 | `is_completed` |

---

## 3. 库的选用

### ✅ 推荐（只允许用这些）

| 用途 | 库 | 备注 |
|------|----|------|
| LLM 调用 | `openai` | DeepSeek 兼容接口 |
| HTTP 请求 | `httpx` | 备用，优先用 openai SDK |
| PDF 解析 | `pypdf` | **不用 PyPDF2** |
| 数据校验 | `pydantic` v2 | `@field_validator` 新语法 |
| 日志 | `loguru` | 永远不用 `print()` |
| 配置管理 | `python-dotenv` + `pydantic-settings` | 集中管理 |

### ❌ 禁用（写之前检查）

- **`PyPDF2`** — 已被 pypdf 取代
- **`print()`** — 用 `loguru.debug()` / `loguru.logger.info()`
- **裸 `logging`** — 用 loguru
- **全局可变变量** — 用类属性或参数传递
- **`pickle`** — 用 JSON 序列化

---

## 4. 错误处理

### 硬规则

- **所有 LLM API 调用必须包在 `try/except` 里**
- 错误信息要可推理——至少包含：**什么失败了、可能原因、建议操作**
- 关键路径每个步骤打 loguru 日志

### 示例

```python
from loguru import logger

try:
    response = client.chat.completions.create(model=MODEL_NAME, messages=msgs)
except Exception as e:
    logger.error(f"LLM 调用失败: {e}")
    raise RuntimeError(
        "DeepSeek API 请求失败，请检查 API Key 是否有效、网络是否可达。"
        f"原始错误: {e}"
    )
```

---

## 5. 注释规则

- **函数必须有中文 docstring**（一句话说清楚干什么 + 参数含义）
- 复杂逻辑用 `#` 行内注释（中文）
- `# TODO(姓名, YYYY-MM-DD): 待做事项`
- `# FIXME(姓名, YYYY-MM-DD): 已知问题`

### 示例

```python
def match_score(jd_text: str, resume_text: str) -> float:
    """计算 JD 与简历的匹配度，返回 0-100 的分数。

    Args:
        jd_text: 职位描述原文
        resume_text: 简历解析后的文本
    """
    ...
```

---

## 6. Pydantic 使用约定

- **所有 LLM 结构化输出必须经过 Pydantic 模型校验**
- 数据模型统一放在 `src/models.py`
- 每个 `Field` 必须填 `description`（中文）

### 示例

```python
from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    """JD-简历匹配结果。"""

    overall_score: float = Field(description="综合匹配度，0-100")
    skill_match: list[str] = Field(description="匹配的技能列表")
    skill_gaps: list[str] = Field(description="缺失的技能列表")
    summary: str = Field(description="一句话总结匹配情况")
```

---

## 7. API Key 处理

- **必须**从 `.env` 通过 `src/config.py` 读取
- **禁止**在任何源码中硬编码 Key（包括测试文件）
- `.env` **必须**在 `.gitignore` 中（已配置）

### 正确用法

```python
# src/config.py 中集中管理，其他模块只 import
from src.config import DEEPSEEK_API_KEY

# ❌ 永远不要：
# api_key = "sk-abc123..."
```

---

## 8. 测试规范

- 框架：`pytest`
- 关键函数必须有单元测试
- **LLM 调用必须 mock**，测试不得真调 API
- 测试文件放 `tests/`，命名格式 `test_<模块名>.py`
- 测试函数命名：`test_<被测函数>_<场景>()`

### 示例

```python
# tests/test_parser.py
import pytest
from unittest.mock import patch


def test_parse_resume_returns_text(tmp_path):
    """传入 PDF 路径，应返回解析后的文本字符串。"""
    ...


@patch("openai.resources.chat.Completions.create")
def test_match_score_with_mock_llm(mock_create):
    """Mock LLM 响应，验证匹配评分逻辑。"""
    ...
```

---

## 9. Git 提交规范

### 格式

```
<type>: <简短描述>
```

### Type 清单

| Type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加 PDF 简历解析器` |
| `fix` | Bug 修复 | `fix: 修复空 JD 导致崩溃的问题` |
| `docs` | 文档变更 | `docs: 更新 PRD v0.1` |
| `refactor` | 重构（不改功能） | `refactor: 抽取匹配算法为独立函数` |
| `test` | 测试 | `test: 添加 resume_parser 单元测试` |
| `chore` | 杂项（依赖、配置） | `chore: 添加 pypdf 依赖` |

### 规则

- 描述用中文
- 一行不超过 72 字符
- 一个 commit 只做一件事

---

## 10. 快速自查清单

写代码前逐条过一遍：

- [ ] 有 type hints 吗？
- [ ] 函数超过 50 行了吗？
- [ ] 用了 `print()` 吗？（应该用 loguru）
- [ ] 导入了 `PyPDF2` 吗？（应该用 `pypdf`）
- [ ] LLM 调用包了 try/except 吗？
- [ ] API Key 硬编码了吗？
- [ ] 关键函数写了中文 docstring 吗？
- [ ] commit message 格式对了吗？
