"""快速验证 renderer 渲染功能."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.models import (
    Resume, ResumeEducation, ResumeSkill, ResumeProject,
    JobDescription, JDRequirement, RequirementType, EducationLevel,
    MatchScore, MatchDimension, MatchLevel, DimensionName, Confidence,
    UniqueAdvantage, SkillGap, InterviewQuestion, CoverLetter, NextStep, MatchReport
)
from src.renderer import render_report, render_to_file

# 构造一份含所有字段的 MatchReport
report = MatchReport(
    resume=Resume(
        name="测试用户", email="test@example.com", target_role="AI PM",
        education=[ResumeEducation(
            school="CityU(DG)", degree=EducationLevel.MASTER,
            major="工程管理", start_date="2025.09", end_date="2026.07",
            highlights=["CareerMatch Agent 项目"]
        )],
        skills=[ResumeSkill(name="Python", level="基础", category="技术")],
        projects=[ResumeProject(
            name="CareerMatch Agent", role="项目负责人",
            duration="2026.05-2026.06", description="AI求职助手",
            highlights=["PRD 10章", "ReAct Agent"]
        )],
        internships=[]
    ),
    jd=JobDescription(
        company="字节跳动", role="豆包 AI PM", location="北京",
        summary="负责豆包C端功能迭代",
        responsibilities=["C端功能迭代", "用户调研"],
        requirements=[
            JDRequirement(content="理解LLM基本概念", type=RequirementType.MUST_HAVE, category="技能"),
            JDRequirement(content="有AI产品作品", type=RequirementType.NICE_TO_HAVE, category="项目"),
        ]
    ),
    match_score=MatchScore(
        overall=78,
        dimensions=[
            MatchDimension(dimension=DimensionName.SKILL, label="技能匹配", score=76,
                           level=MatchLevel.PARTIAL_MATCH,
                           evidence="理解LLM概念但prompt engineering经验不够系统",
                           details=["LLM概念: 匹配", "Prompt Engineering: 部分"]),
            MatchDimension(dimension=DimensionName.EXPERIENCE, label="经验匹配", score=52,
                           level=MatchLevel.NO_MATCH,
                           evidence="无实习经历", details=[]),
            MatchDimension(dimension=DimensionName.EDUCATION, label="学历匹配", score=90,
                           level=MatchLevel.FULL_MATCH,
                           evidence="JD写专业不限，硕士学历超过要求", details=["硕士 > 本科要求"]),
            MatchDimension(dimension=DimensionName.PROJECT, label="项目匹配", score=82,
                           level=MatchLevel.FULL_MATCH,
                           evidence="CareerMatch Agent命中加分项", details=["AI产品作品: 匹配"]),
            MatchDimension(dimension=DimensionName.SOFT_SKILL, label="软素质", score=78,
                           level=MatchLevel.PARTIAL_MATCH,
                           evidence="主动学习但缺少推动落地的闭环", details=["好奇心: 匹配", "推动落地: 部分"]),
            MatchDimension(dimension=DimensionName.INDUSTRY_INSIGHT, label="行业认知", score=75,
                           level=MatchLevel.PARTIAL_MATCH,
                           evidence="PRD体现分析框架", details=["竞品分析: 部分"]),
            MatchDimension(dimension=DimensionName.PM_METHOD, label="产品方法论", score=62,
                           level=MatchLevel.PARTIAL_MATCH,
                           evidence="PRD完整但用户调研不系统", details=["需求分析: 匹配", "用户调研: 部分"]),
            MatchDimension(dimension=DimensionName.GROWTH, label="成长潜力", score=80,
                           level=MatchLevel.FULL_MATCH,
                           evidence="21天构建Agent产品", details=["学习速度: 匹配"]),
        ],
        verdict="建议投递，但需补强2个维度"
    ),
    advantages=[
        UniqueAdvantage(title="有自己的AI产品作品",
                        detail="CareerMatch Agent完整前期文档",
                        why_matters="命中加分项"),
        UniqueAdvantage(title="PM × AI 双视角",
                        detail="工程管理+AI项目实践",
                        why_matters="AI PM核心竞争力"),
        UniqueAdvantage(title="诚实且有自我认知",
                        detail="清楚标注产品边界",
                        why_matters="面试官会信任你"),
    ],
    skill_gaps=[
        SkillGap(gap="缺少跨职能协作经验",
                 impact="面试官最可能追问",
                 talking_points="虽无实习，但用AI协作开发了完整产品...",
                 confidence=Confidence.HIGH),
        SkillGap(gap="没有C端产品实操经验",
                 impact="可能被追问",
                 talking_points="可提交一份豆包体验分析报告作为补充...",
                 confidence=Confidence.MEDIUM),
    ],
    interview_questions=[
        InterviewQuestion(question="说说你的CareerMatch Agent",
                          why_asked="考察产品sense",
                          suggested_answer="第一层：问题是什么...",
                          category="产品sense", confidence=Confidence.HIGH),
        InterviewQuestion(question="豆包最大的产品问题是什么？",
                          why_asked="考察产品洞察",
                          suggested_answer="对话历史管理体验不够好...",
                          category="产品sense", confidence=Confidence.HIGH),
    ],
    cover_letter=CoverLetter(
        greeting="面试官你好，",
        body="我是测试用户，应聘AI PM岗位...",
        closing="测试用户",
        word_count=120
    ),
    next_steps=[
        NextStep(action="投递简历", detail="匹配度较高，建议投递", timing="投递前"),
        NextStep(action="深度使用产品", detail="使用豆包≥3天", timing="面试前"),
    ],
    generated_at="2026-05-27T12:00:00+00:00",
)

# 渲染
md = render_report(report)
print(f"渲染成功！总长度: {len(md)} 字符")
print("=" * 60)
print(md[:3000])

# 写文件
from pathlib import Path
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)
render_to_file(report, str(output_dir / "test_renderer.md"))
print(f"\n[OK] 已写入 outputs/test_renderer.md")
