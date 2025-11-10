# ComfyUI 工作流解包工具

这是一个图形化的 ComfyUI 工作流解包工具，可以将打包的工作流（.cpack.zip）一键安装到现有的 ComfyUI 环境中。

## 功能特性

- 🎨 **现代化图形界面** - 美观直观的操作界面
- 🔍 **智能检测** - 自动检测 Python 环境
- 📦 **自动安装** - 自动安装缺失的插件和依赖
- 🔄 **版本管理** - 自动切换插件到正确版本
- 📊 **实时进度** - 显示详细的安装进度和日志
- 🌐 **Discord 集成** - 完成后可一键加入作者社区

## 使用方法

### 直接使用（推荐）

1. 双击运行 `comfy-pack-unpack.exe`
2. 点击"浏览"选择工作流压缩包（.cpack.zip 文件）
3. 点击"浏览"选择你的 ComfyUI 根目录
4. 工具会自动检测 Python 环境（如有多个会让你选择）
5. 点击"开始解包"按钮
6. 等待完成，查看日志了解详细进度

### 从源码构建

如果你想自己构建 EXE 文件：

```batch
# 1. 安装依赖
cd exe
pip install -r requirements.txt

# 2. 运行构建脚本
build.bat

# 3. 生成的 EXE 文件在 exe 目录
```

## 系统要求

- Windows 10/11
- Git（用于管理插件版本）
- 现有的 ComfyUI 安装

## 常见问题

### Q: 解包失败，提示找不到 Git
**A:** 请安装 Git for Windows: https://git-scm.com/download/win

### Q: 检测不到 Python 环境
**A:** 
- 确保选择的是 ComfyUI 根目录（包含 main.py 的目录）
- 确保 ComfyUI 有虚拟环境（.venv 或 venv 文件夹）
- 可以点击"手动选择"来指定 Python 路径

### Q: 插件安装失败
**A:**
- 检查网络连接
- 查看日志获取详细错误信息
- 确保 Git 可以访问 GitHub

### Q: 依赖安装超时
**A:**
- 可能是网络问题，建议配置 pip 国内镜像
- 或手动在 ComfyUI 环境中安装依赖

## 技术细节

- **GUI 框架**: PySide6 (Qt6)
- **Git 操作**: GitPython
- **打包工具**: PyInstaller
- **文件大小**: 约 80-120MB

## 开发者

- 基于 comfy-pack 项目开发
- GUI 工具由 Aaalice 创建

## 许可证

与主项目保持一致

