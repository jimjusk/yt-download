from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
import yt_dlp
import os
from typing import Optional
import logging
from time import sleep
import random

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def extract_with_retry(ydl, url, max_retries=3):
    """添加重试机制的视频信息提取"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} of {max_retries}")
            return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt + 1 < max_retries:
                sleep(2)  # 在重试之前等待2秒
                # 更新User-Agent
                ydl.params['http_headers']['User-Agent'] = get_random_user_agent()
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
            
            # 连接选项
            'socket_timeout': 15,
            'retries': 5,
            
            # 绕过限制选项
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
            'noprogress': True,
            'prefer_insecure': True,
            
            # 浏览器模拟
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'DNT': '1',
            },
            
            # 地理位置选项
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            
            # 额外选项
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage', 'configs'],
                    'skip': ['dash', 'hls'],
                }
            },
            
            # 调试选项
            'verbose': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Starting video info extraction with retry mechanism...")
                info = extract_with_retry(ydl, url)
                
                if not info:
                    logger.error("Failed to extract video info - no info returned")
                    raise HTTPException(
                        status_code=400, 
                        detail="无法获取视频信息 - 请检查视频URL是否正确"
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
                        detail="没有找到可用的下载格式"
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
                raise HTTPException(status_code=400, detail="���法下载年龄限制视频")
            elif "Private video" in error_message:
                raise HTTPException(status_code=400, detail="无法访问私密视频")
            elif "Video unavailable" in error_message:
                raise HTTPException(status_code=400, detail="视频不可用或已被删除")
            elif "Sign in to confirm you're not a bot" in error_message:
                raise HTTPException(status_code=400, detail="YouTube检测到机器人访问，请稍后再试")
            else:
                raise HTTPException(status_code=400, detail=f"下载错误: {error_message}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"服务器错误: {str(e)}\n请稍后重试"
        ) 