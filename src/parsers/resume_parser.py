"""简历解析器——PDF 文件 → 纯文本 → Resume Pydantic 对象。

链路：extract_text_from_pdf() → build_resume_prompt() → parse_resume_with_llm()
入口：parse_resume(file_path)
"""

from pathlib import Path

from loguru import logger

from src.models import EducationLevel, Resume, ResumeEducation, ResumeProject, ResumeSkill
from src.tools.llm_client import chat_json


# ============================================================
# 阶段 1：PDF → 纯文本
# ============================================================

def extract_text_from_pdf(pdf_path: str) -> str:
    """用 pypdf 从 PDF 文件提取纯文本，遍历所有页面并拼接。

    Args:
        pdf_path: PDF 文件的绝对或相对路径。

    Returns:
        提取到的纯文本字符串。

    Raises:
        FileNotFoundError: 文件不存在。
        RuntimeError: PDF 加密、损坏、或提取到的文本为空。
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    # 延迟导入，避免不读 PDF 时也加载 pypdf
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
    except PdfReadError as e:
        logger.error(f"PDF 读取失败（加密或损坏）: {pdf_path} | 错误: {e}")
        raise RuntimeError(
            f"无法读取 PDF，文件可能已加密或损坏: {pdf_path}"
        ) from e

    pages_text: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages_text.append(text.strip())
        else:
            logger.debug(f"第 {i+1} 页无可提取文本")

    full_text = "\n".join(pages_text)

    if not full_text.strip():
        logger.warning(f"PDF 提取到的文本为空: {pdf_path}")
        raise RuntimeError(
            f"PDF 中未提取到文本内容，可能是扫描版图片 PDF（当前不支持 OCR）: {pdf_path}"
        )

    logger.info(f"PDF 文本提取完成: {pdf_path} | 共 {len(reader.pages)} 页 | {len(full_text)} 字符")
    return full_text


# ============================================================
# 阶段 2：构造 Prompt
# ============================================================

RESUME_PARSE_SYSTEM_PROMPT = """你是一个精确的简历解析器，适配任意行业的简历（技术、金融、设计、产品等）。
你的任务是从简历文本中提取结构化信息，只输出一个 JSON 对象，不要包含任何其他文字。

## JSON 结构

{
  "name": "姓名",
  "email": "邮箱地址",
  "phone": "手机号（没有填 null）",
  "target_role": "求职方向——根据简历内容推断，如'AI PM'、'金融分析师'、'UI 设计师'",
  "education": [
    {
      "school": "学校全称",
      "degree": "bachelor | master | phd | other",
      "major": "专业全称",
      "start_date": "如'2025.09'（没有填''）",
      "end_date": "如'2026.07'（没有填''）",
      "gpa": "GPA——如果简历里写了就提取（如'3.85/4.0'），没有填 null",
      "highlights": ["在校亮点"]
    }
  ],
  "skills": [
    {
      "name": "技能名称（保留父类说明，如'Python (Pandas/NumPy)'）",
      "level": "简历明确写了熟练程度 → 如实取；没写明 → 填'未标明'",
      "category": "根据技能性质选择：编程语言 | 数据分析 | 金融 | 设计 | 产品 | 办公软件 | 语言能力 | 证书 | 其他"
    }
  ],
  "projects": [
    {
      "name": "项目名称",
      "role": "你的角色（PM/独立开发者/个人项目/团队负责人等）",
      "duration": "时间区间",
      "description": "项目简述",
      "highlights": ["关键成果"]
    }
  ],
  "internships": ["工作/实习经历简述——包括'工作经验''实习经历''项目经历'中的工作履历"]
}

## 解析规则

1. **不要编造**：简历里没有的信息不要凭空生成
2. **保持措辞**：不要改写简历原文，尤其是技能名、项目名、公司名
3. **GPA 优先提取**：教育背景中如果出现了数字如「GPA: 3.85/4.0」「3.72/4.0」，一定要提取到 gpa 字段
4. **skill.level 不瞎猜**：简历没写熟练程度 → 填"未标明"；简历写了「精通」「熟练」「了解」→ 如实用
5. **skill.category 看行业**：金融行业技能（Bloomberg、财务建模）标"金融"，设计工具（Figma、Sketch）标"设计"，编程标"编程语言"
6. **工作经验归入 internships**：「工作经验」「实习经历」「工作经历」等标题下的履历全部提取到 internships 数组
7. **教育经历至少提取一条**，信息不足的字段填空字符串或 null

## Few-shot 示例

示例 1 —— 技术/PM 简历片段：
输入：「张三 | 邮箱 zs@example.com | 求职方向: AI PM」
输出片段：{"name": "张三", "email": "zs@example.com", "target_role": "AI PM"}

示例 2 —— 金融简历教育：
输入：「北京大学 | 金融学硕士 | 2024.09 - 2026.07 | GPA: 3.85/4.0」
输出片段：{"school": "北京大学", "degree": "master", "major": "金融学", "start_date": "2024.09", "end_date": "2026.07", "gpa": "3.85/4.0", "highlights": []}

示例 3 —— 设计简历技能：
输入：「Figma (精通), Sketch (精通), Adobe XD, Photoshop, Illustrator」
输出片段：[
  {"name": "Figma", "level": "精通", "category": "设计"},
  {"name": "Sketch", "level": "精通", "category": "设计"},
  {"name": "Adobe XD", "level": "未标明", "category": "设计"},
  {"name": "Photoshop", "level": "未标明", "category": "设计"},
  {"name": "Illustrator", "level": "未标明", "category": "设计"}
]

示例 4 —— 金融技能：
输入：「Bloomberg Terminal, 财务建模, DCF 估值」
输出片段：[
  {"name": "Bloomberg Terminal", "level": "未标明", "category": "金融"},
  {"name": "财务建模", "level": "未标明", "category": "金融"},
  {"name": "DCF 估值", "level": "未标明", "category": "金融"}
]"""


def build_resume_prompt(raw_text: str) -> tuple[str, str]:
    """构造 LLM 解析简历的 prompt。

    Args:
        raw_text: 从 PDF 提取的简历纯文本。

    Returns:
        (system_prompt, user_prompt) 元组。
    """
    user_prompt = (
        "请解析以下简历文本，输出 JSON：\n\n"
        f"<resume_text>\n{raw_text}\n</resume_text>"
    )
    return RESUME_PARSE_SYSTEM_PROMPT, user_prompt


# ============================================================
# 阶段 3：LLM 输出 → Resume 对象
# ============================================================

def _build_education(raw: dict) -> ResumeEducation:
    """将 LLM 返回的 education dict 转为 ResumeEducation 对象。

    LLM 可能将 GPA 返回为 float（如 3.82），统一转 str。
    """
    gpa = raw.get("gpa")
    if gpa is not None:
        gpa = str(gpa)
    return ResumeEducation(
        school=raw.get("school", ""),
        degree=EducationLevel(raw.get("degree", "other")),
        major=raw.get("major", ""),
        start_date=raw.get("start_date", ""),
        end_date=raw.get("end_date", ""),
        gpa=gpa,
        highlights=raw.get("highlights", []),
    )


def _build_skill(raw: dict) -> ResumeSkill:
    """将 LLM 返回的 skill dict 转为 ResumeSkill 对象。"""
    return ResumeSkill(
        name=raw.get("name", ""),
        level=raw.get("level", "了解"),
        category=raw.get("category", "技术"),
    )


def _build_project(raw: dict) -> ResumeProject:
    """将 LLM 返回的 project dict 转为 ResumeProject 对象。"""
    return ResumeProject(
        name=raw.get("name", ""),
        role=raw.get("role", ""),
        duration=raw.get("duration", ""),
        description=raw.get("description", ""),
        highlights=raw.get("highlights", []),
    )


def parse_resume_with_llm(raw_text: str) -> Resume:
    """调用 DeepSeek 将简历纯文本解析为 Resume 对象。

    链路：raw_text → prompt → chat_json() → JSON → Pydantic 校验 → Resume

    Args:
        raw_text: 简历纯文本。

    Returns:
        经过 Pydantic 校验的 Resume 对象。

    Raises:
        RuntimeError: LLM 调用失败。
        ValueError: Pydantic 校验失败（LLM 输出结构与模型不匹配）。
    """
    system_prompt, user_prompt = build_resume_prompt(raw_text)
    logger.info(f"开始 LLM 解析简历 | 文本长度: {len(raw_text)} 字符")

    data = chat_json(system_prompt, user_prompt)

    try:
        # 将 LLM 返回的 dict 结构的子对象转换为 Pydantic 对象
        education_list = [
            _build_education(e) for e in data.get("education", [])
        ]
        skills_list = [
            _build_skill(s) for s in data.get("skills", [])
        ]
        projects_list = [
            _build_project(p) for p in data.get("projects", [])
        ]

        resume = Resume(
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone"),
            target_role=data.get("target_role", "AI PM"),
            education=education_list,
            skills=skills_list,
            projects=projects_list,
            internships=data.get("internships", []),
            raw_text=raw_text,
        )
        logger.info(
            f"简历解析完成 | 姓名={resume.name} | "
            f"教育={len(resume.education)}条 | "
            f"技能={len(resume.skills)}条 | "
            f"项目={len(resume.projects)}条"
        )
        return resume

    except Exception as e:
        logger.error(f"Pydantic 校验失败，LLM 输出与模型不匹配: {e}")
        raise ValueError(
            f"简历解析结果与预期结构不匹配，可能是 LLM 输出格式异常。"
            f"原始错误: {e}"
        ) from e


# ============================================================
# 入口
# ============================================================

def parse_resume(file_path: str) -> Resume:
    """主入口：PDF 文件路径 → Resume 对象。

    编排：
    1. extract_text_from_pdf() → 纯文本
    2. parse_resume_with_llm() → Resume 对象

    Args:
        file_path: PDF 简历文件路径。

    Returns:
        完整的 Resume Pydantic 对象（含 raw_text）。
    """
    logger.info(f"开始解析简历: {file_path}")
    raw_text = extract_text_from_pdf(file_path)
    resume = parse_resume_with_llm(raw_text)
    return resume


# ============================================================
# 自检入口
# ============================================================

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    test_pdf = "data/sample_resumes/my_resume.pdf"
    logger.info(f"自检模式: 解析 {test_pdf}")

    try:
        result = parse_resume(test_pdf)
        print(f"\n[OK] 简历解析成功!")
        print(f"  姓名: {result.name}")
        print(f"  邮箱: {result.email}")
        print(f"  求职方向: {result.target_role}")
        print(f"  教育 ({len(result.education)}):")
        for edu in result.education:
            print(f"    - {edu.school} | {edu.major} | {edu.start_date}-{edu.end_date}")
        print(f"  技能 ({len(result.skills)}):")
        for sk in result.skills:
            print(f"    - {sk.name} ({sk.level}, {sk.category})")
        print(f"  项目 ({len(result.projects)}):")
        for proj in result.projects:
            print(f"    - {proj.name} | {proj.role} | {proj.duration}")
        print(f"  实习: {result.internships if result.internships else '无'}")
    except Exception as e:
        logger.error(f"自检失败: {e}")
        print(f"\n[FAIL] 简历解析失败: {e}")
