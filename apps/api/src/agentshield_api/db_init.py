from __future__ import annotations

import asyncio
import os

from sqlalchemy import text

from .db import engine


async def check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    print(asyncio.run(check_database()))
