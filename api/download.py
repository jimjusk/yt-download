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
            # 首先尝试只获取基本信息
            basic_info = ydl.extract_info(url, download=False, process=False)
            if not basic_info:
                raise Exception("No basic info returned")
            
            logger.info(f"Basic info extracted: {basic_info.get('title', 'Unknown')}")
            
            # 然后获取完整信息
            full_info = ydl.extract_info(url, download=False)
            logger.info("Full info extracted successfully")
            return full_info
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {str(e)}")
            if attempt + 1 < max_retries:
                sleep(2)  # 增加重试等待时间
            else:
                raise

@router.post("/download")
async def download_video(url: str = Body(..., embed=True)):
    try:
        logger.info(f"Received download request for URL: {url}")
        
        ydl_opts = {
            # 基本选项
            'format': 'best[height<=720]/bestvideo[height<=720]+bestaudio/best',
            'quiet': False,
            'no_warnings': False,
            'extract_info_only': True,
            
            # 连接选项
            'socket_timeout': 10,
            'retries': 3,
            
            # 绕过限制选项
            'nocheckcertificate': True,
            'ignoreerrors': False,  # 改为False以获取更详细的错误
            'no_color': True,
            'noprogress': True,
            'prefer_insecure': True,
            
            # 浏览器模拟
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            },
            
            # 地理位置选项
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            
            # 调试选项
            'verbose': True,
            'debug_printtraffic': True,
            
            # 格式选项
            'format_sort': ['res:720', 'ext:mp4:m4a'],
            'merge_output_format': 'mp4',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Starting video info extraction with retry mechanism...")
                info = extract_with_retry(ydl, url)
                
                if not info:
                    logger.error("Failed to extract video info - no info returned")
                    raise HTTPException(
                        status_code=400, 
                        detail="Failed to extract video info - please check if the video URL is correct and accessible"
                    )
                
                logger.info(f"Successfully extracted video info for: {info.get('title', 'Unknown')}")
                
                formats = []
                available_formats = info.get('formats', [])
                logger.info(f"Found {len(available_formats)} available formats")
                
                # 过滤和排序格式
                for f in available_formats:
                    if f.get('url') and f.get('ext') in ['mp4', 'webm', 'm4a']:
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
                    logger.error("No valid formats found after filtering")
                    raise HTTPException(
                        status_code=400, 
                        detail="No suitable download formats available for this video"
                    )
                
                # 按分辨率排序
                formats.sort(
                    key=lambda x: int(x['resolution'].split('x')[1]) 
                    if x['resolution'] and 'x' in x['resolution'] 
                    else 0, 
                    reverse=True
                )
                
                response_data = {
                    'status': 'success',
                    'video_info': {
                        'title': info.get('title', 'Unknown Title'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'Unknown Uploader'),
                        'description': info.get('description', 'No description'),
                        'formats': formats[:5]  # 只返回最好的5个格式
                    }
                }
                
                logger.info("Successfully prepared response data")
                return response_data
                
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            logger.error(f"yt-dlp download error: {error_message}")
            if "Sign in to confirm your age" in error_message:
                raise HTTPException(status_code=400, detail="无法下载年龄限制视频")
            elif "Private video" in error_message:
                raise HTTPException(status_code=400, detail="无法访问私密视频")
            elif "Video unavailable" in error_message:
                raise HTTPException(status_code=400, detail="视频不可用或已被删除")
            else:
                raise HTTPException(status_code=400, detail=f"下载错误: {error_message}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"服务器错误: {str(e)}\n请确保视频URL正确且可访问"
        ) 