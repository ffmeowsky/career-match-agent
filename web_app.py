"""CareerMatch Agent — Streamlit Web 前端.

本地运行:
    streamlit run web_app.py

部署: Streamlit Cloud，详见 docs/PRD.md §11.4
"""

import os
import tempfile
from pathlib import Path

import streamlit as st

# ============================================================
# Streamlit Cloud secrets → os.environ 桥接
# （必须在导入 src 模块之前执行，因为 config.py 读 os.getenv）
# ============================================================
_secrets_loaded = False
try:
    for _key in ["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "MODEL_NAME"]:
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
            _secrets_loaded = True
except Exception as _e:
    st.warning(f"Streamlit Secrets 读取失败: {_e}。本地开发请确认 .env 文件存在。")

# 兜底：OpenAI SDK 默认读 OPENAI_API_KEY，如果 DEEPSEEK_API_KEY 已配则同步设置
if os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

from src.agent.engine import AgentEngine
from src.models import JobDescription, RequirementType, Resume
from src.parsers.jd_parser import parse_jd
from src.parsers.resume_parser import parse_resume
from src.renderer import render_report

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="CareerMatch Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# 工具函数
# ============================================================

TOOL_LABELS: dict[str, str] = {
    "score_project_relevance": "评估项目相关性",
    "score_skill_match": "8 维度技能匹配打分",
    "identify_skill_gap": "识别能力缺口",
    "extract_unique_advantages": "提取差异化优势",
    "predict_interview_questions": "预测面试题",
    "generate_cover_letter": "生成求职信",
    "think": "Agent 正在思考下一步...",
}


def _tool_label(tool_name: str) -> str:
    return TOOL_LABELS.get(tool_name, tool_name)


# ============================================================
# 页面渲染
# ============================================================

# --- 标题 ---
st.title("CareerMatch Agent")
st.caption("上传简历 + 粘贴 JD，3 分钟获得完整匹配报告")

st.divider()

# --- 输入区：两栏 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 上传简历")
    pdf_file = st.file_uploader(
        "拖拽或点击上传 PDF 简历",
        type=["pdf"],
        help="支持可搜索文本的 PDF 文件（非扫描版图片），≤10MB",
        label_visibility="collapsed",
    )

with col2:
    st.subheader("📋 粘贴 JD")
    jd_text = st.text_area(
        "JD 文本",
        height=220,
        placeholder=(
            "在此粘贴 JD 完整文本...\n\n"
            "支持：大厂校招、初创口语文案、中英混杂格式\n"
            "会自动过滤福利待遇等无关内容"
        ),
        label_visibility="collapsed",
    )

# --- 选项 ---
want_cover = st.checkbox("同时生成求职信（可选）", value=False)

# --- 检查输入就绪 ---
resume_ready = pdf_file is not None
jd_ready = bool(jd_text.strip()) and len(jd_text.strip()) >= 30
jd_too_short = bool(jd_text.strip()) and len(jd_text.strip()) < 30

if jd_too_short:
    st.warning("JD 内容过短（< 30 字），分析结果可能不够准确。建议粘贴完整 JD。")

# --- 开始分析按钮 ---
analyze_clicked = st.button(
    "🔍 开始分析",
    type="primary",
    disabled=not (resume_ready and jd_ready),
    use_container_width=True,
)

if not resume_ready and not jd_ready:
    st.info("👆 请上传简历并粘贴 JD 后开始分析")
elif not resume_ready:
    st.info("👆 请上传 PDF 简历")
elif not jd_ready:
    st.info("👆 请粘贴 JD 文本（至少 30 字）")

# ============================================================
# 分析流程
# ============================================================

if analyze_clicked and resume_ready and jd_ready:
    # --- 保存上传的简历到临时文件 ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as _tmp:
        _tmp.write(pdf_file.getbuffer())
        _tmp_path = _tmp.name

    try:
        # --- 阶段 1：解析 ---
        with st.status("正在解析...", expanded=True) as parse_status:
            st.write("解析简历...")
            resume: Resume = parse_resume(_tmp_path)
            st.write(
                f"✓ 简历解析完成：{resume.name} | "
                f"{resume.education[0].school if resume.education else '?'} | "
                f"技能 {len(resume.skills)} 项 | 项目 {len(resume.projects)} 项"
            )

            st.write("解析 JD...")
            jd: JobDescription = parse_jd(jd_text.strip())
            must_n = sum(1 for r in jd.requirements if r.type == RequirementType.MUST_HAVE)
            nice_n = sum(1 for r in jd.requirements if r.type == RequirementType.NICE_TO_HAVE)
            st.write(
                f"✓ JD 解析完成：{jd.company} | {jd.role} | "
                f"must {must_n} 条 · nice {nice_n} 条 | "
                f"信息充足：{'是' if jd.info_sufficient else '否'}"
            )
            parse_status.update(label="解析完成！", state="complete")

        # --- 阶段 2：Agent 分析 ---
        with st.status("Agent 正在分析...", expanded=True) as agent_status:
            step_count = [0]  # 用列表避免 nonlocal

            def on_progress(tool_name: str, status_str: str) -> None:
                """引擎回调：更新进度标签."""
                step_count[0] += 1
                label = _tool_label(tool_name)
                if status_str == "ok":
                    agent_status.update(
                        label=f"✓ {label} ({step_count[0]}/5)"
                    )
                elif status_str == "failed":
                    agent_status.update(
                        label=f"✗ {label} 失败，跳过"
                    )
                else:
                    agent_status.update(label=f"→ {label}")

            engine = AgentEngine(
                resume,
                jd,
                user_wants_cover_letter=want_cover,
                progress_callback=on_progress,
            )
            report, trace = engine.run()

            agent_status.update(
                label=f"分析完成！共 {len(trace)} 轮",
                state="complete",
            )

        # --- 阶段 3：渲染报告 ---
        st.divider()
        st.subheader("📊 匹配报告")

        md = render_report(report)
        st.markdown(md, unsafe_allow_html=False)

        # --- 阶段 4：下载按钮 ---
        safe_company = jd.company.replace("/", "_").replace(" ", "_")
        safe_role = jd.role.replace("/", "_").replace(" ", "_")
        download_name = f"report_{safe_company}_{safe_role}.md"

        st.download_button(
            label="📥 下载报告 (.md)",
            data=md,
            file_name=download_name,
            mime="text/markdown",
            use_container_width=True,
        )

    except Exception as e:
        st.error(
            f"分析过程中出现错误：{e}\n\n"
            "请检查：\n"
            "- 简历 PDF 是否为可搜索文本（非扫描版图片）\n"
            "- JD 文本是否包含岗位要求信息\n"
            "- 网络连接是否正常\n\n"
            "如持续失败，请稍后重试或联系开发者。"
        )

    finally:
        # 清理临时文件
        try:
            Path(_tmp_path).unlink()
        except Exception:
            pass
