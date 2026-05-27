# 关键决策记录 (ADR-Lite)

> 记录项目中的关键技术决策、架构选择及其理由。  
> 格式参考 ADR (Architecture Decision Record)，但更轻量。

---

## 决策记录

### D001 - 项目初始化

- **日期**：2026-05-22
- **决策**：采用 Python 技术栈，LLM 优先对接 DeepSeek API
- **背景**：PM 应届生主导，Python 生态对 AI/LLM 支持最成熟
- **替代方案**：Node.js + TypeScript（前端复用性更好，但 AI 生态弱于 Python）
- **后果**：后期若需 Web UI，需额外引入前端技术栈

---

*后续决策在此追加，每条使用 `### D00X` 编号。*
