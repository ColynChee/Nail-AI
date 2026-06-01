#!/usr/bin/env python
"""环境检查脚本"""
import sys
import subprocess

print("=" * 50)
print("🔍 环境检查")
print("=" * 50)

# 1. Python 版本
print(f"\n✓ Python 版本: {sys.version}")

# 2. CUDA 检查
try:
    import torch
    print(f"✓ PyTorch 已安装: {torch.__version__}")
    print(f"✓ CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  - GPU 设备: {torch.cuda.get_device_name(0)}")
        print(f"  - CUDA 版本: {torch.version.cuda}")
    else:
        print("  ⚠️ 警告: CUDA 不可用，推荐安装 CUDA 支持的 PyTorch")
except ImportError:
    print("✗ PyTorch 未安装，需要: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")

# 3. 核心依赖检查
dependencies = [
    'fastapi', 'uvicorn', 'opencv-python', 'mediapipe',
    'PIL', 'numpy', 'pydantic', 'requests'
]

print("\n检查依赖:")
missing = []
for dep in dependencies:
    try:
        __import__(dep if dep != 'PIL' else 'PIL')
        print(f"  ✓ {dep}")
    except ImportError:
        print(f"  ✗ {dep} 缺失")
        missing.append(dep)

# 4. Ollama 检查
print("\n检查 Ollama:")
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=2)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print(f"  ✓ Ollama 运行中，已拉取 {len(models)} 个模型:")
        for model in models:
            print(f"    - {model['name']}")
    else:
        print(f"  ⚠️ Ollama 响应异常: {response.status_code}")
except:
    print("  ✗ Ollama 未运行，请先启动 Ollama (ollama serve)")

# 5. MediaPipe 模型检查
import os
if os.path.exists("hand_landmarker.task"):
    print("\n✓ hand_landmarker.task 文件存在")
else:
    print("\n✗ hand_landmarker.task 缺失，需要下载")

# 总结
print("\n" + "=" * 50)
if missing:
    print(f"⚠️ 需要安装缺失的包: pip install {' '.join(missing)}")
else:
    print("✅ 所有依赖已安装！")
print("=" * 50)
