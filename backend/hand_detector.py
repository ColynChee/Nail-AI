import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class HandDetector:
    def __init__(self, static_image_mode: bool = True, max_num_hands: int = 2):
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=max_num_hands
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
    
    def detect(self, image: np.ndarray) -> Dict:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        
        detection_result = self.detector.detect(mp_image)
        
        hands_data = []
        if detection_result.hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(detection_result.hand_landmarks):
                landmarks = []
                for idx, landmark in enumerate(hand_landmarks):
                    landmarks.append({
                        "id": idx,
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z
                    })
                
                if detection_result.handedness and hand_idx < len(detection_result.handedness):
                    hand_label = detection_result.handedness[hand_idx][0].category_name
                else:
                    hand_label = "Left" if hand_idx % 2 == 0 else "Right"
                
                hands_data.append({
                    "hand_index": hand_idx,
                    "hand_label": hand_label,
                    "landmarks": landmarks
                })
        
        return {
            "success": len(hands_data) > 0,
            "num_hands": len(hands_data),
            "hands": hands_data
        }
    
    def get_nail_tips(self, landmarks: List[Dict]) -> List[Dict]:
        nail_tip_indices = [4, 8, 12, 16, 20]
        return [landmarks[idx] for idx in nail_tip_indices]
    
    def get_bounding_box(self, landmarks: List[Dict], image_shape: Tuple[int, int]) -> Dict:
        xs = [lm['x'] for lm in landmarks]
        ys = [lm['y'] for lm in landmarks]
        
        h, w = image_shape[:2]
        return {
            "x_min": int(min(xs) * w),
            "y_min": int(min(ys) * h),
            "x_max": int(max(xs) * w),
            "y_max": int(max(ys) * h),
            "width": int((max(xs) - min(xs)) * w),
            "height": int((max(ys) - min(ys)) * h)
        }
    
    def close(self):
        self.detector.close()

# 全局 HandDetector 实例（避免重复加载模型）
_global_detector = None

def get_detector() -> HandDetector:
    """获取全局 HandDetector 实例"""
    global _global_detector
    if _global_detector is None:
        _global_detector = HandDetector()
    return _global_detector

def detect_hands_from_image(image_path: str) -> Dict:
    detector = get_detector()
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"success": False, "error": "无法读取图片"}

        result = detector.detect(image)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

def detect_hands_from_array(image_array: np.ndarray) -> Dict:
    detector = get_detector()
    try:
        result = detector.detect(image_array)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}