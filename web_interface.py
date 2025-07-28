from flask import Flask, render_template, request, jsonify, Response, stream_template
from flask_cors import CORS
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
import logging
from enhanced_downloadhub_agent import EnhancedDownloadHubAgent
from moviezwap_agent import MoviezWapAgent
from skysetx_agent import SkySetXAgent
from movierulz_agent import MovieRulzAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables for our enhanced backend
search_results = {}
extraction_results = {}
downloadhub_agent = None
moviezwap_agent = None
movierulz_agent = None
skysetx_agent = None

def initialize_agents():
    global downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent
    if downloadhub_agent is None:
        downloadhub_agent = EnhancedDownloadHubAgent()
    if moviezwap_agent is None:
        moviezwap_agent = MoviezWapAgent()
    if movierulz_agent is None:
        movierulz_agent = MovieRulzAgent()
    if skysetx_agent is None:
        skysetx_agent = SkySetXAgent()
    return downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent

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
    """Enhanced search using multiple sources (DownloadHub + MoviezWap)"""
    try:
        data = request.get_json()
        movie_name = data.get('movie_name', '').strip()
        language_filter = data.get('language_filter', 'all')
        year_filter = data.get('year_filter', 'all')
        quality_filter = data.get('quality_filter', 'all')
        page = data.get('page', 1)
        sources = data.get('sources', ['downloadhub', 'moviezwap', 'movierulz', 'skysetx'])  # Default to all four sources
        
        if not movie_name:
            return jsonify({'error': 'Movie name is required'}), 400
        
        # Initialize our agents
        downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent = initialize_agents()
        
        # Get page number from request
        per_page = 10
        all_results = []
        
        # Search DownloadHub (Source 1)
        if 'downloadhub' in sources:
            try:
                logger.info(f"Searching DownloadHub for: {movie_name}")
                downloadhub_result = downloadhub_agent.search_movies(movie_name, page=page, per_page=per_page)
                downloadhub_movies = downloadhub_result['movies']
                # Add source identifier to each movie
                for movie in downloadhub_movies:
                    movie['source'] = 'DownloadHub'
                    movie['source_color'] = '#4CAF50'  # Green
                all_results.extend(downloadhub_movies)
                logger.info(f"DownloadHub returned {len(downloadhub_movies)} movies")
            except Exception as e:
                logger.error(f"DownloadHub search failed: {str(e)}")
        
        # Search MoviezWap (Source 2)
        if 'moviezwap' in sources:
            try:
                logger.info(f"Searching MoviezWap for: {movie_name}")
                moviezwap_result = moviezwap_agent.search_movies(movie_name, page=page, per_page=per_page)
                moviezwap_movies = moviezwap_result['movies']
                # Add source identifier to each movie
                for movie in moviezwap_movies:
                    movie['source'] = 'MoviezWap'
                    movie['source_color'] = '#2196F3'  # Blue
                all_results.extend(moviezwap_movies)
                logger.info(f"MoviezWap returned {len(moviezwap_movies)} movies")
            except Exception as e:
                logger.error(f"MoviezWap search failed: {str(e)}")
        
        # Search MovieRulz (Source 3)
        if 'movierulz' in sources:
            try:
                logger.info(f"Searching MovieRulz for: {movie_name}")
                movierulz_result = movierulz_agent.search_movies(movie_name, page=page, per_page=per_page)
                movierulz_movies = movierulz_result['movies']
                # Add source identifier to each movie
                for movie in movierulz_movies:
                    movie['source'] = 'MovieRulz'
                    movie['source_color'] = '#FF9800'  # Orange
                all_results.extend(movierulz_movies)
                logger.info(f"MovieRulz returned {len(movierulz_movies)} movies")
            except Exception as e:
                logger.error(f"MovieRulz search failed: {str(e)}")
        
        # Search SkySetX (Source 4)
        if 'skysetx' in sources:
            try:
                logger.info(f"Searching SkySetX for: {movie_name}")
                skysetx_movies = skysetx_agent.search_movies(movie_name, limit=per_page)
                # Add source identifier to each movie
                for movie in skysetx_movies:
                    movie['source'] = 'SkySetX'
                    movie['source_color'] = '#9C27B0'  # Purple
                all_results.extend(skysetx_movies)
                logger.info(f"SkySetX returned {len(skysetx_movies)} movies")
            except Exception as e:
                logger.error(f"SkySetX search failed: {str(e)}")
        
        # Calculate pagination for combined results
        total_movies = len(all_results)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        movies_page = all_results[start_index:end_index]
        
        total_pages = (total_movies + per_page - 1) // per_page
        
        pagination = {
            'current_page': page,
            'per_page': per_page,
            'total_movies': total_movies,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        # Store results for later use
        search_id = f"search_{int(time.time())}"
        search_results[search_id] = all_results
        
        logger.info(f"Combined search returned {total_movies} movies from {len(sources)} sources")
        
        return jsonify({
            'success': True,
            'search_id': search_id,
            'results': movies_page,
            'total': total_movies,
            'pagination': pagination,
            'sources_used': sources,
            'filters_applied': {
                'language': language_filter,
                'year': year_filter,
                'quality': quality_filter
            }
        })
        
    except Exception as e:
        logger.error(f"Multi-source search failed: {str(e)}")
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
                print(f"DEBUG: Starting extraction for {extraction_id}")
                
                # Determine which agent to use based on movie source
                movie_source = selected_movie.get('source', 'DownloadHub')
                downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent = initialize_agents()
                
                if movie_source == 'MoviezWap':
                    agent = moviezwap_agent
                    print(f"DEBUG: Using MoviezWap agent for extraction")
                elif movie_source == 'MovieRulz':
                    agent = movierulz_agent
                    print(f"DEBUG: Using MovieRulz agent for extraction")
                elif movie_source == 'SkySetX':
                    agent = skysetx_agent
                    print(f"DEBUG: Using SkySetX agent for extraction")
                else:
                    agent = downloadhub_agent
                    print(f"DEBUG: Using DownloadHub agent for extraction")
                
                # Get the URL - different sources use different keys
                movie_url = selected_movie.get('url') or selected_movie.get('detail_url')
                print(f"DEBUG: Agent initialized, extracting from {movie_url}")
                # Use appropriate method based on agent type
                if movie_source == 'MovieRulz':
                    result = agent.extract_download_links(movie_url)
                elif movie_source == 'SkySetX':
                    result = agent.get_download_links(movie_url)
                    print(f"DEBUG: SkySetX extraction result type: {type(result)}")
                    print(f"DEBUG: SkySetX extraction result: {result}")
                else:
                    result = agent.get_download_links(movie_url)
                print(f"DEBUG: Extraction completed for {extraction_id} with {len(result) if result else 0} links")
                
                # Normalize result format for consistency
                if movie_source == 'SkySetX':
                    # SkySetX now returns a structured dict like other agents
                    if isinstance(result, dict) and 'download_links' in result:
                        normalized_result = result
                        print(f"DEBUG: SkySetX returned structured result with {len(result.get('download_links', []))} links")
                    elif isinstance(result, list):
                        # Fallback for old format
                        normalized_result = {
                            'download_links': result,
                            'total_links': len(result),
                            'source': movie_source,
                            'movie_url': movie_url
                        }
                        print(f"DEBUG: Normalized SkySetX legacy result format with {len(result)} links")
                    else:
                        normalized_result = result
                else:
                    normalized_result = result
                
                extraction_results[extraction_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'result': normalized_result,
                    'source': movie_source
                }
            except Exception as e:
                print(f"DEBUG: Extraction failed for {extraction_id}: {str(e)}")
                extraction_results[extraction_id] = {
                    'status': 'error',
                    'progress': 0,
                    'error': str(e),
                    'source': selected_movie.get('source', 'Unknown')
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
    print(f"DEBUG: Checking extraction_id: {extraction_id}")
    print(f"DEBUG: Available extraction_results: {list(extraction_results.keys())}")
    
    if extraction_id not in extraction_results:
        return jsonify({'error': f'Invalid extraction ID: {extraction_id}. Available: {list(extraction_results.keys())}'}), 404
    
    result = extraction_results[extraction_id]
    
    # Auto-trigger health check when extraction is completed
    if result.get('status') == 'completed' and not result.get('health_check_started', False):
        extraction_result = result.get('result', {})
        
        # Handle different result formats
        if isinstance(extraction_result, dict):
            links_data = extraction_result.get('download_links', [])
        elif isinstance(extraction_result, list):
            links_data = extraction_result
        else:
            links_data = []
        
        if links_data:
            import threading
            def auto_health_check():
                try:
                    print(f"DEBUG: Starting auto health check for {len(links_data)} links")
                    # Prepare links for health checking
                    health_results = {}
                    for i, link in enumerate(links_data):
                        # Handle both dict and string formats
                        if isinstance(link, dict):
                            url = link.get('url', '')
                        elif isinstance(link, str):
                            url = link
                        else:
                            print(f"DEBUG: Unexpected link format: {type(link)} - {link}")
                            continue
                            
                        if url:
                            print(f"DEBUG: Checking health for link {i}: {url}")
                            health_result = check_download_link_health(url)
                            health_results[str(i)] = health_result
                    
                    # Store health results globally
                    global health_check_results
                    if 'health_check_results' not in globals():
                        health_check_results = {}
                    health_check_results[extraction_id] = health_results
                    
                    # Mark health check as completed
                    extraction_results[extraction_id]['health_check_completed'] = True
                    print(f"DEBUG: Auto health check completed for extraction_id: {extraction_id}")
                    
                except Exception as e:
                    print(f"ERROR: Auto health check failed: {e}")
            
            # Start health check in background thread
            health_thread = threading.Thread(target=auto_health_check)
            health_thread.daemon = True
            health_thread.start()
            
            # Mark that health check has been started
            extraction_results[extraction_id]['health_check_started'] = True
            print(f"DEBUG: Auto health check thread started for extraction_id: {extraction_id}")
    
    # Add auto health check flag to response if completed
    if result.get('status') == 'completed':
        result['auto_health_check'] = True
    
    return jsonify(result)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'downloadhub_agent_initialized': downloadhub_agent is not None,
        'moviezwap_agent_initialized': moviezwap_agent is not None,
        'movierulz_agent_initialized': movierulz_agent is not None,
        'sources_available': ['DownloadHub', 'MoviezWap', 'MovieRulz'],
        'timestamp': time.time()
    })

@app.route('/check_link_health', methods=['POST'])
def check_link_health():
    """Check the health of a download link"""
    try:
        data = request.get_json()
        link_url = data.get('url')
        
        if not link_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Check link health
        health_status = check_download_link_health(link_url)
        return jsonify(health_status)
        
    except Exception as e:
        return jsonify({'error': f'Health check failed: {str(e)}'}), 500

@app.route('/check_multiple_links_health', methods=['POST'])
def check_multiple_links_health():
    """Check health of multiple download links"""
    try:
        data = request.get_json()
        links = data.get('links', [])
        
        if not links:
            return jsonify({'error': 'No links provided'}), 400
        
        results = {}
        for i, link in enumerate(links):
            url = link.get('url') if isinstance(link, dict) else link
            if url:
                health_status = check_download_link_health(url)
                results[str(i)] = health_status
        
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': f'Health check failed: {str(e)}'}), 500

@app.route('/unlock_shortlink', methods=['POST'])
def unlock_shortlink():
    """Unlock a shortlink and extract actual download links"""
    try:
        data = request.get_json()
        shortlink_url = data.get('url')
        
        if not shortlink_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        print(f"DEBUG: Unlocking shortlink: {shortlink_url}")
        
        # Use Selenium to unlock and extract links
        unlocked_links = unlock_and_extract_links(shortlink_url)
        
        return jsonify({
            'status': 'success',
            'unlocked_links': unlocked_links,
            'original_url': shortlink_url
        })
        
    except Exception as e:
        print(f"DEBUG: Unlock failed: {str(e)}")
        return jsonify({'error': f'Unlock failed: {str(e)}'}), 500

@app.route('/resolve_download', methods=['POST'])
def resolve_download():
    """Automatically resolve MoviezWap download.php URLs to final download links"""
    try:
        data = request.get_json()
        download_url = data.get('url')
        
        if not download_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        print(f"DEBUG: Resolving download URL: {download_url}")
        
        # Check if it's a MoviezWap URL (download.php, extlinks_, or getlinks_)
        if 'moviezwap' in download_url.lower() and ('download.php' in download_url or 'extlinks_' in download_url or 'getlinks_' in download_url):
            print(f"DEBUG: MoviezWap URL detected (download.php, extlinks_, or getlinks_) - using automation to resolve")
            
            # Initialize MoviezWap agent
            downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent = initialize_agents()
            
            # Use the MoviezWap agent's resolve_fast_download_server method
            final_url = moviezwap_agent.resolve_fast_download_server(download_url)
            
            if final_url:
                print(f"DEBUG: Successfully resolved to final URL: {final_url}")
                return jsonify({
                    'status': 'success',
                    'final_download_url': final_url,
                    'original_url': download_url,
                    'message': 'Direct download link resolved automatically',
                    'instructions': 'Click the link below to start downloading the movie directly.'
                })
            else:
                print(f"DEBUG: Failed to resolve automatically, returning manual instructions")
                return jsonify({
                    'status': 'partial_success',
                    'final_download_url': download_url,
                    'original_url': download_url,
                    'message': 'Automatic resolution failed - manual action required',
                    'instructions': 'This will open the MoviezWap download page. Click the "Fast Download Server" link and handle the popup to start the download.'
                })
        
        # Check if it's a protected moviezzwaphd.xyz URL
        elif 'moviezzwaphd.xyz' in download_url.lower():
            print(f"DEBUG: Protected moviezzwaphd.xyz URL detected - using Selenium to handle")
            
            # Initialize MoviezWap agent
            downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent = initialize_agents()
            
            # Use Selenium to handle the protected link with proper headers and referrer
            try:
                import undetected_chromedriver as uc
                from selenium.webdriver.common.by import By
                import time
                
                options = uc.ChromeOptions()
                options.headless = True
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                
                driver = None
                try:
                    print(f"DEBUG: Starting Chrome to handle protected link: {download_url}")
                    driver = uc.Chrome(options=options)
                    driver.set_page_load_timeout(30)
                    
                    # Set proper referrer to MoviezWap
                    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    })
                    
                    # Navigate to MoviezWap first to set proper referrer
                    driver.get("https://www.moviezwap.pink")
                    time.sleep(2)
                    
                    # Now navigate to the protected URL with proper referrer
                    driver.get(download_url)
                    time.sleep(8)
                    
                    # Check if we got redirected to a download or if the file starts downloading
                    current_url = driver.current_url
                    print(f"DEBUG: Current URL after navigation: {current_url}")
                    
                    # Check if the page has a download button or direct download link
                    download_elements = driver.find_elements(By.XPATH, "//a[contains(text(), 'Download') or contains(text(), 'download') or contains(@href, '.mp4') or contains(@href, '.mkv') or contains(@href, '.avi')]")
                    
                    if download_elements:
                        # Click the download button/link
                        download_element = download_elements[0]
                        download_href = download_element.get_attribute('href')
                        download_text = download_element.text
                        
                        print(f"DEBUG: Found download element: '{download_text}' -> {download_href}")
                        
                        if download_href and any(ext in download_href.lower() for ext in ['.mp4', '.mkv', '.avi']):
                            print(f"DEBUG: Direct file link found: {download_href}")
                            return jsonify({
                                'status': 'success',
                                'final_download_url': download_href,
                                'original_url': download_url,
                                'message': 'Protected link resolved to direct file',
                                'instructions': 'Direct download link extracted.'
                            })
                        else:
                            # Try clicking the download button
                            try:
                                driver.execute_script("arguments[0].click();", download_element)
                                time.sleep(5)
                                
                                # Check if download started or we got redirected
                                new_url = driver.current_url
                                print(f"DEBUG: URL after clicking download: {new_url}")
                                
                                if new_url != current_url and any(ext in new_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                                    return jsonify({
                                        'status': 'success',
                                        'final_download_url': new_url,
                                        'original_url': download_url,
                                        'message': 'Protected link resolved by clicking download',
                                        'instructions': 'Direct download link extracted.'
                                    })
                            except Exception as click_error:
                                print(f"DEBUG: Error clicking download button: {click_error}")
                    
                    # Check if current URL is a direct file
                    elif any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                        print(f"DEBUG: Current URL is direct file: {current_url}")
                        return jsonify({
                            'status': 'success',
                            'final_download_url': current_url,
                            'original_url': download_url,
                            'message': 'Protected link resolved to direct file',
                            'instructions': 'Direct download link extracted.'
                        })
                    
                    # If no direct download found, return for manual handling
                    print(f"DEBUG: No direct download found, returning original URL for manual handling")
                    return jsonify({
                        'status': 'partial_success',
                        'final_download_url': download_url,
                        'original_url': download_url,
                        'message': 'Protected link requires manual action',
                        'instructions': 'Please click the download link manually on the opened page.'
                    })
                        
                except Exception as e:
                    print(f"DEBUG: Error handling protected link: {str(e)}")
                    return jsonify({
                        'status': 'partial_success',
                        'final_download_url': download_url,
                        'original_url': download_url,
                        'message': 'Protected link processing failed',
                        'instructions': 'Please click the download link manually on the opened page.'
                    })
                finally:
                    if driver:
                        driver.quit()
                        
            except ImportError:
                print(f"DEBUG: Selenium not available for protected link handling")
                return jsonify({
                    'status': 'partial_success',
                    'final_download_url': download_url,
                    'original_url': download_url,
                    'message': 'Protected link requires manual action',
                    'instructions': 'Please click the download link manually on the opened page.'
                })
        
        # For non-MoviezWap URLs, return as-is
        else:
            print(f"DEBUG: Non-MoviezWap URL, returning as-is: {download_url}")
            return jsonify({
                'status': 'success',
                'final_download_url': download_url,
                'original_url': download_url,
                'message': 'Direct download link',
                'instructions': 'Click the link to start downloading.'
            })
        
    except Exception as e:
        print(f"DEBUG: Download resolution failed: {str(e)}")
        return jsonify({'error': f'Resolution failed: {str(e)}'}), 500

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

def check_download_link_health(url, timeout=10):
    """
    Check the health of a download link or streaming service
    Returns status with color indicator, including locked link detection
    """
    try:
        # Handle different types of URLs
        if not url or not url.startswith('http'):
            return {
                'status': 'invalid',
                'color': 'red',
                'message': 'Invalid URL',
                'response_code': None,
                'response_time': None,
                'is_locked': False
            }
        
        # Check if it's a streaming service
        streaming_services = [
            'streamlare', 'vcdnlare', 'slmaxed', 'sltube', 'streamlare.com',
            'netutv', 'uperbox', 'streamtape', 'droplare', 'streamwish', 
            'filelions', 'mixdrop', 'doodstream', 'upstream'
        ]
        
        # Check if it's a known shortlink/unlock service
        shortlink_services = [
            'shortlinkto.onl',
            'shortlinkto.biz',
            'uptobhai.blog',
            'shortlink.to',
            'short.link',
            'unlock.link',
            'linkvertise.com',
            'adf.ly',
            'bit.ly',
            'tinyurl.com',
            'ow.ly',
            'goo.gl'
        ]
        
        url_lower = url.lower()
        is_streaming = any(service in url_lower for service in streaming_services)
        is_shortlink = any(service in url_lower for service in shortlink_services)
        
        start_time = time.time()
        
        # Set up headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # For streaming services, check if the stream is accessible
        if is_streaming:
            try:
                response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                response_time = round((time.time() - start_time) * 1000, 2)
                
                if response.status_code == 200:
                    page_content = response.text.lower()
                    
                    # Check for streaming service indicators
                    streaming_indicators = [
                        'video', 'player', 'stream', 'play', 'media',
                        'jwplayer', 'videojs', 'plyr', 'hls', 'm3u8'
                    ]
                    
                    # Check for error indicators
                    error_indicators = [
                        'file not found', 'video not found', 'expired',
                        'deleted', 'removed', 'unavailable', 'error 404',
                        'access denied', 'forbidden'
                    ]
                    
                    has_streaming_content = any(indicator in page_content for indicator in streaming_indicators)
                    has_errors = any(indicator in page_content for indicator in error_indicators)
                    
                    if has_errors:
                        return {
                            'status': 'error',
                            'color': 'red',
                            'message': 'Stream unavailable or expired',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False,
                            'is_streaming': True
                        }
                    elif has_streaming_content:
                        return {
                            'status': 'healthy',
                            'color': 'green',
                            'message': 'Stream is accessible and ready to play',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False,
                            'is_streaming': True
                        }
                    else:
                        return {
                            'status': 'unknown',
                            'color': 'yellow',
                            'message': 'Stream status unclear',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False,
                            'is_streaming': True
                        }
                else:
                    return {
                        'status': 'unhealthy',
                        'color': 'red',
                        'message': f'Stream not accessible (HTTP {response.status_code})',
                        'response_code': response.status_code,
                        'response_time': response_time,
                        'is_locked': False,
                        'is_streaming': True
                    }
                    
            except Exception as e:
                response_time = round((time.time() - start_time) * 1000, 2)
                return {
                    'status': 'error',
                    'color': 'red',
                    'message': f'Stream check failed: {str(e)}',
                    'response_code': None,
                    'response_time': response_time,
                    'is_locked': False,
                    'is_streaming': True
                }
        
        # For shortlinks, we need to get the page content to check if it's locked
        if is_shortlink:
            try:
                response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                response_time = round((time.time() - start_time) * 1000, 2)
                
                if response.status_code == 200:
                    page_content = response.text.lower()
                    final_url = response.url.lower()
                    
                    # Debug logging - print page content snippet
                    print(f"DEBUG: Checking URL: {url}")
                    print(f"DEBUG: Final URL after redirects: {response.url}")
                    print(f"DEBUG: Page content snippet (first 500 chars): {page_content[:500]}")
                    
                    # Check if we were redirected to a direct download link
                    direct_download_indicators = [
                        'drive.google.com/file',
                        'mega.nz',
                        'mediafire.com/file',
                        'dropbox.com',
                        'onedrive.live.com',
                        '.zip',
                        '.rar',
                        '.mp4',
                        '.mkv',
                        '.avi'
                    ]
                    
                    # Check if redirected to actual download
                    is_direct_download = any(indicator in final_url for indicator in direct_download_indicators)
                    
                    # Check for the specific unlock button text (locked state)
                    locked_indicators = [
                        'click to unlock download links',
                        'click to unlock download link',
                        'unlock download links',
                        'click here to unlock',
                        'verify you are human',
                        'complete captcha',
                        'human verification',
                        # Additional patterns for shortlinkto.onl
                        'get link',
                        'get links',
                        'continue to link',
                        'continue to links',
                        'please wait',
                        'loading...',
                        'generating link',
                        'generating links',
                        'unlock now',
                        'unlock link',
                        'unlock links'
                    ]
                    
                    # Check for download links being visible (unlocked state)
                    unlocked_indicators = [
                        'links unlocked now',
                        'links unlocked now.',
                        'google drive',
                        'mega.nz',
                        'mediafire',
                        'dropbox',
                        'onedrive',
                        'download link:',
                        'download links:',
                        'direct download',
                        'file download',
                        'download now',
                        'get download'
                    ]
                    
                    is_locked = any(indicator in page_content for indicator in locked_indicators)
                    is_unlocked = any(indicator in page_content for indicator in unlocked_indicators)
                    
                    # Debug logging
                    print(f"DEBUG: Locked indicators found: {[indicator for indicator in locked_indicators if indicator in page_content]}")
                    print(f"DEBUG: Unlocked indicators found: {[indicator for indicator in unlocked_indicators if indicator in page_content]}")
                    print(f"DEBUG: is_locked: {is_locked}, is_unlocked: {is_unlocked}")
                    
                    # Check if redirected to dead/invalid page
                    dead_page_indicators = [
                        'page not found',
                        '404 not found',
                        'file not found',
                        'link expired',
                        'link not found',
                        'invalid link',
                        'broken link',
                        'access denied',
                        'forbidden',
                        'this link has expired',
                        'link has been removed',
                        'file has been deleted'
                    ]
                    
                    is_dead_page = any(indicator in page_content for indicator in dead_page_indicators)
                    
                    # Priority 1: Check if redirected to dead/invalid page
                    if is_dead_page or response.status_code in [404, 403, 410]:
                        return {
                            'status': 'dead',
                            'color': 'red',
                            'message': f'Dead Link - File Not Found ({response_time}ms)',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False,
                            'final_url': response.url
                        }
                    
                    # Priority 2: Check if redirected to direct download
                    elif is_direct_download:
                        return {
                            'status': 'unlocked_redirect',
                            'color': 'green',
                            'message': f'Unlocked - Direct Link ({response_time}ms)',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False,
                            'final_url': response.url
                        }
                    
                    # Priority 3: Check if locked (has unlock button)
                    elif is_locked:
                        return {
                            'status': 'locked',
                            'color': 'yellow',
                            'message': f'Locked - Click to Unlock ({response_time}ms)',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': True,
                            'unlock_url': url
                        }
                    
                    # Priority 4: Check if unlocked (download links visible)
                    elif is_unlocked:
                        return {
                            'status': 'unlocked',
                            'color': 'green',
                            'message': f'Unlocked - Download Links Available ({response_time}ms)',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False
                        }
                    
                    # Default: Shortlink active but status unclear
                    else:
                        return {
                            'status': 'shortlink_active',
                            'color': 'orange',
                            'message': f'Shortlink Active ({response_time}ms)',
                            'response_code': response.status_code,
                            'response_time': response_time,
                            'is_locked': False
                        }
                else:
                    return {
                        'status': 'shortlink_error',
                        'color': 'red',
                        'message': f'Shortlink Error ({response_time}ms)',
                        'response_code': response.status_code,
                        'response_time': response_time,
                        'is_locked': False
                    }
            except Exception as e:
                return {
                    'status': 'shortlink_error',
                    'color': 'red',
                    'message': f'Shortlink Check Failed',
                    'response_code': None,
                    'response_time': None,
                    'is_locked': False
                }
        
        # For regular links, use the original logic
        try:
            response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        except:
            # If HEAD fails, try GET with limited content
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            # Close the connection after getting headers
            response.close()
        
        response_time = round((time.time() - start_time) * 1000, 2)  # in milliseconds
        status_code = response.status_code
        
        # Determine health status based on response code
        if status_code == 200:
            # Check if it's actually a file or a redirect page
            content_type = response.headers.get('content-type', '').lower()
            content_length = response.headers.get('content-length')
            
            # Good indicators for actual files
            if (any(file_type in content_type for file_type in ['video/', 'application/octet-stream', 'application/zip']) or
                (content_length and int(content_length) > 1000000)):  # > 1MB
                return {
                    'status': 'healthy',
                    'color': 'green',
                    'message': f'Active ({response_time}ms)',
                    'response_code': status_code,
                    'response_time': response_time,
                    'content_type': content_type,
                    'file_size': content_length,
                    'is_locked': False
                }
            else:
                return {
                    'status': 'warning',
                    'color': 'orange',
                    'message': f'Redirect/Page ({response_time}ms)',
                    'response_code': status_code,
                    'response_time': response_time,
                    'content_type': content_type,
                    'is_locked': False
                }
        
        elif status_code in [301, 302, 303, 307, 308]:
            return {
                'status': 'redirect',
                'color': 'orange',
                'message': f'Redirect ({response_time}ms)',
                'response_code': status_code,
                'response_time': response_time,
                'is_locked': False
            }
        
        elif status_code == 403:
            return {
                'status': 'forbidden',
                'color': 'red',
                'message': f'Access Denied ({response_time}ms)',
                'response_code': status_code,
                'response_time': response_time,
                'is_locked': False
            }
        
        elif status_code == 404:
            return {
                'status': 'not_found',
                'color': 'red',
                'message': f'Not Found ({response_time}ms)',
                'response_code': status_code,
                'response_time': response_time,
                'is_locked': False
            }
        
        elif status_code >= 500:
            return {
                'status': 'server_error',
                'color': 'red',
                'message': f'Server Error ({response_time}ms)',
                'response_code': status_code,
                'response_time': response_time,
                'is_locked': False
            }
        
        else:
            return {
                'status': 'unknown',
                'color': 'orange',
                'message': f'Status {status_code} ({response_time}ms)',
                'response_code': status_code,
                'response_time': response_time,
                'is_locked': False
            }
    
    except requests.exceptions.Timeout:
        return {
            'status': 'timeout',
            'color': 'red',
            'message': 'Timeout',
            'response_code': None,
            'response_time': timeout * 1000,
            'is_locked': False
        }
    
    except requests.exceptions.ConnectionError:
        return {
            'status': 'connection_error',
            'color': 'red',
            'message': 'Connection Failed',
            'response_code': None,
            'response_time': None,
            'is_locked': False
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'color': 'red',
            'message': f'Error: {str(e)[:50]}',
            'response_code': None,
            'response_time': None,
            'is_locked': False
        }

def unlock_and_extract_links(shortlink_url):
    """
    Use Selenium to unlock shortlink and extract ALL download links comprehensively
    Based on tmp_rovodev_extract_all_links.py logic
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from urllib.parse import urlparse
    import time
    
    options = Options()
    options.add_argument('--headless=true')  # Run in background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    driver = None
    try:
        print(f"DEBUG: Starting Chrome for comprehensive unlock: {shortlink_url}")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Load the shortlink page
        driver.get(shortlink_url)
        time.sleep(5)
        
        print("DEBUG: Looking for unlock button...")
        
        # Find unlock button with comprehensive search
        all_buttons = driver.find_elements(By.TAG_NAME, "button")
        unlock_button = None
        
        # Check for various unlock button patterns
        unlock_button_patterns = [
            lambda text: "unlock" in text and "download" in text,  # Original pattern
            lambda text: "get link" in text,                       # shortlinkto.onl pattern
            lambda text: "get links" in text,                      # shortlinkto.onl pattern
            lambda text: "continue" in text,                       # shortlinkto.onl pattern
            lambda text: "unlock now" in text,                     # shortlinkto.onl pattern
            lambda text: "unlock link" in text,                    # shortlinkto.onl pattern
            lambda text: text == "unlock" or text == "continue",   # Simple patterns
        ]
        
        for button in all_buttons:
            button_text = button.text.strip().lower()
            if any(pattern(button_text) for pattern in unlock_button_patterns):
                unlock_button = button
                print(f"DEBUG: Found unlock button: '{button.text}'")
                break
        
        if not unlock_button:
            print("DEBUG: No unlock button found")
            return []
        
        print("DEBUG: Clicking unlock button...")
        driver.execute_script("arguments[0].scrollIntoView(true);", unlock_button)
        time.sleep(2)
        
        try:
            unlock_button.click()
        except:
            driver.execute_script("arguments[0].click();", unlock_button)
        
        print("DEBUG: Waiting for content to load...")
        time.sleep(10)  # Wait for links to appear
        
        # Extract ALL links comprehensively
        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"DEBUG: Found {len(all_links)} total links on page")
        
        extracted_links = []
        
        for link in all_links:
            try:
                href = link.get_attribute('href')
                text = link.text.strip()
                
                if href and href.startswith('http'):
                    domain = urlparse(href).netloc
                    
                    # Skip internal site links
                    if any(internal in domain.lower() for internal in ['uptobhai.blog', 'shortlinkto.onl', 'shortlink.to']):
                        continue
                    
                    # Comprehensive download service detection
                    download_services = [
                        'drive.google.com', 'mega.nz', 'mediafire.com', 'dropbox.com', 'onedrive.live.com',
                        'drop.download', 'megaup.net', 'uploadrar.com', 'rapidgator.net', 'nitroflare.com',
                        'turbobit.net', 'uploaded.net', 'katfile.com', 'ddownload.com', 'file-upload.org',
                        'hexupload.net', 'send.cm', 'workupload.com', 'racaty.io', 'krakenfiles.com',
                        'gofile.io', 'pixeldrain.com', 'anonfiles.com', 'zippyshare.com', 'sendspace.com',
                        'filedot.top', 'ranoz.gg', 'uptobox.com', 'filecrypt.cc', 'dailyuploads.net',
                        'upload.ee', 'filerio.in', 'doodstream.com', 'streamtape.com', 'mixdrop.co'
                    ]
                    
                    # Check if it's a known download service
                    is_download_service = any(service in domain.lower() for service in download_services)
                    
                    # Check if URL looks like a download link (has file extension or download patterns)
                    has_file_extension = any(ext in href.lower() for ext in ['.mkv', '.mp4', '.avi', '.zip', '.rar', '.mp3', '.pdf'])
                    has_download_pattern = any(pattern in href.lower() for pattern in ['download', 'file', 'get'])
                    
                    # Check text for download indicators
                    text_indicates_download = text and any(word in text.lower() for word in ['download', 'file', 'drive', 'mega', 'mediafire'])
                    
                    # Determine if this is a download link
                    is_download_link = (
                        is_download_service or 
                        has_file_extension or 
                        (has_download_pattern and len(href) > 20) or
                        text_indicates_download
                    )
                    
                    if is_download_link:
                        # Determine service type and quality
                        service_type = "Unknown"
                        quality = "Unknown"
                        
                        # Identify service type
                        if 'drive.google' in domain:
                            service_type = "Google Drive"
                        elif 'mega.nz' in domain:
                            service_type = "Mega"
                        elif 'mediafire' in domain:
                            service_type = "MediaFire"
                        elif 'dropbox' in domain:
                            service_type = "Dropbox"
                        elif 'onedrive' in domain:
                            service_type = "OneDrive"
                        elif any(service in domain for service in ['upload', 'download', 'file']):
                            service_type = domain.replace('.com', '').replace('.net', '').replace('.org', '').replace('.top', '').replace('.gg', '').title()
                        
                        # Try to extract quality from text or URL
                        quality_indicators = ['480p', '720p', '1080p', '4k', '2160p', 'hd', 'full hd', 'uhd']
                        for q in quality_indicators:
                            if q in text.lower() or q in href.lower():
                                quality = q.upper()
                                break
                        
                        # Try to extract file size
                        file_size = "Unknown"
                        size_patterns = ['gb', 'mb', 'kb']
                        for pattern in size_patterns:
                            if pattern in text.lower():
                                # Try to find number before the size unit
                                import re
                                size_match = re.search(r'(\d+(?:\.\d+)?)\s*' + pattern, text.lower())
                                if size_match:
                                    file_size = size_match.group(0).upper()
                                    break
                        
                        extracted_links.append({
                            'text': text or f'{service_type} Download',
                            'url': href,
                            'host': domain,
                            'service_type': service_type,
                            'quality': quality,
                            'file_size': file_size
                        })
                        
                        print(f"DEBUG: Found download link: {service_type} - {text[:30]}...")
                        
            except Exception as e:
                continue
        
        print(f"DEBUG: Successfully extracted {len(extracted_links)} download links")
        
        # Log the extracted links for debugging
        for i, link in enumerate(extracted_links, 1):
            print(f"DEBUG: Link {i}: {link['service_type']} - {link['url'][:50]}...")
        
        return extracted_links
        
    except Exception as e:
        print(f"DEBUG: Selenium unlock error: {str(e)}")
        return []
    
    finally:
        if driver:
            driver.quit()

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

def resolve_moviezwap_download(download_url):
    """Use Selenium to resolve MoviezWap download.php URL to final download link"""
    driver = None
    try:
        # More robust Chrome options
        options = uc.ChromeOptions()
        options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        # options.add_argument("--disable-javascript")  # Re-enable JavaScript as it might be needed
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        print(f"DEBUG: Creating Chrome driver for MoviezWap resolution")
        driver = uc.Chrome(options=options, version_main=None)
        driver.set_page_load_timeout(20)
        driver.implicitly_wait(10)
        
        print(f"DEBUG: Navigating to download page: {download_url}")
        driver.get(download_url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Check if we're already on a direct download page
        current_url = driver.current_url
        print(f"DEBUG: Current URL after navigation: {current_url}")
        
        # Debug: Print page title and some content to understand the page structure
        try:
            page_title = driver.title
            print(f"DEBUG: Page title: {page_title}")
            
            # Look for all links and buttons on the page for debugging
            all_links = driver.find_elements(By.TAG_NAME, "a")
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            
            print(f"DEBUG: Found {len(all_links)} links and {len(all_buttons)} buttons on page")
            
            # Print ALL links that might be download related (not just first 10)
            for i, link in enumerate(all_links):
                try:
                    link_text = link.text.strip()
                    link_href = link.get_attribute('href')
                    link_onclick = link.get_attribute('onclick')
                    if link_text and ('download' in link_text.lower() or 'server' in link_text.lower() or 'mirror' in link_text.lower() or 'fast' in link_text.lower()):
                        print(f"DEBUG: Link {i}: '{link_text}' -> Href: {link_href} | Onclick: {link_onclick}")
                except:
                    continue
            
            # Also print all buttons
            for i, button in enumerate(all_buttons):
                try:
                    button_text = button.text.strip()
                    button_onclick = button.get_attribute('onclick')
                    if button_text:
                        print(f"DEBUG: Button {i}: '{button_text}' | Onclick: {button_onclick}")
                except:
                    continue
                    
        except Exception as e:
            print(f"DEBUG: Error inspecting page: {str(e)}")
        
        # Check if current URL is already a direct download link (but not download.php)
        if (any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.avi', '.mov']) and 
            'download.php' not in current_url.lower()):
            print(f"DEBUG: Already on direct download URL: {current_url}")
            return current_url
        
        # Look for "Download Servers Below" section and find legitimate download server
        
        # First, try to find the "Download Servers Below" section
        try:
            download_servers_section = driver.find_elements(By.XPATH, "//*[contains(text(), 'Download Servers Below') or contains(text(), 'Download Server')]")
            if download_servers_section:
                print(f"DEBUG: Found 'Download Servers' section")
                
                # Since XPath isn't finding it, let's search through all links we already found
                print(f"DEBUG: XPath search failed, checking all links for moviezzwaphd.xyz URLs")
                
                # Get all links again and check for moviezzwaphd URLs
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for i, link in enumerate(all_links):
                    try:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        
                        # Look for links with moviezzwaphd.xyz and .mp4
                        if href and 'moviezzwaphd.xyz' in href.lower() and any(ext in href.lower() for ext in ['.mp4', '.mkv', '.avi']):
                            print(f"DEBUG: FOUND moviezzwaphd link {i}: Text='{text}', Href='{href}'")
                            
                            # Instead of returning the href, click the link and follow redirects
                            print(f"DEBUG: Clicking the moviezzwaphd link to get final URL...")
                            try:
                                # Store current URL
                                current_url = driver.current_url
                                
                                # Click the link
                                driver.execute_script("arguments[0].click();", link)
                                
                                # Wait for navigation/download to start
                                time.sleep(3)
                                
                                # Check for popup or new window
                                print(f"DEBUG: Checking for popups or new windows...")
                                
                                # Handle potential popup windows
                                try:
                                    # Check if there are multiple windows/tabs
                                    all_windows = driver.window_handles
                                    print(f"DEBUG: Found {len(all_windows)} browser windows/tabs")
                                    
                                    if len(all_windows) > 1:
                                        # Switch to the new window/popup
                                        driver.switch_to.window(all_windows[-1])
                                        popup_url = driver.current_url
                                        print(f"DEBUG: Switched to popup window: {popup_url}")
                                        
                                        # Look for "Continue download" button or similar
                                        continue_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Download')] | //a[contains(text(), 'Continue') or contains(text(), 'Download')]")
                                        
                                        if continue_buttons:
                                            print(f"DEBUG: Found {len(continue_buttons)} continue/download buttons in popup")
                                            for btn in continue_buttons:
                                                btn_text = btn.text.strip()
                                                print(f"DEBUG: Button text: '{btn_text}'")
                                                
                                                # Click the continue download button
                                                driver.execute_script("arguments[0].click();", btn)
                                                time.sleep(3)
                                                
                                                # Check final URL after clicking continue
                                                final_popup_url = driver.current_url
                                                print(f"DEBUG: URL after clicking continue: {final_popup_url}")
                                                
                                                # If this looks like a download URL, return it
                                                if any(ext in final_popup_url.lower() for ext in ['.mp4', '.mkv', '.avi']) or 'moviezzwaphd' in final_popup_url.lower():
                                                    print(f"DEBUG: SUCCESS! Final download URL from popup: {final_popup_url}")
                                                    return final_popup_url
                                        
                                        # If no continue button worked, return the popup URL
                                        if any(ext in popup_url.lower() for ext in ['.mp4', '.mkv', '.avi']) or 'moviezzwaphd' in popup_url.lower():
                                            print(f"DEBUG: SUCCESS! Using popup URL: {popup_url}")
                                            return popup_url
                                
                                except Exception as popup_error:
                                    print(f"DEBUG: Error handling popup: {str(popup_error)}")
                                
                                # Get the final URL after click (main window)
                                final_url = driver.current_url
                                print(f"DEBUG: Main window URL after click: {final_url}")
                                
                                # If URL changed, return the new URL
                                if final_url != current_url:
                                    print(f"DEBUG: SUCCESS! Final URL after click: {final_url}")
                                    return final_url
                                else:
                                    # If URL didn't change, the original href might still be valid
                                    print(f"DEBUG: No URL change, returning original href: {href}")
                                    return href
                                    
                            except Exception as click_error:
                                print(f"DEBUG: Error clicking link: {str(click_error)}")
                                print(f"DEBUG: Fallback to original href: {href}")
                                return href
                            
                    except Exception as e:
                        continue
                
                print(f"DEBUG: No moviezzwaphd links found in all links search")
                        
        except Exception as e:
            print(f"DEBUG: Could not find Download Servers section: {str(e)}")
        
        # Approach 1: Look specifically for legitimate download server buttons (avoid ads)
        download_selectors = [
            "//a[contains(text(), 'Fast Download Server') and not(contains(@href, 'betspintrack') or contains(@href, 'ads') or contains(@onclick, 'betspintrack'))]",
            "//button[contains(text(), 'Fast Download Server') and not(contains(@onclick, 'betspintrack') or contains(@onclick, 'ads'))]",
            "//a[contains(text(), 'Download Server') and not(contains(@href, 'betspintrack') or contains(@href, 'ads') or contains(@onclick, 'betspintrack'))]", 
            "//button[contains(text(), 'Download Server') and not(contains(@onclick, 'betspintrack') or contains(@onclick, 'ads'))]",
            "//a[contains(text(), 'Fast Server') and not(contains(@href, 'betspintrack') or contains(@href, 'ads'))]",
            "//a[contains(text(), 'Server 1') and not(contains(@href, 'betspintrack') or contains(@href, 'ads'))]",
            "//a[contains(text(), 'Server 2') and not(contains(@href, 'betspintrack') or contains(@href, 'ads'))]",
            "//a[contains(text(), 'Mirror 1') and not(contains(@href, 'betspintrack') or contains(@href, 'ads'))]",
            "//a[contains(text(), 'Mirror 2') and not(contains(@href, 'betspintrack') or contains(@href, 'ads'))]",
            "//a[contains(text(), 'Download') and not(contains(@href, 'betspintrack') or contains(@href, 'ads') or contains(@onclick, 'betspintrack') or contains(text(), 'NOW!')) and not(contains(text(), 'Movies')) and not(contains(text(), 'Telegram'))]",
            "//button[contains(text(), 'Download') and not(contains(@onclick, 'betspintrack') or contains(@onclick, 'ads') or contains(text(), 'NOW!'))]",
            "//a[contains(@class, 'btn') and contains(text(), 'Download') and not(contains(@href, 'betspintrack'))]",
            "//button[contains(@class, 'btn') and contains(text(), 'Download') and not(contains(@onclick, 'betspintrack'))]"
        ]
        
        # Try each selector and attempt to click
        for selector in download_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    try:
                        element_text = element.text.strip()
                        element_href = element.get_attribute('href')
                        element_onclick = element.get_attribute('onclick')
                        
                        print(f"DEBUG: Found element - Text: '{element_text}', Href: '{element_href}', Onclick: '{element_onclick}'")
                        
                        # Skip ad elements and non-download links
                        skip_patterns = ['home', 'back', 'contact', 'about', 'telegram', 'betspintrack', 'ads', 'now!']
                        if element_text and any(skip in element_text.lower() for skip in skip_patterns):
                            print(f"DEBUG: Skipping ad/navigation element: {element_text}")
                            continue
                        
                        # Skip elements with ad-related hrefs or onclick
                        if element_href and any(ad in element_href.lower() for ad in ['betspintrack', 'ads', 'popup']):
                            print(f"DEBUG: Skipping ad href: {element_href}")
                            continue
                        
                        if element_onclick and any(ad in element_onclick.lower() for ad in ['betspintrack', 'ads', 'popup']):
                            print(f"DEBUG: Skipping ad onclick: {element_onclick}")
                            continue
                        
                        # Special handling for legitimate download server buttons
                        if element_text and ('download server' in element_text.lower() or 'fast download' in element_text.lower()):
                            print(f"DEBUG: Found legitimate download server button! Text: '{element_text}'")
                            # If href exists and looks like a direct download, return it immediately
                            if element_href and (any(ext in element_href.lower() for ext in ['.mp4', '.mkv', '.avi']) or 'moviezzwaphd' in element_href.lower()):
                                print(f"DEBUG: Download server button has direct download href: {element_href}")
                                return element_href
                            
                        # Try clicking this element
                        print(f"DEBUG: Attempting to click element: {element_text or element_href or 'Unknown'}")
                        
                        # Store current URL before clicking
                        before_click_url = driver.current_url
                        
                        # Click the element
                        driver.execute_script("arguments[0].click();", element)
                        
                        # Wait for potential redirect
                        time.sleep(4)
                        
                        # Check new URL
                        after_click_url = driver.current_url
                        print(f"DEBUG: URL changed from {before_click_url} to {after_click_url}")
                        
                        # Check if we got a direct download URL or download started
                        if after_click_url != before_click_url:
                            if any(ext in after_click_url.lower() for ext in ['.mp4', '.mkv', '.avi', '.mov']):
                                print(f"DEBUG: SUCCESS! Found direct download URL: {after_click_url}")
                                return after_click_url
                            elif 'moviezzwaphd.xyz' in after_click_url or 'moviezwap' in after_click_url:
                                print(f"DEBUG: SUCCESS! Found download URL: {after_click_url}")
                                return after_click_url
                        
                        # Check if download started (URL might not change but download begins)
                        # Look for download indicators in page content or check for blob URLs
                        try:
                            # Check if there are any download links that appeared after clicking
                            download_links_after_click = driver.find_elements(By.XPATH, "//a[contains(@href, '.mp4') or contains(@href, '.mkv') or contains(@href, '.avi') or contains(@href, 'moviezzwaphd') or contains(@href, 'blob:')]")
                            if download_links_after_click:
                                final_url = download_links_after_click[0].get_attribute('href')
                                print(f"DEBUG: SUCCESS! Found download link after Fast Server click: {final_url}")
                                return final_url
                        except Exception as e:
                            print(f"DEBUG: Error checking for download links after click: {str(e)}")
                        
                        # If no redirect, check for new download links on the page
                        new_download_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.mp4') or contains(@href, '.mkv') or contains(@href, '.avi') or contains(@href, 'moviezzwaphd')]")
                        if new_download_links:
                            final_url = new_download_links[0].get_attribute('href')
                            print(f"DEBUG: Found new download link after click: {final_url}")
                            return final_url
                            
                    except Exception as e:
                        print(f"DEBUG: Error with element: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"DEBUG: Selector {selector} failed: {str(e)}")
                continue
        
        # Final approach: Click the "Fast Download Server" link and handle redirects
        print(f"DEBUG: Reached final approach - looking for Fast Download Server link")
        try:
            fast_server_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Fast Download Server')]")
            print(f"DEBUG: Found {len(fast_server_links)} Fast Download Server links")
            
            for i, link in enumerate(fast_server_links):
                href = link.get_attribute('href')
                text = link.text.strip()
                print(f"DEBUG: Fast Download Server link {i}: Text='{text}', Href='{href}'")
                
                if href and (any(ext in href.lower() for ext in ['.mp4', '.mkv', '.avi']) or 'moviezzwaphd' in href.lower()):
                    print(f"DEBUG: FOUND VALID Fast Download Server link: {href}")
                    
                    # Since we already have the direct .mp4 URL, let's return it immediately
                    # The href already contains the final download URL
                    print(f"DEBUG: SUCCESS! Returning Fast Download Server href directly: {href}")
                    return href
                        
        except Exception as e:
            print(f"DEBUG: Error finding Fast Download Server link: {str(e)}")
        
        print(f"DEBUG: No download server button found through selectors - trying final approach")
        
        print(f"DEBUG: No final download URL found")
        return None
        
    except Exception as e:
        print(f"DEBUG: Error resolving MoviezWap download: {str(e)}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
                print(f"DEBUG: Chrome driver closed successfully")
            except Exception as e:
                print(f"DEBUG: Error closing driver: {str(e)}")

@app.route('/download_file')
def download_file():
    """Proxy download endpoint to handle protected links with proper headers"""
    try:
        file_url = request.args.get('url')
        if not file_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        print(f"DEBUG: Proxying download for URL: {file_url}")
        
        # Set proper headers for the request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.moviezwap.pink/',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Make request to the protected URL
        response = requests.get(file_url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            # Extract filename from URL or Content-Disposition header
            filename = None
            if 'Content-Disposition' in response.headers:
                content_disposition = response.headers['Content-Disposition']
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
            
            if not filename:
                # Extract from URL
                filename = file_url.split('/')[-1].split('?')[0]
                if not filename or '.' not in filename:
                    filename = 'movie_download.mp4'
            
            print(f"DEBUG: Serving file as: {filename}")
            
            # Create response with proper download headers
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            return Response(
                generate(),
                headers={
                    'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': response.headers.get('Content-Length', ''),
                    'Cache-Control': 'no-cache'
                }
            )
        else:
            print(f"DEBUG: Failed to fetch file, status: {response.status_code}")
            return jsonify({'error': f'Failed to fetch file: {response.status_code}'}), response.status_code
            
    except Exception as e:
        print(f"DEBUG: Error in download proxy: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
@app.route('/auto_health_results/<extraction_id>')
def get_auto_health_results(extraction_id):
    """Get auto health check results"""
    global health_check_results
    
    if 'health_check_results' not in globals():
        health_check_results = {}
    
    print(f"DEBUG: Checking auto health results for extraction_id: {extraction_id}")
    print(f"DEBUG: Available health results: {list(health_check_results.keys()) if 'health_check_results' in globals() else 'None'}")
    
    if extraction_id in health_check_results:
        return jsonify({
            'results': health_check_results[extraction_id],
            'completed': True
        })
    else:
        # Check if health check is still in progress
        if extraction_id in extraction_results:
            extraction_result = extraction_results[extraction_id]
            if extraction_result.get('health_check_started', False):
                return jsonify({
                    'results': {},
                    'completed': False,
                    'in_progress': True
                })
        
        return jsonify({
            'results': {},
            'completed': False,
            'in_progress': False
        })
