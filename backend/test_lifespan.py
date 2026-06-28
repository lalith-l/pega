import sys
print("1: Importing asyncio...")
import asyncio
print("2: Importing app from main...")
from main import app
print("3: Imported app. Defining test()...")
async def test():
    print("5: Inside test()!")
    try:
        print("6: Calling lifespan_context...")
        async with app.router.lifespan_context(app):
            print("7: Lifespan started successfully!")
    except Exception as e:
        print(f"Error during lifespan: {e}")
print("4: Calling asyncio.run(test())...")
asyncio.run(test())
print("8: Done!")
