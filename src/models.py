"""Pydantic 数据模型——CareerMatch Agent 所有结构化数据定义。"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================
# 枚举定义
# ============================================================

class RequirementType(str, Enum):
    """JD 要求的类型。"""
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class MatchLevel(str, Enum):
    """单维度匹配程度。"""
    FULL_MATCH = "full_match"
    PARTIAL_MATCH = "partial_match"
    NO_MATCH = "no_match"


class Confidence(str, Enum):
    """分析结论的置信度。"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EducationLevel(str, Enum):
    """学历层次。"""
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    OTHER = "other"


class DimensionName(str, Enum):
    """匹配维度名称——对应 PRD 定义的 8 个维度。"""
    SKILL = "skill"                # 技能匹配
    EXPERIENCE = "experience"       # 经验匹配
    EDUCATION = "education"         # 学历匹配
    PROJECT = "project"             # 项目匹配
    SOFT_SKILL = "soft_skill"       # 软素质
    INDUSTRY_INSIGHT = "industry"   # 行业认知
    PM_METHOD = "pm_method"         # 产品方法论
    GROWTH = "growth"              # 成长潜力


# ============================================================
# 简历相关模型
# ============================================================

class ResumeProject(BaseModel):
    """简历中的单个项目经历。"""
    name: str = Field(description="项目名称")
    role: str = Field(description="你在项目中的角色，如'项目负责人'")
    duration: str = Field(description="项目时间，如'2025.09-2025.12'")
    description: str = Field(description="项目描述，做了什么、用了什么技术")
    highlights: list[str] = Field(default_factory=list, description="关键成果或亮点")


class ResumeSkill(BaseModel):
    """单项技能。"""
    name: str = Field(description="技能名称，如'Python'")
    level: str = Field(description="熟练程度，如'熟练'、'了解'、'精通'")
    category: str = Field(default="技术", description="技能分类：技术/产品/语言/其他")


class ResumeEducation(BaseModel):
    """教育经历。"""
    school: str = Field(description="学校名称")
    degree: EducationLevel = Field(description="学历层次")
    major: str = Field(description="专业名称")
    start_date: str = Field(description="入学时间，如'2025.09'")
    end_date: str = Field(description="预计毕业时间，如'2026.07'")
    gpa: Optional[str] = Field(default=None, description="GPA（如有）")
    highlights: list[str] = Field(default_factory=list, description="在校亮点：奖学金、竞赛、社团等")


class Resume(BaseModel):
    """完整简历结构化对象——解析器输出。"""
    name: str = Field(description="姓名")
    email: str = Field(description="邮箱")
    phone: Optional[str] = Field(default=None, description="手机号")
    target_role: str = Field(default="AI PM", description="求职方向")
    education: list[ResumeEducation] = Field(default_factory=list, description="教育经历")
    skills: list[ResumeSkill] = Field(default_factory=list, description="技能列表")
    projects: list[ResumeProject] = Field(default_factory=list, description="项目经历")
    internships: list[str] = Field(default_factory=list, description="实习经历简述")
    raw_text: str = Field(default="", description="简历原始文本（解析前保留）")

    @field_validator("education")
    @classmethod
    def education_not_empty(cls, v: list[ResumeEducation]) -> list[ResumeEducation]:
        """教育经历至少填一条。"""
        if not v:
            raise ValueError("教育经历不能为空")
        return v

    # 模型级示例（用于 AI 生成参考）
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "用户",
                "email": "user@example.com",
                "target_role": "AI PM",
                "education": [{
                    "school": "Example University",
                    "degree": "master",
                    "major": "Computer Science",
                    "start_date": "2025.09",
                    "end_date": "2026.07",
                    "highlights": ["CareerMatch Agent 项目"]
                }],
                "skills": [
                    {"name": "Python", "level": "基础", "category": "技术"},
                    {"name": "产品需求分析", "level": "熟练", "category": "产品"}
                ],
                "projects": [{
                    "name": "CareerMatch Agent",
                    "role": "项目负责人",
                    "duration": "2026.05-2026.06",
                    "description": "AI Agent 求职助手，21 天从 0 到上线",
                    "highlights": ["PRD 10 章", "ReAct Agent 7 工具"]
                }],
                "internships": []
            }
        }
    }


# ============================================================
# JD 相关模型
# ============================================================

class JDRequirement(BaseModel):
    """JD 中的单条要求。"""
    content: str = Field(description="要求原文或归纳")
    type: RequirementType = Field(description="硬性要求还是加分项")
    category: str = Field(
        default="技能",
        description="所属类别：技能/经验/学历/软素质/其他"
    )


class JobDescription(BaseModel):
    """完整 JD 结构化对象——JD 解析器输出。"""
    company: str = Field(description="公司名称")
    role: str = Field(description="岗位名称")
    location: str = Field(default="未知", description="工作地点")
    summary: str = Field(default="", description="一句话岗位摘要")
    responsibilities: list[str] = Field(default_factory=list, description="岗位职责列表")
    requirements: list[JDRequirement] = Field(default_factory=list, description="任职要求")
    raw_text: str = Field(default="", description="JD 原始文本（解析前保留）")
    info_sufficient: bool = Field(default=True, description="JD 信息是否足够分析")

    @model_validator(mode="after")
    def requirements_empty_only_when_insufficient(self):
        """JD 信息不足时可允许 requirements 为空，否则至少一条。"""
        if not self.requirements and self.info_sufficient:
            raise ValueError("JD 要求不能为空（info_sufficient=True 时至少需要一条要求）")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "company": "字节跳动",
                "role": "豆包 AI PM 应届生",
                "location": "北京",
                "summary": "负责豆包 C 端功能的需求定义与迭代",
                "responsibilities": [
                    "参与豆包 C 端功能的需求定义与迭代",
                    "通过用户调研和数据分析发现产品机会",
                    "跟踪国内外 AI 产品动态"
                ],
                "requirements": [
                    {"content": "理解大模型基本概念", "type": "must_have", "category": "技能"},
                    {"content": "有自己的 AI 产品作品", "type": "nice_to_have", "category": "项目"}
                ]
            }
        }
    }


# ============================================================
# 匹配分析相关模型
# ============================================================

class MatchDimension(BaseModel):
    """单个维度的匹配分析——对应 PRD 的 8 维度。"""
    dimension: DimensionName = Field(description="维度名称")
    label: str = Field(description="维度中文名，如'技能匹配'")
    score: float = Field(ge=0, le=100, description="该维度评分 0-100")
    level: MatchLevel = Field(description="匹配程度")
    evidence: str = Field(description="一句证据——为什么给这个分")
    details: list[str] = Field(default_factory=list, description="子项分析要点")


class MatchScore(BaseModel):
    """综合匹配度——8 维汇总。"""
    overall: float = Field(ge=0, le=100, description="综合评分 0-100")
    dimensions: list[MatchDimension] = Field(description="各维度详情")
    verdict: str = Field(description="一句话判定，如'建议投递，但需补强 2 个维度'")


class UniqueAdvantage(BaseModel):
    """差异化优势。"""
    title: str = Field(description="优势标题")
    detail: str = Field(description="优势详细说明")
    why_matters: str = Field(description="为什么这条优势对这个岗位很重要")


class ProjectRelevance(BaseModel):
    """单个项目与目标岗位的相关性评估——score_project_relevance 的输出。"""
    project_name: str = Field(description="项目名称")
    relevance_score: float = Field(ge=0, le=5, description="相关性分 0-5（5=高度对口）")
    direction_match: str = Field(description="方向是否匹配 + 一句解释")
    depth_assessment: str = Field(description="深度评估：课程作业级 / Demo 级 / 可上线级")
    key_evidence: str = Field(description="项目中和 JD 最相关的 1-2 个亮点")
    suggestion: str = Field(description="如果相关性 < 3，给一条提升建议")


class SkillGap(BaseModel):
    """能力缺口 + 面试话术。"""
    gap: str = Field(description="缺口描述——JD 要什么、你差什么")
    impact: str = Field(description="这个缺口在面试中的影响")
    talking_points: str = Field(description="面试时怎么说——逐字稿级回答模板")
    confidence: Confidence = Field(description="缺口判断的置信度")


class ResumeEdit(BaseModel):
    """简历定制优化建议——suggest_resume_edits 的输出单元。"""
    location: str = Field(description="改哪里，如'项目经历-CanteenGo 第2条'或'技能栈'")
    original: str = Field(description="简历中的原文（如无明确原文则写'（简历中未提及）'）")
    suggested: str = Field(description="建议改写后的文本")
    reason: str = Field(description="为什么这样改更匹配该 JD——要具体到 JD 的某个要求")
    priority: Confidence = Field(description="优先级 high/medium/low——high=直接影响匹配度的关键改动")


class InterviewQuestion(BaseModel):
    """面试预测题。"""
    question: str = Field(description="面试题原文")
    why_asked: str = Field(description="面试官为什么问这个——考察点分析")
    suggested_answer: str = Field(description="参考回答框架与要点")
    category: str = Field(default="产品sense", description="题型分类：产品sense/技术理解/行为/压力")
    confidence: Confidence = Field(description="这道题被问到的概率置信度")


class CoverLetter(BaseModel):
    """个性化求职信。"""
    greeting: str = Field(default="面试官你好，", description="称呼")
    body: str = Field(description="正文")
    closing: str = Field(default="用户", description="署名")
    word_count: int = Field(default=0, description="正文字数")


class CompanyBrief(BaseModel):
    """公司评估简报。"""
    company: str = Field(description="公司名称")
    pmf_status: str = Field(description="PMF 状态评估")
    funding_status: str = Field(description="融资/现金流评估")
    leader_assessment: str = Field(description="直属 Leader 评估")
    direction_fit: str = Field(description="方向是否主流 + 匹配度")
    risk_note: str = Field(description="风险提示")
    suggested_questions: list[str] = Field(default_factory=list, description="面试时建议反问 Leader 的问题")
    confidence: Confidence = Field(description="评估置信度——信息越少越不确定")


class NextStep(BaseModel):
    """下一步行动建议。"""
    action: str = Field(description="建议的行动")
    detail: str = Field(description="具体怎么做")
    timing: str = Field(default="投递前", description="什么时候做：投递前/面试前/面试中/面试后")


# ============================================================
# 汇总报告
# ============================================================

class MatchReport(BaseModel):
    """完整匹配报告——Agent 最终输出，对应 DEMO_v0.md 的 8 个模块。"""
    resume: Resume = Field(description="解析后的简历摘要")
    jd: JobDescription = Field(description="解析后的 JD 摘要")
    match_score: MatchScore = Field(description="综合匹配度 + 8 维详情")
    advantages: list[UniqueAdvantage] = Field(description="差异化优势 Top 3")
    skill_gaps: list[SkillGap] = Field(description="能力缺口 + 面试话术")
    interview_questions: list[InterviewQuestion] = Field(description="面试预测题 Top 5")
    cover_letter: Optional[CoverLetter] = Field(default=None, description="求职信（可选）")
    company_brief: Optional[CompanyBrief] = Field(default=None, description="公司评估简报（可选）")
    next_steps: list[NextStep] = Field(default_factory=list, description="下一步行动建议")
    model_used: str = Field(default="deepseek-chat", description="生成报告使用的模型")
    generated_at: str = Field(default="", description="报告生成时间 ISO 格式")
    resume_edits: list[ResumeEdit] = Field(
        default_factory=list,
        description="简历定制优化建议（可选，用户主动触发时生成）",
    )


# ============================================================
# 自检入口
# ============================================================

if __name__ == "__main__":
    """快速自检：用示例数据构造一份 Resume，验证模型能正常实例化。"""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    r = Resume(
        name="用户",
        email="user@example.com",
        target_role="AI PM",
        education=[
            ResumeEducation(
                school="Example University",
                degree=EducationLevel.MASTER,
                major="Computer Science",
                start_date="2025.09",
                end_date="2026.07",
                highlights=["CareerMatch Agent"]
            )
        ],
        skills=[
            ResumeSkill(name="Python", level="基础", category="技术"),
            ResumeSkill(name="产品需求分析", level="熟练", category="产品"),
        ],
        projects=[
            ResumeProject(
                name="CareerMatch Agent",
                role="项目负责人",
                duration="2026.05-2026.06",
                description="AI Agent 求职助手，21 天从 0 到上线",
                highlights=["10 章 PRD", "ReAct Agent 7 工具", "Pydantic 校验"]
            )
        ],
    )
    print("[OK] Resume 模型验证通过")
    print(f"   姓名: {r.name}")
    print(f"   教育: {r.education[0].school} {r.education[0].major}")
    print(f"   项目: {r.projects[0].name}")
    print(f"   技能数: {len(r.skills)}")

    jd = JobDescription(
        company="字节跳动",
        role="豆包 AI PM 应届生",
        location="北京",
        responsibilities=["C 端功能迭代", "用户调研", "AI 产品竞品分析"],
        requirements=[
            JDRequirement(content="理解大模型基本概念", type=RequirementType.MUST_HAVE),
            JDRequirement(content="有 AI 产品作品", type=RequirementType.NICE_TO_HAVE),
        ],
    )
    print("[OK] JobDescription 模型验证通过")
    print(f"   公司: {jd.company} | 岗位: {jd.role}")
    print("[OK] 所有基础模型自检通过！")
