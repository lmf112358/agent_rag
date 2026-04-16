"""
检查 qdrant_client Distance 枚举的实际值
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("检查 qdrant_client Distance 枚举")
print("=" * 60)

try:
    from qdrant_client.http import models

    print("\nDistance 枚举成员:")
    for member in models.Distance:
        print(f"  - {member.name} = {member.value}")

    print("\n可用值列表:")
    print([m.name for m in models.Distance])

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
