"""快速批量测试：用 resume_parser 解析 3 份不同风格的简历并对比结果。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.parsers.resume_parser import parse_resume

test_files = [
    ("my_resume", "data/sample_resumes/my_resume.pdf"),
    ("finance", "data/sample_resumes/sample_resume_2_finance.pdf"),
    ("designer", "data/sample_resumes/sample_resume_3_designer.pdf"),
]

for label, path in test_files:
    print(f"\n{'='*60}")
    print(f"[{label}] {path}")
    try:
        r = parse_resume(path)
        print(f"  姓名: {r.name}")
        print(f"  邮箱: {r.email}")
        print(f"  方向: {r.target_role}")
        print(f"  教育 ({len(r.education)}):")
        for e in r.education:
            highlights_str = ", ".join(e.highlights[:2]) if e.highlights else "无"
            print(f"    [{e.degree.value}] {e.school} {e.major} | {e.start_date}-{e.end_date} | {highlights_str}")
        print(f"  技能 ({len(r.skills)}):")
        for s in r.skills[:5]:
            print(f"    {s.name} ({s.level}, {s.category})")
        if len(r.skills) > 5:
            print(f"    ... 另有 {len(r.skills)-5} 项")
        print(f"  项目 ({len(r.projects)}):")
        for p in r.projects:
            print(f"    {p.name} | {p.role} | {p.duration}")
        print(f"  实习: {r.internships if r.internships else '无'}")
    except Exception as e:
        print(f"  [FAIL] {e}")
