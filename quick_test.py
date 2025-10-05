#!/usr/bin/env python
"""Quick test to verify anti-spam is working"""

import asyncio
import time

import httpx


async def test_flood():
    """Send multiple messages quickly to trigger flood detection"""
    webhook_url = "http://localhost:8000/webhook/1"

    print("🔍 Testing flood detection...")
    print("Sending 10 messages rapidly to trigger ban...")

    for i in range(10):
        update = {
            "update_id": int(time.time() * 1000000) + i,
            "message": {
                "message_id": int(time.time() * 1000) + i,
                "date": int(time.time()),
                "chat": {"id": 123456789, "type": "private"},
                "from": {
                    "id": 2001,
                    "is_bot": False,
                    "first_name": "Flood Tester",
                    "username": "floodtest",
                },
                "text": f"Test message {i}",
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(webhook_url, json=update, timeout=2.0)
                print(f"  Message {i+1}: Status {response.status_code}")
            except Exception as e:
                print(f"  Message {i+1}: Error - {e}")

        await asyncio.sleep(0.1)  # 100ms between messages

    print("\n✅ Test completed! Check logs for ban:")
    print("  docker-compose logs --tail=50 worker-bans | grep 'User 2001'")
    print("  docker-compose logs --tail=50 worker | grep 'Anti-spam violation'")


if __name__ == "__main__":
    asyncio.run(test_flood())
