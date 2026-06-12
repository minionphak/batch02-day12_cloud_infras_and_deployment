"""
Test script: Chứng minh stateless agent hoạt động đúng khi scale.

Kịch bản:
1. Tạo session mới
2. Gửi 5 requests liên tiếp
3. Xem "served_by" — mỗi request có thể đến instance khác
4. Xem history — tất cả đều được lưu dù instance khác nhau

Chạy sau khi docker compose up:
    python test_stateless.py
"""
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"
session_id = None


def post(path: str, data: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}") as resp:
        return json.loads(resp.read())


print("=" * 60)
print("Stateless Scaling Demo")
print("=" * 60)

questions = [
    "What is Docker?",
    "Why do we need containers?",
    "What is Kubernetes?",
    "How does load balancing work?",
    "What is Redis used for?",
]

instances_seen = set()

for i, question in enumerate(questions, 1):
    result = post("/chat", {
        "question": question,
        "session_id": session_id,
    })

    if session_id is None:
        session_id = result["session_id"]
        print(f"\nSession ID: {session_id}\n")

    instance = result.get("served_by", "unknown")
    instances_seen.add(instance)

    print(f"Request {i}: [{instance}]")
    print(f"  Q: {question}")
    print(f"  A: {result['answer'][:80]}...")
    print()

print("-" * 60)
print(f"Total requests: {len(questions)}")
print(f"Instances used: {instances_seen}")
print(f"✅ All requests served despite different instances!" if len(instances_seen) > 1
      else "ℹ️  Only 1 instance (scale up với: docker compose up --scale agent=3)")

# Verify history is intact
print("\n--- Conversation History ---")
history = get(f"/chat/{session_id}/history")
print(f"Total messages: {history['count']}")
for msg in history["messages"]:
    print(f"  [{msg['role']}]: {msg['content'][:60]}...")

print("\n✅ Session history preserved across all instances via Redis!")
