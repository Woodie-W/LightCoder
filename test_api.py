import requests
import json
import os

# 说明：
# 之前这里强制清空代理环境变量 + session.trust_env=False，
# 在 WSL2 mirrored 模式 + Windows 端 TUN fake-ip 环境下会卡死。
# 原因：api.deepseek.com 被解析成 198.18.0.x fake-ip，
# 而 fake-ip 只有走代理才能被 Clash 还原成真实域名+TLS。
# 所以这里改为尊重系统代理（trust_env=True），让 requests 走 127.0.0.1:7897。
# 如果将来在纯净网络下想强制直连，设置环境变量 FORCE_DIRECT=1 即可。

FORCE_DIRECT = os.getenv("FORCE_DIRECT", "0") == "1"

# --- 请确认以下参数 ---
# BASE_URL = "http://100.104.128.29:1234/v1"
# MODEL_ID = "unsloth/qwen3.5-35b-a3b"
# API_KEY = "lmstudio"

BASE_URL = "https://api.deepseek.com/v1"
MODEL_ID = "deepseek-v4-pro"
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
# --------------------

def test_lm_studio():
    if not API_KEY:
        raise RuntimeError("Set DEEPSEEK_API_KEY before running this connectivity test.")
    print(f"开始测试连接: {BASE_URL}")
    print(f"模式: {'直连 (trust_env=False)' if FORCE_DIRECT else '走系统代理 (trust_env=True)'}")
    print("-" * 30)

    # 创建 Session
    session = requests.Session()
    if FORCE_DIRECT:
        # 仅在显式要求直连时才禁用代理
        session.trust_env = False
        for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
            os.environ.pop(k, None)

    # 1. 测试 /models 接口 (GET)
    print(f"测试 1: 获取模型列表 (/models)...")
    try:
        response = session.get(f"{BASE_URL}/models", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("成功连通！服务器返回的模型列表如下:")
            models = response.json().get('data', [])
            for m in models:
                print(f" - 可用模型 ID: {m['id']}")
        else:
            print(f"连接成功但返回错误: {response.text}")
    except Exception as e:
        print(f"连接失败！错误详情:\n{e}")

    print("-" * 30)

    # 2. 测试聊天接口 (POST)
    print(f"测试 2: 发送对话请求 (/chat/completions)...")
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "你好，请回复'连接成功'"}],
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = session.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            print(f"成功！模型回复: {answer}")
        else:
            print(f"请求失败！返回内容: {response.text}")
    except Exception as e:
        print(f"对话请求发生异常:\n{e}")

if __name__ == "__main__":
    test_lm_studio()
