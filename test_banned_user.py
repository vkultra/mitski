#!/usr/bin/env python
"""Test that banned user messages are ignored"""

import asyncio
import time

import httpx


async def test_banned_user():
    """Send message from banned user 2001"""
    webhook_url = "http://localhost:8000/webhook/1"

    print("🔍 Testing banned user blocking...")
    print("User 2001 was banned for FLOOD violation")
    print("Sending a message from banned user 2001...")

    update = {
        "update_id": int(time.time() * 1000000),
        "message": {
            "message_id": int(time.time() * 1000),
            "date": int(time.time()),
            "chat": {"id": 123456789, "type": "private"},
            "from": {
                "id": 2001,
                "is_bot": False,
                "first_name": "Banned User",
                "username": "banneduser",
            },
            "text": "This message should be ignored",
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=update, timeout=2.0)
        print(f"  Response: Status {response.status_code}")

    print("\n✅ Test completed!")
    print("Check logs to verify message was ignored:")
    print("  docker-compose logs --tail=20 worker | grep 'Blocked user'")


if __name__ == "__main__":
    asyncio.run(test_banned_user())
