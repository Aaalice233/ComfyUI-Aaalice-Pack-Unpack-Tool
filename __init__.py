import os
import subprocess
import sys

# Comfy-Pack 精简版本 - 只提供打包功能
# 不再包含节点功能，但仍需要API路由支持打包界面
from .nodes import api  # noqa
from .nodes.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

# 由于NODE_CLASS_MAPPINGS为空，仍需要导出以避免ComfyUI报错
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("Comfy-Pack => Installing Python dependencies")
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    stdout=subprocess.DEVNULL,
    cwd=os.path.dirname(__file__),
)
