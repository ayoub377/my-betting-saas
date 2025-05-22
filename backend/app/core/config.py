from fastapi import Depends, HTTPException,Request
import redis.asyncio as redis

from app.core.auth import get_current_user
import os

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


async def rate_limit(uid: str, endpoint: str, max_requests: int, reset_duration: int = 86400):
    redis_key = f"rate_limit:{uid}:{endpoint}"

    # Await the asynchronous Redis `get` call
    request_count = await redis_client.get(redis_key)

    if request_count is None:
        # Initialize the count if it doesn't exist
        await redis_client.set(redis_key, 1, ex=reset_duration)
    else:
        # Convert the request count to an integer
        request_count = int(request_count)
        if request_count >= max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        # Increment the request count
        await redis_client.incr(redis_key)


async def rate_limit_dependency(
    request: Request,  # Access request details
    uid: str = "default_user",  # Replace this with actual user info
    max_requests: int = 5,  # Maximum requests allowed
):
    endpoint = request.url.path  # Get the current endpoint path
    await rate_limit(uid, endpoint, max_requests)