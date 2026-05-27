"""生成 2 份假简历 PDF——测试解析器对不同风格的兼容性。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
pdfmetrics.registerFont(TTFont("SimHei", FONT_PATH))

WIDTH, HEIGHT = A4
OUTPUT_DIR = "data/sample_resumes"

# ---- 自定义含中文的样式 ----
h1 = ParagraphStyle("CN_H1", fontName="SimHei", fontSize=22, leading=30, spaceAfter=6)
h2 = ParagraphStyle("CN_H2", fontName="SimHei", fontSize=14, leading=20, spaceAfter=4, spaceBefore=10)
body = ParagraphStyle("CN_Body", fontName="SimHei", fontSize=10, leading=16)


def build_pdf(filename: str, content: list[str]):
    """生成单页 PDF，content 每项为一行。"""
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        topMargin=30, bottomMargin=30, leftMargin=40, rightMargin=40
    )
    story: list = []
    for text in content:
        if text.startswith("# "):
            story.append(Paragraph(text[2:], h1))
        elif text.startswith("## "):
            story.append(Spacer(1, 8))
            story.append(Paragraph(text[3:], h2))
        else:
            story.append(Paragraph(text, body))
        story.append(Spacer(1, 2))
    doc.build(story)


# ============================================================
# 简历 2：金融分析师
# ============================================================
finance_resume = [
    "# 李明",
    "手机: 138-0000-0001 | 邮箱: liming@example.com | 求职方向: 金融分析师",

    "## 教育背景",
    "北京大学 | 金融学硕士 | 2024.09 - 2026.07 | GPA: 3.85/4.0",
    "武汉大学 | 经济学学士 | 2020.09 - 2024.06 | GPA: 3.72/4.0",

    "## 专业技能",
    "数据工具: Python (Pandas/NumPy), SQL, Excel (VBA), Wind, Bloomberg Terminal",
    "分析方法: 财务建模, DCF 估值, 比率分析, 回归分析, 蒙特卡洛模拟",
    "证书: CFA Level II Candidate, 证券从业资格证",
    "语言: 中文 (母语), 英语 (流利, 托福 105)",

    "## 实习经历",
    "中信证券 | 行业研究助理 | 2025.06 - 2025.09",
    "- 覆盖 A 股 AI 赛道 6 家上市公司，撰写深度研报 3 篇（单篇阅读量 2,000+）",
    "- 搭建 DCF 财务模型，预测宁德时代 2026-2028 年营收与利润",
    "- 协助团队完成 2 个 IPO 项目的行业分析章节",

    "华泰证券 | 投行部实习生 | 2024.07 - 2024.09",
    "- 参与某新能源企业 Pre-IPO 轮融资，整理尽调材料 200+ 页",
    "- 独立完成可比公司分析，覆盖 10 家 A 股/港股上市公司",

    "## 项目经历",
    "A 股 AI 概念股量化筛选模型 | 个人项目 | 2025.11 - 2025.12",
    "- 用 Python 爬取 4,000+ A 股 AI 概念股财务数据，搭建多因子筛选模型",
    "- 回测年化收益率 18.7%，夏普比率 1.42",
    "- 开源在 GitHub，获得 120+ Stars",

    "## 其他",
    "CFA 协会会员, 北大金融俱乐部副会长, 马拉松爱好者 (PB 3:45)"
]

# ============================================================
# 简历 3：UI 设计师
# ============================================================
designer_resume = [
    "# 王晓华",
    "手机: 159-0000-0002 | 邮箱: wangxh@design.cn | 作品集: dribbble.com/wangxh",

    "## 关于我",
    "3 年经验 UI 设计师，专注 B 端 SaaS 产品与移动端设计。擅长从用户旅程出发构建设计语言系统，",
    "曾独立负责一款 50 万用户产品的 0→1 设计。相信好设计是「让用户感觉不到设计的存在」。",

    "## 教育",
    "中国美术学院 | 视觉传达设计 硕士 | 2021.09 - 2024.06",
    "湖北美术学院 | 数字媒体艺术 学士 | 2017.09 - 2021.06",

    "## 工具",
    "设计: Figma (精通), Sketch (精通), Adobe XD, Photoshop, Illustrator",
    "动效: After Effects, Principle, Rive",
    "协作: Notion, Linear, Zeplin, Abstract",
    "前端基础: HTML/CSS (能独立切图), 了解 React 组件化思维",

    "## 工作经验",
    "字节跳动 (飞书) | UI 设计师 | 2024.07 - 至今",
    "- 负责飞书日历模块的视觉改版，DAU 提升 12%",
    "- 主导设计语言系统 (Design Token) 从 v1→v2 迁移，覆盖 200+ 组件",
    "- 与 3 名产品经理 + 6 名前端工程师协作，输出高保真设计稿 + 交互原型",

    "某 SaaS 初创 (智简科技) | 唯一设计师 | 2023.03 - 2024.06",
    "- 从零搭建 B 端 CRM 产品的完整设计体系（品牌 → 组件库 → 交互规范）",
    "- 用户量从 0 增长至 5 万，NPS 从 32 提升至 58",
    "- 独立完成 80+ 页面设计，产出 3 个版本迭代",

    "## 项目",
    "Design System · Chuva | 开源项目 | 2024.10 - 至今",
    "- 基于 Radix UI + Tailwind CSS 构建的开源设计系统，GitHub 800+ Stars",
    "- 被 3 家 startup 采用为企业内部组件库",
    "- 包含 60+ Figma 组件 + 配套 React 代码实现",

    "AI 生图工具 PromptCraft | 副项目 | 2023.06 - 2023.09",
    "- 一款面向设计师的 Stable Diffusion Prompt 辅助工具",
    "- 负责整体 UX 流程设计 + 部分前端实现 (React)",
    "- 上线 3 个月 DAU 2,000+, 付费转化率 4.8%",

    "## 其他",
    "dribbble 年度推荐设计师 (2024), Figma 社区贡献者, 独立音乐人 (业余)"
]

# ---- 生成 ----
build_pdf(f"{OUTPUT_DIR}/sample_resume_2_finance.pdf", finance_resume)
print(f"[OK] {OUTPUT_DIR}/sample_resume_2_finance.pdf 已生成")

build_pdf(f"{OUTPUT_DIR}/sample_resume_3_designer.pdf", designer_resume)
print(f"[OK] {OUTPUT_DIR}/sample_resume_3_designer.pdf 已生成")
