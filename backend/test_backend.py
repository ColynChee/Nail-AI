#!/usr/bin/env python
"""后端快速测试脚本"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_health_check():
    """测试服务健康状态"""
    print("\n1️⃣ 测试服务健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("  ✅ 服务运行正常")
            print(f"     {response.json()}")
            return True
        else:
            print(f"  ❌ 服务响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 无法连接到服务: {e}")
        print(f"     请确保后端已启动: python main.py")
        return False

def test_get_designs():
    """测试获取设计库"""
    print("\n2️⃣ 测试获取美甲设计...")
    try:
        response = requests.get(f"{BASE_URL}/api/designs", timeout=5)
        if response.status_code == 200:
            data = response.json()
            num_designs = len(data.get('designs', []))
            print(f"  ✅ 成功获取 {num_designs} 个美甲设计")
            if num_designs > 0:
                print(f"     第一个设计: {data['designs'][0]['name']}")
            return True
        else:
            print(f"  ❌ 获取设计失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False

def test_hand_detection():
    """测试手部检测"""
    print("\n3️⃣ 测试手部检测...")

    # 查找测试图片
    test_image_paths = [
        Path("../手图").glob("*.webp"),
        Path("../手图").glob("*.jpg"),
        Path("../手图").glob("*.png"),
    ]

    test_image = None
    for pattern in test_image_paths:
        images = list(pattern)
        if images:
            test_image = images[0]
            break

    if not test_image:
        print("  ⚠️ 未找到测试图片，跳过此测试")
        return None

    try:
        with open(test_image, 'rb') as f:
            files = {'image': f}
            response = requests.post(f"{BASE_URL}/api/detect-hands", files=files, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                num_hands = data.get('num_hands', 0)
                print(f"  ✅ 检测成功，识别到 {num_hands} 只手")
                if num_hands > 0:
                    landmarks = data['hands'][0]['landmarks']
                    print(f"     获得 {len(landmarks)} 个关键点")
                    return True
            else:
                print(f"  ⚠️ {data.get('message', '检测失败')}")
                return False
        else:
            print(f"  ❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False

def test_hand_analysis():
    """测试手部分析"""
    print("\n4️⃣ 测试手部分析（肤色识别）...")

    # 查找测试图片
    test_image = None
    for pattern_dir in ["../手图"]:
        images = list(Path(pattern_dir).glob("*.webp"))
        if images:
            test_image = images[0]
            break

    if not test_image:
        print("  ⚠️ 未找到测试图片，跳过此测试")
        return None

    try:
        with open(test_image, 'rb') as f:
            files = {'image': f}
            response = requests.post(f"{BASE_URL}/api/analyze-hand", files=files, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  ✅ 分析成功")
                print(f"     肤色: {data.get('skin_tone')}")
                print(f"     基调: {data.get('undertone')}")
                print(f"     推荐颜色: {', '.join(data.get('recommended_colors', []))}")
                print(f"     置信度: {data.get('confidence')}")
                return True
            else:
                print(f"  ⚠️ {data.get('message', '分析失败')}")
                return False
        else:
            print(f"  ❌ 请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 后端 API 测试")
    print("=" * 60)

    # 健康检查必须通过
    if not test_health_check():
        print("\n❌ 后端服务未启动，请先运行: python main.py")
        return

    results = {
        "health": True,
        "designs": test_get_designs(),
        "detection": test_hand_detection(),
        "analysis": test_hand_analysis(),
    }

    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    total = len(results)

    print(f"\n✅ 通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！后端已就绪。")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息。")

if __name__ == "__main__":
    main()
