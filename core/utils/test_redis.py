import asyncio
from backend.core.utils.redis import RedisClient

async def test_redis_connection():
    try:
        redis = await RedisClient.get_redis()
        response = await redis.ping()
        print(f"Redis connection successful! Response: {response}")
    except Exception as e:
        print(f"Redis connection failed: {str(e)}")
    finally:
        await RedisClient.close_redis()

if __name__ == "__main__":
    asyncio.run(test_redis_connection())
