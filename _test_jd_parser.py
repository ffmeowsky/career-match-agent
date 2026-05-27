"""批量测试 JD 解析器：5 份不同风格的 JD。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from src.parsers.jd_parser import parse_jd
from src.models import RequirementType

JD_DIR = Path("data/sample_jds")
test_files = sorted(JD_DIR.glob("jd_*.txt"))

for fpath in test_files:
    label = fpath.stem
    text = fpath.read_text(encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"[{label}] ({len(text)} 字符)")
    try:
        jd = parse_jd(text)
        print(f"  公司: {jd.company} | 岗位: {jd.role} | 地点: {jd.location}")
        print(f"  摘要: {jd.summary[:80]}...")
        print(f"  职责: {len(jd.responsibilities)} 条")
        must = [r for r in jd.requirements if r.type == RequirementType.MUST_HAVE]
        nice = [r for r in jd.requirements if r.type == RequirementType.NICE_TO_HAVE]
        print(f"  硬性要求: {len(must)} 条 | 加分项: {len(nice)} 条")
        for r in jd.requirements:
            t = "[硬]" if r.type == RequirementType.MUST_HAVE else "[加]"
            print(f"    {t} [{r.category}] {r.content[:60]}")
        print(f"  信息充足: {jd.info_sufficient}")
        # 检查去噪
        benefit_kw = ["食堂", "零食", "健身", "期权", "咖啡", "Blue Bottle", "salary", "equity", "offsite", "Bali"]
        leaked = [kw for kw in benefit_kw if any(kw in r.content for r in jd.requirements)]
        if leaked:
            print(f"  [WARN] 疑似福利未过滤: {leaked}")
        else:
            print(f"  [OK] 去噪检查通过")
    except Exception as e:
        print(f"  [FAIL] {e}")
