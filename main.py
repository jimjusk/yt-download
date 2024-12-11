from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import yt_dlp
import json
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 初始化必要的目录结构
def init_directories():
    # 创建下载目录
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    # 创建模板目录
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    # 创建空的video_info.json如果不存在
    if not Path("video_info.json").exists():
        with open("video_info.json", "w") as f:
            f.write("")

# 确保在应用启动前创建目录
init_directories()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# 定义下载目录常量
DOWNLOAD_DIR = Path("downloads")

# 存储下载任务状态
download_tasks = {}

def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

async def download_video(url: str, websocket: WebSocket):
    def progress_hook(d):
        if d['status'] == 'downloading':
            progress = {
                'status': 'downloading',
                'percentage': d.get('_percent_str', '0%'),
                'speed': d.get('_speed_str', 'N/A'),
                'eta': d.get('_eta_str', 'N/A')
            }
            asyncio.create_task(websocket.send_json(progress))
        elif d['status'] == 'finished':
            progress = {'status': 'finished'}
            asyncio.create_task(websocket.send_json(progress))

    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
        'format_sort': [
            'res:720',
            'ext:mp4:m4a',
            'codec:h264:aac',
        ],
        'prefer_free_formats': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_info = {
                'title': info['title'],
                'duration': str(datetime.fromtimestamp(info['duration']).strftime('%H:%M:%S')),
                'uploader': info['uploader'],
                'description': info['description'],
                'filename': ydl.prepare_filename(info),
                'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存视频信息到JSON文件
            with open('video_info.json', 'a+') as f:
                json.dump(video_info, f)
                f.write('\n')
                
            return video_info
    except Exception as e:
        await websocket.send_json({'status': 'error', 'message': str(e)})
        raise e

@app.get("/")
async def home(request: Request):
    # 读取已下载视频列表
    videos = []
    if os.path.exists('video_info.json'):
        with open('video_info.json', 'r') as f:
            for line in f:
                if line.strip():
                    videos.append(json.loads(line))
    
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "videos": videos}
    )

@app.websocket("/ws/download")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            url = await websocket.receive_text()
            video_info = await download_video(url, websocket)
            await websocket.send_json({
                'status': 'complete',
                'video_info': video_info
            })
    except Exception as e:
        await websocket.send_json({
            'status': 'error',
            'message': str(e)
        })
    finally:
        await websocket.close() 