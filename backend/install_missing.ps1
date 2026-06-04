# 安装缺失的包

Write-Host "📦 安装缺失的包..." -ForegroundColor Cyan

# 1. OpenCV
Write-Host "`n安装 opencv-python..." -ForegroundColor Yellow
pip install opencv-python

# 2. PyTorch with CUDA 11.8
Write-Host "`n安装 PyTorch (CUDA 11.8)..." -ForegroundColor Yellow
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

Write-Host "`n✅ 安装完成！" -ForegroundColor Green
Write-Host "运行 `python check_env.py` 验证环境" -ForegroundColor Cyan
