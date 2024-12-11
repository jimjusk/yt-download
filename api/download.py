from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
import yt_dlp
import os
from typing import Optional
import logging
from time import sleep

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def extract_with_retry(ydl, url, max_retries=3):
    """添加重试机制的视频信息提取"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} of {max_retries}")
            return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt + 1 < max_retries:
                sleep(1)  # 在重试之前等待1秒
            else:
                raise

@router.post("/download")
async def download_video(url: str = Body(..., embed=True)):
    try:
        logger.info(f"Received download request for URL: {url}")
        
        ydl_opts = {
            # 基本选项
            'format': 'best[height<=720]/worst',  # 更保守的格式选择
            'quiet': False,
            'no_warnings': False,
            'extract_info_only': True,
            
            # 连接选项
            'socket_timeout': 30,
            'retries': 3,
            
            # 绕过限制选项
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'no_color': True,
            'noprogress': True,
            'prefer_insecure': True,
            'legacy_server_connect': True,
            
            # 浏览器模拟
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
            },
            
            # 额外选项
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],  # 跳过某些格式以提高成功率
                }
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Starting video info extraction with retry mechanism...")
                info = extract_with_retry(ydl, url)
                
                if not info:
                    logger.error("Failed to extract video info - no info returned")
                    raise HTTPException(status_code=400, detail="Failed to extract video info - no data available")
                
                logger.info("Successfully extracted video info")
                logger.info(f"Video title: {info.get('title', 'Unknown')}")
                
                formats = []
                available_formats = info.get('formats', [])
                logger.info(f"Found {len(available_formats)} available formats")
                
                for f in available_formats:
                    if f.get('url'):
                        format_info = {
                            'format_id': f.get('format_id', 'N/A'),
                            'ext': f.get('ext', 'N/A'),
                            'resolution': f.get('resolution', 'unknown'),
                            'filesize': f.get('filesize', 0),
                            'url': f.get('url', '')
                        }
                        formats.append(format_info)
                        logger.info(f"Added format: {format_info['resolution']} - {format_info['ext']}")
                
                if not formats:
                    logger.error("No valid formats found")
                    raise HTTPException(status_code=400, detail="No valid download formats available")
                
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
            error_message = str(e)
            logger.error(f"yt-dlp download error: {error_message}")
            if "Sign in to confirm your age" in error_message:
                raise HTTPException(status_code=400, detail="Age-restricted video - cannot download")
            elif "Private video" in error_message:
                raise HTTPException(status_code=400, detail="This video is private")
            else:
                raise HTTPException(status_code=400, detail=f"Download error: {error_message}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") 