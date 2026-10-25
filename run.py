"""Start PhysioTeam: python run.py  ->  http://127.0.0.1:8000"""

import os
import sys
import threading
import webbrowser

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    if host == "127.0.0.1" and not os.getenv("NO_BROWSER") and "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")
