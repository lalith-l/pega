import uvicorn
from main import app
print("Starting uvicorn...")
try:
    uvicorn.run(app, host="0.0.0.0", port=8000)
except Exception as e:
    print(f"Exception: {e}")
print("Finished!")
