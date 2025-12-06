from __future__ import annotations

import asyncio
import json
import os
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
    snapshot_path = get_snapshot_path()
    # Ensure the snapshot directory exists
    snapshot_path.mkdir(parents=True, exist_ok=True)

    # Try to use ComfyUI-Manager's snapshot functionality directly
    try:
        # Import ComfyUI-Manager's snapshot module directly
        import importlib.util
        manager_path = Path(folder_paths.get_folder_paths("custom_nodes")[0]) / "ComfyUI-Manager"

        if manager_path.exists():
            # Try to import and call the snapshot save function
            snapshot_module_path = manager_path / "glob" / "manager_core.py"
            if not snapshot_module_path.exists():
                snapshot_module_path = manager_path / "manager_core.py"

            if snapshot_module_path.exists():
                spec = importlib.util.spec_from_file_location("manager_core", snapshot_module_path)
                manager_core = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(manager_core)

                if hasattr(manager_core, 'save_snapshot'):
                    await manager_core.save_snapshot()
                    print("[Comfy-Pack] Snapshot saved via ComfyUI-Manager")
    except Exception as e:
        print(f"[Comfy-Pack] Direct snapshot save failed: {e}")

    # Fallback: Try the route handler with a mock request
    if not list(snapshot_path.glob("*.json")):
        try:
            save_snapshot_route = next(
                (
                    route
                    for route in PromptServer.instance.routes
                    if route.path == "/snapshot/save"
                ),
                None,
            )
            if save_snapshot_route:
                # Create a minimal mock request
                from aiohttp.test_utils import make_mocked_request
                mock_request = make_mocked_request("GET", "/snapshot/save")
                await save_snapshot_route.handler(mock_request)
                print("[Comfy-Pack] Snapshot saved via route handler")
        except Exception as e:
            print(f"[Comfy-Pack] Route handler snapshot save failed: {e}")

    # Final fallback: Generate basic snapshot ourselves
    if not list(snapshot_path.glob("*.json")):
        try:
            await _generate_basic_snapshot(snapshot_path)
            print("[Comfy-Pack] Generated basic snapshot")
        except Exception as e:
            print(f"[Comfy-Pack] Basic snapshot generation failed: {e}")

    if not snapshot_path.exists():
        raise RuntimeError(f"Snapshot directory does not exist: {snapshot_path}")

    most_recent = max(
        snapshot_path.glob("*.json"), key=lambda x: x.stat().st_mtime, default=None
    )
    if not most_recent:
        raise RuntimeError(f"No snapshot files found in {snapshot_path}. Please check ComfyUI-Manager installation.")
    with most_recent.open("r") as f:
        return json.load(f)


async def _generate_basic_snapshot(snapshot_path: Path) -> None:
    """Generate a basic snapshot with installed custom nodes info."""
    import datetime

    custom_nodes_path = Path(folder_paths.get_folder_paths("custom_nodes")[0])
    custom_nodes = {}

    for node_dir in custom_nodes_path.iterdir():
        if node_dir.is_dir() and not node_dir.name.startswith('.'):
            git_dir = node_dir / ".git"
            if git_dir.exists():
                # Try to get git info
                try:
                    import subprocess
                    result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(node_dir),
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"

                    result = subprocess.run(
                        ["git", "config", "--get", "remote.origin.url"],
                        cwd=str(node_dir),
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    remote_url = result.stdout.strip() if result.returncode == 0 else ""

                    custom_nodes[remote_url or node_dir.name] = {
                        "hash": commit_hash,
                        "disabled": False
                    }
                except Exception:
                    custom_nodes[node_dir.name] = {
                        "hash": "unknown",
                        "disabled": False
                    }

    snapshot = {
        "comfyui": "unknown",
        "git_custom_nodes": custom_nodes,
        "file_custom_nodes": [],
        "pips": []
    }

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snapshot_file = snapshot_path / f"{timestamp}.json"
    with open(snapshot_file, "w") as f:
        json.dump(snapshot, f, indent=2)


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


@PromptServer.instance.routes.post("/bentoml/pack")
async def pack_workspace(request):
    try:
        data = await request.json()
        client_id = data.get("client_id", "")
    except Exception as e:
        return web.json_response({"error": f"Invalid request: {str(e)}"}, status=400)

    try:
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

    except Exception as e:
        error_msg = str(e)
        print(f"[Comfy-Pack] Pack error: {error_msg}")
        if client_id:
            await send_pack_progress(
                client_id,
                stage="error",
                message=f"打包失败: {error_msg}",
                percentage=0,
                level="error",
            )
        return web.json_response({"error": error_msg}, status=500)


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

    # Simplified - skip model processing
    if client_id:
        await send_pack_progress(
            client_id,
            stage="finalizing",
            message="正在完成打包...",
            percentage=80,
            level="info",
        )