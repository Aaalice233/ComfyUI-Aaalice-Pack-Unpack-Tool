# 更新 EXE 文件的辅助脚本
Write-Host "==============================================="
Write-Host "更新 comfy-pack-unpack.exe"
Write-Host "==============================================="
Write-Host ""

# 检查程序是否在运行
$processes = Get-Process -Name "comfy-pack-unpack" -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "发现正在运行的程序实例:" -ForegroundColor Yellow
    $processes | ForEach-Object { Write-Host "  - PID: $($_.Id)" }
    Write-Host ""
    Write-Host "请手动关闭所有解包工具窗口，然后按任意键继续..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Write-Host ""
}

# 再次检查
$processes = Get-Process -Name "comfy-pack-unpack" -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "程序仍在运行，尝试强制结束..." -ForegroundColor Yellow
    Stop-Process -Name "comfy-pack-unpack" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 复制文件
Write-Host "正在复制最新版本..." -ForegroundColor Green
try {
    Copy-Item "dist\comfy-pack-unpack.exe" "comfy-pack-unpack.exe" -Force
    Write-Host "✓ 更新成功！" -ForegroundColor Green
    Write-Host ""
    Get-Item "comfy-pack-unpack.exe" | Format-Table LastWriteTime, Length, Name
} catch {
    Write-Host "✗ 复制失败: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "请手动复制:" -ForegroundColor Yellow
    Write-Host "  从: dist\comfy-pack-unpack.exe"
    Write-Host "  到: comfy-pack-unpack.exe"
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

