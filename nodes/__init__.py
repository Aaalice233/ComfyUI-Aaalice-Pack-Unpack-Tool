import pathlib
import sys

SRC_DIR = pathlib.Path(__file__).parent.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 导入API模块以支持打包功能
from . import api  # noqa
