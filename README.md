# ComfyUI-Aaalice-Pack-Unpack-Tool

![banner2](https://github.com/user-attachments/assets/14a7e469-6683-4818-9d54-5e5a8d0aa454)

## English Description

ComfyUI-Aaalice-Pack-Unpack-Tool is a simplified toolkit for packing and unpacking ComfyUI workflows.

**This project is based on [comfy-pack](https://github.com/bentoml/comfy-pack) with significant modifications to focus on essential functionality.**

### Key Differences from Original comfy-pack:
- **Simplified Workflow**: Removed complex API deployment and cloud features
- **EXE-based Unpacking**: Uses executable files for easy environment setup
- **Enhanced GUI Interface**: Improved user interface for better user experience
- **Custom Node Management**: Streamlined handling of custom node dependencies
- **Performance Optimizations**: Improved packing and unpacking speed
- **Localized Support**: Added Chinese language support

### Core Features:
- 📦 **Pack workflow environments**: Creates `.cpack.zip` artifacts containing ComfyUI workflows and custom nodes
- ✨ **EXE-based unpacking**: Uses executable files to easily recreate ComfyUI environments
- 🚀 **Simplified deployment**: Focus on local workflow sharing without complex API features

## 中文描述

ComfyUI-Aaalice-Pack-Unpack-Tool 是一个简化的 ComfyUI 工作流打包和解包工具包。

**本项目基于 [comfy-pack](https://github.com/bentoml/comfy-pack) 进行大幅修改，专注于核心功能。**

### 与原版 comfy-pack 的主要区别：
- **简化工作流程**：移除了复杂的 API 部署和云端功能
- **基于 EXE 的解包**：使用可执行文件进行简单的环境设置
- **增强的图形界面**：改进用户界面，提供更好的用户体验
- **简化的自定义节点管理**：精简自定义节点依赖关系处理
- **性能优化**：改进打包和解包速度
- **本地化支持**：增加了中文语言支持

### 核心功能：
- 📦 **打包工作流环境**：创建包含 ComfyUI 工作流和自定义节点的 `.cpack.zip` 工件
- ✨ **基于 EXE 解包**：使用可执行文件轻松重现 ComfyUI 环境
- 🚀 **简化部署**：专注于本地工作流共享，无需复杂的 API 功能

## Installation / 安装

### English Installation
We recommend you use ComfyUI Manager to install this tool. Simply search for `ComfyUI-Aaalice-Pack-Unpack-Tool` and click **Install**. Restart the server and refresh your ComfyUI interface to apply changes.

Alternatively, clone the project repository through `git`:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Aaalice233/ComfyUI-Aaalice-Pack-Unpack-Tool.git
```

### 中文安装说明
我们建议使用 ComfyUI Manager 安装。只需搜索 `ComfyUI-Aaalice-Pack-Unpack-Tool` 并点击 **安装**。重启服务器并刷新 ComfyUI 界面以应用更改。

或者通过 `git` 克隆项目仓库：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Aaalice233/ComfyUI-Aaalice-Pack-Unpack-Tool.git
```

## Usage / 使用方法

### Pack a ComfyUI workflow / 打包 ComfyUI 工作流

You can package a workflow and the custom nodes required to run the workflow into an artifact that can be unpacked elsewhere.

您可以将工作流和运行工作流所需的自定义节点打包成一个工件，可以在其他地方解包使用。

1. Click the **Package** button in the ComfyUI interface to create a `.cpack.zip` artifact.
2. The artifact will contain your workflow JSON and necessary custom nodes.

### Unpack the ComfyUI environments / 解包 ComfyUI 环境

#### Windows

Unpacking is done through the provided executable file for simple setup.

解包通过提供的可执行文件进行，操作简单。

1. Run the provided executable file (included in the package)
2. Select your `.cpack.zip` file
3. The executable will automatically set up the ComfyUI environment with required custom nodes

#### Linux

On Linux, use the command-line tool to unpack workflows.

在 Linux 上，使用命令行工具解包工作流。

```bash
# Method 1: Run as module / 方式 1：作为模块运行
cd ComfyUI/custom_nodes/ComfyUI-Aaalice-Pack-Unpack-Tool
python -m comfy_pack.unpacker_cli workflow.cpack.zip --comfyui /path/to/ComfyUI

# Method 2: Install and use command / 方式 2：安装后使用命令
pip install -e .
comfy-unpack workflow.cpack.zip --comfyui /path/to/ComfyUI

# With manual Python and Git paths / 手动指定 Python 和 Git 路径
comfy-unpack workflow.cpack.zip --comfyui /path/to/ComfyUI \
    --python /usr/bin/python3 --git /usr/bin/git

# Verbose output / 详细输出
comfy-unpack workflow.cpack.zip --comfyui /path/to/ComfyUI -v
```

**CLI Options / CLI 选项:**
- `--comfyui, -c` : ComfyUI root directory (required) / ComfyUI 根目录（必需）
- `--python, -p` : Python executable path (optional, auto-detect) / Python 路径（可选，自动检测）
- `--git, -g` : Git executable path (optional, auto-detect) / Git 路径（可选，自动检测）
- `--verbose, -v` : Show detailed output / 显示详细输出

## Important Notes / 重要说明

### What's NOT included in this version:
- ❌ **No API deployment features**
- ❌ **No model hash verification**
- ❌ **No cloud deployment options**
- ❌ **No BentoML integration**

### What IS included:
- ✅ **Local workflow packaging**
- ✅ **EXE-based easy unpacking**
- ✅ **Custom node management**
- ✅ **Enhanced GUI interface**
- ✅ **Chinese language support**

### Security Guidelines / 安全指南

The cpack files contain workflow JSON and custom node information. Only unpack cpack files from trusted sources.

cpack 文件包含工作流 JSON 和自定义节点信息。请只解包来自可信来源的 cpack 文件。

## Contributing / 贡献

As an open-source project, we welcome contributions focused on simplifying workflow sharing.

作为开源项目，我们欢迎专注于简化工作流共享的贡献。

- For issues and suggestions: Please create issues on [our repository](https://github.com/Aaalice233/ComfyUI-Aaalice-Pack-Unpack-Tool/issues)
- For the original project: [comfy-pack issues](https://github.com/bentoml/comfy-pack/issues)

## Acknowledgments / 致谢

This project is based on the excellent work of the [comfy-pack](https://github.com/bentoml/comfy-pack) project by the BentoML team. We appreciate their contributions to the ComfyUI community and have modified their work to focus on simplified local workflow sharing.

本项目基于 BentoML 团队的 [comfy-pack](https://github.com/bentoml/comfy-pack) 项目的优秀工作。我们感谢他们对 ComfyUI 社区的贡献，并修改了他们的工作以专注于简化的本地工作流共享。

## License / 许可证

This project follows the same license as the original comfy-pack project.

本项目遵循与原版 comfy-pack 项目相同的许可证。