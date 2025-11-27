#!/usr/bin/env python3
"""
ComfyUI Workflow Unpacker - Cross-platform CLI
跨平台命令行解包工具

Usage:
    python -m comfy_pack.unpacker_cli <cpack_file> --comfyui <comfyui_dir>

Examples:
    # 自动检测环境
    python -m comfy_pack.unpacker_cli workflow.cpack.zip --comfyui /path/to/ComfyUI

    # 手动指定 Python 和 Git
    python -m comfy_pack.unpacker_cli workflow.cpack.zip --comfyui /path/to/ComfyUI \
        --python /path/to/python3 --git /usr/bin/git

    # 详细输出
    python -m comfy_pack.unpacker_cli workflow.cpack.zip --comfyui /path/to/ComfyUI -v
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .unpacker_core import (
    detect_python_environments,
    detect_git_executable,
    unpack_to_existing_comfyui,
    UnpackerError,
)


def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("  ComfyUI 工作流解包工具 (CLI)")
    print("  ComfyUI Workflow Unpacker")
    print("=" * 60)
    print()


def main(args: Optional[list] = None) -> int:
    """
    CLI 主入口

    Args:
        args: 命令行参数列表，如果为 None 则使用 sys.argv

    Returns:
        退出码：0 表示成功，非 0 表示失败
    """
    parser = argparse.ArgumentParser(
        prog="comfy-unpack",
        description="ComfyUI 工作流解包工具 - 将 .cpack.zip 文件解包到现有 ComfyUI 环境",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 自动检测环境
  %(prog)s workflow.cpack.zip --comfyui /path/to/ComfyUI

  # 手动指定 Python 和 Git
  %(prog)s workflow.cpack.zip --comfyui /path/to/ComfyUI \\
      --python /path/to/python3 --git /usr/bin/git

  # 详细输出模式
  %(prog)s workflow.cpack.zip --comfyui /path/to/ComfyUI -v
"""
    )

    parser.add_argument(
        "cpack",
        type=Path,
        help="要解包的 .cpack.zip 文件路径"
    )
    parser.add_argument(
        "--comfyui", "-c",
        type=Path,
        required=True,
        help="ComfyUI 根目录路径"
    )
    parser.add_argument(
        "--python", "-p",
        type=Path,
        default=None,
        help="Python 可执行文件路径（可选，默认自动检测）"
    )
    parser.add_argument(
        "--git", "-g",
        type=Path,
        default=None,
        help="Git 可执行文件路径（可选，默认自动检测）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    parsed_args = parser.parse_args(args)

    # 打印横幅
    print_banner()

    # 验证输入文件
    cpack_path: Path = parsed_args.cpack
    if not cpack_path.exists():
        print(f"错误: 找不到文件 {cpack_path}", file=sys.stderr)
        return 1

    if not cpack_path.is_file():
        print(f"错误: {cpack_path} 不是文件", file=sys.stderr)
        return 1

    # 验证 ComfyUI 目录
    comfyui_dir: Path = parsed_args.comfyui
    if not comfyui_dir.exists():
        print(f"错误: ComfyUI 目录不存在 {comfyui_dir}", file=sys.stderr)
        return 1

    if not comfyui_dir.is_dir():
        print(f"错误: {comfyui_dir} 不是目录", file=sys.stderr)
        return 1

    # 检查是否是有效的 ComfyUI 目录（检查是否存在 main.py 或 comfy 目录）
    if not (comfyui_dir / "main.py").exists() and not (comfyui_dir / "comfy").exists():
        print(f"警告: {comfyui_dir} 可能不是有效的 ComfyUI 目录", file=sys.stderr)
        print("  （找不到 main.py 或 comfy 目录）", file=sys.stderr)

    # 检测或验证 Python
    python_exe: Optional[Path] = parsed_args.python
    if python_exe:
        if not python_exe.exists():
            print(f"错误: 指定的 Python 不存在 {python_exe}", file=sys.stderr)
            return 1
        print(f"使用指定的 Python: {python_exe}")
    else:
        print("正在自动检测 Python 环境...")
        pythons = detect_python_environments(comfyui_dir)
        if not pythons:
            print("错误: 未找到 Python 环境", file=sys.stderr)
            print("提示: 请使用 --python 参数手动指定 Python 路径", file=sys.stderr)
            return 1
        python_exe = pythons[0]
        print(f"  检测到: {python_exe}")
        if len(pythons) > 1:
            print(f"  （还发现了 {len(pythons) - 1} 个其他 Python 环境）")

    # 检测或验证 Git
    git_exe: Optional[Path] = parsed_args.git
    if git_exe:
        if not git_exe.exists():
            print(f"警告: 指定的 Git 不存在 {git_exe}", file=sys.stderr)
            git_exe = None
        else:
            print(f"使用指定的 Git: {git_exe}")
    else:
        print("正在自动检测 Git...")
        git_exe = detect_git_executable(comfyui_dir)
        if git_exe:
            print(f"  检测到: {git_exe}")
        else:
            print("  警告: 未找到 Git，插件克隆功能可能受限")
            print("  提示: 可使用 --git 参数手动指定 Git 路径")

    print()

    # 定义回调函数
    def log_callback(msg: str):
        print(msg)

    def progress_callback(stage: str, pct: int):
        if parsed_args.verbose:
            print(f"[{pct:3d}%] {stage}")

    # 执行解包
    print(f"开始解包: {cpack_path.name}")
    print(f"目标目录: {comfyui_dir}")
    print("-" * 50)

    try:
        success = unpack_to_existing_comfyui(
            cpack_path,
            comfyui_dir,
            python_exe,
            git_exe,
            progress_callback=progress_callback,
            log_callback=log_callback
        )

        if success:
            print()
            print("=" * 50)
            print("解包完成！")
            print("=" * 50)
            print()
            print("下一步:")
            print("  1. 启动 ComfyUI")
            print("  2. 在工作流列表中找到解包的工作流")
            print()
            return 0
        else:
            print()
            print("解包过程中出现错误", file=sys.stderr)
            return 1

    except UnpackerError as e:
        print(f"\n解包错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n用户取消操作", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n未知错误: {e}", file=sys.stderr)
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
