#!/usr/bin/env python
"""
Test script for anti-spam system
Tests various spam detection scenarios
"""

import asyncio
import time
from datetime import datetime

import httpx

# Configuration
WEBHOOK_URL = "http://localhost:8000/webhook"
BOT_ID = 1  # Adjust based on your bot
CHAT_ID = 123456789  # Test chat ID
USER_ID = 987654321  # Test user ID


async def send_update(text: str, user_id: int = USER_ID):
    """Send a fake Telegram update to webhook"""
    update = {
        "update_id": int(time.time() * 1000000),
        "message": {
            "message_id": int(time.time() * 1000),
            "date": int(time.time()),
            "chat": {"id": CHAT_ID, "type": "private"},
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": f"Test User {user_id}",
                "username": f"testuser{user_id}",
            },
            "text": text,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{WEBHOOK_URL}/{BOT_ID}", json=update, timeout=5.0
        )
        return response.status_code


async def test_dot_after_start():
    """Test: Dot after /start (ban if sends '.' within 60s)"""
    print("\n🔍 Testing: Dot after /start")

    # Send /start
    await send_update("/start", 1001)
    await asyncio.sleep(0.5)

    # Send dot immediately after
    result = await send_update(".", 1001)
    print(f"  ✓ Sent '.' after /start - Response: {result}")
    print("  → User 1001 should be banned for DOT_AFTER_START")


async def test_flood():
    """Test: Flood detection (>8 messages in 10s)"""
    print("\n🔍 Testing: Flood detection")

    # Send 10 messages rapidly
    for i in range(10):
        await send_update(f"Flood message {i}", 1002)
        await asyncio.sleep(0.3)

    print("  ✓ Sent 10 messages in ~3 seconds")
    print("  → User 1002 should be banned for FLOOD")


async def test_repetition():
    """Test: Repetition (3+ identical messages in 30s)"""
    print("\n🔍 Testing: Message repetition")

    # Send same message 4 times
    for i in range(4):
        await send_update("Buy cheap products now!", 1003)
        await asyncio.sleep(2)

    print("  ✓ Sent same message 4 times")
    print("  → User 1003 should be banned for REPETITION")


async def test_links_mentions():
    """Test: Links and mentions (2+ in 60s)"""
    print("\n🔍 Testing: Links and mentions")

    # Send messages with links and mentions
    await send_update("Check out https://example.com", 1004)
    await asyncio.sleep(1)
    await send_update("Visit https://another.site and @username", 1004)
    await asyncio.sleep(1)
    await send_update("More info at @channel and https://link.com", 1004)

    print("  ✓ Sent 3 messages with links and mentions")
    print("  → User 1004 should be banned for LINKS_MENTIONS")


async def test_short_messages():
    """Test: Short messages (5 messages <3 chars)"""
    print("\n🔍 Testing: Short messages spam")

    short_msgs = ["ok", ".", "hi", "no", "1", "!"]
    for msg in short_msgs:
        await send_update(msg, 1005)
        await asyncio.sleep(0.5)

    print(f"  ✓ Sent {len(short_msgs)} short messages")
    print("  → User 1005 should be banned for SHORT_MESSAGES")


async def test_loop_start():
    """Test: Loop /start (3 /starts in 5 min)"""
    print("\n🔍 Testing: /start loop")

    for i in range(4):
        await send_update("/start", 1006)
        await asyncio.sleep(30)  # 30s between each

    print("  ✓ Sent 4 /start commands in ~90 seconds")
    print("  → User 1006 should be banned for LOOP_START")


async def test_total_limit():
    """Test: Total message limit"""
    print("\n🔍 Testing: Total message limit (default 100)")
    print("  ⚠️  This test takes longer - sending 101 messages...")

    for i in range(101):
        await send_update(f"Normal message {i}", 1007)
        await asyncio.sleep(0.5)  # Avoid flood detection

        if i % 20 == 0:
            print(f"    Progress: {i}/101 messages sent")

    print("  ✓ Sent 101 messages")
    print("  → User 1007 should be banned for TOTAL_LIMIT")


async def main():
    print("=" * 50)
    print("🛡️  ANTI-SPAM SYSTEM TEST")
    print("=" * 50)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Bot ID: {BOT_ID}")
    print(f"Test started at: {datetime.now()}")

    # Run tests
    tests = [
        test_dot_after_start,
        test_flood,
        test_repetition,
        test_links_mentions,
        test_short_messages,
        test_loop_start,
        # test_total_limit  # Commented out as it takes long
    ]

    for test in tests:
        await test()
        await asyncio.sleep(2)  # Wait between tests

    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("Check the logs to verify bans were applied correctly:")
    print("  docker-compose logs worker-bans | grep 'banned'")
    print("  docker-compose logs worker | grep 'Anti-spam'")
    print("=" * 50)


if __name__ == "__main__":
    print("\n⚠️  NOTE: Make sure you have:")
    print("  1. A bot registered in the system")
    print("  2. Anti-spam protections enabled for that bot")
    print("  3. Update BOT_ID in this script to match your bot")
    print("\nPress Enter to continue or Ctrl+C to abort...")
    input()

    asyncio.run(main())
