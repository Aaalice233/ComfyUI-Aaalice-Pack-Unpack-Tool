"""
开发环境下运行 GUI（不需要打包成 EXE）
用于快速测试和调试
"""
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
root_dir = Path(__file__).parent.parent
src_dir = root_dir / 'src'
sys.path.insert(0, str(src_dir))

# 导入并运行 GUI
from comfy_pack.unpacker_gui import main

if __name__ == "__main__":
    main()

