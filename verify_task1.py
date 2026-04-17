"""
验证 Task 1: 路径元数据提取增强
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("验证 Task 1: 路径元数据提取增强")
print("=" * 60)

try:
    from langchain_rag.document.processor import DocumentMetadata

    print("\n[1] 测试品牌提取...")
    test_cases = [
        ("特灵---10-22", "特灵"),
        ("开利-19XR", "开利"),
        ("约克", "约克"),
        ("麦克维尔", "麦克维尔"),
        ("良机-LCP", "良机"),
        ("未知品牌", None),
    ]
    all_passed = True
    for input_val, expected in test_cases:
        result = DocumentMetadata._extract_brand(input_val)
        status = "✅" if result == expected else "❌"
        print(f"    {status} _extract_brand('{input_val}') = '{result}' (expected: '{expected}')")
        if result != expected:
            all_passed = False

    print("\n[2] 测试型号提取...")
    test_cases = [
        ("CCTV-1650RT-6.45.pdf", "CCTV-1650RT-6.45"),
        ("19XR-84V4F30MHT5A.pdf", "19XR-84V4F30MHT5A"),
        ("LCP-4059S-L-C1-JC.pdf", "LCP-4059S-L-C1-JC"),
        ("SRN-900LG-1.pdf", "SRN-900LG-1"),
    ]
    for input_val, expected in test_cases:
        result, _ = DocumentMetadata._extract_model_spec(input_val)
        status = "✅" if result == expected else "❌"
        print(f"    {status} _extract_model_spec('{input_val}') = '{result}' (expected: '{expected}')")
        if result != expected:
            all_passed = False

    print("\n[3] 测试文件类型标签提取...")
    test_cases = [
        ("产品样本.pdf", "样本"),
        ("技术参数表.pdf", "参数表"),
        ("Product Report.pdf", "Product Report"),
        ("设备外形图.pdf", "外形图"),
        ("普通文件.pdf", None),
    ]
    for input_val, expected in test_cases:
        result = DocumentMetadata._extract_file_type_tag(input_val)
        status = "✅" if result == expected else "❌"
        print(f"    {status} _extract_file_type_tag('{input_val}') = '{result}' (expected: '{expected}')")
        if result != expected:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Task 1 验证通过！")
    else:
        print("❌ Task 1 验证失败")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
