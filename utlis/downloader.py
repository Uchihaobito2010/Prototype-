import requests
import html
import re
from bs4 import BeautifulSoup
from user_agent import generate_user_agent
from urllib.parse import urlparse, parse_qs

class InstagramDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": generate_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    
    def sanitize_url(self, url):
        """Clean and validate Instagram URL"""
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        
        # Validate it's an Instagram URL
        patterns = [
            r'https?://(www\.)?instagram\.com/(p|reel|reels|stories|story|tv)/[A-Za-z0-9_-]+/?',
            r'https?://(www\.)?instagram\.com/[A-Za-z0-9_.]+/?(?:\?.*)?'
        ]
        
        for pattern in patterns:
            if re.match(pattern, url):
                return url.strip()
        return None
    
    def get_media_type(self, url):
        """Determine media type from URL"""
        if '/reel/' in url or '/reels/' in url:
            return 'reel'
        elif '/stories/' in url or '/story/' in url:
            return 'story'
        elif '/tv/' in url:
            return 'igtv'
        elif '/p/' in url:
            return 'post'
        else:
            # Try to determine from page content
            return 'unknown'
    
    def download_from_snapdownloader(self, url, downloader_url):
        """Generic method to download from snapdownloader"""
        try:
            target = downloader_url + requests.utils.quote(url, safe="")
            
            headers = {
                "User-Agent": generate_user_agent(),
                "Referer": "https://snapdownloader.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            r = self.session.get(target, headers=headers, timeout=30)
            
            if r.status_code != 200:
                return {"status": "error", "message": f"Failed to load page: {r.status_code}"}
            
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Extract metadata if available
            metadata = {}
            title_elem = soup.select_one('title')
            if title_elem:
                metadata['title'] = title_elem.text.strip()
            
            # Find all download links
            media_items = []
            
            # For videos
            for a in soup.select("a.btn-download, a.download-button, a[href*='.mp4']"):
                href = html.unescape(a.get("href", ""))
                text = a.get_text(strip=True).lower()
                
                if href and ('.mp4' in href or 'video' in text):
                    media_items.append({
                        'url': href,
                        'type': 'video',
                        'quality': self._extract_quality(text),
                        'size': self._extract_size(text)
                    })
            
            # For images
            for a in soup.select("a.btn-download, a.download-button, a[href*='.jpg'], a[href*='.jpeg'], a[href*='.png']"):
                href = html.unescape(a.get("href", ""))
                text = a.get_text(strip=True).lower()
                
                if href and any(ext in href for ext in ['.jpg', '.jpeg', '.png']):
                    media_items.append({
                        'url': href,
                        'type': 'image',
                        'quality': self._extract_quality(text),
                        'size': self._extract_size(text)
                    })
            
            # Alternative method: look for video tags
            for video in soup.select("video source"):
                src = html.unescape(video.get("src", ""))
                if src and '.mp4' in src:
                    media_items.append({
                        'url': src,
                        'type': 'video',
                        'quality': 'unknown',
                        'size': 'unknown'
                    })
            
            # Remove duplicates
            unique_items = []
            seen_urls = set()
            for item in media_items:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_items.append(item)
            
            if unique_items:
                return {
                    "status": "success",
                    "media": unique_items,
                    "metadata": metadata,
                    "count": len(unique_items)
                }
            
            return {"status": "error", "message": "No media found"}
            
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Request timeout"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _extract_quality(self, text):
        """Extract quality from text"""
        qualities = ['hd', 'high', '720p', '1080p', '4k', 'sd', 'low']
        for q in qualities:
            if q in text:
                return q
        return 'standard'
    
    def _extract_size(self, text):
        """Extract size from text"""
        match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|KB|GB)', text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} {match.group(2).upper()}"
        return 'unknown'
    
    def get_reel(self, url):
        """Download Instagram Reel"""
        from config import Config
        return self.download_from_snapdownloader(url, Config.REEL_DOWNLOADER)
    
    def get_story(self, url):
        """Download Instagram Story"""
        from config import Config
        return self.download_from_snapdownloader(url, Config.STORY_DOWNLOADER)
    
    def get_post(self, url):
        """Download Instagram Post"""
        from config import Config
        return self.download_from_snapdownloader(url, Config.POST_DOWNLOADER)
    
    def get_igtv(self, url):
        """Download Instagram IGTV"""
        from config import Config
        return self.download_from_snapdownloader(url, Config.IGTV_DOWNLOADER)
    
    def get_all(self, url):
        """Auto-detect and download any Instagram media"""
        media_type = self.get_media_type(url)
        
        if media_type == 'reel':
            return self.get_reel(url)
        elif media_type == 'story':
            return self.get_story(url)
        elif media_type == 'igtv':
            return self.get_igtv(url)
        elif media_type == 'post':
            return self.get_post(url)
        else:
            # Try all endpoints
            for func in [self.get_reel, self.get_post, self.get_igtv]:
                result = func(url)
                if result['status'] == 'success':
                    return result
            return {"status": "error", "message": "Unable to download media"}
