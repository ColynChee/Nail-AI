from llm_client import LLMClient

# 读取手图片
with open(r"D:\指上谈兵\手图\3cd4bc446f321574df68ce0a749b16b62603765.webp", "rb") as f:
    image_data = f.read()

print("=== 测试肤色分析 ===")
print(f"图片大小: {len(image_data)} 字节")

client = LLMClient()
result = client.analyze_hand(image_data)

print("\n分析结果:")
print(f"成功: {result.get('success')}")
print(f"肤色: {result.get('skin_tone')}")
print(f"基调: {result.get('undertone')}")
print(f"手型: {result.get('hand_shape')}")
print(f"推荐颜色: {result.get('recommended_colors')}")
print(f"置信度: {result.get('confidence')}")
print(f"描述: {result.get('description')}")
print(f"错误: {result.get('error')}")