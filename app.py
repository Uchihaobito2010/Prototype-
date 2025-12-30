from flask import Flask, request, jsonify, render_template, send_file, abort
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import json
import os
import tempfile
import requests
from io import BytesIO

from config import Config
from utils.downloader import InstagramDownloader

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

downloader = InstagramDownloader()

# Rate limiting dictionary (for simple in-memory rate limiting)
request_counts = {}

def check_rate_limit(ip):
    """Simple rate limiting"""
    from datetime import datetime, timedelta
    import time
    
    current_time = time.time()
    if ip not in request_counts:
        request_counts[ip] = {'count': 1, 'timestamp': current_time}
        return True
    
    # Reset counter if more than 1 hour has passed
    if current_time - request_counts[ip]['timestamp'] > 3600:
        request_counts[ip] = {'count': 1, 'timestamp': current_time}
        return True
    
    # Check if limit exceeded (100 requests per hour)
    if request_counts[ip]['count'] >= 100:
        return False
    
    request_counts[ip]['count'] += 1
    return True

@app.before_request
def before_request():
    # Skip rate limiting for health check
    if request.path == '/health':
        return
    
    ip = request.remote_addr
    if not check_rate_limit(ip):
        return jsonify({
            "status": "error",
            "message": "Rate limit exceeded. Please try again later."
        }), 429

@app.route('/')
def index():
    """Serve API documentation"""
    return render_template('index.html') if os.path.exists('templates/index.html') else jsonify({
        "api": "Instagram Downloader API",
        "version": "1.0.0",
        "endpoints": {
            "/download": "Download any Instagram media (auto-detect)",
            "/download/reel": "Download Instagram Reel",
            "/download/story": "Download Instagram Story",
            "/download/post": "Download Instagram Post",
            "/download/igtv": "Download Instagram IGTV",
            "/info": "Get media info without downloading",
            "/health": "Health check endpoint"
        },
        "usage": "Send POST request with JSON: {'url': 'instagram_url'}"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "instagram-downloader-api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/download', methods=['POST'])
def download_all():
    """Download any Instagram media (auto-detect type)"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "status": "error",
                "message": "Please provide 'url' in JSON body"
            }), 400
        
        url = downloader.sanitize_url(data['url'])
        if not url:
            return jsonify({
                "status": "error",
                "message": "Invalid Instagram URL"
            }), 400
        
        result = downloader.get_all(url)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/download/<media_type>', methods=['POST'])
def download_specific(media_type):
    """Download specific media type"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "status": "error",
                "message": "Please provide 'url' in JSON body"
            }), 400
        
        url = downloader.sanitize_url(data['url'])
        if not url:
            return jsonify({
                "status": "error",
                "message": "Invalid Instagram URL"
            }), 400
        
        media_type = media_type.lower()
        
        if media_type == 'reel':
            result = downloader.get_reel(url)
        elif media_type == 'story':
            result = downloader.get_story(url)
        elif media_type == 'post':
            result = downloader.get_post(url)
        elif media_type == 'igtv':
            result = downloader.get_igtv(url)
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid media type. Use: reel, story, post, or igtv"
            }), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/info', methods=['POST'])
def get_info():
    """Get media information without downloading"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "status": "error",
                "message": "Please provide 'url' in JSON body"
            }), 400
        
        url = downloader.sanitize_url(data['url'])
        if not url:
            return jsonify({
                "status": "error",
                "message": "Invalid Instagram URL"
            }), 400
        
        # Get media info
        result = downloader.get_all(url)
        
        if result['status'] == 'success':
            info = {
                "status": "success",
                "url": url,
                "media_type": downloader.get_media_type(url),
                "media_count": result.get('count', 0),
                "media_items": result.get('media', []),
                "metadata": result.get('metadata', {})
            }
            return jsonify(info)
        else:
            return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.route('/proxy', methods=['GET'])
def proxy_download():
    """Proxy download endpoint (direct download through API)"""
    try:
        media_url = request.args.get('url')
        
        if not media_url:
            return jsonify({
                "status": "error",
                "message": "Please provide 'url' parameter"
            }), 400
        
        # Validate it's a media URL
        if not any(ext in media_url.lower() for ext in ['.mp4', '.jpg', '.jpeg', '.png']):
            return jsonify({
                "status": "error",
                "message": "Invalid media URL"
            }), 400
        
        # Download the media
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(media_url, headers=headers, stream=True, timeout=30)
        
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": f"Failed to download media: {response.status_code}"
            }), 500
        
        # Determine content type
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        # Send the file
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=media_url.split('/')[-1],
            mimetype=content_type
        )
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "Endpoint not found"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "message": "Method not allowed"
    }), 405

if __name__ == '__main__':
    from datetime import datetime
    app.run(host='0.0.0.0', port=5000, debug=True)
