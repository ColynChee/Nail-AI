"""使用 Qwen VL 分析 + 文生图 API 增强美甲试戴效果"""

import os
import json
import time
import requests
import base64
from typing import Optional
from pathlib import Path
from openai import OpenAI
import httpx

MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_TOKEN", "")
MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/v1"  # 包含/v1
MODEL_NAME_VL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
MODEL_NAME_GENIMAGE = "Qwen/Qwen-VL-Plus"  # 文生图模型

# 初始化Qwen VL客户端
if MODELSCOPE_API_KEY:
    http_client = httpx.Client(timeout=120.0, verify=True)
    vl_client = OpenAI(
        base_url=MODELSCOPE_BASE_URL,
        api_key=MODELSCOPE_API_KEY,
        http_client=http_client
    )
else:
    vl_client = None

COMMON_HEADERS = {
    "Authorization": f"Bearer {MODELSCOPE_API_KEY}",
    "Content-Type": "application/json",
}


def image_to_base64(image_path: str) -> str:
    """将图片文件转换为base64"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def upload_image_to_modelscope(image_path_or_base64: str, is_base64: bool = False) -> str:
    """上传图片到ModelScope并返回URL（或直接返回base64用于API）"""
    # 对于这个API，我们可以直接用base64
    if is_base64:
        return f"data:image/jpeg;base64,{image_path_or_base64}"
    else:
        # 如果是本地文件路径，转换为base64
        base64_str = image_to_base64(image_path_or_base64)
        return f"data:image/jpeg;base64,{base64_str}"


async def enhance_nail_tryon(
    hand_image_path: str,
    design_image_path: str,
    design_name: str = "美甲款式"
) -> Optional[dict]:
    """虚拟试戴增强功能（暂未实现）"""
    return {
        "success": False,
        "message": "虚拟增强功能开发中"
    }


async def enhance_nail_tryon_old(
    hand_image_path: str,
    design_image_path: str,
    design_name: str = "美甲款式"
) -> Optional[dict]:
    """使用Qwen-Image-Edit-2511直接进行虚拟试戴

    Args:
        hand_image_path: 用户手部图片路径
        design_image_path: 美甲款式详细图路径
        design_name: 美甲款式名称

    Returns:
        包含增强结果的字典或None
    """

    if not MODELSCOPE_API_KEY:
        print("[ImageEnhancer] 未配置 ModelScope API Key")
        return None

    try:
        print(f"[ImageEnhancer] 准备虚拟试戴...")
        print(f"[ImageEnhancer] 手部图: {hand_image_path}")
        print(f"[ImageEnhancer] 款式图: {design_image_path}")

        # 验证文件存在
        if not os.path.exists(hand_image_path):
            print(f"[ImageEnhancer] 手部图不存在: {hand_image_path}")
            return None
        if not os.path.exists(design_image_path):
            print(f"[ImageEnhancer] 款式图不存在: {design_image_path}")
            return None

        # 读取图片并转换为base64
        with open(design_image_path, 'rb') as f:
            design_base64 = base64.b64encode(f.read()).decode('utf-8')
        with open(hand_image_path, 'rb') as f:
            hand_base64 = base64.b64encode(f.read()).decode('utf-8')

        print(f"[ImageEnhancer] 图片转base64完成，大小: 设计={len(design_base64)}, 手部={len(hand_base64)}")

        # 构造豆包多图编辑请求（关键：使用明确的数字前缀指示图片顺序）
        prompt = f"""第一张图是{design_name}美甲款式的详细设计图。第二张图是用户的真实手部照片。
任务：生成虚拟试戴效果图 - 将第一张图中的美甲款式的颜色、纹理和设计完全套用到第二张图用户的所有5个手指指甲上。
要求：
- 所有5个手指的指甲都要被正确套用这款美甲
- 美甲的位置、大小、方向与用户真实指甲完全贴合
- 保留用户手部的所有自然特征：肤色、皮肤纹理、手指形状、手势、背景
- 只修改指甲部分，手部其他区域保持完全原样
- 最终结果看起来非常自然逼真，就像用户真的涂上了这款美甲"""

        print(f"[ImageEnhancer] 调用豆包多图编辑...")

        # 调用豆包多图编辑API（使用base64方式）
        request_data = {
            "model": "z1596407/doubao",
            "prompt": prompt,
            "image_url": [
                f"data:image/jpeg;base64,{design_base64}",
                f"data:image/jpeg;base64,{hand_base64}"
            ]
        }

        print(f"[ImageEnhancer] 请求提交: prompt_len={len(request_data['prompt'])}, images={len(request_data['image_url'])}")

        response = requests.post(
            "https://api-inference.modelscope.cn/v1/images/generations",
            headers={**COMMON_HEADERS, "X-ModelScope-Async-Mode": "true"},
            data=json.dumps(request_data, ensure_ascii=False).encode('utf-8'),
            timeout=30,
            proxies={"https": "", "http": ""}
        )

        if response.status_code != 200:
            print(f"[ImageEnhancer] 提交任务失败: {response.status_code}")
            print(f"[ImageEnhancer] 错误: {response.text}")
            return None

        task_data = response.json()
        task_id = task_data.get("task_id")
        if not task_id:
            print(f"[ImageEnhancer] 未获得task_id: {task_data}")
            return None

        print(f"[ImageEnhancer] 任务已提交，task_id: {task_id}")

        # 轮询等待结果
        enhanced_image = _poll_doubao_result(task_id)

        if not enhanced_image:
            print("[ImageEnhancer] 虚拟试戴失败")
            return None

        return {
            "success": True,
            "image_base64": enhanced_image,
            "design_name": design_name,
            "message": f"{design_name}虚拟试戴成功！"
        }

    except Exception as e:
        print(f"[ImageEnhancer] 异常: {e}")
        import traceback
        traceback.print_exc()
        return None


def _poll_doubao_result(task_id: str) -> Optional[str]:
    """轮询豆包多图编辑任务结果

    Args:
        task_id: 任务ID

    Returns:
        生成图片的base64编码
    """
    max_wait_time = 300  # 最多等待300秒（5分钟）
    start_time = time.time()
    poll_interval = 5

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            print(f"[ImageEnhancer] 任务超时（{max_wait_time}秒）")
            return None

        try:
            result = requests.get(
                f"https://api-inference.modelscope.cn/v1/tasks/{task_id}",
                headers={**COMMON_HEADERS, "X-ModelScope-Task-Type": "image_generation"},
                timeout=30,
                proxies={"https": "", "http": ""}
            )
            result.raise_for_status()
            data = result.json()
        except Exception as e:
            print(f"[ImageEnhancer] 查询失败: {str(e)[:50]}, {poll_interval}秒后重试...")
            time.sleep(poll_interval)
            continue

        status = data.get("task_status", "UNKNOWN")
        print(f"[ImageEnhancer] 任务状态: {status} (已耗时 {elapsed:.1f}s)")

        if status == "SUCCEED":
            output_images = data.get("output_images", [])
            if not output_images:
                print(f"[ImageEnhancer] 任务成功但无输出图片")
                return None

            print(f"[ImageEnhancer] 虚拟试戴成功，下载图片...")
            image_url = output_images[0]

            # 下载图片（带重试和SSL容错）
            max_download_retries = 3
            for download_attempt in range(max_download_retries):
                try:
                    print(f"[ImageEnhancer] 下载图片 (第 {download_attempt + 1}/{max_download_retries} 次)...")
                    img_response = requests.get(
                        image_url,
                        timeout=30,
                        verify=False,
                        proxies={"https": "", "http": ""}
                    )
                    img_response.raise_for_status()
                    enhanced_base64 = base64.b64encode(img_response.content).decode('utf-8')
                    print(f"[ImageEnhancer] 图片下载成功，大小: {len(enhanced_base64)} bytes")
                    return enhanced_base64
                except Exception as e:
                    print(f"[ImageEnhancer] 下载异常 (第 {download_attempt + 1} 次): {str(e)[:80]}")
                    if download_attempt < max_download_retries - 1:
                        print(f"[ImageEnhancer] 2秒后重试...")
                        time.sleep(2)
                    else:
                        print(f"[ImageEnhancer] 多次下载失败")
                        return None

        elif status == "FAILED":
            error_msg = data.get('error', '未知错误')
            print(f"[ImageEnhancer] 任务失败: {error_msg}")
            return None

        elif status in ["PROCESSING", "RUNNING", "QUEUED"]:
            print(f"[ImageEnhancer] {status}中，{poll_interval}秒后重试...")
            time.sleep(poll_interval)

        else:
            print(f"[ImageEnhancer] 未知状态: {status}，{poll_interval}秒后重试...")
            time.sleep(poll_interval)
