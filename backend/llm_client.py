import json
import hashlib
import requests
import base64
from typing import Dict, List, Optional
import cv2
import numpy as np

class LLMClient:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.cache = {}
        self.available_models = []
        self._check_available_models()
    
    def _check_available_models(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                for model in models:
                    model_name = model.get('name', '')
                    if any(keyword in model_name.lower() for keyword in ['llava', 'moondream', 'cogvlm']):
                        self.available_models.append(model_name)
                
                if self.available_models:
                    print("Available vision models: " + ", ".join(self.available_models))
                else:
                    print("No vision models found, using color-based analysis")
            else:
                print("Failed to get models: " + str(response.status_code))
        except Exception as e:
            print("Error checking models: " + str(e) + ", using color-based analysis")
    
    def generate_image_hash(self, image_data: bytes) -> str:
        return hashlib.md5(image_data).hexdigest()
    
    def _analyze_color_based(self, image_data: bytes) -> Dict:
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return self._get_default_result()
        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        face_region = img_rgb[img_rgb.shape[0]//4:img_rgb.shape[0]//2, :]
        
        avg_color = np.mean(face_region, axis=(0, 1))
        brightness = np.mean(avg_color)
        
        r, g, b = avg_color[0], avg_color[1], avg_color[2]
        
        if brightness > 200:
            skin_tone = "暖白色"
            undertone = "冷色调" if b > r else "暖色调"
            recommended_colors = ["裸粉色", "豆沙色", "蜜桃色", "浅紫色", "薄荷绿"]
        elif brightness > 150:
            skin_tone = "自然色"
            undertone = "中性色调"
            recommended_colors = ["奶茶色", "焦糖色", "豆沙色", "裸粉色", "酒红色"]
        elif brightness > 100:
            skin_tone = "小麦色"
            undertone = "暖色调"
            recommended_colors = ["焦糖色", "巧克力色", "酒红色", "墨绿色", "金色"]
        else:
            skin_tone = "健康棕"
            undertone = "暖色调"
            recommended_colors = ["酒红色", "深紫色", "金色", "墨绿色", "古铜色"]
        
        color_tip = recommended_colors[0] if recommended_colors else "裸粉色"
        description = f"{skin_tone}肤色，{undertone}，适合{color_tip}系美甲。推荐尝试{'、'.join(recommended_colors[:3])}，显色效果佳。"
        return {
            "success": True,
            "skin_tone": skin_tone,
            "undertone": undertone,
            "hand_shape": "普通",
            "recommended_colors": recommended_colors,
            "confidence": 0.6,
            "description": description
        }
    
    def _get_default_result(self) -> Dict:
        return {
            "success": False,
            "error": "无法分析",
            "skin_tone": "自然色",
            "undertone": "中性色调",
            "hand_shape": "普通",
            "recommended_colors": ["裸粉色", "豆沙色", "奶茶色"],
            "confidence": 0.5,
            "description": "使用默认推荐"
        }
    
    def _build_description(self, result: Dict) -> str:
        """根据结构化分析结果生成自然语言描述"""
        skin_tone  = result.get("skin_tone", "自然色")
        hand_shape = result.get("hand_shape", "普通")
        colors     = result.get("recommended_colors", [])
        undertone  = result.get("undertone", "中性色调")

        shape_map = {"修长": "手型修长纤细，气质优雅", "偏宽": "手型偏宽，饱满圆润", "普通": "手型匀称自然"}
        tone_map  = {"暖白色": "暖白肤色", "自然色": "自然肤色", "小麦色": "小麦肤色", "健康棕": "健康棕肤色"}

        shape_desc = shape_map.get(hand_shape, "手型匀称")
        tone_desc  = tone_map.get(skin_tone, skin_tone)
        color_list = "、".join(colors[:3]) if colors else "裸粉色"

        return f"{shape_desc}，{tone_desc}搭配{color_list}系美甲效果极佳，非常显手白，特别推荐尝试！"

    def _compress_image(self, image_data: bytes, max_width: int = 640) -> bytes:
        """压缩图像以减少显存占用"""
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return image_data

            h, w = img.shape[:2]
            if w > max_width:
                ratio = max_width / w
                new_h = int(h * ratio)
                img = cv2.resize(img, (max_width, new_h), interpolation=cv2.INTER_AREA)

            # 压缩为 JPEG
            _, compressed = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return compressed.tobytes()
        except Exception as e:
            print(f"图像压缩失败: {e}，使用原始图像")
            return image_data

    def _try_llm_model(self, model_name: str, image_data: bytes) -> Optional[Dict]:
        try:
            # 压缩图像以减少显存占用（320px 防止显存溢出）
            compressed_data = self._compress_image(image_data, max_width=320)
            image_base64 = base64.b64encode(compressed_data).decode('utf-8')

            prompt = """Look at this hand photo. Reply with ONLY a JSON object, no explanation.

{"skin_tone":"X","undertone":"Y","hand_shape":"Z","recommended_colors":["color1","color2","color3"],"confidence":0.0}

Rules:
- skin_tone: one of [暖白色, 自然色, 小麦色, 健康棕]
- undertone: one of [冷色调, 暖色调, 中性色调]
- hand_shape: one of [修长, 普通, 偏宽]
- recommended_colors: 3-5 nail polish color names in Chinese
- confidence: float between 0.0 and 1.0
- Output ONLY the JSON object, no other text"""
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_base64]
                    }
                ],
                "stream": False
            }
            
            response = requests.post(
                "http://localhost:11434/api/chat",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get('message', {}).get('content', '')
                
                try:
                    result = json.loads(content)
                    result["success"] = True
                    result["model_used"] = model_name
                    # 始终用结构化数据生成 description，不依赖 LLM 输出
                    result["description"] = self._build_description(result)
                    return result
                except json.JSONDecodeError:
                    return self._parse_fallback(content, model_name)
            else:
                print("Model " + model_name + " failed with status: " + str(response.status_code))
                return None
                
        except Exception as e:
            print("Model " + model_name + " failed: " + str(e))
            return None
    
    def analyze_hand(self, image_data: bytes) -> Dict:
        image_hash = self.generate_image_hash(image_data)

        if image_hash in self.cache:
            print("Using cached result")
            return self.cache[image_hash]
        
        result = None
        
        for model_name in self.available_models:
            print("Trying model: " + model_name)
            result = self._try_llm_model(model_name, image_data)
            if result:
                break
        
        if not result:
            print("All models failed, using color-based analysis")
            result = self._analyze_color_based(image_data)
        
        self.cache[image_hash] = result
        return result
    
    def _parse_fallback(self, content: str, model_name: str = "") -> Dict:
        import re
        
        skin_tone = "自然色"
        undertone = "中性色调"
        hand_shape = "普通"
        colors = ["裸粉色", "豆沙色", "奶茶色"]
        
        if "暖白" in content or "白皙" in content:
            skin_tone = "暖白色"
        elif "小麦" in content or "健康" in content:
            skin_tone = "小麦色"
        elif "深" in content or "棕" in content:
            skin_tone = "健康棕"
        
        if "冷" in content:
            undertone = "冷色调"
        elif "暖" in content:
            undertone = "暖色调"
        
        if "修长" in content:
            hand_shape = "修长"
        elif "宽" in content:
            hand_shape = "偏宽"
        
        color_pattern = r'([\u4e00-\u9fa5]+色)'
        found_colors = re.findall(color_pattern, content)
        if found_colors:
            colors = found_colors[:5]
        
        # 根据提取的信息生成自然语言描述
        shape_desc = {"修长": "手型修长纤细，", "偏宽": "手型偏宽，", "普通": "手型匀称，"}.get(hand_shape, "")
        tone_desc = {"暖白色": "暖白肤色搭配", "自然色": "自然肤色搭配", "小麦色": "小麦肤色搭配", "健康棕": "健康棕肤色搭配"}.get(skin_tone, "肤色搭配")
        color_tip = colors[0] if colors else "裸粉色"
        description = f"{shape_desc}{tone_desc}{color_tip}系美甲效果极佳，推荐尝试{'、'.join(colors[:3])}。"

        return {
            "success": True,
            "skin_tone": skin_tone,
            "undertone": undertone,
            "hand_shape": hand_shape,
            "recommended_colors": colors,
            "confidence": 0.75,
            "description": description
        }
    
    def clear_cache(self):
        self.cache.clear()
        print("Cache cleared")
    
    def get_cache_size(self) -> int:
        return len(self.cache)
    
    def get_available_models(self) -> List[str]:
        return self.available_models

def analyze_hand_image(image_path: str) -> Dict:
    client = LLMClient()
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return client.analyze_hand(image_data)
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_hand_base64(base64_image: str) -> Dict:
    client = LLMClient()
    try:
        image_data = base64.b64decode(base64_image)
        return client.analyze_hand(image_data)
    except Exception as e:
        return {"success": False, "error": str(e)}
