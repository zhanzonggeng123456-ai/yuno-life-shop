"""一条命令启动: python run.py (或 ./start.sh)。
默认 http://127.0.0.1:8000,货币 JPY,时区 Asia/Tokyo(代码内)。
环境变量: YUNO_DB_PATH / YUNO_UPLOAD_DIR / YUNO_HOST / YUNO_PORT。
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=os.environ.get("YUNO_HOST", "127.0.0.1"),
                port=int(os.environ.get("YUNO_PORT", "8000")), reload=False)
