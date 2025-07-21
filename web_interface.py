from flask import Flask, render_template, request, jsonify, Response, stream_template
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import Levenshtein
import base64
import threading
from enhanced_downloadhub_agent import EnhancedDownloadHubAgent

app = Flask(__name__)

# Global variables for our enhanced backend
search_results = {}
extraction_results = {}
agent = None

def initialize_agent():
    global agent
    if agent is None:
        agent = EnhancedDownloadHubAgent()
    return agent

def clean_text(text):
    """Clean and normalize text for better matching"""
    return ''.join(e for e in text.lower() if e.isalnum() or e.isspace()).strip()

def is_fuzzy_match(input_title, candidate_title, threshold=60):
    """Improved fuzzy matching with lower threshold"""
    input_clean = clean_text(input_title)
    candidate_clean = clean_text(candidate_title)
    
    # Check if input is contained in candidate
    if input_clean in candidate_clean or candidate_clean in input_clean:
        return True
    
    # Use Levenshtein ratio
    ratio = Levenshtein.ratio(input_clean, candidate_clean) * 100
    return ratio >= threshold

def get_rendered_html(url, wait_time=10):
    """Get rendered HTML with improved error handling"""
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, wait_time).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Additional wait for dynamic content
        time.sleep(5)
        
        return driver.page_source, driver.current_url
    except Exception as e:
        print(f"Error loading page {url}: {e}")
        return None, None
    finally:
        if driver:
            driver.quit()

def search_movie_on_site(base_url, movie_name):
    """Search for movie using site's search functionality"""
    search_results = []
    
    # Try different search URL patterns
    search_patterns = [
        f"{base_url}/search?q={quote(movie_name)}",
        f"{base_url}/search/{quote(movie_name)}",
        f"{base_url}/?s={quote(movie_name)}",
        f"{base_url}/movies/search/{quote(movie_name)}",
        f"{base_url}/movie/search?query={quote(movie_name)}"
    ]
    
    for search_url in search_patterns:
        try:
            print(f"Trying search URL: {search_url}")
            html, current_url = get_rendered_html(search_url, wait_time=8)
            if html:
                results = extract_movie_links(html, movie_name, base_url)
                if results:
                    search_results.extend(results)
                    break  # Found results, no need to try other patterns
        except Exception as e:
            print(f"Search pattern failed: {e}")
            continue
    
    return search_results

def parse_movie_info_from_url(url):
    """Extract movie information from URL"""
    import re
    
    # Common patterns in movie URLs
    url_lower = url.lower()
    
    # Extract movie info patterns
    movie_info = {
        'title': '',
        'year': '',
        'language': '',
        'quality': '',
        'format': ''
    }
    
    # Extract year (4 digits between 1900-2030)
    year_match = re.search(r'\b(19\d{2}|20[0-3]\d)\b', url)
    if year_match:
        movie_info['year'] = year_match.group(1)
    
    # Extract language
    languages = ['hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'bengali', 'punjabi', 'marathi', 'gujarati']
    for lang in languages:
        if lang in url_lower:
            movie_info['language'] = lang.title()
            break
    
    # Extract quality
    qualities = ['720p', '1080p', '480p', '360p', '4k', 'hd', 'cam', 'dvdrip', 'webrip', 'bluray']
    for quality in qualities:
        if quality in url_lower:
            movie_info['quality'] = quality.upper()
            break
    
    # Extract format
    formats = ['mp4', 'mkv', 'avi', 'mov', 'wmv']
    for fmt in formats:
        if fmt in url_lower:
            movie_info['format'] = fmt.upper()
            break
    
    # Extract title from URL path
    path_parts = url.split('/')
    for part in reversed(path_parts):
        if part and len(part) > 3:
            # Clean the part
            clean_part = re.sub(r'[_\-\.]', ' ', part)
            clean_part = re.sub(r'\.(html?|php|asp)$', '', clean_part, re.IGNORECASE)
            
            # Remove common URL artifacts
            clean_part = re.sub(r'\b(movie|watch|download|stream|play)\b', '', clean_part, re.IGNORECASE)
            clean_part = re.sub(r'\b\d{4}\b', '', clean_part)  # Remove year
            clean_part = clean_part.strip()
            
            if len(clean_part) > 3:
                movie_info['title'] = clean_part
                break
    
    return movie_info

def is_relevant_movie_link(url, text, search_movie_name):
    """Check if a movie link is relevant based on URL and text analysis"""
    movie_info = parse_movie_info_from_url(url)
    
    # Check if URL contains movie-related keywords
    movie_keywords = ['movie', 'watch', 'download', 'stream', 'play', 'film']
    url_lower = url.lower()
    has_movie_keyword = any(keyword in url_lower for keyword in movie_keywords)
    
    # Check if it's a proper movie page (not homepage, category, etc.)
    is_movie_page = (
        has_movie_keyword and
        not any(skip in url_lower for skip in ['category', 'genre', 'search', 'page', 'tag', 'author']) and
        len(url.split('/')) > 3  # Has some depth
    )
    
    # Check title relevance
    title_relevant = False
    if text and len(text) > 3:
        title_relevant = (
            is_fuzzy_match(search_movie_name, text, threshold=40) or
            search_movie_name.lower() in text.lower() or
            any(word.lower() in text.lower() for word in search_movie_name.split() if len(word) > 2)
        )
    
    # Check URL title relevance
    url_title_relevant = False
    if movie_info['title']:
        url_title_relevant = (
            is_fuzzy_match(search_movie_name, movie_info['title'], threshold=40) or
            search_movie_name.lower() in movie_info['title'].lower()
        )
    
    return is_movie_page and (title_relevant or url_title_relevant), movie_info

def extract_movie_links(html, movie_name, base_url):
    """Enhanced movie link extraction with URL analysis and filtering"""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    
    # Get all links
    all_links = soup.find_all("a", href=True)
    
    for a in all_links:
        href = a.get('href', '')
        text = a.get_text(strip=True)
        title_attr = a.get('title', '')
        alt_text = ''
        
        # Check for images with alt text
        img = a.find('img')
        if img:
            alt_text = img.get('alt', '')
        
        # Combine all text sources
        all_text_sources = [text, title_attr, alt_text]
        best_text = max(all_text_sources, key=len) if all_text_sources else text
        
        if href:
            full_url = urljoin(base_url, href)
            
            # Check relevance using URL analysis
            is_relevant, movie_info = is_relevant_movie_link(full_url, best_text, movie_name)
            
            if is_relevant:
                # Calculate match score
                text_score = 0
                if best_text:
                    text_score = Levenshtein.ratio(clean_text(movie_name), clean_text(best_text))
                
                url_score = 0
                if movie_info['title']:
                    url_score = Levenshtein.ratio(clean_text(movie_name), clean_text(movie_info['title']))
                
                match_score = max(text_score, url_score)
                
                # Create enhanced title with movie info
                enhanced_title = best_text
                if movie_info['year'] or movie_info['language'] or movie_info['quality']:
                    info_parts = []
                    if movie_info['year']:
                        info_parts.append(movie_info['year'])
                    if movie_info['language']:
                        info_parts.append(movie_info['language'])
                    if movie_info['quality']:
                        info_parts.append(movie_info['quality'])
                    
                    if info_parts:
                        enhanced_title = f"{best_text} ({' | '.join(info_parts)})"
                
                found.append({
                    'title': enhanced_title,
                    'url': full_url,
                    'match_score': match_score,
                    'movie_info': movie_info,
                    'original_text': best_text
                })
    
    # Sort by match score and remove duplicates
    seen_urls = set()
    unique_found = []
    for item in sorted(found, key=lambda x: x['match_score'], reverse=True):
        if item['url'] not in seen_urls and item['match_score'] > 0.3:  # Higher threshold
            seen_urls.add(item['url'])
            unique_found.append(item)
    
    return unique_found[:5]  # Return top 5 most relevant matches

def extract_video_sources(movie_page_url):
    """Enhanced video source extraction with better embedding support"""
    html, _ = get_rendered_html(movie_page_url, wait_time=15)
    if not html:
        return []
    
    soup = BeautifulSoup(html, "html.parser")
    video_sources = []
    
    # Look for iframes with better filtering
    iframes = soup.find_all("iframe")
    for iframe in iframes:
        src = iframe.get("src")
        if src:
            # Make URL absolute
            if not src.startswith('http'):
                src = urljoin(movie_page_url, src)
            
            # Check for known video hosting domains
            video_domains = [
                'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
                'streamtape.com', 'doodstream.com', 'mixdrop.co', 'upstream.to',
                'streamlare.com', 'streamhub.to', 'vidcloud.co', 'fembed.com',
                'embedgram.com', 'streamwish.to', 'filemoon.sx', 'vtube.to'
            ]
            
            is_video_iframe = (
                any(domain in src.lower() for domain in video_domains) or
                any(keyword in src.lower() for keyword in ['embed', 'player', 'stream', 'video', 'watch'])
            )
            
            if is_video_iframe:
                # Convert to embeddable format
                embed_url = convert_to_embed_url(src)
                video_sources.append({
                    'type': 'iframe',
                    'url': embed_url,
                    'original_url': src,
                    'quality': 'Stream',
                    'embeddable': True
                })
    
    # Look for video tags
    videos = soup.find_all("video")
    for video in videos:
        sources = video.find_all("source")
        if sources:
            for source in sources:
                src = source.get("src")
                if src:
                    if not src.startswith('http'):
                        src = urljoin(movie_page_url, src)
                    video_sources.append({
                        'type': 'video',
                        'url': src,
                        'quality': source.get('label', 'Direct'),
                        'embeddable': True
                    })
        else:
            src = video.get("src")
            if src:
                if not src.startswith('http'):
                    src = urljoin(movie_page_url, src)
                video_sources.append({
                    'type': 'video',
                    'url': src,
                    'quality': 'Direct',
                    'embeddable': True
                })
    
    # Look for streaming URLs in JavaScript
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string:
            # Enhanced patterns for video URLs
            video_patterns = [
                r'["\']https?://[^"\']*\.(?:mp4|m3u8|mkv|avi|webm|mov)[^"\']*["\']',
                r'["\']https?://[^"\']*(?:embed|player|stream|video|watch)[^"\']*["\']',
                r'file\s*:\s*["\']([^"\']+)["\']',
                r'src\s*:\s*["\']([^"\']+)["\']',
                r'source\s*:\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    clean_url = match.strip('"\'') if isinstance(match, str) else match[0].strip('"\'')
                    if clean_url and 'http' in clean_url:
                        if not clean_url.startswith('http'):
                            clean_url = urljoin(movie_page_url, clean_url)
                        
                        video_sources.append({
                            'type': 'extracted',
                            'url': clean_url,
                            'quality': 'JS Extracted',
                            'embeddable': True
                        })
    
    # Look for download links as backup
    download_links = soup.find_all("a", href=True)
    for link in download_links:
        href = link.get("href")
        text = link.get_text(strip=True).lower()
        
        if href and any(keyword in text for keyword in ['download', 'watch', 'play', 'stream']):
            if any(ext in href.lower() for ext in ['.mp4', '.mkv', '.avi', '.m3u8']):
                if not href.startswith('http'):
                    href = urljoin(movie_page_url, href)
                
                video_sources.append({
                    'type': 'download',
                    'url': href,
                    'quality': 'Download Link',
                    'embeddable': False
                })
    
    return video_sources

def convert_to_embed_url(url):
    """Convert various video URLs to embeddable format"""
    # YouTube
    if 'youtube.com/watch' in url:
        video_id = url.split('v=')[1].split('&')[0]
        return f"https://www.youtube.com/embed/{video_id}"
    elif 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[1].split('?')[0]
        return f"https://www.youtube.com/embed/{video_id}"
    
    # Vimeo
    elif 'vimeo.com/' in url and '/embed/' not in url:
        video_id = url.split('vimeo.com/')[1].split('?')[0]
        return f"https://player.vimeo.com/video/{video_id}"
    
    # For other URLs, return as-is if they already contain embed/player
    elif any(keyword in url.lower() for keyword in ['embed', 'player']):
        return url
    
    # Default: return original URL
    return url

def apply_filters(movies, language_filter, year_filter, quality_filter):
    """Apply language, year, and quality filters to movie results"""
    filtered_movies = []
    
    for movie in movies:
        # Language filter
        if language_filter != 'all':
            movie_language = movie.get('language', '').lower()
            if language_filter.lower() not in movie_language:
                continue
        
        # Year filter
        if year_filter != 'all':
            movie_year = movie.get('year', '')
            if str(year_filter) != str(movie_year):
                continue
        
        # Quality filter
        if quality_filter != 'all':
            movie_qualities = movie.get('quality', [])
            if isinstance(movie_qualities, str):
                movie_qualities = [movie_qualities]
            
            # Check if any quality matches the filter
            quality_match = False
            for quality in movie_qualities:
                if quality_filter.lower() in quality.lower():
                    quality_match = True
                    break
            
            if not quality_match:
                continue
        
        # If movie passes all filters, add it to results
        filtered_movies.append(movie)
    
    return filtered_movies

def load_site_urls(file_path="movie_sites.txt"):
    """Load movie sites from file"""
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_movie():
    """Enhanced search using our downloadhub.legal backend"""
    try:
        data = request.get_json()
        movie_name = data.get('movie_name', '').strip()
        language_filter = data.get('language_filter', 'all')
        year_filter = data.get('year_filter', 'all')
        quality_filter = data.get('quality_filter', 'all')
        page = data.get('page', 1)
        
        if not movie_name:
            return jsonify({'error': 'Movie name is required'}), 400
        
        # Initialize our enhanced agent
        agent = initialize_agent()
        
        # Get page number from request
        per_page = 10
        
        # Perform search on downloadhub.legal with pagination
        search_result = agent.search_movies(movie_name, page=page, per_page=per_page)
        results = search_result['movies']
        pagination = search_result['pagination']
        
        # Store results for later use
        search_id = f"search_{int(time.time())}"
        search_results[search_id] = results
        
        return jsonify({
            'success': True,
            'search_id': search_id,
            'results': results,
            'total': len(results),
            'pagination': pagination,
            'filters_applied': {
                'language': language_filter,
                'year': year_filter,
                'quality': quality_filter
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/extract', methods=['POST'])
def extract_download_links():
    """Extract download links for selected movie"""
    try:
        data = request.get_json()
        search_id = data.get('search_id')
        movie_index = data.get('movie_index')
        
        if not search_id or movie_index is None:
            return jsonify({'error': 'Search ID and movie index are required'}), 400
        
        if search_id not in search_results:
            return jsonify({'error': 'Invalid search ID'}), 400
        
        movies = search_results[search_id]
        if movie_index >= len(movies):
            return jsonify({'error': 'Invalid movie index'}), 400
        
        selected_movie = movies[movie_index]
        extraction_id = f"extract_{int(time.time())}"
        
        # Start extraction in background
        def extract_in_background():
            try:
                agent = initialize_agent()
                result = agent.get_download_links(selected_movie['detail_url'])
                extraction_results[extraction_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'result': result
                }
            except Exception as e:
                extraction_results[extraction_id] = {
                    'status': 'error',
                    'progress': 0,
                    'error': str(e)
                }
        
        # Initialize extraction status
        extraction_results[extraction_id] = {
            'status': 'processing',
            'progress': 0
        }
        
        # Start background thread
        thread = threading.Thread(target=extract_in_background)
        thread.start()
        
        return jsonify({
            'success': True,
            'extraction_id': extraction_id,
            'message': 'Extraction started'
        })
        
    except Exception as e:
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500

@app.route('/status/<extraction_id>')
def get_extraction_status(extraction_id):
    """Get extraction status"""
    if extraction_id not in extraction_results:
        return jsonify({'error': 'Invalid extraction ID'}), 404
    
    return jsonify(extraction_results[extraction_id])

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent_initialized': agent is not None,
        'timestamp': time.time()
    })

@app.route('/proxy_video')
def proxy_video():
    """Proxy endpoint to bypass CORS for video streaming"""
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # Decode if base64 encoded
        try:
            video_url = base64.b64decode(video_url).decode('utf-8')
        except:
            pass
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': urlparse(video_url).netloc,
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            content_type=response.headers.get('content-type', 'video/mp4'),
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Length': response.headers.get('content-length'),
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            }
        )
    except Exception as e:
        return jsonify({'error': f'Proxy failed: {str(e)}'}), 500

@app.route('/extract_video_direct')
def extract_video_direct():
    """Extract video sources directly from a movie page"""
    page_url = request.args.get('url')
    if not page_url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # Use a more aggressive approach to find video sources
        video_sources = extract_video_sources_aggressive(page_url)
        return jsonify({'video_sources': video_sources})
    except Exception as e:
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500

def is_valid_video_source(url):
    """Check if a URL is likely a valid video source"""
    url_lower = url.lower()
    
    # Check for video file extensions
    video_extensions = ['.mp4', '.m3u8', '.mkv', '.avi', '.webm', '.mov', '.flv']
    has_video_ext = any(ext in url_lower for ext in video_extensions)
    
    # Check for streaming domains
    streaming_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'streamtape.com', 'doodstream.com', 'mixdrop.co', 'upstream.to',
        'streamlare.com', 'streamhub.to', 'vidcloud.co', 'fembed.com',
        'embedgram.com', 'streamwish.to', 'filemoon.sx', 'vtube.to'
    ]
    has_streaming_domain = any(domain in url_lower for domain in streaming_domains)
    
    # Check for streaming keywords
    streaming_keywords = ['embed', 'player', 'stream', 'video', 'watch']
    has_streaming_keyword = any(keyword in url_lower for keyword in streaming_keywords)
    
    # Exclude obviously bad URLs
    bad_patterns = [
        'facebook.com', 'twitter.com', 'instagram.com', 'google.com',
        'advertisement', 'ads', 'popup', 'banner', 'tracking',
        'analytics', 'cdn.js', '.css', '.png', '.jpg', '.gif'
    ]
    has_bad_pattern = any(pattern in url_lower for pattern in bad_patterns)
    
    return (has_video_ext or has_streaming_domain or has_streaming_keyword) and not has_bad_pattern

def extract_video_sources_aggressive(movie_page_url):
    """More aggressive video source extraction with better filtering"""
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    
    driver = None
    video_sources = []
    
    try:
        driver = uc.Chrome(options=options)
        driver.get(movie_page_url)
        
        # Wait for page to load and dynamic content
        time.sleep(12)
        
        # Execute JavaScript to find video sources
        js_script = """
        var sources = [];
        
        // Find all video elements
        document.querySelectorAll('video').forEach(function(video) {
            if (video.src && video.src.length > 10) {
                sources.push({type: 'video', url: video.src, quality: 'Direct Video', priority: 10});
            }
            video.querySelectorAll('source').forEach(function(source) {
                if (source.src && source.src.length > 10) {
                    var quality = source.getAttribute('label') || source.getAttribute('data-quality') || 'Video Source';
                    sources.push({type: 'video', url: source.src, quality: quality, priority: 9});
                }
            });
        });
        
        // Find all iframes with better filtering
        document.querySelectorAll('iframe').forEach(function(iframe) {
            var src = iframe.src;
            if (src && src.length > 10) {
                var isVideoIframe = (
                    src.includes('embed') || src.includes('player') || 
                    src.includes('stream') || src.includes('video') ||
                    src.includes('watch') || src.includes('movie')
                );
                if (isVideoIframe && !src.includes('ads') && !src.includes('banner')) {
                    sources.push({type: 'iframe', url: src, quality: 'Embedded Player', priority: 8});
                }
            }
        });
        
        // Look for video URLs in JavaScript variables and functions
        var scripts = document.querySelectorAll('script');
        scripts.forEach(function(script) {
            if (script.innerHTML) {
                var content = script.innerHTML;
                
                // Look for direct video file URLs
                var videoRegex = /(https?:\/\/[^\s"'<>]+\.(?:mp4|m3u8|mkv|avi|webm|mov)(?:\?[^\s"'<>]*)?)/gi;
                var videoMatches = content.match(videoRegex);
                if (videoMatches) {
                    videoMatches.forEach(function(match) {
                        if (match.length > 20) {
                            sources.push({type: 'extracted', url: match, quality: 'Direct File', priority: 7});
                        }
                    });
                }
                
                // Look for streaming URLs
                var streamRegex = /(https?:\/\/[^\s"'<>]*(?:embed|player|stream|watch|video)[^\s"'<>]*)/gi;
                var streamMatches = content.match(streamRegex);
                if (streamMatches) {
                    streamMatches.forEach(function(match) {
                        if (match.length > 20 && 
                            !match.includes('facebook') && 
                            !match.includes('twitter') && 
                            !match.includes('google') &&
                            !match.includes('ads')) {
                            sources.push({type: 'stream', url: match, quality: 'Stream Link', priority: 6});
                        }
                    });
                }
                
                // Look for HLS/DASH streams
                var hlsRegex = /(https?:\/\/[^\s"'<>]+\.m3u8[^\s"'<>]*)/gi;
                var hlsMatches = content.match(hlsRegex);
                if (hlsMatches) {
                    hlsMatches.forEach(function(match) {
                        sources.push({type: 'hls', url: match, quality: 'HLS Stream', priority: 8});
                    });
                }
            }
        });
        
        // Look for download links
        document.querySelectorAll('a[href]').forEach(function(link) {
            var href = link.href;
            var text = link.textContent.toLowerCase();
            if (href && (text.includes('download') || text.includes('watch') || text.includes('play'))) {
                if (href.includes('.mp4') || href.includes('.mkv') || href.includes('.avi')) {
                    sources.push({type: 'download', url: href, quality: 'Download Link', priority: 5});
                }
            }
        });
        
        return sources;
        """
        
        sources = driver.execute_script(js_script)
        
        # Process and filter sources
        for source in sources:
            if source and source.get('url'):
                url = source['url']
                
                # Validate the video source
                if is_valid_video_source(url) and len(url) > 15:
                    video_sources.append({
                        'type': source.get('type', 'unknown'),
                        'url': url,
                        'quality': source.get('quality', 'Unknown'),
                        'priority': source.get('priority', 1),
                        'embeddable': True,
                        'proxy_url': f"/proxy_video?url={base64.b64encode(url.encode()).decode()}"
                    })
        
        # Sort by priority and remove duplicates
        seen_urls = set()
        unique_sources = []
        
        # Sort by priority (higher first) then by quality
        sorted_sources = sorted(video_sources, key=lambda x: (x['priority'], len(x['url'])), reverse=True)
        
        for source in sorted_sources:
            if source['url'] not in seen_urls:
                seen_urls.add(source['url'])
                unique_sources.append(source)
                
                # Limit to top 5 high-quality sources
                if len(unique_sources) >= 5:
                    break
        
        return unique_sources
        
    except Exception as e:
        print(f"Aggressive extraction error: {e}")
        return []
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)