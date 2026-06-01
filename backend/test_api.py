import requests
import json

BASE_URL = "http://localhost:8000"

print("=== 测试后端API ===")

# 1. 测试健康检查
print("\n1. 测试健康检查接口")
try:
    response = requests.get(f"{BASE_URL}/")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.json()}")
except Exception as e:
    print(f"   错误: {e}")

# 2. 测试设计库
print("\n2. 测试设计库接口")
try:
    response = requests.get(f"{BASE_URL}/api/designs")
    print(f"   状态码: {response.status_code}")
    data = response.json()
    designs = data.get('designs', [])
    print(f"   设计数量: {len(designs)}")
    if designs:
        print(f"   第一个设计: {designs[0]['name']} (ID: {designs[0]['id']})")
except Exception as e:
    print(f"   错误: {e}")

# 3. 测试手部检测
print("\n3. 测试手部检测接口")
try:
    with open(r"D:\指上谈兵\手图\3cd4bc446f321574df68ce0a749b16b62603765.webp", "rb") as f:
        files = {"image": f}
        response = requests.post(f"{BASE_URL}/api/detect-hands", files=files)
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   检测成功: {data.get('success')}")
    print(f"   手数量: {data.get('num_hands', 0)}")
    if data.get('hands'):
        print(f"   第一个手的关键点数量: {len(data['hands'][0]['landmarks'])}")
except Exception as e:
    print(f"   错误: {e}")

# 4. 测试AI试戴
print("\n4. 测试AI试戴接口")
try:
    with open(r"D:\指上谈兵\手图\3cd4bc446f321574df68ce0a749b16b62603765.webp", "rb") as f:
        files = {"image": f}
        data = {"design_id": "design_001"}
        response = requests.post(f"{BASE_URL}/api/try-on", files=files, data=data)
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   试戴成功: {data.get('success')}")
    print(f"   消息: {data.get('message')}")
    design = data.get('design')
    if design:
        print(f"   使用设计: {design.get('name')}")
    analysis = data.get('analysis')
    if analysis:
        print(f"   肤色分析: {analysis.get('skin_tone')}")
        print(f"   推荐颜色: {analysis.get('recommended_colors')}")
    if data.get('image_base64'):
        print(f"   返回图片大小: {len(data['image_base64'])} 字节")
except Exception as e:
    print(f"   错误: {e}")

# 5. 测试数据分析
print("\n5. 测试数据分析接口")
try:
    response = requests.get(f"{BASE_URL}/api/analytics")
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   总试戴次数: {data.get('total_try_ons')}")
    print(f"   总分析次数: {data.get('total_analyzes')}")
    print(f"   今日试戴: {data.get('today_try_ons')}")
except Exception as e:
    print(f"   错误: {e}")

print("\n=== 测试完成 ===")