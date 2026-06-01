# Week 1: Server Foundation 任务清单

## Day 1: Environment ✅

- [x] Install Python 3.10+ (已有 3.11)
- [x] Install Ollama for Windows
- [x] Pull llava:7b model (已拉取)
- [x] Verify CUDA available (已验证 - 需要安装 PyTorch)
- [ ] **现在做**: 
  ```powershell
  pip install opencv-python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  python check_env.py  # 验证所有依赖安装成功
  ```

---

## Day 2-3: FastAPI Scaffold

- [x] FastAPI, Uvicorn 已安装
- [x] CORS 已配置
- [x] POST /api/try-on endpoint 已实现
- [x] GET /api/designs endpoint 已实现
- [ ] **现在做**:
  ```powershell
  # 启动后端
  python main.py
  # 在另一个终端测试
  python test_backend.py
  ```

---

## Day 4-5: MediaPipe Hand Detection

- [x] MediaPipe Hands 已集成
- [x] 返回 21 landmarks（已实现）
- [x] 处理多手情况（已实现）
- [x] POST /api/detect-hands 已实现
- [ ] **现在做**: 
  ```powershell
  # 用 test_backend.py 测试手部检测
  python test_backend.py  # 第3步
  ```

---

## Day 6-7: LLM Vision Endpoint

- [x] POST /api/analyze-hand 已实现
- [x] Ollama/LLaVA 集成（已完成）
- [x] 缓存机制（已有）
- [ ] **现在做**:
  ```powershell
  # 测试手部分析
  python test_backend.py  # 第4步
  # 确保响应时间 < 3s
  ```

---

## 当前进度

```
Week 1 完成度: 60%
缺失项: 
  - [ ] PyTorch 安装（CUDA 支持）
  - [ ] 实际运行和端到端测试
  - [ ] 性能测试（响应时间检查）
```

---

## 立即行动

1. **安装 PyTorch + OpenCV** (~5 分钟)
   ```powershell
   pip install opencv-python torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **验证环境** (~1 分钟)
   ```powershell
   python check_env.py
   ```

3. **启动后端** (~10 秒)
   ```powershell
   python main.py
   ```

4. **运行测试** (~30 秒)
   ```powershell
   python test_backend.py
   ```

预期完成时间: **8-10 分钟**
