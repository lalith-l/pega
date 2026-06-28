import asyncio
from db import AsyncSessionLocal
from routers.court import _do_compile

async def run():
    async with AsyncSessionLocal() as db:
        await _do_compile("06f4e7e4-d303-4d6c-b257-1818e1d8dee0", db)

asyncio.run(run())
