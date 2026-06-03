"""AI 分析模块 - 使用 Qwen-VL-30B 进行多模态分析"""

import os
import json
import base64
import cv2
import numpy as np
from typing import Optional, Dict
from openai import OpenAI
from io import BytesIO
from PIL import Image

# ModelScope API 配置
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_TOKEN", "")
MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/v1"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Instruct"

# 初始化客户端（增加超时配置）
if MODELSCOPE_API_KEY:
    import httpx
    # 创建自定义httpx client，设置更长的超时时间
    http_client = httpx.Client(
        timeout=120.0,  # 全局120秒超时
        verify=True
    )
    client = OpenAI(
        base_url=MODELSCOPE_BASE_URL,
        api_key=MODELSCOPE_API_KEY,
        http_client=http_client
    )
else:
    client = None


def compress_image_to_base64(image_array: np.ndarray, max_size: int = 1024, quality: int = 85) -> str:
    """将图片压缩并转换为base64

    Args:
        image_array: numpy图像数组
        max_size: 最大边长（像素）
        quality: JPEG质量 (1-100)

    Returns:
        base64编码的压缩图片
    """
    h, w = image_array.shape[:2]

    # 如果图片太大，压缩
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        image_array = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"[AI分析] 图片已压缩: {w}x{h} → {new_w}x{new_h}")

    # 转换为JPEG并压缩质量
    _, buffer = cv2.imencode('.jpg', image_array, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buffer).decode('utf-8')


def image_to_base64(image_array: np.ndarray) -> str:
    """将numpy图像数组转换为base64字符串"""
    _, buffer = cv2.imencode('.jpg', image_array, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buffer).decode('utf-8')


def analyze_with_vision(
    hand_image: np.ndarray,
    design_image_path: Optional[str] = None,
    design_name: str = "美甲款式",
) -> Dict[str, str]:
    """使用Qwen VL对手部图片和美甲款式进行分析

    Args:
        hand_image: 用户上传的手部图片 (numpy array)
        design_image_path: 美甲款式图片路径
        design_name: 美甲款式名称

    Returns:
        包含分析结果的字典
    """

    if not MODELSCOPE_API_KEY or not client:
        print("[AI分析] 未配置 ModelScope API Key，返回示例数据")
        return _get_fallback_analysis(design_name)

    try:
        # 将手部图片转换为base64（尽量保留细节，便于准确分析肤色和手型）
        hand_base64 = compress_image_to_base64(hand_image, max_size=1280, quality=92)
        hand_image_url = f"data:image/jpeg;base64,{hand_base64}"

        # 构造消息内容
        content = [
            {
                "type": "text",
                "text": f"""你是一位专业的美甲搭配顾问和色彩搭配专家。请根据提供的用户手部照片和美甲款式图片，进行详细的搭配分析。

分析任务：
1. 分析用户的肤色特征（冷色调/暖色调，亮度，肤质）
2. 分析用户的手型特征（手指长度、宽度、骨架大小）
3. 评估美甲款式与用户肤色、手型的搭配度
4. 根据用户肤色，推荐最适合的色系和美甲风格
5. 给出专业的搭配建议和适用场景

请生成以下JSON格式的分析（必须是有效的JSON）：
{{
    "confidence": 0.85,
    "hand_rating": "A+",
    "skin_tone": "冷白皮",
    "hand_shape": "修长型",
    "description": "分析评价和建议，一句话专业总结",
    "why_match": "为什么这款美甲适合这位用户，具体说明肤色和手型的搭配点",
    "recommended_colors": ["正红", "樱花粉", "雾紫"],
    "best_color_systems": {{
        "primary": "冷色调色系，特别是玫红、深紫、宝蓝等高级色",
        "secondary": "中性色如黑色、裸色也能很好地衬托肤色",
        "avoid": "过于鲜艳的暖橙色、土黄色容易显肤色暗沉"
    }},
    "style_recommendations": ["极简主义", "高级感纯色", "几何图案", "金属质感"],
    "applicable_scenes": ["约会", "日常通勤", "职场"]
}}

要求：
1. 分析要基于实际图片内容，个性化具体
2. confidence 范围 0-1，根据搭配协调度评分
3. hand_rating 为 A+, A, B+, B, C 之一
4. description 要包含对肤色、手型、款式的评价
5. why_match 要说明具体的色彩搭配原理和肤色相关的理由
6. recommended_colors 只返回颜色名称，不要色号
7. best_color_systems 要详细说明该肤色适合的色系（primary主要推荐、secondary次要推荐、avoid要避免）
8. style_recommendations 列出该肤色和手型适合的美甲风格（如极简、复古、个性、甜美等）
9. applicable_scenes 返回适用场景列表
10. 所有文本使用简体中文
11. 必须返回有效的JSON格式，不要有其他文本"""
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": hand_image_url
                }
            }
        ]

        # 如果有美甲款式图片，也添加到内容中
        if design_image_path and os.path.exists(design_image_path):
            try:
                design_img = cv2.imread(design_image_path)
                if design_img is not None:
                    design_base64 = compress_image_to_base64(design_img, max_size=1280, quality=92)
                    design_image_url = f"data:image/jpeg;base64,{design_base64}"
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": design_image_url
                        }
                    })
                    print(f"[AI分析] 已加载美甲款式图片: {design_image_path}")
            except Exception as e:
                print(f"[AI分析] 读取美甲款式图片失败: {e}")

        # 调用 Qwen VL API（增加超时时间和重试）
        print(f"[AI分析] 调用 {MODEL_NAME} 进行分析...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[AI分析] 尝试请求 (第 {attempt + 1}/{max_retries} 次)...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{
                        "role": "user",
                        "content": content
                    }],
                    temperature=0.7,
                    max_tokens=800,
                    stream=False,
                    timeout=120.0  # 增加超时时间到120秒
                )
                break  # 成功，跳出重试循环
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[AI分析] 请求失败 (第 {attempt + 1} 次): {str(e)[:100]}")
                    import time
                    time.sleep(2)  # 等待2秒后重试
                else:
                    raise  # 最后一次尝试失败，抛出异常

        # 提取返回内容
        if not response.choices or not response.choices[0].message:
            print("[AI分析] 模型返回为空")
            return _get_fallback_analysis(design_name)

        analysis_text = response.choices[0].message.content
        print(f"[AI分析] Qwen 返回: {analysis_text[:100]}...")

        # 解析JSON响应
        try:
            # 尝试从返回文本中提取JSON
            analysis = _extract_json_from_text(analysis_text)

            if analysis and all(k in analysis for k in ["confidence", "hand_rating", "description"]):
                return analysis
        except Exception as e:
            print(f"[AI分析] JSON解析失败: {e}")

        return _get_fallback_analysis(design_name)

    except Exception as e:
        print(f"[AI分析] Qwen VL 分析异常: {e}")
        import traceback
        traceback.print_exc()
        return _get_fallback_analysis(design_name)


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """从文本中提取JSON对象"""
    try:
        # 尝试直接解析
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试找到JSON块
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        try:
            json_str = text[start_idx:end_idx + 1]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None


def _get_fallback_analysis(design_name: str) -> Dict[str, str]:
    """返回备用分析数据"""
    return {
        "confidence": 0.80,
        "hand_rating": "A",
        "skin_tone": "自然肤色",
        "hand_shape": "修长型",
        "description": f"这款{design_name}款式优雅大气，适合多种场景搭配。",
        "why_match": "款式设计经典，颜色搭配温和，适合日常和正式场合。",
        "recommended_colors": ["正红", "樱花粉", "雾紫"],
        "best_color_systems": {
            "primary": "百搭中性色系，适合多种场景",
            "secondary": "温和的粉色和裸色也能很好表现气质",
            "avoid": "过于浓烈的荧光色可能显得突兀"
        },
        "style_recommendations": ["极简主义", "高级感纯色", "温柔甜美"],
        "applicable_scenes": ["日常通勤", "约会", "职场"]
    }
