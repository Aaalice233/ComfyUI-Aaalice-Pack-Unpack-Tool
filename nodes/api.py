from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Union

import folder_paths
from aiohttp import web
from server import PromptServer

ZPath = Union[Path, zipfile.Path]
TEMP_FOLDER = Path(__file__).parent.parent / "temp"
COMFY_PACK_DIR = Path(__file__).parent.parent / "src" / "comfy_pack"


async def send_pack_progress(
    client_id: str,
    stage: str,
    message: str,
    current: int = 0,
    total: int = 0,
    current_file: str = "",
    percentage: int = 0,
    eta: float = 0.0,
    level: str = "info",
) -> None:
    """
    Send pack progress update via WebSocket.

    Args:
        client_id: Client ID for WebSocket routing
        stage: Current stage identifier
        message: Human-readable message
        current: Current progress count
        total: Total items count
        current_file: Current file being processed
        percentage: Progress percentage (0-100)
        eta: Estimated time remaining in seconds
        level: Log level ('info', 'success', 'progress', 'cache')
    """
    data = {
        "type": "pack_progress",
        "data": {
            "stage": stage,
            "message": message,
            "current_file": current_file,
            "progress": current,
            "total": total,
            "percentage": percentage,
            "eta": eta,
            "level": level,
        },
    }
    await PromptServer.instance.send_json("pack_progress", data, client_id)


def get_snapshot_path() -> Path | None:
    manager_file_path = Path(
        folder_paths.get_user_directory(), "default", "ComfyUI-Manager"
    )
    return manager_file_path / "snapshots"


async def _save_snapshot() -> dict[str, Any]:
    save_snapshot_route = next(
        (
            route
            for route in PromptServer.instance.routes
            if route.path == "/snapshot/save"
        ),
        None,
    )
    if not save_snapshot_route:
        raise RuntimeError("ComfyUI-Manager must be installed to save snapshot")
    await save_snapshot_route.handler(None)
    snapshot_path = get_snapshot_path()
    if not snapshot_path.exists():
        raise RuntimeError("Snapshot save failed")

    most_recent = max(
        snapshot_path.glob("*.json"), key=lambda x: x.stat().st_mtime, default=None
    )
    if not most_recent:
        raise RuntimeError("Snapshot save failed")
    with most_recent.open("r") as f:
        return json.load(f)


async def _write_snapshot(path: ZPath, data: dict) -> None:
    snapshot = await _save_snapshot()
    with path.joinpath("snapshot.json").open("w") as f:
        snapshot.update(
            {
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "models": [],  # 简化版不收集模型信息
            }
        )
        f.write(json.dumps(snapshot, indent=2))


async def _write_workflow(path: ZPath, data: dict) -> None:
    print("Package => Writing workflow")
    with path.joinpath("workflow_api.json").open("w") as f:
        f.write(json.dumps(data["workflow_api"], indent=2))
    with path.joinpath("workflow.json").open("w") as f:
        f.write(json.dumps(data["workflow"], indent=2))


async def _write_completion_message(path: ZPath, data: dict) -> None:
    """写入自定义完成消息"""
    completion_message = data.get("completion_message", "").strip()
    if completion_message:
        print("Package => Writing completion message")
        with path.joinpath("completion_message.txt").open("w", encoding="utf-8") as f:
            f.write(completion_message)


async def _write_inputs(path: ZPath, data: dict) -> None:
    print("Package => Writing inputs (自动处理所有文件)")
    if isinstance(path, Path):
        path.joinpath("input").mkdir(exist_ok=True)

    input_dir = folder_paths.get_input_directory()

    # 简化版：自动包含所有输入文件，无需用户选择
    selected = None  # 不再过滤文件，包含所有文件

    src_root = Path(input_dir).absolute()
    for src in src_root.glob("**/*"):
        rel = src.relative_to(src_root)
        # 简化版：不再检查文件选择，直接包含所有文件
        if src.is_dir():
            if isinstance(path, Path):
                path.joinpath("input").joinpath(rel).mkdir(parents=True, exist_ok=True)
        if src.is_file():
            with path.joinpath("input").joinpath(rel).open("wb") as f:
                with open(src, "rb") as input_file:
                    shutil.copyfileobj(input_file, f)


@PromptServer.instance.routes.post("/bentoml/pack")
async def pack_workspace(request):
    data = await request.json()
    client_id = data.get("client_id", "")

    # Send initial progress
    if client_id:
        await send_pack_progress(
            client_id,
            stage="preparing",
            message="开始准备打包...",
            percentage=5,
            level="info",
        )

    TEMP_FOLDER.mkdir(exist_ok=True)
    older_than_1h = time.time() - 60 * 60
    for file in TEMP_FOLDER.iterdir():
        if file.is_file() and file.stat().st_ctime < older_than_1h:
            file.unlink()

    # 使用用户指定的文件名，如果没有则使用uuid
    user_filename = data.get("filename", "").strip()
    if user_filename:
        # 清理文件名，移除非法字符
        import re
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', user_filename)
        zip_filename = f"{safe_filename}.cpack.zip"
    else:
        zip_filename = f"{uuid.uuid4()}.zip"

    with zipfile.ZipFile(TEMP_FOLDER / zip_filename, "w") as zf:
        path = zipfile.Path(zf)
        await _prepare_pack(path, data, client_id=client_id)

    # Send completion progress
    if client_id:
        await send_pack_progress(
            client_id,
            stage="completed",
            message="打包完成！",
            percentage=100,
            level="success",
        )

    return web.json_response({"download_url": f"/bentoml/download/{zip_filename}"})


@PromptServer.instance.routes.get("/bentoml/download/{zip_filename}")
async def download_workspace(request):
    zip_filename = request.match_info["zip_filename"]
    return web.FileResponse(TEMP_FOLDER / zip_filename)


async def _prepare_pack(
    working_dir: ZPath,
    data: dict,
    store_models: bool = False,
    ensure_source: bool = True,
    client_id: str = "",
) -> None:
    # Write snapshot
    if client_id:
        await send_pack_progress(
            client_id,
            stage="writing_snapshot",
            message="正在写入快照文件...",
            percentage=40,
            level="info",
        )
    await _write_snapshot(working_dir, data)

    # Write workflow
    if client_id:
        await send_pack_progress(
            client_id,
            stage="writing_workflow",
            message="正在写入工作流文件...",
            percentage=60,
            level="info",
        )
    await _write_workflow(working_dir, data)

    # Write completion message (if provided)
    await _write_completion_message(working_dir, data)

    # Write inputs
    if client_id:
        await send_pack_progress(
            client_id,
            stage="writing_inputs",
            message="正在复制输入文件...",
            percentage=80,
            level="info",
        )
    await _write_inputs(working_dir, data)

    # Simplified - skip model processing
    if client_id:
        await send_pack_progress(
            client_id,
            stage="finalizing",
            message="正在完成打包...",
            percentage=95,
            level="info",
        )