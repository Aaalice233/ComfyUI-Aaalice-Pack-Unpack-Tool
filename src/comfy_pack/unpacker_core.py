"""
ComfyUI Workflow Unpacker - Core Logic
解包核心逻辑，不安装 ComfyUI，只更新现有环境
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Windows 下隐藏 subprocess 窗口的标志
if sys.platform == 'win32':
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

# 保存原始的 subprocess.run
_original_subprocess_run = subprocess.run


def run_subprocess(*args, **kwargs):
    """
    运行 subprocess，自动添加 Windows 下的隐藏窗口标志
    """
    if 'creationflags' not in kwargs:
        kwargs['creationflags'] = SUBPROCESS_FLAGS
    return _original_subprocess_run(*args, **kwargs)


# 替换 subprocess.run 为我们的包装函数，自动隐藏窗口
subprocess.run = run_subprocess


class UnpackerError(Exception):
    """解包过程中的错误"""
    pass


def detect_python_environments(comfyui_dir: Path, log_callback=None) -> List[Path]:
    """
    检测 Python 环境
    优先从 ComfyUI 同级目录查找，然后是 ComfyUI 内部，最后是全局
    
    Args:
        comfyui_dir: ComfyUI 根目录
        log_callback: 可选的日志回调函数
    
    Returns:
        Python 可执行文件路径列表（已去重）
    """
    python_paths = []
    seen_paths = set()  # 用于去重
    parent_dir = comfyui_dir.parent
    
    def log(msg: str):
        if log_callback:
            log_callback(msg)
    
    def add_if_valid(py_path: Path):
        """添加路径并快速验证"""
        log(f"  检查: {py_path}")
        if not py_path.exists():
            log(f"    ✗ 不存在")
            return False
        # 使用绝对路径进行去重
        abs_path = py_path.resolve()
        if abs_path in seen_paths:
            log(f"    ✗ 重复路径")
            return False
        seen_paths.add(abs_path)
        python_paths.append(abs_path)
        log(f"    ✓ 找到")
        return True
    
    log(f"开始检测 Python（ComfyUI: {comfyui_dir}）")
    log(f"父目录: {parent_dir}")
    
    # 1. 检查 ComfyUI 同级的 python 目录（最优先）
    log("1. 检查同级 python 目录...")
    sibling_python_dirs = ["python", "Python", "python_embeded"]
    for dirname in sibling_python_dirs:
        sibling_path = parent_dir / dirname
        log(f"  查找目录: {sibling_path}")
        if not sibling_path.exists():
            log(f"    ✗ 目录不存在")
            continue
        
        log(f"    ✓ 目录存在，检查 python.exe...")
        # Windows - 直接在目录下
        add_if_valid(sibling_path / "python.exe")
        # Windows - Scripts 目录
        add_if_valid(sibling_path / "Scripts" / "python.exe")
    
    # 2. 检查 ComfyUI 内部的虚拟环境
    log("2. 检查 ComfyUI 内部虚拟环境...")
    venv_locations = [".venv", "venv", "python_embeded", "python"]
    for venv_name in venv_locations:
        venv_path = comfyui_dir / venv_name
        if not venv_path.exists():
            continue
            
        log(f"  找到虚拟环境目录: {venv_path}")
        # Windows - Scripts
        if add_if_valid(venv_path / "Scripts" / "python.exe"):
            continue
        # Linux/Mac - bin
        if add_if_valid(venv_path / "bin" / "python"):
            continue
        # Embedded Python
        add_if_valid(venv_path / "python.exe")
    
    # 3. 检查全局 Python（最后选择，仅限 Windows）
    if os.name == "nt" and len(python_paths) == 0:
        log("3. 检查全局 Python...")
        try:
            result = subprocess.run(
                ["where", "python"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    py_path = Path(line.strip())
                    add_if_valid(py_path)
                    if len(python_paths) >= 2:  # 最多添加2个全局Python
                        break
        except Exception as e:
            log(f"  检查全局 Python 失败: {e}")
    
    log(f"检测完成，共找到 {len(python_paths)} 个 Python 环境")
    # 直接返回找到的路径，不验证（提高速度，避免验证失败导致的问题）
    return python_paths


def detect_git_executable(comfyui_dir: Path) -> Optional[Path]:
    """
    检测 Git 可执行文件
    优先从 ComfyUI 同级目录查找，然后是全局
    
    Returns:
        Git 可执行文件路径，如果未找到返回 None
    """
    parent_dir = comfyui_dir.parent
    
    # 1. 检查 ComfyUI 同级的 git 目录（最优先）
    sibling_git_dirs = ["git", "Git", "PortableGit"]
    for dirname in sibling_git_dirs:
        sibling_path = parent_dir / dirname
        if not sibling_path.exists():
            continue
            
        # Windows: git/bin/git.exe 或 git/cmd/git.exe
        for subdir in ["cmd", "bin"]:  # cmd 优先，通常更稳定
            git_exe = sibling_path / subdir / "git.exe"
            if git_exe.exists():
                # 快速检查文件是否可执行（不运行验证以提高速度）
                return git_exe
    
    # 2. 检查全局 Git
    try:
        # Windows
        if os.name == "nt":
            result = subprocess.run(
                ["where", "git"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                git_path = Path(result.stdout.strip().split("\n")[0])
                if git_path.exists():
                    return git_path
        else:
            # Linux/Mac
            result = subprocess.run(
                ["which", "git"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                git_path = Path(result.stdout.strip())
                if git_path.exists():
                    return git_path
    except Exception:
        pass
    
    return None


def get_installed_packages(python_exe: Path) -> Dict[str, str]:
    """获取已安装的包列表和版本"""
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {pkg["name"].lower(): pkg["version"] for pkg in packages}
    except Exception:
        pass
    return {}


def get_installed_plugins(comfyui_dir: Path, git_exe: Optional[Path] = None) -> Dict[str, dict]:
    """
    获取已安装的插件和当前 commit
    返回: {插件名: {'commit': 'xxx', 'url': 'xxx', 'path': Path}}
    """
    custom_nodes = comfyui_dir / "custom_nodes"
    if not custom_nodes.exists():
        return {}
    
    git_cmd = str(git_exe) if git_exe else "git"
    
    plugins = {}
    for item in custom_nodes.iterdir():
        if not item.is_dir() or item.name.startswith('.'):
            continue
        
        git_dir = item / ".git"
        if not git_dir.exists():
            continue
        
        try:
            # 获取当前 commit
            result = subprocess.run(
                [git_cmd, "rev-parse", "HEAD"],
                cwd=item,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                continue
            
            commit = result.stdout.strip()
            
            # 获取 remote URL
            url_result = subprocess.run(
                [git_cmd, "remote", "get-url", "origin"],
                cwd=item,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            url = url_result.stdout.strip() if url_result.returncode == 0 else ""
            
            # 标准化 URL（移除 .git 后缀，统一 https/git 格式）
            if url:
                url = url.rstrip('/').rstrip('.git')
                url = url.replace('git@github.com:', 'https://github.com/')
            
            plugins[item.name] = {
                'commit': commit,
                'url': url,
                'path': item
            }
        except Exception:
            continue
    
    return plugins


def get_comfyui_commit(comfyui_dir: Path) -> Optional[str]:
    """获取 ComfyUI 当前的 git commit"""
    git_dir = comfyui_dir / ".git"
    if not git_dir.exists():
        return None
    
    try:
        result = run_subprocess(
            ["git", "rev-parse", "HEAD"],
            cwd=comfyui_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def switch_comfyui_version(
    comfyui_dir: Path,
    target_commit: str,
    git_exe: Optional[Path] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """
    切换 ComfyUI 到指定版本
    
    Args:
        comfyui_dir: ComfyUI 根目录
        target_commit: 目标 commit hash
        git_exe: Git 可执行文件路径
        log_callback: 日志回调
    
    Returns:
        是否成功
    """
    git_cmd = str(git_exe) if git_exe else "git"
    
    # 检查是否有未提交的更改
    try:
        result = subprocess.run(
            [git_cmd, "status", "--porcelain"],
            cwd=comfyui_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            if log_callback:
                log_callback("  警告: ComfyUI 目录有未提交的更改，将暂存这些更改")
            
            # 暂存更改
            subprocess.run(
                [git_cmd, "stash"],
                cwd=comfyui_dir,
                capture_output=True,
                timeout=30
            )
    except Exception as e:
        if log_callback:
            log_callback(f"  警告: 检查 git 状态失败: {e}")
    
    # 切换到目标版本
    try:
        if log_callback:
            log_callback(f"  切换到 commit: {target_commit[:8]}")
        
        result = subprocess.run(
            [git_cmd, "checkout", target_commit],
            cwd=comfyui_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            if log_callback:
                log_callback(f"  ✗ 切换失败: {result.stderr}")
            return False
        
        if log_callback:
            log_callback(f"  ✓ 成功切换到版本: {target_commit[:8]}")
        
        return True
        
    except Exception as e:
        if log_callback:
            log_callback(f"  ✗ 切换版本失败: {e}")
        return False


def check_plugin_versions(
    snapshot: dict,
    comfyui_dir: Path,
    git_exe: Optional[Path] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Dict]:
    """
    检查插件版本差异
    
    Returns:
        {
            'to_install': [{'url': ..., 'commit': ...}],
            'to_update': [{'name': ..., 'current': ..., 'target': ...}],
            'ok': [...]
        }
    """
    if log_callback:
        log_callback("正在检查插件版本...")
    
    installed = get_installed_plugins(comfyui_dir, git_exe)
    
    # ComfyUI Manager 的 snapshot 使用 git_custom_nodes 字段
    git_nodes = snapshot.get("git_custom_nodes", {})
    
    if log_callback:
        log_callback(f"  快照中 git_custom_nodes 字段类型: {type(git_nodes)}")
        if isinstance(git_nodes, dict):
            log_callback(f"  git_custom_nodes 包含 {len(git_nodes)} 项")
            # 显示前几个键名
            keys = list(git_nodes.keys())[:3]
            if keys:
                log_callback(f"  示例键名: {', '.join(keys)}")
        elif isinstance(git_nodes, list):
            log_callback(f"  git_custom_nodes 是列表，长度: {len(git_nodes)}")
    
    # 将字典格式转换为列表格式
    # 注意：键名本身就是 URL
    required = []
    if isinstance(git_nodes, dict):
        for repo_url, info in git_nodes.items():
            if isinstance(info, dict):
                required.append({
                    'url': repo_url,  # 键名就是 URL
                    'commit_hash': info.get('hash', '')
                })
                if log_callback and len(required) <= 3:
                    log_callback(f"  解析插件: url={repo_url[:60]}, hash={info.get('hash', 'N/A')[:8]}")
    elif isinstance(git_nodes, list):
        required = git_nodes
    
    if log_callback:
        log_callback(f"  快照中记录了 {len(required)} 个插件")
    
    result = {
        'to_install': [],
        'to_update': [],
        'ok': []
    }
    
    # 标准化 URL 的辅助函数
    def normalize_url(url: str) -> str:
        """标准化 Git URL 用于比较"""
        url = url.strip().rstrip('/').rstrip('.git')
        url = url.replace('git@github.com:', 'https://github.com/')
        return url.lower()
    
    # 建立 URL 到已安装插件的映射，同时检测重复插件
    url_to_installed = {}
    duplicates_to_remove = []  # 需要删除的重复插件
    
    for name, info in installed.items():
        if info['url']:
            normalized = normalize_url(info['url'])
            
            # 检测是否已存在相同 URL 的插件
            if normalized in url_to_installed:
                # 发现重复插件！保留其中一个，删除另一个
                existing = url_to_installed[normalized]
                
                # 决策：保留目录名较短的（通常是官方推荐的名称）
                if len(name) < len(existing['name']):
                    # 当前插件名更短，保留当前，删除已存在的
                    duplicates_to_remove.append(existing['path'])
                    url_to_installed[normalized] = {
                        'name': name,
                        'commit': info['commit'],
                        'path': info['path']
                    }
                    if log_callback:
                        log_callback(f"检测到重复插件: {existing['name']} 和 {name}，将删除 {existing['name']}")
                else:
                    # 已存在的名称更短或相同，删除当前
                    duplicates_to_remove.append(info['path'])
                    if log_callback:
                        log_callback(f"检测到重复插件: {existing['name']} 和 {name}，将删除 {name}")
            else:
                url_to_installed[normalized] = {
                    'name': name,
                    'commit': info['commit'],
                    'path': info['path']
                }
    
    # 删除重复的插件
    if duplicates_to_remove:
        if log_callback:
            log_callback(f"\n开始清理 {len(duplicates_to_remove)} 个重复插件...")
        
        for plugin_path in duplicates_to_remove:
            try:
                if log_callback:
                    log_callback(f"  删除: {plugin_path.name}")
                
                # 使用健壮的删除方法
                if plugin_path.exists():
                    def remove_readonly(func, path, _):
                        """清除只读位并重试"""
                        import stat
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    
                    shutil.rmtree(plugin_path, onerror=remove_readonly)
                    
                    if log_callback:
                        log_callback(f"  ✓ 已删除重复插件: {plugin_path.name}")
            except Exception as e:
                if log_callback:
                    log_callback(f"  ✗ 删除失败 {plugin_path.name}: {e}")
        
        if log_callback:
            log_callback("")
    
    for plugin in required:
        url = plugin.get("url", "").strip()
        if not url:
            continue
        
        # 标准化快照中的 URL
        normalized_url = normalize_url(url)
        plugin_name = url.split("/")[-1].replace(".git", "")
        
        # 跳过解包器本身，避免自我更新导致的问题
        if plugin_name.lower() in ['comfy-pack-aaalice', 'comfy-pack']:
            if log_callback:
                log_callback(f"  ⊙ 跳过解包器本身: {plugin_name}")
            continue
        
        target_commit = plugin.get("commit_hash", "").strip()
        
        # 通过 URL 查找是否已安装（而不是通过插件名）
        if normalized_url in url_to_installed:
            existing = url_to_installed[normalized_url]
            actual_name = existing['name']
            current_commit = existing['commit']
            
            if current_commit[:8] != target_commit[:8]:
                result['to_update'].append({
                    'name': actual_name,  # 使用实际的目录名
                    'url': url,
                    'current': current_commit[:8],
                    'target': target_commit[:8],
                    'target_full': target_commit
                })
            else:
                result['ok'].append(actual_name)
        else:
            # 未安装
            result['to_install'].append({
                'name': plugin_name,
                'url': url,
                'commit': target_commit
            })
    
    if log_callback:
        log_callback(f"需要安装: {len(result['to_install'])} 个插件")
        if result['to_install']:
            for plugin in result['to_install']:
                log_callback(f"  - {plugin['name']}")
        
        log_callback(f"需要更新: {len(result['to_update'])} 个插件")
        if result['to_update']:
            for plugin in result['to_update']:
                log_callback(f"  - {plugin['name']} (当前: {plugin['current']} → 目标: {plugin['target']})")
        
        log_callback(f"已是最新: {len(result['ok'])} 个插件")
        if result['ok']:
            for plugin_name in result['ok']:
                log_callback(f"  ✓ {plugin_name}")
    
    return result


def check_dependencies(
    snapshot: dict,
    python_exe: Path,
    log_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, List]:
    """检查依赖包差异"""
    if log_callback:
        log_callback("正在检查 Python 依赖...")
    
    installed = get_installed_packages(python_exe)
    required = snapshot.get("pips", {})
    
    result = {
        'to_install': [],
        'to_update': [],
        'ok': []
    }
    
    for package_spec, version_info in required.items():
        # package_spec 格式: "package==version" 或 "package"
        if "==" in package_spec:
            pkg_name, target_version = package_spec.split("==", 1)
        else:
            pkg_name = package_spec
            target_version = None
        
        pkg_name_lower = pkg_name.lower()
        
        if pkg_name_lower not in installed:
            result['to_install'].append(package_spec)
        elif target_version and installed[pkg_name_lower] != target_version:
            result['to_update'].append({
                'name': pkg_name,
                'current': installed[pkg_name_lower],
                'target': target_version,
                'spec': package_spec
            })
        else:
            result['ok'].append(pkg_name)
    
    if log_callback:
        log_callback(f"需要安装: {len(result['to_install'])} 个依赖包")
        if result['to_install']:
            for pkg in result['to_install']:
                log_callback(f"  - {pkg}")
        
        log_callback(f"需要更新: {len(result['to_update'])} 个依赖包")
        if result['to_update']:
            for pkg in result['to_update']:
                log_callback(f"  - {pkg['name']} (当前: {pkg['current']} → 目标: {pkg['target']})")
        
        log_callback(f"已安装最新: {len(result['ok'])} 个依赖包")
        if result['ok']:
            for pkg_name in result['ok']:
                log_callback(f"  ✓ {pkg_name}")
    
    return result


def fix_detached_head(
    plugin_dir: Path,
    commit_hash: str,
    git_cmd: str,
    log_callback: Optional[Callable[[str], None]] = None
) -> None:
    """
    切换到主分支（main/master）并重置到目标版本
    无论当前是什么状态（detached HEAD 或其他分支）
    """
    try:
        # 获取当前分支名（如果有）
        result = run_subprocess(
            [git_cmd, "symbolic-ref", "--short", "HEAD"],
            cwd=plugin_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        current_branch = result.stdout.strip() if result.returncode == 0 else None
        
        # 如果已经在 main 或 master 分支上，只需 reset
        if current_branch in ['main', 'master']:
            reset_result = run_subprocess(
                [git_cmd, "reset", "--hard", commit_hash],
                cwd=plugin_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if reset_result.returncode == 0 and log_callback:
                log_callback(f"    ✓ 已在 {current_branch} 分支，重置到目标版本")
            return
        
        if log_callback:
            if current_branch:
                log_callback(f"    当前分支: {current_branch}，切换到主分支...")
            else:
                log_callback(f"    检测到游离状态，切换到主分支...")
        
        # 尝试找到主分支（优先 main，然后 master）
        main_branch = None
        for branch_name in ['main', 'master']:
            check_result = run_subprocess(
                [git_cmd, "rev-parse", "--verify", f"refs/heads/{branch_name}"],
                cwd=plugin_dir,
                capture_output=True,
                timeout=5
            )
            if check_result.returncode == 0:
                main_branch = branch_name
                break
        
        if not main_branch:
            # 如果本地没有 main/master，尝试从远程创建
            for branch_name in ['main', 'master']:
                check_remote = run_subprocess(
                    [git_cmd, "rev-parse", "--verify", f"origin/{branch_name}"],
                    cwd=plugin_dir,
                    capture_output=True,
                    timeout=5
                )
                if check_remote.returncode == 0:
                    # 创建本地分支跟踪远程分支
                    run_subprocess(
                        [git_cmd, "branch", branch_name, f"origin/{branch_name}"],
                        cwd=plugin_dir,
                        capture_output=True,
                        timeout=5
                    )
                    main_branch = branch_name
                    break
        
        if main_branch:
            # 切换到主分支
            checkout_result = run_subprocess(
                [git_cmd, "checkout", main_branch],
                cwd=plugin_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if checkout_result.returncode == 0:
                # 重置到目标版本
                reset_result = run_subprocess(
                    [git_cmd, "reset", "--hard", commit_hash],
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if reset_result.returncode == 0:
                    if log_callback:
                        log_callback(f"    ✓ 已切换到 {main_branch} 分支并重置到目标版本")
                else:
                    if log_callback:
                        log_callback(f"    ⚠ 重置失败: {reset_result.stderr[:50]}")
            else:
                if log_callback:
                    log_callback(f"    ⚠ 切换分支失败: {checkout_result.stderr[:50]}")
        else:
            # 找不到主分支，使用默认的 main
            if log_callback:
                log_callback(f"    创建新的 main 分支...")
            
            run_subprocess(
                [git_cmd, "checkout", "-b", "main"],
                cwd=plugin_dir,
                capture_output=True,
                timeout=10
            )
            
            if log_callback:
                log_callback(f"    ✓ 已创建 main 分支")
        
    except Exception as e:
        # 忽略错误，保持原状态
        if log_callback:
            log_callback(f"    ⚠ 无法修复游离状态: {str(e)[:50]}")


def install_or_update_plugins(
    plugins_diff: Dict,
    comfyui_dir: Path,
    python_exe: Path,
    git_exe: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """安装或更新插件"""
    custom_nodes = comfyui_dir / "custom_nodes"
    custom_nodes.mkdir(exist_ok=True)
    
    all_tasks = plugins_diff['to_install'] + plugins_diff['to_update']
    total = len(all_tasks)
    
    if total == 0:
        if log_callback:
            log_callback("所有插件已是最新版本")
        return True
    
    # 确定使用哪个 Git
    git_cmd = str(git_exe) if git_exe else "git"
    
    # 记录结果
    success_plugins = []
    failed_plugins = []
    
    for idx, task in enumerate(all_tasks):
        plugin_name = task['name']
        plugin_dir = custom_nodes / plugin_name
        
        if log_callback:
            log_callback(f"处理插件: {plugin_name}")
        
        if progress_callback:
            progress_callback(idx, total, plugin_name)
        
        try:
            if task in plugins_diff['to_install']:
                # 标记为"需要安装"的插件
                # 检查目录是否已存在
                if plugin_dir.exists():
                    git_dir = plugin_dir / ".git"
                    
                    if git_dir.exists():
                        # 目录存在且是 Git 仓库
                        if log_callback:
                            log_callback(f"  检查插件 Git 仓库: {plugin_name}")
                        
                        # 先检查当前是否已经是目标版本
                        current_commit_result = subprocess.run(
                            [git_cmd, "rev-parse", "HEAD"],
                            cwd=plugin_dir,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if current_commit_result.returncode == 0:
                            current_commit = current_commit_result.stdout.strip()
                            target_commit = task['commit'].strip()
                            
                            if log_callback:
                                log_callback(f"    当前版本: {current_commit[:8]}")
                                log_callback(f"    目标版本: {target_commit[:8]}")
                            
                            # 比较 commit（支持短格式和长格式）
                            if current_commit.startswith(target_commit) or target_commit.startswith(current_commit):
                                if log_callback:
                                    log_callback(f"  ✓ {plugin_name} 已是目标版本")
                                
                                # 即使版本正确，也需要修复游离状态
                                fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                                
                                success_plugins.append(plugin_name)
                                continue
                        else:
                            if log_callback:
                                log_callback(f"    ⚠ 无法获取当前版本")
                        
                        # 需要切换版本
                        if log_callback:
                            log_callback(f"    需要切换版本")
                        
                        # 先尝试直接 checkout（如果 commit 已经在本地）
                        if log_callback:
                            log_callback(f"    [步骤1] 尝试直接 checkout...")
                        
                        result = subprocess.run(
                            [git_cmd, "checkout", task['commit']],
                            cwd=plugin_dir,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        if result.returncode == 0:
                            if log_callback:
                                log_callback(f"    ✓ checkout 成功")
                            
                            # 修复 detached HEAD 状态
                            fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                        else:
                            # checkout 失败，说明本地没有这个 commit，需要 fetch
                            if log_callback:
                                log_callback(f"    ✗ 本地没有该 commit")
                                log_callback(f"    [步骤2] 执行 fetch --all --tags...")
                            
                            # 策略1: 先尝试 fetch 所有远程分支和标签
                            fetch_result = subprocess.run(
                                [git_cmd, "fetch", "--all", "--tags"],
                                cwd=plugin_dir,
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            
                            if fetch_result.returncode == 0:
                                if log_callback:
                                    log_callback(f"    ✓ fetch 完成")
                            else:
                                if log_callback:
                                    log_callback(f"    ⚠ fetch 警告: {fetch_result.stderr[:100] if fetch_result.stderr else 'N/A'}")
                            
                            # 再次尝试 checkout
                            if log_callback:
                                log_callback(f"    [步骤3] 再次尝试 checkout...")
                            
                            result = subprocess.run(
                                [git_cmd, "checkout", task['commit']],
                                cwd=plugin_dir,
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                            
                            if result.returncode == 0:
                                if log_callback:
                                    log_callback(f"    ✓ checkout 成功")
                                
                                # 修复 detached HEAD 状态
                                fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                            else:
                                # 策略2: 如果还是失败，尝试直接从 origin fetch 这个 commit
                                if log_callback:
                                    log_callback(f"    ✗ 仍然失败")
                                    log_callback(f"    [步骤4] 尝试 fetch origin {task['commit'][:8]}...")
                                
                                fetch_result = subprocess.run(
                                    [git_cmd, "fetch", "origin", task['commit']],
                                    cwd=plugin_dir,
                                    capture_output=True,
                                    text=True,
                                    timeout=120
                                )
                                
                                if fetch_result.returncode == 0:
                                    if log_callback:
                                        log_callback(f"    ✓ fetch 指定 commit 成功")
                                else:
                                    if log_callback:
                                        log_callback(f"    ⚠ fetch 失败: {fetch_result.stderr[:100] if fetch_result.stderr else 'N/A'}")
                                
                                # 第三次尝试 checkout
                                if log_callback:
                                    log_callback(f"    [步骤5] 第三次尝试 checkout...")
                                
                                result = subprocess.run(
                                    [git_cmd, "checkout", task['commit']],
                                    cwd=plugin_dir,
                                    capture_output=True,
                                    text=True,
                                    timeout=30
                                )
                                
                                if result.returncode == 0:
                                    if log_callback:
                                        log_callback(f"    ✓ checkout 成功")
                                    
                                    # 修复 detached HEAD 状态
                                    fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                                else:
                                    # 策略3: 最后尝试 unshallow（如果是浅克隆）
                                    if log_callback:
                                        log_callback(f"    ✗ 仍然失败")
                                        log_callback(f"    [步骤6] 尝试 fetch --unshallow（获取完整历史）...")
                                    
                                    unshallow_result = subprocess.run(
                                        [git_cmd, "fetch", "--unshallow"],
                                        cwd=plugin_dir,
                                        capture_output=True,
                                        text=True,
                                        timeout=180
                                    )
                                    
                                    if unshallow_result.returncode == 0:
                                        if log_callback:
                                            log_callback(f"    ✓ unshallow 完成")
                                    else:
                                        if log_callback:
                                            error_msg = unshallow_result.stderr[:100] if unshallow_result.stderr else 'N/A'
                                            log_callback(f"    ⚠ unshallow 警告: {error_msg}")
                                    
                                    # 最后一次尝试 checkout
                                    if log_callback:
                                        log_callback(f"    [步骤7] 最后一次尝试 checkout...")
                                    
                                    result = subprocess.run(
                                        [git_cmd, "checkout", task['commit']],
                                        cwd=plugin_dir,
                                        capture_output=True,
                                        text=True,
                                        timeout=30
                                    )
                                    
                                    if result.returncode == 0:
                                        if log_callback:
                                            log_callback(f"    ✓ checkout 成功！")
                                        
                                        # 修复 detached HEAD 状态
                                        fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                                    else:
                                        error_msg = result.stderr or "无法切换到指定版本"
                                        if log_callback:
                                            log_callback(f"    ✗ 所有策略都失败了")
                                            log_callback(f"    错误详情: {error_msg[:150]}")
                                            log_callback(f"    可能原因: commit {task['commit'][:8]} 不存在或已被删除")
                                        raise subprocess.CalledProcessError(
                                            result.returncode,
                                            result.args,
                                            stderr=error_msg
                                        )
                    else:
                        # 目录存在但不是 Git 仓库 → 可能是损坏的，删除后重新克隆
                        if log_callback:
                            log_callback(f"  ⚠ 目录不是有效的 Git 仓库: {plugin_name}")
                            log_callback(f"    删除损坏的目录...")
                        
                        import time
                        def remove_readonly(func, path, excinfo):
                            """处理只读文件"""
                            import stat
                            os.chmod(path, stat.S_IWRITE)
                            func(path)
                        
                        shutil.rmtree(plugin_dir, onerror=remove_readonly)
                        time.sleep(0.2)
                        
                        if log_callback:
                            log_callback(f"    ✓ 旧目录已删除")
                        
                        # 克隆新仓库
                        if log_callback:
                            log_callback(f"    克隆仓库: {task['url'][:60]}...")
                        
                        result = subprocess.run(
                            [git_cmd, "clone", task['url'], str(plugin_dir)],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        
                        if result.returncode != 0:
                            error_msg = result.stderr or result.stdout or "未知错误"
                            if log_callback:
                                log_callback(f"    ✗ 克隆失败: {error_msg[:100]}")
                            raise subprocess.CalledProcessError(
                                result.returncode, 
                                result.args, 
                                output=result.stdout,
                                stderr=error_msg
                            )
                        
                        if log_callback:
                            log_callback(f"    ✓ 克隆完成")
                            log_callback(f"    切换到 commit: {task['commit'][:8]}")
                        
                        # Checkout 到指定版本
                        checkout_result = subprocess.run(
                            [git_cmd, "checkout", task['commit']],
                            cwd=plugin_dir,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        if checkout_result.returncode != 0:
                            error_msg = checkout_result.stderr or "checkout 失败"
                            if log_callback:
                                log_callback(f"    ✗ checkout 失败: {error_msg[:100]}")
                            raise subprocess.CalledProcessError(
                                checkout_result.returncode,
                                checkout_result.args,
                                stderr=error_msg
                            )
                        
                        if log_callback:
                            log_callback(f"    ✓ checkout 成功")
                        
                        # 修复 detached HEAD 状态
                        fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
                else:
                    # 目录不存在 → 真正的全新安装
                    if log_callback:
                        log_callback(f"  全新安装: {plugin_name}")
                        log_callback(f"    克隆仓库: {task['url'][:60]}...")
                    
                    result = subprocess.run(
                        [git_cmd, "clone", task['url'], str(plugin_dir)],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if result.returncode != 0:
                        error_msg = result.stderr or result.stdout or "未知错误"
                        if log_callback:
                            log_callback(f"    ✗ 克隆失败: {error_msg[:100]}")
                        raise subprocess.CalledProcessError(
                            result.returncode, 
                            result.args, 
                            output=result.stdout,
                            stderr=error_msg
                        )
                    
                    if log_callback:
                        log_callback(f"    ✓ 克隆完成")
                        log_callback(f"    切换到 commit: {task['commit'][:8]}")
                    
                    checkout_result = subprocess.run(
                        [git_cmd, "checkout", task['commit']],
                        cwd=plugin_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if checkout_result.returncode != 0:
                        error_msg = checkout_result.stderr or "checkout 失败"
                        if log_callback:
                            log_callback(f"    ✗ checkout 失败: {error_msg[:100]}")
                        raise subprocess.CalledProcessError(
                            checkout_result.returncode,
                            checkout_result.args,
                            stderr=error_msg
                        )
                    
                    if log_callback:
                        log_callback(f"    ✓ checkout 成功")
                    
                    # 修复 detached HEAD 状态
                    fix_detached_head(plugin_dir, task['commit'], git_cmd, log_callback)
            else:
                # 更新现有插件
                if log_callback:
                    log_callback(f"  更新插件: {plugin_name}")
                    log_callback(f"    当前版本: {task['current']}")
                    log_callback(f"    目标版本: {task['target']}")
                    log_callback(f"    执行 fetch origin {task['target']}...")
                
                # Fetch 新的 commit
                fetch_result = subprocess.run(
                    [git_cmd, "fetch", "origin", task['target_full']],
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if fetch_result.returncode != 0:
                    error_msg = fetch_result.stderr or "fetch 失败"
                    if log_callback:
                        log_callback(f"    ✗ fetch 失败: {error_msg[:100]}")
                    raise subprocess.CalledProcessError(
                        fetch_result.returncode,
                        fetch_result.args,
                        stderr=error_msg
                    )
                
                if log_callback:
                    log_callback(f"    ✓ fetch 完成")
                    log_callback(f"    执行 checkout...")
                
                # Checkout 到指定 commit
                checkout_result = subprocess.run(
                    [git_cmd, "checkout", task['target_full']],
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if checkout_result.returncode != 0:
                    error_msg = checkout_result.stderr or "checkout 失败"
                    if log_callback:
                        log_callback(f"    ✗ checkout 失败: {error_msg[:100]}")
                    raise subprocess.CalledProcessError(
                        checkout_result.returncode,
                        checkout_result.args,
                        stderr=error_msg
                    )
                
                if log_callback:
                    log_callback(f"    ✓ checkout 成功")
                
                # 修复 detached HEAD 状态
                fix_detached_head(plugin_dir, task['target_full'], git_cmd, log_callback)
            
            # 运行 install.py（如果存在）
            install_script = plugin_dir / "install.py"
            if install_script.exists():
                if log_callback:
                    log_callback(f"    运行安装脚本 install.py...")
                
                install_result = subprocess.run(
                    [str(python_exe), "install.py"],
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if install_result.returncode != 0:
                    error_msg = install_result.stderr or "install.py 执行失败"
                    if log_callback:
                        log_callback(f"    ⚠ install.py 警告: {error_msg[:100]}")
                    # 不抛出异常，只警告
                else:
                    if log_callback:
                        log_callback(f"    ✓ install.py 执行完成")
            
            if log_callback:
                log_callback(f"  ✓ {plugin_name} 完成")
            success_plugins.append(plugin_name)
        
        except subprocess.TimeoutExpired as e:
            if log_callback:
                log_callback(f"  ✗ {plugin_name} 操作超时")
                log_callback(f"    超时命令: {' '.join(e.cmd) if hasattr(e, 'cmd') else 'N/A'}")
                log_callback(f"    超时时长: {e.timeout if hasattr(e, 'timeout') else 'N/A'} 秒")
            failed_plugins.append({'name': plugin_name, 'reason': '操作超时'})
            continue  # 继续处理下一个插件
        except subprocess.CalledProcessError as e:
            if log_callback:
                log_callback(f"  ✗ {plugin_name} Git 操作失败")
                log_callback(f"    命令: {' '.join(e.cmd) if hasattr(e, 'cmd') else 'N/A'}")
                log_callback(f"    返回码: {e.returncode}")
                if hasattr(e, 'stderr') and e.stderr:
                    log_callback(f"    错误信息: {e.stderr[:200]}")
                if hasattr(e, 'stdout') and e.stdout:
                    log_callback(f"    输出信息: {e.stdout[:200]}")
            failed_plugins.append({'name': plugin_name, 'reason': f'Git 错误 (exit {e.returncode})'})
            continue  # 继续处理下一个插件
        except Exception as e:
            if log_callback:
                log_callback(f"  ✗ {plugin_name} 未知错误")
                log_callback(f"    错误类型: {type(e).__name__}")
                log_callback(f"    错误详情: {str(e)[:200]}")
            failed_plugins.append({'name': plugin_name, 'reason': f'{type(e).__name__}: {str(e)[:50]}'})
            continue  # 继续处理下一个插件
    
    if progress_callback:
        progress_callback(total, total, "完成")
    
    # 处理那些版本已正确但可能处于游离状态的插件
    if plugins_diff['ok']:
        if log_callback:
            log_callback("")
            log_callback("检查已是最新版本的插件的 Git 状态...")
        
        for plugin_name in plugins_diff['ok']:
            plugin_dir = custom_nodes / plugin_name
            
            if not plugin_dir.exists():
                continue
            
            git_dir = plugin_dir / ".git"
            if not git_dir.exists():
                continue
            
            try:
                # 修复可能的游离状态
                # 先获取当前 commit
                result = subprocess.run(
                    [git_cmd, "rev-parse", "HEAD"],
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    current_commit = result.stdout.strip()
                    fix_detached_head(plugin_dir, current_commit, git_cmd, log_callback)
            except Exception:
                continue
    
    # 显示最终统计
    if log_callback:
        log_callback("")
        log_callback(f"插件处理完成:")
        log_callback(f"  ✓ 成功: {len(success_plugins)} 个")
        log_callback(f"  ✗ 失败: {len(failed_plugins)} 个")
        if failed_plugins:
            log_callback("")
            log_callback("失败的插件:")
            for failed in failed_plugins:
                log_callback(f"  - {failed['name']}: {failed['reason'][:50]}")
    
    # 只要有至少一个成功就算部分成功
    return len(failed_plugins) == 0


def install_dependencies_to_existing(
    deps_diff: Dict,
    python_exe: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """安装或更新 Python 依赖"""
    # 已知的非标准 pip 包（通常由插件自己处理）
    KNOWN_NON_PIP_PACKAGES = {
        'SAM-2',  # ComfyUI-SAM2 插件自带
        'segment-anything-2',
    }
    
    to_install = deps_diff['to_install']
    to_update = deps_diff['to_update']
    
    all_packages = to_install + [item['spec'] for item in to_update]
    
    # 分离标准包和非标准包
    standard_packages = []
    non_standard_packages = []
    
    for pkg in all_packages:
        pkg_name = pkg.split('==')[0].split('>=')[0].split('<=')[0].strip()
        if pkg_name in KNOWN_NON_PIP_PACKAGES:
            non_standard_packages.append(pkg)
        else:
            standard_packages.append(pkg)
    
    total = len(all_packages)
    
    if total == 0:
        if log_callback:
            log_callback("所有依赖已是最新版本")
        return True
    
    if log_callback:
        log_callback(f"准备安装/更新 {len(standard_packages)} 个依赖包...")
        if non_standard_packages:
            log_callback(f"  （跳过 {len(non_standard_packages)} 个非标准包: {', '.join([p.split('==')[0] for p in non_standard_packages])}）")
    
    # 批量安装标准包
    if standard_packages:
        try:
            if progress_callback:
                progress_callback(0, total, "安装依赖包...")
            
            cmd = [str(python_exe), "-m", "pip", "install", "--upgrade"] + standard_packages
            
            if log_callback:
                log_callback(f"执行: pip install --upgrade {' '.join(standard_packages[:3])}{'...' if len(standard_packages) > 3 else ''}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                if log_callback:
                    log_callback(f"⚠ 部分依赖安装失败:\n{result.stderr[:500]}")
                    log_callback("  提示: 某些依赖可能由插件自动处理，可以尝试启动 ComfyUI 测试")
                # 不返回 False，继续执行
            
            if progress_callback:
                progress_callback(total, total, "完成")
            
            if log_callback:
                if result.returncode == 0:
                    log_callback("✓ 所有依赖安装完成")
                else:
                    log_callback("⚠ 依赖安装完成（部分失败）")
        
        except subprocess.TimeoutExpired:
            if log_callback:
                log_callback("⚠ 安装超时，但可以继续")
        except Exception as e:
            if log_callback:
                log_callback(f"⚠ 安装警告: {e}")
    
    # 对于非标准包，显示提示信息
    if non_standard_packages and log_callback:
        log_callback(f"ℹ 已跳过 {len(non_standard_packages)} 个非标准包（通常由插件自动安装）")
    
    return True  # 总是返回 True，让解包继续


def copy_input_files(
    pack_dir: Path,
    comfyui_dir: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """复制 input 文件"""
    source_input = pack_dir / "input"
    target_input = comfyui_dir / "input"
    
    if not source_input.exists():
        if log_callback:
            log_callback("压缩包中没有 input 文件")
        return True
    
    target_input.mkdir(exist_ok=True)
    
    # 收集所有文件
    all_files = list(source_input.rglob("*"))
    files_to_copy = [f for f in all_files if f.is_file()]
    total = len(files_to_copy)
    
    if total == 0:
        if log_callback:
            log_callback("没有需要复制的 input 文件")
        return True
    
    if log_callback:
        log_callback(f"准备复制 {total} 个 input 文件...")
    
    for idx, file in enumerate(files_to_copy):
        rel_path = file.relative_to(source_input)
        target_file = target_input / rel_path
        
        if progress_callback:
            progress_callback(idx, total, str(rel_path))
        
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target_file)
            
            if log_callback:
                log_callback(f"  复制: {rel_path}")
        
        except Exception as e:
            if log_callback:
                log_callback(f"  ✗ 复制失败 {rel_path}: {e}")
            return False
    
    if progress_callback:
        progress_callback(total, total, "完成")
    
    if log_callback:
        log_callback("✓ 所有文件复制完成")
    
    return True


def copy_workflow_files(
    pack_dir: Path,
    comfyui_dir: Path,
    cpack_path: Path,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """
    复制工作流文件到 ComfyUI user/default 目录
    
    Args:
        pack_dir: 解压后的临时目录
        comfyui_dir: ComfyUI 根目录
        cpack_path: 压缩包文件路径（用于获取文件名）
        log_callback: 日志回调
    
    Returns:
        是否成功
    """
    # 只复制 workflow.json，不需要 workflow_api.json
    source = pack_dir / "workflow.json"
    if not source.exists():
        if log_callback:
            log_callback("✗ 压缩包中没有 workflow.json")
        return False
    
    # 目标目录：ComfyUI/user/default/workflows
    target_dir = comfyui_dir / "user" / "default" / "workflows"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 从压缩包文件名获取工作流名称
    # 移除 .cpack.zip 或 .zip 后缀
    workflow_name = cpack_path.stem
    if workflow_name.endswith('.cpack'):
        workflow_name = workflow_name[:-6]  # 移除 .cpack
    
    # 目标文件名
    target_filename = f"{workflow_name}.json"
    target = target_dir / target_filename
    
    # 检查是否会覆盖已存在的文件
    if target.exists():
        if log_callback:
            log_callback(f"⚠ 工作流文件已存在，将覆盖: user/default/workflows/{target_filename}")
    
    try:
        # 只复制单个工作流文件，不会删除或影响目录中的其他文件
        shutil.copy2(source, target)
        if log_callback:
            log_callback(f"✓ 工作流文件已保存到: user/default/workflows/{target_filename}")
            log_callback(f"  （其他工作流文件保持不变）")
        return True
    except Exception as e:
        if log_callback:
            log_callback(f"✗ 复制工作流文件失败: {e}")
        return False


def unpack_to_existing_comfyui(
    cpack_path: Path,
    comfyui_dir: Path,
    python_exe: Path,
    git_exe: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """
    解包到现有 ComfyUI 环境
    
    Args:
        cpack_path: 压缩包路径
        comfyui_dir: ComfyUI 根目录
        python_exe: Python 可执行文件路径
        git_exe: Git 可执行文件路径（可选）
        progress_callback: 进度回调 (stage, percentage)
        log_callback: 日志回调
    
    Returns:
        是否成功
    """
    import tempfile
    import zipfile
    
    if log_callback:
        log_callback("=" * 50)
        log_callback("开始解包工作流")
        log_callback(f"压缩包: {cpack_path}")
        log_callback(f"目标目录: {comfyui_dir}")
        log_callback(f"Python: {python_exe}")
        log_callback("=" * 50)
    
    # 解压到临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        pack_dir = Path(temp_dir)
        
        if progress_callback:
            progress_callback("解压压缩包", 5)
        if log_callback:
            log_callback("正在解压压缩包...")
        
        try:
            with zipfile.ZipFile(cpack_path, 'r') as zip_ref:
                zip_ref.extractall(pack_dir)
        except Exception as e:
            if log_callback:
                log_callback(f"✗ 解压失败: {e}")
            return False
        
        # 读取 snapshot
        snapshot_file = pack_dir / "snapshot.json"
        if not snapshot_file.exists():
            if log_callback:
                log_callback("✗ 压缩包中缺少 snapshot.json")
            return False
        
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
        except Exception as e:
            if log_callback:
                log_callback(f"✗ 读取 snapshot.json 失败: {e}")
            return False
        
        # 检查并切换 ComfyUI 版本
        target_commit = snapshot.get("comfyui_commit")
        if target_commit:
            if progress_callback:
                progress_callback("检查 ComfyUI 版本", 7)
            
            current_commit = get_comfyui_commit(comfyui_dir)
            
            if log_callback:
                log_callback("正在检查 ComfyUI 版本...")
                if current_commit:
                    log_callback(f"  当前版本: {current_commit[:8]}")
                else:
                    log_callback("  当前版本: 未知 (非 git 仓库)")
                log_callback(f"  目标版本: {target_commit[:8]}")
            
            if current_commit and current_commit != target_commit:
                if log_callback:
                    log_callback("  版本不匹配，正在切换...")
                
                if not switch_comfyui_version(comfyui_dir, target_commit, git_exe, log_callback):
                    if log_callback:
                        log_callback("  ✗ 切换 ComfyUI 版本失败，继续解包...")
                else:
                    if log_callback:
                        log_callback("  ✓ ComfyUI 版本已切换")
            elif current_commit == target_commit:
                if log_callback:
                    log_callback("  ✓ ComfyUI 版本已是目标版本")
            else:
                if log_callback:
                    log_callback("  ⚠ 无法验证 ComfyUI 版本 (非 git 仓库)")
        else:
            if log_callback:
                log_callback("  ⚠ 压缩包中未记录 ComfyUI 版本信息")
        
        # 检查插件
        if progress_callback:
            progress_callback("检查插件", 10)
        
        plugins_diff = check_plugin_versions(snapshot, comfyui_dir, git_exe, log_callback)
        
        # 检查依赖
        if progress_callback:
            progress_callback("检查依赖", 15)
        
        deps_diff = check_dependencies(snapshot, python_exe, log_callback)
        
        # 安装/更新插件
        if progress_callback:
            progress_callback("处理插件", 20)
        
        def plugin_progress(current, total, name):
            if progress_callback:
                pct = 20 + int((current / max(total, 1)) * 40)
                progress_callback(f"处理插件: {name}", pct)
        
        plugins_success = install_or_update_plugins(
            plugins_diff, comfyui_dir, python_exe, git_exe, plugin_progress, log_callback
        )
        # 即使有插件失败，也继续处理依赖和其他步骤
        
        # 安装/更新依赖
        if progress_callback:
            progress_callback("处理依赖", 60)
        
        def deps_progress(current, total, name):
            if progress_callback:
                pct = 60 + int((current / max(total, 1)) * 20)
                progress_callback(f"安装依赖: {name}", pct)
        
        if not install_dependencies_to_existing(
            deps_diff, python_exe, deps_progress, log_callback
        ):
            return False
        
        # 复制 input 文件
        if progress_callback:
            progress_callback("复制文件", 80)
        
        def file_progress(current, total, name):
            if progress_callback:
                pct = 80 + int((current / max(total, 1)) * 15)
                progress_callback(f"复制文件: {name}", pct)
        
        if not copy_input_files(pack_dir, comfyui_dir, file_progress, log_callback):
            return False
        
        # 复制工作流文件
        if progress_callback:
            progress_callback("复制工作流", 95)
        
        if not copy_workflow_files(pack_dir, comfyui_dir, cpack_path, log_callback):
            return False
        
        if progress_callback:
            progress_callback("完成", 100)
        
        if log_callback:
            # 输出最终统计
            log_callback("")
            log_callback("=" * 50)
            log_callback("解包统计")
            log_callback("=" * 50)
            
            # ComfyUI 版本
            if target_commit:
                final_commit = get_comfyui_commit(comfyui_dir)
                if final_commit:
                    if final_commit == target_commit:
                        log_callback(f"ComfyUI 版本: {final_commit[:8]} ✓")
                    else:
                        log_callback(f"ComfyUI 版本: {final_commit[:8]} (目标: {target_commit[:8]})")
                else:
                    log_callback(f"ComfyUI 版本: 未知")
            
            # 插件统计
            total_plugins = len(plugins_diff['to_install']) + len(plugins_diff['to_update']) + len(plugins_diff['ok'])
            log_callback(f"插件总数: {total_plugins}")
            log_callback(f"  - 新安装: {len(plugins_diff['to_install'])} 个")
            log_callback(f"  - 已更新: {len(plugins_diff['to_update'])} 个")
            log_callback(f"  - 已是最新: {len(plugins_diff['ok'])} 个")
            
            # 依赖统计
            total_deps = len(deps_diff['to_install']) + len(deps_diff['to_update']) + len(deps_diff['ok'])
            log_callback(f"依赖包总数: {total_deps}")
            log_callback(f"  - 新安装: {len(deps_diff['to_install'])} 个")
            log_callback(f"  - 已更新: {len(deps_diff['to_update'])} 个")
            log_callback(f"  - 已是最新: {len(deps_diff['ok'])} 个")
            
            log_callback("=" * 50)
            if plugins_success:
                log_callback("✓ 解包完成！")
            else:
                log_callback("⚠ 解包完成（部分插件失败）")
            log_callback("=" * 50)
        
        # 只要依赖和文件处理成功就返回 True
        return True

