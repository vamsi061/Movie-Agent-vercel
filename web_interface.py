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

def initialize_agents():
    global downloadhub_agent, moviezwap_agent, movierulz_agent
    if downloadhub_agent is None:
        downloadhub_agent = EnhancedDownloadHubAgent()
    if moviezwap_agent is None:
        moviezwap_agent = MoviezWapAgent()
    if movierulz_agent is None:
        movierulz_agent = MovieRulzAgent()
    return downloadhub_agent, moviezwap_agent, movierulz_agent

def clean_text(text):
    """Clean and normalize text for better matching"""
    return ''.join(e for e in text.lower() if e.isalnum() or e.isspace()).strip()

def is_fuzzy_match(input_title, candidate_title, threshold=60):
    """Improved fuzzy matching with lower threshold"""
    if not input_title or not candidate_title:
        return False
    
    # Clean both titles
    clean_input = clean_text(input_title)
    clean_candidate = clean_text(candidate_title)
    
    # Calculate similarity
    similarity = Levenshtein.ratio(clean_input, clean_candidate) * 100
    
    # Also check if input is contained in candidate (for partial matches)
    containment_score = 0
    if clean_input in clean_candidate or clean_candidate in clean_input:
        containment_score = 30
    
    final_score = max(similarity, containment_score)
    return final_score >= threshold

def get_rendered_html(url, wait_time=10):
    """Get rendered HTML using Selenium with undetected Chrome"""
    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        driver = uc.Chrome(options=options)
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(3)
        
        return driver.page_source
        
    except Exception as e:
        logger.error(f"Error getting rendered HTML: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()

def search_movie_on_site(base_url, movie_name):
    """Search for a movie on a specific site"""
    try:
        search_url = f"{base_url}/?s={quote(movie_name)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.text
        
    except Exception as e:
        logger.error(f"Error searching on {base_url}: {str(e)}")
        return None

def parse_movie_info_from_url(url):
    """Extract movie information from URL"""
    try:
        # Parse URL to extract movie info
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        # Extract year using regex
        year_match = re.search(r'(19|20)\d{2}', path)
        year = year_match.group() if year_match else None
        
        # Extract quality
        quality = None
        quality_patterns = ['720p', '1080p', '480p', '4k', 'hd', 'cam', 'ts', 'dvdrip', 'brrip', 'webrip']
        for pattern in quality_patterns:
            if pattern in path:
                quality = pattern.upper()
                break
        
        # Extract language
        language = None
        language_patterns = ['hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'punjabi']
        for lang in language_patterns:
            if lang in path:
                language = lang.title()
                break
        
        return {
            'year': year,
            'quality': quality,
            'language': language
        }
        
    except Exception as e:
        logger.error(f"Error parsing movie info from URL: {str(e)}")
        return {}

def is_relevant_movie_link(url, text, search_movie_name):
    """Check if a link is relevant to the searched movie"""
    if not url or not text:
        return False
    
    # Skip common non-movie links
    skip_patterns = [
        'contact', 'about', 'privacy', 'terms', 'dmca', 'disclaimer',
        'category', 'tag', 'author', 'admin', 'login', 'register',
        'facebook', 'twitter', 'instagram', 'youtube', 'telegram',
        'advertisement', 'ads', 'sponsor'
    ]
    
    url_lower = url.lower()
    text_lower = text.lower()
    
    for pattern in skip_patterns:
        if pattern in url_lower or pattern in text_lower:
            return False
    
    # Check if the link text contains movie-related keywords
    movie_keywords = ['watch', 'download', 'movie', 'film', 'cinema', 'hd', 'quality']
    has_movie_keyword = any(keyword in text_lower for keyword in movie_keywords)
    
    # Check if the link text is similar to the search query
    is_similar = is_fuzzy_match(search_movie_name, text, threshold=40)
    
    return has_movie_keyword or is_similar

def extract_movie_links(html, movie_name, base_url):
    """Extract movie links from HTML content"""
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    movie_links = []
    
    # Find all links
    links = soup.find_all('a', href=True)
    
    for link in links:
        href = link.get('href')
        text = link.get_text(strip=True)
        
        if not href or not text:
            continue
        
        # Convert relative URLs to absolute
        if href.startswith('/'):
            href = urljoin(base_url, href)
        elif not href.startswith('http'):
            continue
        
        # Check if this is a relevant movie link
        if is_relevant_movie_link(href, text, movie_name):
            # Extract additional info
            movie_info = parse_movie_info_from_url(href)
            
            # Look for additional info in the link's parent elements
            parent = link.parent
            if parent:
                parent_text = parent.get_text(strip=True)
                
                # Try to extract file size
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB|KB)', parent_text, re.IGNORECASE)
                size = size_match.group() if size_match else None
                
                if size:
                    movie_info['size'] = size
            
            movie_links.append({
                'title': text,
                'url': href,
                'year': movie_info.get('year'),
                'quality': movie_info.get('quality'),
                'language': movie_info.get('language'),
                'size': movie_info.get('size')
            })
    
    # Remove duplicates and sort by relevance
    unique_links = []
    seen_urls = set()
    
    for link in movie_links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)
    
    # Sort by fuzzy match score with the search query
    unique_links.sort(key=lambda x: is_fuzzy_match(movie_name, x['title'], threshold=0), reverse=True)
    
    return unique_links[:10]  # Return top 10 matches

def extract_video_sources(movie_page_url):
    """Extract video sources from a movie page"""
    try:
        html = get_rendered_html(movie_page_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        video_sources = []
        
        # Look for video tags
        videos = soup.find_all('video')
        for video in videos:
            src = video.get('src')
            if src:
                video_sources.append({
                    'type': 'video',
                    'url': src,
                    'quality': 'Unknown'
                })
        
        # Look for iframe sources (embedded players)
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src')
            if src and any(domain in src for domain in ['youtube', 'vimeo', 'dailymotion', 'streamlare', 'doodstream']):
                video_sources.append({
                    'type': 'iframe',
                    'url': src,
                    'quality': 'Unknown'
                })
        
        # Look for download links
        download_patterns = [
            r'href=["\']([^"\']*\.(?:mp4|mkv|avi|mov|wmv|flv|webm))["\']',
            r'href=["\']([^"\']*(?:download|stream|watch)[^"\']*)["\']'
        ]
        
        for pattern in download_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if match.startswith('http'):
                    video_sources.append({
                        'type': 'download',
                        'url': match,
                        'quality': 'Unknown'
                    })
        
        return video_sources
        
    except Exception as e:
        logger.error(f"Error extracting video sources: {str(e)}")
        return []

def convert_to_embed_url(url):
    """Convert regular video URLs to embeddable URLs"""
    try:
        if 'youtube.com/watch' in url:
            video_id = re.search(r'v=([^&]+)', url)
            if video_id:
                return f"https://www.youtube.com/embed/{video_id.group(1)}"
        elif 'vimeo.com/' in url:
            video_id = re.search(r'vimeo\.com/(\d+)', url)
            if video_id:
                return f"https://player.vimeo.com/video/{video_id.group(1)}"
        
        return url
    except:
        return url

def apply_filters(movies, language_filter, year_filter, quality_filter):
    """Apply filters to movie results"""
    filtered_movies = []
    
    for movie in movies:
        # Language filter
        if language_filter != 'all':
            movie_lang = (movie.get('language') or '').lower()
            if language_filter.lower() not in movie_lang:
                continue
        
        # Year filter
        if year_filter != 'all':
            movie_year = movie.get('year')
            if not movie_year or year_filter not in str(movie_year):
                continue
        
        # Quality filter
        if quality_filter != 'all':
            movie_quality = (movie.get('quality') or '').lower()
            if quality_filter.lower() not in movie_quality:
                continue
        
        filtered_movies.append(movie)
    
    return filtered_movies

def load_site_urls(file_path="movie_sites.txt"):
    """Load movie site URLs from file"""
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return urls
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
        sources = data.get('sources', ['downloadhub', 'moviezwap', 'movierulz'])  # Default to all three sources
        
        if not movie_name:
            return jsonify({'error': 'Movie name is required'}), 400
        
        # Initialize our agents
        downloadhub_agent, moviezwap_agent, movierulz_agent = initialize_agents()
        
        # Get page number from request
        per_page = 10
        
        all_movies = []
        
        # Search DownloadHub (Source 1)
        if 'downloadhub' in sources:
            try:
                logger.info(f"Searching DownloadHub for: {movie_name}")
                downloadhub_results = downloadhub_agent.search_movies(movie_name, page=page, per_page=per_page)
                downloadhub_movies = downloadhub_results.get('movies', [])
                for movie in downloadhub_movies:
                    movie['source'] = 'DownloadHub'
                all_movies.extend(downloadhub_movies)
                logger.info(f"DownloadHub returned {len(downloadhub_movies)} movies")
            except Exception as e:
                logger.error(f"DownloadHub search failed: {str(e)}")
        
        # Search MoviezWap (Source 2)
        if 'moviezwap' in sources:
            try:
                logger.info(f"Searching MoviezWap for: {movie_name}")
                moviezwap_results = moviezwap_agent.search_movies(movie_name, page=page, per_page=per_page)
                moviezwap_movies = moviezwap_results.get('movies', [])
                for movie in moviezwap_movies:
                    movie['source'] = 'MoviezWap'
                all_movies.extend(moviezwap_movies)
                logger.info(f"MoviezWap returned {len(moviezwap_movies)} movies")
            except Exception as e:
                logger.error(f"MoviezWap search failed: {str(e)}")
        
        # Search MovieRulz (Source 3)
        if 'movierulz' in sources:
            try:
                logger.info(f"Searching MovieRulz for: {movie_name}")
                movierulz_results = movierulz_agent.search_movies(movie_name, page=page, per_page=per_page)
                movierulz_movies = movierulz_results.get('movies', [])
                for movie in movierulz_movies:
                    movie['source'] = 'MovieRulz'
                all_movies.extend(movierulz_movies)
                logger.info(f"MovieRulz returned {len(movierulz_movies)} movies")
            except Exception as e:
                logger.error(f"MovieRulz search failed: {str(e)}")
        
        # Apply filters
        filtered_movies = apply_filters(all_movies, language_filter, year_filter, quality_filter)
        
        # Remove duplicates based on title similarity
        unique_movies = []
        for movie in filtered_movies:
            is_duplicate = False
            for existing in unique_movies:
                if is_fuzzy_match(movie.get('title', ''), existing.get('title', ''), threshold=80):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_movies.append(movie)
        
        # Generate search ID for this search
        search_id = f"search_{int(time.time())}"
        search_results[search_id] = unique_movies
        
        # Calculate pagination
        total_movies = len(unique_movies)
        total_pages = max(1, (total_movies + per_page - 1) // per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_movies = unique_movies[start_idx:end_idx]
        
        logger.info(f"Combined search returned {len(unique_movies)} movies from {len(sources)} sources")
        
        return jsonify({
            'search_id': search_id,
            'movies': page_movies,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_movies': total_movies,
                'per_page': per_page
            },
            'filters': {
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
                downloadhub_agent, moviezwap_agent, movierulz_agent = initialize_agents()
                
                if movie_source == 'MoviezWap':
                    agent = moviezwap_agent
                    print(f"DEBUG: Using MoviezWap agent for extraction")
                elif movie_source == 'MovieRulz':
                    agent = movierulz_agent
                    print(f"DEBUG: Using MovieRulz agent for extraction")
                else:
                    agent = downloadhub_agent
                    print(f"DEBUG: Using DownloadHub agent for extraction")
                
                print(f"DEBUG: Agent initialized, extracting from {selected_movie['url']}")
                
                # Extract download links using the appropriate agent
                if movie_source == 'MovieRulz':
                    result = agent.extract_download_links(selected_movie['url'])
                else:
                    result = agent.extract_download_links(selected_movie['url'])
                
                print(f"DEBUG: Extraction completed for {extraction_id}")
                
                # Store result
                extraction_results[extraction_id] = {
                    'status': 'completed',
                    'result': result,
                    'movie': selected_movie
                }
                
            except Exception as e:
                print(f"DEBUG: Extraction failed for {extraction_id}: {str(e)}")
                extraction_results[extraction_id] = {
                    'status': 'error',
                    'error': str(e),
                    'movie': selected_movie
                }
        
        # Initialize extraction status
        extraction_results[extraction_id] = {
            'status': 'processing',
            'progress': 0,
            'movie': selected_movie
        }
        
        # Start background thread
        thread = threading.Thread(target=extract_in_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'extraction_id': extraction_id,
            'status': 'started',
            'message': 'Extraction started in background'
        })
        
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
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
                        link_url = link.get('url', '') if isinstance(link, dict) else str(link)
                        print(f"DEBUG: Auto health check link {i}: {link_url}")
                        
                        # Store basic health info
                        health_results[i] = {
                            'status': 'unknown',
                            'message': 'Auto health check completed',
                            'color': 'yellow'
                        }
                    
                    # Store health results
                    result['auto_health_results'] = health_results
                    print(f"DEBUG: Auto health check completed for extraction_id: {extraction_id}")
                    
                except Exception as e:
                    print(f"DEBUG: Auto health check failed: {str(e)}")
            
            # Mark as started and run in background
            result['health_check_started'] = True
            health_thread = threading.Thread(target=auto_health_check)
            health_thread.daemon = True
            health_thread.start()
            print(f"DEBUG: Auto health check thread started for extraction_id: {extraction_id}")
    
    # Add auto health check flag to response
    if result.get('auto_health_results'):
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
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'error': f'Health check failed: {str(e)}'}), 500

def check_download_link_health(url):
    """Check if a download link is accessible"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            return {
                'status': 'healthy',
                'message': 'Link is accessible',
                'response_code': response.status_code,
                'color': 'green'
            }
        else:
            return {
                'status': 'unhealthy',
                'message': f'HTTP {response.status_code}',
                'response_code': response.status_code,
                'color': 'red'
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'color': 'red'
        }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)