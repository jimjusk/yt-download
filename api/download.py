from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
import yt_dlp
import os
from typing import Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/download")
async def download_video(url: str = Body(..., embed=True)):
    try:
        logger.info(f"Received download request for URL: {url}")
        
        ydl_opts = {
            'format': 'best[height<=720]',
            'quiet': False,  # 启用输出以便调试
            'no_warnings': False,  # 显示警告信息
            'extract_info_only': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'no_color': True,
            'noprogress': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            }
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Extracting video info...")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.error("Failed to extract video info")
                    raise HTTPException(status_code=400, detail="Failed to extract video info")
                
                logger.info("Successfully extracted video info")
                
                formats = []
                for f in info.get('formats', []):
                    if f.get('url'):
                        format_info = {
                            'format_id': f.get('format_id', 'N/A'),
                            'ext': f.get('ext', 'N/A'),
                            'resolution': f.get('resolution', 'unknown'),
                            'filesize': f.get('filesize', 0),
                            'url': f.get('url', '')
                        }
                        formats.append(format_info)
                
                response_data = {
                    'status': 'success',
                    'video_info': {
                        'title': info.get('title', 'Unknown Title'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'Unknown Uploader'),
                        'description': info.get('description', 'No description'),
                        'formats': formats
                    }
                }
                
                logger.info("Returning video info")
                return response_data
                
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Download error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") 