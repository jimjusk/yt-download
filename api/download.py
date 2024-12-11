from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
import yt_dlp
import os
from typing import Optional

router = APIRouter()

@router.post("/download")
async def download_video(url: str = Body(..., embed=True)):
    try:
        ydl_opts = {
            'format': 'best[height<=720]',
            'quiet': True,
            'no_warnings': True,
            'extract_info_only': True  # 只获取信息,不下载
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'status': 'success',
                'video_info': {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', ''),
                    'uploader': info.get('uploader', ''),
                    'description': info.get('description', ''),
                    'formats': [
                        {
                            'format_id': f['format_id'],
                            'ext': f['ext'],
                            'resolution': f.get('resolution', 'unknown'),
                            'filesize': f.get('filesize', 0),
                            'url': f['url']
                        }
                        for f in info['formats']
                        if f.get('url')
                    ]
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 