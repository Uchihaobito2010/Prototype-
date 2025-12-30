import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    RATE_LIMIT = os.getenv('RATE_LIMIT', '100 per day')
    DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 30))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    
    # Snapdownloader endpoints
    REEL_DOWNLOADER = "https://snapdownloader.com/tools/instagram-reels-downloader/download?url="
    STORY_DOWNLOADER = "https://snapdownloader.com/tools/instagram-story-downloader/download?url="
    POST_DOWNLOADER = "https://snapdownloader.com/tools/instagram-photo-downloader/download?url="
    IGTV_DOWNLOADER = "https://snapdownloader.com/tools/instagram-igtv-downloader/download?url="
    
    ALLOWED_EXTENSIONS = {'mp4', 'jpg', 'jpeg', 'png'}
