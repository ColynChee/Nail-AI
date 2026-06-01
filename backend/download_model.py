import urllib.request
import os

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_PATH = "hand_landmarker.task"

def download_model():
    if os.path.exists(MODEL_PATH):
        print(f"模型文件 {MODEL_PATH} 已存在")
        return True
    
    print(f"正在下载模型文件 {MODEL_URL}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"模型文件下载完成: {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False

if __name__ == "__main__":
    download_model()