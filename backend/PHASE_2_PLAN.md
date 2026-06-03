# Phase 2: 极端点对齐 (Extreme Points Alignment)

**创建时间**: 2026-06-02  
**状态**: 实验版本 (🧪)  
**目标**: 测试极端点对齐是否比原版角度对齐更精准

## 核心思路

### 原版方法 (角度对齐)
```
已知信息:
  - 用户指甲的中心点 (cx, cy)
  - 用户指甲的倾斜角度 tip_angle
  - 用户指甲的长宽尺寸 L, W
  
计算方式:
  根据角度生成 4 个角点 → 透视变换
```

**问题**: 当指甲倾斜较大时，用角度和中心点计算的 4 个角点可能不够精确

### Phase 2 方法 (极端点对齐) ✨
```
已知信息:
  - 用户指甲的指尖极端点 (tip_point)
  - 用户指甲的指根极端点 (root_point)
  - 用户指甲的宽度 W (从指尖到指根的垂直距离)
  
计算方式:
  1. 直接使用指尖/指根点作为关键点
  2. 根据宽度计算左右两侧偏移
  3. 形成 4 个角点 → 透视变换
  
优点:
  ✓ 不依赖角度计算，直接基于指甲形状
  ✓ 特别适合倾斜较大的指甲
  ✓ 更精确的极端点匹配
```

## 文件结构

```
backend/
├── nail_tryon_v2.py              (原版 - 角度对齐)
├── nail_tryon_v2_extreme.py      (Phase 2 - 极端点对齐) ← 新增
├── test_alignment_compare.py     (对比测试脚本) ← 新增
└── PHASE_2_PLAN.md              (本文档) ← 新增
```

## 使用方法

### 直接调用 Phase 2

```python
import nail_tryon_v2_extreme as v2ex
import cv2

img = cv2.imread("user_hand.jpg")
design_id = "dior_design"

# 极端点对齐版本
result = v2ex.try_on(img, design_id, use_extreme_alignment=True)

# 原版角度对齐（用于对比）
result = v2ex.try_on(img, design_id, use_extreme_alignment=False)
```

### 运行对比测试

```bash
# 对比两个版本的效果
python test_alignment_compare.py user_hand.jpg dior_design output_compare/

# 会生成：
# - output_compare/01_original_angle_align.jpg (原版结果)
# - output_compare/02_extreme_align.jpg        (Phase 2结果)
# - output_compare/03_side_by_side.jpg         (并排对比)
```

## 评估标准

对比时关注以下指标：

| 指标 | 原版角度对齐 | Phase 2极端点对齐 | 评分 |
|------|------------|------------------|------|
| 位置准确度 | ? | ? | |
| 倾斜时稳定性 | ? | ? | |
| 纹理覆盖度 | ? | ? | |
| 边缘对齐 | ? | ? | |
| **综合评分** | | | |

## 回滚计划

如果 Phase 2 效果不如原版：

```bash
# 简单回滚 - 继续使用原版
rm nail_tryon_v2_extreme.py test_alignment_compare.py

# 或保留实验版，继续优化
# Phase 2 失败的原因可能是：
# - 极端点检测不够精确
# - 垂直方向计算有偏差
# - 覆盖因子需要调整
```

## 下一步优化方向 (如果需要)

1. **极端点检测优化**
   - 使用更稳健的算法 (RANSAC?)
   - 排除YOLO mask的毛刺影响

2. **动态覆盖因子**
   - 根据指甲倾斜角度调整 cover = 1.15
   - 倾斜越大，覆盖因子越大

3. **多尺度匹配**
   - 尝试多个角度偏移 (-10° 到 +10°)
   - 选择覆盖度最高的匹配

4. **混合方案**
   - 结合极端点和中心点的优点
   - 用极端点做主变换，用中心点做校准

## 核心代码文件

| 文件 | 关键函数 |
|------|---------|
| nail_tryon_v2_extreme.py | `_warp_mold_to_nail_extreme()` |
| nail_tryon_v2_extreme.py | `_get_nail_extremes()` |
| nail_tryon_v2_extreme.py | `try_on(use_extreme_alignment=True)` |

## 问题排查

### Q: 如何判断极端点对齐是否成功？
**A**: 
```python
result = v2ex.try_on(img, design_id, use_extreme_alignment=True)
print(result["mode"])  # 应该是 "pattern_extreme" 而非 "pattern"
```

### Q: 为什么保留原版函数在 extreme 文件里？
**A**: 方便对比测试，不需要改动原版文件。测试可以直接在一个文件里比较。

### Q: 什么时候应该合并回 nail_tryon_v2.py？
**A**: 
- ✓ Phase 2 在所有测试图片上效果都更好时
- ✓ 性能没有显著下降时
- ✓ 边界情况(倾斜、手指弯曲等)都处理良好时

---

**记录日期**: 2026-06-02  
**实验者**: Claude Code  
**预计完成**: 2026-06-05
