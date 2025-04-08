try:
    from QTUtils import *
    print("✅ 模块导入成功")
except ImportError as e:
    print(f"❌ 导入失败：{e}")