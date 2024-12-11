from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import json
import os
from pathlib import Path

app = FastAPI()

# 添加错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)},
    )

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 使用相对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 简单的首页路由
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "videos": []}
    )

# WebSocket 路由
@app.websocket("/ws/download")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            url = await websocket.receive_text()
            try:
                # 简化的下载选项
                ydl_opts = {
                    'format': 'best[height<=720]',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    await websocket.send_json({
                        'status': 'complete',
                        'video_info': {
                            'title': info.get('title', ''),
                            'duration': info.get('duration', ''),
                            'uploader': info.get('uploader', ''),
                            'description': info.get('description', '')
                        }
                    })
            except Exception as e:
                await websocket.send_json({
                    'status': 'error',
                    'message': str(e)
                })
    except Exception as e:
        if not websocket.client_state.DISCONNECTED:
            await websocket.send_json({
                'status': 'error',
                'message': str(e)
            })
    finally:
        if not websocket.client_state.DISCONNECTED:
            await websocket.close() 