from flask import Flask, render_template, request, jsonify, Response, stream_template, session, redirect, url_for
from flask_cors import CORS
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote
# Selenium imports - disabled for Render deployment
# import undetected_chromedriver as uc
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
import Levenshtein
import base64
import threading
import logging
from agents.enhanced_downloadhub_agent import EnhancedDownloadHubAgent
from agents.moviezwap_agent import MoviezWapAgent
from agents.skysetx_agent import SkySetXAgent
from agents.movierulz_agent import MovieRulzAgent
from agents.telegram_agent import telegram_agent
from agents.movies4u_agent import Movies4UAgent
from agent_manager import AgentManager
from llm_chat_agent import EnhancedLLMChatAgent
from admin_routes import register_admin_routes
from session_manager import session_manager
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())  # For session management
CORS(app)  # Enable CORS for all routes

# Register admin routes for API key management
register_admin_routes(app)

# Global variables for our enhanced backend
search_results = {}
extraction_results = {}
downloadhub_agent = None
moviezwap_agent = None
movierulz_agent = None
skysetx_agent = None
telegram_agent_instance = None
movies4u_agent = None

# Initialize Agent Manager
agent_manager = AgentManager()

# Initialize LLM Chat Agent
llm_chat_agent = None
try:
    # Try to initialize with API key
    together_api_key = '4c5cffacdd859cda65379811c500fa703359c93e1ffdcce5fc1adc17eaaa578e'
    if together_api_key:
        llm_chat_agent = EnhancedLLMChatAgent(together_api_key)
        logger.info("LLM Chat Agent initialized successfully")
    else:
        logger.warning("TOGETHER_API_KEY not found. Chat features will be limited.")
except Exception as e:
    logger.error(f"Failed to initialize LLM Chat Agent: {str(e)}")
    llm_chat_agent = None

def initialize_agents():
    global downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent_instance, movies4u_agent
    
    # Initialize agents through agent manager
    agent_manager.initialize_agents()
    enabled_agents = agent_manager.get_enabled_agents()
    
    # Set global agent variables based on enabled agents
    downloadhub_agent = enabled_agents.get("downloadhub")
    moviezwap_agent = enabled_agents.get("moviezwap")
    movierulz_agent = enabled_agents.get("movierulz")
    skysetx_agent = enabled_agents.get("skysetx")
    telegram_agent_instance = enabled_agents.get("telegram")
    movies4u_agent = enabled_agents.get("movies4u")
    
    return downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent_instance, movies4u_agent

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
    """Get rendered HTML - Selenium disabled for Render deployment"""
    print(f"Warning: Selenium functionality disabled for Render deployment. URL: {url}")
    try:
        # Fallback to simple requests for basic HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text, response.url
    except Exception as e:
        print(f"Error loading page {url}: {e}")
        return None, None

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
    # Get or create session ID for chat history persistence
    user_session_id = session.get('session_id')
    if not user_session_id:
        user_session_id = session_manager.create_session()
        session['session_id'] = user_session_id
        logger.info(f"Created new session for index page: {user_session_id}")
    
    # Get session stats
    session_stats = session_manager.get_session_stats(user_session_id)
    
    return render_template('index.html', 
                         session_id=user_session_id,
                         session_stats=session_stats)

@app.route('/api')
def api():
    return render_template('api/index.html')

@app.route('/search', methods=['POST'])
def search_movie():
    """Enhanced search using multiple sources (DownloadHub + MoviezWap)"""
    try:
        data = request.get_json()
        movie_name = data.get('movie_name', '').strip()
        language_filter = data.get('language_filter', 'all')
        year_filter = data.get('year_filter', 'all')
        quality_filter = data.get('quality_filter', 'all')
        sources = data.get('sources', ['downloadhub', 'moviezwap', 'movierulz', 'skysetx', 'telegram', 'movies4u', 'moviebox'])  # Default to all six sources
        
        if not movie_name:
            return jsonify({'error': 'Movie name is required'}), 400
        
        # Initialize our agents
        downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
        
        # Fetch all results without pagination
        all_results = []
        
        # Search DownloadHub (Source 1)
        if 'downloadhub' in sources:
            try:
                logger.info(f"Searching DownloadHub for: {movie_name}")
                downloadhub_result = downloadhub_agent.search_movies(movie_name)
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
                moviezwap_result = moviezwap_agent.search_movies(movie_name)
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
                movierulz_result = movierulz_agent.search_movies(movie_name)
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
                skysetx_movies = skysetx_agent.search_movies(movie_name)
                # Add source identifier to each movie
                for movie in skysetx_movies:
                    movie['source'] = 'SkySetX'
                    movie['source_color'] = '#9C27B0'  # Purple
                all_results.extend(skysetx_movies)
                logger.info(f"SkySetX returned {len(skysetx_movies)} movies")
            except Exception as e:
                logger.error(f"SkySetX search failed: {str(e)}")

        # Search Telegram (Source 5)
        if 'telegram' in sources and telegram_agent:
            try:
                logger.info(f"Searching Telegram for: {movie_name}")
                # Telegram agent search is synchronous
                telegram_movies = telegram_agent.search_movies(movie_name)

                for movie in telegram_movies:
                    movie['source'] = 'Telegram'
                    movie['source_color'] = '#0088cc'  # Telegram brand color
                    # Prefer deep link to bot which can handle forwarding
                    if movie.get('detail_url'):
                        movie['url'] = movie['detail_url']
                    elif movie.get('bot_username'):
                        movie['url'] = f"https://t.me/{movie['bot_username'].replace('@', '')}"
                    # Fallback: construct from message id if nothing else
                    elif movie.get('telegram_message_id'):
                        movie['url'] = f"telegram://message/{movie['telegram_message_id']}"

                all_results.extend(telegram_movies)
                logger.info(f"Telegram returned {len(telegram_movies)} movies")
            except Exception as e:
                logger.error(f"Telegram search failed: {str(e)}")
        elif 'telegram' in sources and not telegram_agent:
            logger.warning("Telegram search requested but agent not configured")
        
        # Search Movies4U (Source 6)
        if 'movies4u' in sources and movies4u_agent:
            try:
                logger.info(f"Searching Movies4U for: {movie_name}")
                movies4u_result = movies4u_agent.search_movies(movie_name)
                movies4u_movies = movies4u_result['movies']
                # Add source identifier to each movie
                for movie in movies4u_movies:
                    movie['source'] = 'Movies4U'
                    movie['source_color'] = '#E91E63'  # Pink
                all_results.extend(movies4u_movies)
                logger.info(f"Movies4U returned {len(movies4u_movies)} movies")
            except Exception as e:
                logger.error(f"Movies4U search failed: {str(e)}")
        elif 'movies4u' in sources and not movies4u_agent:
            logger.warning("Movies4U search requested but agent not configured")

        # Search MovieBox (Source 7)
        if 'moviebox' in sources:
            try:
                logger.info(f"Searching MovieBox for: {movie_name}")
                moviebox_agent = agent_manager.get_agent('moviebox')
                if moviebox_agent:
                    moviebox_result = moviebox_agent.search_movies(movie_name)
                    moviebox_movies = moviebox_result.get('movies', [])
                    for movie in moviebox_movies:
                        movie['source'] = 'MovieBox'
                        movie['source_color'] = '#3CB371'  # teal/green
                    all_results.extend(moviebox_movies)
                    logger.info(f"MovieBox returned {len(moviebox_movies)} movies")
                else:
                    logger.warning("MovieBox agent not initialized")
            except Exception as e:
                logger.error(f"MovieBox search failed: {str(e)}")
        
        # Return all results without pagination
        total_movies = len(all_results)
        
        # Store results for later use
        search_id = f"search_{int(time.time())}"
        search_results[search_id] = all_results
        
        logger.info(f"Combined search returned {total_movies} movies from {len(sources)} sources")
        
        return jsonify({
            'success': True,
            'search_id': search_id,
            'results': all_results,
            'total': total_movies,
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
                downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
                
                if movie_source == 'MoviezWap':
                    agent = moviezwap_agent
                    print(f"DEBUG: Using MoviezWap agent for extraction")
                elif movie_source == 'MovieRulz':
                    agent = movierulz_agent
                    print(f"DEBUG: Using MovieRulz agent for extraction")
                elif movie_source == 'SkySetX':
                    agent = skysetx_agent
                    print(f"DEBUG: Using SkySetX agent for extraction")
                elif movie_source == 'Movies4U':
                    agent = movies4u_agent
                    print(f"DEBUG: Using Movies4U agent for extraction")
                elif movie_source == 'MovieBox':
                    agent = agent_manager.get_agent('moviebox')
                    print(f"DEBUG: Using MovieBox agent for extraction")
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
                elif movie_source == 'Movies4U':
                    result = agent.extract_download_links(movie_url)
                    print(f"DEBUG: Movies4U extraction completed")
                elif movie_source == 'MovieBox':
                    result = agent.get_download_links(movie_url)
                    print(f"DEBUG: MovieBox extraction completed")
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
@app.route('/api/check_link_health', methods=['POST'])
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
@app.route('/api/check_multiple_links_health', methods=['POST'])
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
@app.route('/api/unlock_shortlink', methods=['POST'])
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

@app.route('/check_links_health', methods=['POST'])
def check_links_health():
    """Check health status of multiple download links and prioritize Gofile"""
    try:
        data = request.get_json()
        links = data.get('links', [])
        
        if not links:
            return jsonify({'error': 'No links provided'}), 400
        
        print(f"DEBUG: Checking health of {len(links)} links")
        
        # Initialize SkySetX agent for health checking
        skysetx_agent = SkySetXAgent()
        
        # First, filter and prioritize Gofile links
        filter_result = skysetx_agent.filter_and_prioritize_gofile_links(links)
        filtered_links = filter_result['filtered_links']
        has_gofile = filter_result['has_gofile']
        hidden_count = filter_result['hidden_count']
        hidden_links = filter_result.get('hidden_links', [])
        
        # Check health of filtered links
        enhanced_links = skysetx_agent.check_multiple_links_health(filtered_links)
        
        print(f"DEBUG: Health check complete. Priority links: {sum(1 for link in enhanced_links if link.get('is_priority'))}")
        print(f"DEBUG: Working links: {sum(1 for link in enhanced_links if link.get('is_working'))}")
        print(f"DEBUG: Gofile prioritization: {has_gofile}, Hidden links: {hidden_count}")
        
        return jsonify({
            'status': 'success',
            'enhanced_links': enhanced_links,
            'total_links': len(enhanced_links),
            'priority_count': sum(1 for link in enhanced_links if link.get('is_priority')),
            'working_count': sum(1 for link in enhanced_links if link.get('is_working')),
            'has_gofile_priority': has_gofile,
            'hidden_links_count': hidden_count,
            'hidden_links': hidden_links if not has_gofile else []
        })
        
    except Exception as e:
        print(f"DEBUG: Health check failed: {str(e)}")
        return jsonify({'error': f'Health check failed: {str(e)}'}), 500

@app.route('/api/resolve_taazabull', methods=['POST'])
def resolve_taazabull():
    """Resolve taazabull24.com links on-demand when user clicks"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url or 'taazabull24.com' not in url.lower():
            return jsonify({'error': 'Invalid taazabull24.com URL'}), 400
        
        logger.info(f"On-demand taazabull resolution requested for: {url}")
        
        # Use the DownloadHub agent's taazabull resolution method
        from agents.enhanced_downloadhub_agent import EnhancedDownloadHubAgent
        agent = EnhancedDownloadHubAgent()
        
        # Resolve the taazabull link
        resolved_url = agent.resolve_taazabull_link(url)
        
        if resolved_url and resolved_url != url:
            logger.info(f"Successfully resolved taazabull link: {url} -> {resolved_url}")
            return jsonify({
                'success': True,
                'original_url': url,
                'resolved_url': resolved_url
            })
        else:
            logger.warning(f"Could not resolve taazabull link: {url}")
            return jsonify({
                'success': False,
                'original_url': url,
                'error': 'Could not resolve the taazabull24.com link'
            })
        
    except Exception as e:
        logger.error(f"Error resolving taazabull link: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/resolve_download', methods=['POST'])
@app.route('/api/resolve_download', methods=['POST'])
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
            downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
            
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
            downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
            
            # Selenium disabled for Render deployment
            print(f"DEBUG: Selenium not available for protected link handling (Render deployment)")
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
    Selenium disabled for Render deployment - return empty list
    """
    print(f"DEBUG: Selenium unlock disabled for Render deployment. URL: {shortlink_url}")
    return []

def extract_video_sources_aggressive(movie_page_url):
    """Selenium disabled for Render deployment - return empty list"""
    print(f"DEBUG: Selenium video extraction disabled for Render deployment. URL: {movie_page_url}")
    return []

def resolve_moviezwap_download(download_url):
    """Selenium disabled for Render deployment - return None"""
    print(f"DEBUG: Selenium MoviezWap resolution disabled for Render deployment. URL: {download_url}")
    return None

@app.route('/download_file')
def download_file():
    """Proxy download endpoint to handle protected links with proper headers and Range support"""
    try:
        file_url = request.args.get('url')
        if not file_url:
            return jsonify({'error': 'No URL provided'}), 400

        # For DownloadHub/HDHub4u/Taazabull/HubDrive links, open in new tab instead of downloading
        if any(host in file_url.lower() for host in ['downloadhub', 'hdhub4u', 'taazabull', 'hubdrive']):
            logger.info(f"DownloadHub link detected, opening in new tab: {file_url}")
            return f'''
            <html>
            <head><title>Opening Link...</title></head>
            <body>
                <script>
                    window.open('{file_url}', '_blank');
                    window.close();
                </script>
                <p>Opening link in new tab... <a href="{file_url}" target="_blank">Click here if it doesn't open automatically</a></p>
            </body>
            </html>
            ''', 200, {'Content-Type': 'text/html'}

        print(f"DEBUG: Proxying download for URL: {file_url}")

        parsed = urlparse(file_url)
        referer_host = f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else 'https://www.moviezwap.pink/'
        # Prefer file host as referer for hosts like moviezzwaphd; fallback to MoviezWap
        default_referer = 'https://www.moviezwap.pink/'
        referer = referer_host if 'moviezzwaphd' in (parsed.netloc or '') else default_referer

        # Pass through Range header if present for resumable/partial downloads
        client_range = request.headers.get('Range')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'identity',  # avoid gzip for easier streaming of ranges
            'Connection': 'close',  # Use close instead of keep-alive for better reliability
            'Referer': referer,
            'Origin': default_referer.rstrip('/'),
        }
        if client_range:
            headers['Range'] = client_range

        # Try multiple times with different approaches
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"DEBUG: Attempt {attempt + 1} to download from {file_url}")
                
                # Make request to the protected URL with shorter timeout
                upstream = requests.get(file_url, headers=headers, stream=True, timeout=30, allow_redirects=True)
                upstream.raise_for_status()
                
                # Determine filename
                filename = None
                cd = upstream.headers.get('Content-Disposition', '')
                if 'filename=' in cd:
                    filename = cd.split('filename=')[1].strip('"')
                if not filename:
                    filename = parsed.path.split('/')[-1] or 'movie_download.mp4'

                print(f"DEBUG: Upstream responded {upstream.status_code}, filename={filename}")

                # For moviezzwaphd URLs, redirect directly instead of proxying
                if 'moviezzwaphd' in file_url.lower():
                    print(f"DEBUG: MoviezzWapHD URL detected, redirecting directly to avoid proxy issues")
                    upstream.close()  # Close the connection
                    return redirect(file_url, code=302)

                # Stream response back to client
                def generate():
                    try:
                        for chunk in upstream.iter_content(chunk_size=1024 * 128):  # Smaller chunks for better reliability
                            if chunk:
                                yield chunk
                    except Exception as stream_err:
                        print(f"DEBUG: Upstream stream error: {stream_err}")
                        raise

                status = upstream.status_code if upstream.status_code in (200, 206) else 200
                resp_headers = {
                    'Content-Type': upstream.headers.get('Content-Type', 'application/octet-stream'),
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Cache-Control': 'no-cache',
                }
                # Propagate size and range headers when available
                if upstream.headers.get('Content-Length'):
                    resp_headers['Content-Length'] = upstream.headers['Content-Length']
                if upstream.headers.get('Accept-Ranges'):
                    resp_headers['Accept-Ranges'] = upstream.headers['Accept-Ranges']
                if upstream.status_code == 206 and upstream.headers.get('Content-Range'):
                    resp_headers['Content-Range'] = upstream.headers['Content-Range']

                return Response(generate(), status=status, headers=resp_headers)
                
            except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
                print(f"DEBUG: Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"DEBUG: Retrying in 2 seconds...")
                    time.sleep(2)
                    continue
                else:
                    print(f"DEBUG: All proxy attempts failed, redirecting directly")
                    return redirect(file_url, code=302)
                    
            except requests.exceptions.Timeout as e:
                print(f"DEBUG: Timeout on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"DEBUG: Retrying with shorter timeout...")
                    continue
                else:
                    print(f"DEBUG: All proxy attempts timed out, redirecting directly")
                    return redirect(file_url, code=302)

    except requests.exceptions.RequestException as e:
        # As a last resort, try redirecting the client to the file URL
        print(f"DEBUG: Error in download proxy (requests): {e}")
        print(f"DEBUG: Redirecting directly to file URL as fallback")
        return redirect(file_url, code=302)
    except Exception as e:
        print(f"DEBUG: Error in download proxy: {str(e)}")
        print(f"DEBUG: Redirecting directly to file URL as fallback")
        return redirect(file_url, code=302)

# Removed duplicate main block - admin routes are below
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

# Admin Panel Routes

def _admin_guard():
    try:
        return session.get('admin_logged_in') is True
    except Exception:
        return False

@app.route('/admin')
def admin_panel():
    """Redirect to blueprint admin panel (session-protected)"""
    if not _admin_guard():
        return redirect(url_for('admin.login'))
    return redirect(url_for('admin.admin_panel'))

# Removed duplicate /api route - using the one that serves api/index.html with Filter by Source

@app.route('/admin/agents', methods=['GET'])
@app.route('/api/agents', methods=['GET'])
def get_agent_configuration():
    """Get the current agent configuration"""
    try:
        config = agent_manager.get_configuration()
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting agent configuration: {str(e)}")
        return jsonify({'error': 'Failed to get agent configuration'}), 500

@app.route('/admin/agents/toggle', methods=['POST'])
@app.route('/api/agents/toggle', methods=['POST'])
def toggle_agent():
    """Toggle an agent's enabled state"""
    try:
        data = request.get_json()
        agent_key = data.get('agent')
        enabled = data.get('enabled', False)
        
        if not agent_key:
            return jsonify({'error': 'Agent key is required'}), 400
        
        success = agent_manager.toggle_agent(agent_key, enabled)
        if success:
            # Reinitialize global agents
            initialize_agents()
            return jsonify({'success': True, 'message': f'Agent {agent_key} {"enabled" if enabled else "disabled"}'})
        else:
            return jsonify({'error': 'Failed to toggle agent'}), 500
            
    except Exception as e:
        logger.error(f"Error toggling agent: {str(e)}")
        return jsonify({'error': 'Failed to toggle agent'}), 500

@app.route('/admin/agents/enable-all', methods=['POST'])
@app.route('/api/agents/enable-all', methods=['POST'])
def enable_all_agents():
    """Enable all agents"""
    try:
        agent_manager.enable_all_agents()
        initialize_agents()
        return jsonify({'success': True, 'message': 'All agents enabled'})
    except Exception as e:
        logger.error(f"Error enabling all agents: {str(e)}")
        return jsonify({'error': 'Failed to enable all agents'}), 500

@app.route('/admin/agents/disable-all', methods=['POST'])
@app.route('/api/agents/disable-all', methods=['POST'])
def disable_all_agents():
    """Disable all agents"""
    try:
        agent_manager.disable_all_agents()
        initialize_agents()
        return jsonify({'success': True, 'message': 'All agents disabled'})
    except Exception as e:
        logger.error(f"Error disabling all agents: {str(e)}")
        return jsonify({'error': 'Failed to disable all agents'}), 500

@app.route('/admin/agents/save', methods=['POST'])
@app.route('/api/agents/save', methods=['POST'])
def save_agent_configuration():
    """Save the current agent configuration"""
    try:
        agent_manager.save_configuration()
        return jsonify({'success': True, 'message': 'Configuration saved'})
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/admin/agents/stats', methods=['GET'])
@app.route('/api/agents/stats', methods=['GET'])
def get_agent_stats():
    """Get agent statistics"""
    try:
        stats = agent_manager.get_agent_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting agent stats: {str(e)}")
        return jsonify({'error': 'Failed to get agent stats'}), 500

@app.route('/admin/agents/update-url', methods=['POST'])
@app.route('/api/agents/update-url', methods=['POST'])
def update_agent_url():
    """Update an agent's URL configuration"""
    try:
        data = request.get_json()
        agent_key = data.get('agent')
        base_url = data.get('base_url')
        search_url = data.get('search_url')
        
        if not agent_key or not base_url:
            return jsonify({'error': 'Agent key and base URL are required'}), 400
        
        success = agent_manager.update_agent_url(agent_key, base_url, search_url)
        if success:
            # Reinitialize global agents
            initialize_agents()
            # Return updated URLs so the UI can display exact values stored server-side
            updated_urls = agent_manager.get_agent_url(agent_key)
            return jsonify({'success': True, 'message': f'URLs updated for {agent_key}', 'urls': updated_urls})
        else:
            return jsonify({'error': 'Failed to update agent URLs'}), 500
            
    except Exception as e:
        logger.error(f"Error updating agent URLs: {str(e)}")
        return jsonify({'error': 'Failed to update agent URLs'}), 500

@app.route('/admin/agents/<agent_key>/urls', methods=['GET'])
@app.route('/api/agents/<agent_key>/urls', methods=['GET'])
def get_agent_urls(agent_key):
    """Get an agent's URL configuration"""
    try:
        urls = agent_manager.get_agent_url(agent_key)
        return jsonify(urls)
    except Exception as e:
        logger.error(f"Error getting agent URLs: {str(e)}")
        return jsonify({'error': 'Failed to get agent URLs'}), 500

# Chat Routes
@app.route('/cancel_extraction', methods=['POST'])
def cancel_extraction():
    """Cancel an active extraction"""
    try:
        data = request.get_json()
        extraction_id = data.get('extraction_id')
        
        if not extraction_id:
            return jsonify({'error': 'Extraction ID is required'}), 400
        
        # Set the stop flag
        if extraction_id in extraction_stop_flags:
            extraction_stop_flags[extraction_id] = True
            logger.info(f"Cancellation requested for extraction {extraction_id}")
            
            # Update the extraction result to show cancellation
            if extraction_id in extraction_results:
                extraction_results[extraction_id].update({
                    'status': 'cancelled',
                    'message': 'Extraction cancelled by user'
                })
            
            return jsonify({
                'success': True,
                'message': f'Extraction {extraction_id} cancelled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Extraction {extraction_id} not found or already completed'
            })
            
    except Exception as e:
        logger.error(f"Error cancelling extraction: {str(e)}")
        return jsonify({'error': f'Failed to cancel extraction: {str(e)}'}), 500

@app.route('/cancel_all_extractions', methods=['POST'])
def cancel_all_extractions():
    """Cancel all active extractions"""
    try:
        cancelled_count = 0
        
        # Cancel all active extractions
        for extraction_id in list(extraction_stop_flags.keys()):
            extraction_stop_flags[extraction_id] = True
            cancelled_count += 1
            
            # Update the extraction result to show cancellation
            if extraction_id in extraction_results:
                extraction_results[extraction_id].update({
                    'status': 'cancelled',
                    'message': 'Extraction cancelled by user'
                })
        
        logger.info(f"Cancelled {cancelled_count} active extractions")
        
        return jsonify({
            'success': True,
            'message': f'Cancelled {cancelled_count} active extractions'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling all extractions: {str(e)}")
        return jsonify({'error': f'Failed to cancel extractions: {str(e)}'}), 500

@app.route('/chat')
def chat_interface():
    """Render the chat interface"""
    return render_template('chat.html')

@app.route('/telegram')
def telegram_interface():
    """Render the Telegram bot interface"""
    return render_template('telegram.html')


@app.route('/extract', methods=['POST'])
def extract_from_chat():
    """Handle extraction requests from chat interface"""
    try:
        data = request.get_json()
        movie_title = data.get('movie_title')
        movie_url = data.get('movie_url')
        movie_source = data.get('movie_source')
        
        if not all([movie_title, movie_url, movie_source]):
            return jsonify({'error': 'Missing required movie information'}), 400
        
        # Generate extraction ID
        import time
        extraction_id = f"extract_{int(time.time() * 1000)}"
        
        # Start extraction in background
        def extract_links():
            try:
                # Initialize agents
                downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
                
                # Determine which agent to use
                agent = None
                if movie_source == 'DownloadHub':
                    agent = downloadhub_agent
                elif movie_source == 'MoviezWap':
                    agent = moviezwap_agent
                elif movie_source == 'MovieRulz':
                    agent = movierulz_agent
                elif movie_source == 'SkySetX':
                    agent = skysetx_agent
                elif movie_source == 'Movies4U':
                    agent = movies4u_agent
                elif movie_source == 'Telegram':
                    agent = telegram_agent
                
                if not agent:
                    extraction_results[extraction_id] = {
                        'status': 'failed',
                        'error': f'Agent not available for {movie_source}',
                        'download_links': []
                    }
                    return
                
                # Extract download links
                if movie_source == 'SkySetX':
                    result = agent.get_download_links(movie_url)
                elif movie_source == 'Telegram':
                    result = agent.get_download_links(movie_url)
                else:
                    result = agent.extract_download_links(movie_url)
                
                # Store results
                extraction_results[extraction_id] = {
                    'status': 'completed',
                    'movie_title': movie_title,
                    'movie_url': movie_url,
                    'movie_source': movie_source,
                    'download_links': result.get('download_links', []) if isinstance(result, dict) else result,
                    'timestamp': time.time()
                }
                
            except Exception as e:
                logger.error(f"Extraction failed for {extraction_id}: {str(e)}")
                extraction_results[extraction_id] = {
                    'status': 'failed',
                    'error': str(e),
                    'download_links': []
                }
        
        # Start extraction in background thread
        import threading
        thread = threading.Thread(target=extract_links)
        thread.daemon = True
        thread.start()
        
        # Store initial status
        extraction_results[extraction_id] = {
            'status': 'processing',
            'movie_title': movie_title,
            'movie_source': movie_source
        }
        
        return jsonify({
            'success': True,
            'extraction_id': extraction_id,
            'message': 'Extraction started'
        })
        
    except Exception as e:
        logger.error(f"Chat extraction error: {str(e)}")
        return jsonify({'error': 'Failed to start extraction'}), 500

@app.route('/extraction-results')
def extraction_results_page():
    """Show extraction results page"""
    extraction_id = request.args.get('id')
    if not extraction_id or extraction_id not in extraction_results:
        return render_template('error.html', error='Extraction not found'), 404
    
    result = extraction_results[extraction_id]
    return render_template('extraction_results.html', 
                         extraction_id=extraction_id,
                         result=result)

@app.route('/enhanced_chat_extract', methods=['POST'])
def enhanced_chat_extract():
    """Enhanced chat extraction endpoint for modal"""
    try:
        data = request.get_json()
        movie_title = data.get('movie_title')
        movie_url = data.get('movie_url')
        movie_source = data.get('movie_source')
        
        if not movie_title or not movie_url or not movie_source:
            return jsonify({'error': 'Movie title, URL, and source are required'}), 400
        
        extraction_id = f"chat_extract_{int(time.time())}"
        
        # Initialize extraction status
        extraction_results[extraction_id] = {
            'status': 'processing',
            'progress': 0
        }
        
        # Start extraction in background
        def extract_in_background_chat():
            try:
                print(f"DEBUG: Starting enhanced chat extraction for {extraction_id}")
                
                # Determine which agent to use based on movie source
                downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
                
                if movie_source == 'MoviezWap':
                    agent = moviezwap_agent
                    print(f"DEBUG: Using MoviezWap agent for extraction")
                elif movie_source == 'MovieRulz':
                    agent = movierulz_agent
                    print(f"DEBUG: Using MovieRulz agent for extraction")
                elif movie_source == 'SkySetX':
                    agent = skysetx_agent
                    print(f"DEBUG: Using SkySetX agent for extraction")
                elif movie_source == 'Movies4U':
                    agent = movies4u_agent
                    print(f"DEBUG: Using Movies4U agent for extraction")
                elif movie_source == 'MovieBox':
                    agent = agent_manager.get_agent('moviebox')
                    print(f"DEBUG: Using MovieBox agent for extraction")
                else:
                    agent = downloadhub_agent
                    print(f"DEBUG: Using DownloadHub agent for extraction")
                
                print(f"DEBUG: Agent initialized, extracting from {movie_url}")
                
                # Validate agent before extraction
                if not agent:
                    print(f"DEBUG: Agent is None for {movie_source}, cannot extract from {movie_url}")
                    extraction_results[extraction_id] = {
                        'status': 'error',
                        'message': f'Agent for {movie_source} is disabled. Please enable it in admin panel.',
                        'links': []
                    }
                    return
                
                # Use appropriate method based on agent type
                if movie_source == 'MovieRulz':
                    result = agent.extract_download_links(movie_url)
                elif movie_source == 'SkySetX':
                    result = agent.get_download_links(movie_url)
                elif movie_source == 'Movies4U':
                    result = agent.extract_download_links(movie_url)
                elif movie_source == 'MovieBox':
                    result = agent.get_download_links(movie_url)
                else:
                    result = agent.get_download_links(movie_url)
                
                print(f"DEBUG: Extraction completed for {extraction_id} with {len(result) if result else 0} links")
                
                # Normalize result format - preserve full result structure for MovieBox
                if isinstance(result, dict) and 'download_links' in result:
                    # For structured results (like MovieBox), preserve the full structure
                    extraction_results[extraction_id] = {
                        'status': 'completed',
                        'movie_title': movie_title,
                        'movie_url': movie_url,
                        'movie_source': movie_source,
                        'result': result,  # Store full result with all metadata
                        'timestamp': time.time()
                    }
                else:
                    # For simple list results, wrap in structure
                    download_links = result if isinstance(result, list) else []
                    extraction_results[extraction_id] = {
                        'status': 'completed',
                        'movie_title': movie_title,
                        'movie_url': movie_url,
                        'movie_source': movie_source,
                        'result': {'download_links': download_links},
                        'timestamp': time.time()
                    }
            except Exception as e:
                print(f"DEBUG: Extraction failed for {extraction_id} in chat: {str(e)}")
                extraction_results[extraction_id] = {
                    'status': 'failed',
                    'error': str(e),
                    'result': []
                }

        import threading
        thread = threading.Thread(target=extract_in_background_chat)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'extraction_id': extraction_id,
            'message': 'Extraction started'
        })
        
    except Exception as e:
        logger.error(f"Enhanced chat extraction failed: {str(e)}")
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500

@app.route('/chat', methods=['POST'])
def chat_with_ai():
    """Handle chat messages with AI"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        conversation_history = data.get('conversation_history', [])
        direct_search = data.get('direct_search', False)  # Flag for direct movie searches
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        if not llm_chat_agent:
            # Fallback response when LLM is not available
            return jsonify({
                'success': True,
                'response': "I'm sorry, but the AI chat feature is currently unavailable. You can still search for movies using the main search page!",
                'movie_results': [],
                'suggestions': ["Try the main search page", "Search for specific movie titles"],
                'conversation_history': conversation_history
            })
        
        # Get or create session ID
        user_session_id = session.get('session_id')
        if not user_session_id:
            user_session_id = session_manager.create_session()
            session['session_id'] = user_session_id
            logger.info(f"Created new session for user: {user_session_id}")
        
        # Validate session is still active
        session_data = session_manager.get_session(user_session_id)
        if not session_data:
            # Session expired, create new one
            user_session_id = session_manager.create_session()
            session['session_id'] = user_session_id
            logger.info(f"Session expired, created new session: {user_session_id}")
        
        # Use enhanced movie request processing with session context
        if direct_search:
            # For direct searches (movie chip clicks), bypass LLM analysis and search directly
            logger.info(f"Direct search requested for: {user_message}")
            search_result = llm_chat_agent.search_movies_with_sources(user_message, [user_message])
            # Create a simple response structure for direct searches
            if search_result.get('movies'):
                result = {
                    'response_text': f"Found results for '{user_message}':",
                    'movies': search_result.get('movies', []),
                    'search_performed': True,
                    'intent': {
                        'intent_type': 'movie_request',
                        'movie_details': {'movie_titles': [user_message]},
                        'user_intent_analysis': {'is_specific_movie': True}
                    }
                }
            else:
                result = {
                    'response_text': f"Sorry, I couldn't find '{user_message}' in our download sources. The movie might not be available yet or could have a different title spelling.",
                    'movies': [],
                    'search_performed': True,
                    'intent': {
                        'intent_type': 'movie_request',
                        'movie_details': {'movie_titles': []},
                        'user_intent_analysis': {'is_specific_movie': True}
                    }
                }
        else:
            # Normal chat processing with LLM analysis
            result = llm_chat_agent.process_movie_request(user_message, session_id=user_session_id)
        
        # Add conversation to session memory
        session_manager.add_conversation(
            user_session_id, 
            user_message, 
            result.get('response_text', ''),
            result.get('movies', [])
        )

        # If a specific movie was identified, set movie context for follow-ups like "yes"
        try:
            intent = result.get('intent', {})
            details = intent.get('movie_details', {})
            research = details.get('movie_research', {})
            specific = intent.get('user_intent_analysis', {}).get('is_specific_movie', False)
            top_movie = (result.get('movies') or [{}])[0]
            if specific and (research.get('full_title') or top_movie.get('title')):
                session_manager.set_movie_context(user_session_id, {
                    'title': research.get('full_title') or top_movie.get('title'),
                    'year': research.get('release_year') or top_movie.get('year'),
                    'source': top_movie.get('source'),
                    'url': top_movie.get('url') or top_movie.get('detail_url')
                })
        except Exception:
            pass
        
        # Extract data from result
        intent = result.get('intent', {})
        movies = result.get('movies', [])
        search_performed = result.get('search_performed', False)
        response_text = result.get('response_text', '')
        
        # Store movie titles for frontend to create movie selection chips
        movie_details = intent.get('movie_details', {})
        movie_titles = movie_details.get('movie_titles', [])
        
        if movie_titles and len(movie_titles) > 0:
            logger.info(f"Movie titles available for frontend selection: {movie_titles}")
            # The frontend will handle creating the selection UI using the intent data
        
        # Log for debugging
        if search_performed:
            logger.info(f"Chat: Found {len(movies)} movies for user request")
        
        # Get session stats
        session_stats = session_manager.get_session_stats(user_session_id)
        
        # Return enhanced response with movies and session info
        return jsonify({
            'success': True,
            'response': response_text,
            'movie_results': movies,
            'search_performed': search_performed,
            'intent_type': intent.get('intent_type', 'unknown'),
            'intent': intent,  # Include full intent data for movie selection buttons
            'session_info': {
                'session_id': user_session_id,
                'conversation_count': session_stats.get('conversation_count', 0),
                'time_remaining_minutes': session_stats.get('time_remaining_minutes', 15)
            },
            'conversation_history': conversation_history + [
                {'role': 'user', 'content': user_message},
                {'role': 'assistant', 'content': response_text}
            ]
        })
        
        # OLD CODE BELOW - keeping for reference but not executing
        if False:  # This block won't execute
            search_queries = []
            if intent.get('intent_type') == 'movie_request':
                # Check if this is a specific movie request
                user_analysis = intent.get("user_intent_analysis", {})
                is_specific_movie = user_analysis.get("is_specific_movie", False)
            
            if is_specific_movie:
                # For specific movies, use multiple search variations
                search_variations = llm_chat_agent.get_search_variations(intent)
                search_queries = search_variations[:3]  # Use top 3 variations
                logger.info(f"Specific movie request - using search variations: {search_queries}")
            else:
                # For general requests, use single optimized query
                search_query = llm_chat_agent.extract_movie_search_query(intent)
                search_queries = [search_query]
                logger.info(f"General movie request - using search query: {search_query}")
        else:
            # For non-movie requests, no search needed
            search_queries = []
        
        # Search for movies
        movie_results = []
        
        if search_queries:
            try:
                # Initialize agents
                downloadhub_agent, moviezwap_agent, movierulz_agent, skysetx_agent, telegram_agent, movies4u_agent = initialize_agents()
                
                # Search for each query
                all_results = []
                
                for search_query in search_queries:
                    logger.info(f"Searching for: {search_query}")
                    
                    # Search MoviezWap
                    if moviezwap_agent:
                        try:
                            moviezwap_result = moviezwap_agent.search_movies(search_query)
                            moviezwap_movies = moviezwap_result['movies'][:2]  # Limit per query
                            for movie in moviezwap_movies:
                                movie['source'] = 'MoviezWap'
                            all_results.extend(moviezwap_movies)
                        except Exception as e:
                            logger.error(f"MoviezWap search failed for '{search_query}': {str(e)}")
                    
                    # Search MovieRulz
                    if movierulz_agent:
                        try:
                            movierulz_result = movierulz_agent.search_movies(search_query)
                            movierulz_movies = movierulz_result['movies'][:2]  # Limit per query
                            for movie in movierulz_movies:
                                movie['source'] = 'MovieRulz'
                            all_results.extend(movierulz_movies)
                        except Exception as e:
                            logger.error(f"MovieRulz search failed for '{search_query}': {str(e)}")
                    
                    # Search SkySetX
                    if skysetx_agent:
                        try:
                            skysetx_movies = skysetx_agent.search_movies(search_query, limit=2)
                            for movie in skysetx_movies:
                                movie['source'] = 'SkySetX'
                            all_results.extend(skysetx_movies)
                        except Exception as e:
                            logger.error(f"SkySetX search failed for '{search_query}': {str(e)}")
                
                # FILTER RESULTS FOR SPECIFIC MOVIE REQUESTS
                if user_analysis.get("is_specific_movie", False):
                    movie_research = intent.get("movie_details", {}).get("movie_research", {})
                    target_title = movie_research.get("full_title", "")
                    target_year = movie_research.get("release_year", "")
                    
                    logger.info(f"Filtering results for specific movie: {target_title} ({target_year})")
                    
                    # Filter results to only show movies that match the specific request
                    filtered_results = []
                    for movie in all_results:
                        movie_title = movie.get('title', '').lower()
                        movie_year = str(movie.get('year', ''))
                        
                        # Check if this movie matches the target
                        title_match = (target_title.lower() in movie_title or 
                                     movie_title in target_title.lower() or
                                     any(alt.lower() in movie_title for alt in movie_research.get("alternate_names", [])))
                        
                        year_match = (not target_year or target_year in movie_year or movie_year in target_year)
                        
                        if title_match and year_match:
                            logger.info(f"MATCH: {movie.get('title')} ({movie.get('year')}) from {movie.get('source')}")
                            filtered_results.append(movie)
                        else:
                            logger.info(f"FILTERED OUT: {movie.get('title')} ({movie.get('year')}) - no match for {target_title}")
                    
                    # Remove duplicates from filtered results
                    deduplicated_results = []
                    seen_movies = set()
                    
                    for movie in filtered_results:
                        # Create a unique identifier for the movie
                        movie_key = f"{movie.get('title', '').lower().strip()}_{movie.get('year', '')}"
                        
                        if movie_key not in seen_movies:
                            seen_movies.add(movie_key)
                            deduplicated_results.append(movie)
                            logger.info(f"KEPT: {movie.get('title')} ({movie.get('year')}) from {movie.get('source')}")
                        else:
                            logger.info(f"DUPLICATE REMOVED: {movie.get('title')} ({movie.get('year')}) from {movie.get('source')}")
                    
                    movie_results = deduplicated_results[:5]  # Show top 5 unique matches for specific movies
                    logger.info(f"After deduplication: {len(movie_results)} unique specific movie matches")
                else:
                    # Remove duplicates from general results too
                    deduplicated_results = []
                    seen_movies = set()
                    
                    for movie in all_results:
                        movie_key = f"{movie.get('title', '').lower().strip()}_{movie.get('year', '')}"
                        
                        if movie_key not in seen_movies:
                            seen_movies.add(movie_key)
                            deduplicated_results.append(movie)
                    
                    movie_results = deduplicated_results[:10]  # Limit total unique results for general requests
                
            except Exception as e:
                logger.error(f"Movie search failed in chat: {str(e)}")
                movie_results = []
        
        # Generate AI response AFTER search is complete (synchronized)
        ai_response = llm_chat_agent.generate_contextual_response(user_message, intent, movie_results)
        
        # Generate search suggestions for movie requests with no results
        suggestions = []
        if intent.get('intent_type') == 'movie_request' and len(movie_results) == 0:
            suggestions = llm_chat_agent.generate_search_suggestions(user_message)
        
        # Determine the primary search query for frontend display
        primary_search_query = ""
        if search_queries:
            primary_search_query = search_queries[0]
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'movie_results': movie_results,
            'search_query': primary_search_query,
            'search_queries_used': search_queries,  # Show all queries used
            'suggestions': suggestions,
            'conversation_history': llm_chat_agent.conversation_history[-10:]  # Keep last 10 messages
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Sorry, I encountered an error. Please try again.',
            'movie_results': [],
            'suggestions': []
        }), 500

def extract_movie_titles_from_response(ai_response):
    """Extract movie titles from AI response text"""
    import re
    
    movie_titles = []
    
    # Pattern 1: "Movie Title (Year)" format
    pattern1 = r'([A-Za-z0-9\s:&\-\'\.]+)\s*\((\d{4})\)'
    matches1 = re.findall(pattern1, ai_response)
    for title, year in matches1:
        clean_title = title.strip()
        if len(clean_title) > 2 and clean_title not in movie_titles:
            movie_titles.append(clean_title)
    
    # Pattern 2: Numbered list format "1. Movie Title"
    pattern2 = r'\d+\.\s*"([^"]+)"'  # Quoted titles in numbered lists
    matches2 = re.findall(pattern2, ai_response)
    for title in matches2:
        clean_title = title.strip()
        if len(clean_title) > 2 and clean_title not in movie_titles:
            movie_titles.append(clean_title)
    
    # Pattern 3: Numbered list without quotes "1. Movie Title (Year)"
    pattern3 = r'\d+\.\s*([A-Za-z0-9\s:&\-\'\.!]+?)(?:\s*\(|\s*-|\n|$)'
    matches3 = re.findall(pattern3, ai_response)
    for title in matches3:
        clean_title = title.strip()
        if len(clean_title) > 2 and clean_title not in movie_titles:
            movie_titles.append(clean_title)
    
    # Filter out common non-movie words
    filtered_titles = []
    exclude_words = ['movie', 'film', 'action', 'comedy', 'drama', 'thriller', 'horror']
    
    for title in movie_titles:
        if not any(exclude.lower() == title.lower() for exclude in exclude_words):
            filtered_titles.append(title)
    
    logger.info(f"Extracted movie titles from AI response: {filtered_titles}")
    return filtered_titles[:3]  # Return top 3 titles

# New endpoint: Return Telegram deep link for a movie if available
@app.route('/api/telegram/link', methods=['POST'])
def get_telegram_movie_link():
    """Return a Telegram deep link for a searched movie if available in the bot's chat"""
    try:
        data = request.get_json(silent=True) or {}
        query = (data.get('query') or data.get('title') or '').strip()
        year = str(data.get('year') or '').strip()
        language = (data.get('language') or '').strip().lower()

        if not query:
            return jsonify({'error': 'query or title is required'}), 400

        # Initialize agents and get Telegram agent
        _, _, _, _, telegram_agent, _ = initialize_agents()
        if not telegram_agent:
            return jsonify({'success': False, 'available': False, 'error': 'Telegram agent not configured or disabled'}), 503

        # Search in Telegram DB
        results = telegram_agent.search_movies(query)

        if not results:
            return jsonify({'success': True, 'available': False, 'matches': 0})

        # Score and select best match
        def score(movie):
            s = 0
            # Title similarity
            if is_fuzzy_match(query, movie.get('title', ''), threshold=40):
                s += 2
            # Year preference
            if year and str(movie.get('year') or '') == year:
                s += 2
            # Language preference
            if language and language in str(movie.get('language') or '').lower():
                s += 1
            # Access count as tie-breaker if present
            try:
                s += int(movie.get('access_count') or 0) / 1000.0
            except Exception:
                pass
            return s

        results_sorted = sorted(results, key=score, reverse=True)
        best = results_sorted[0]

        # Build best deep link
        deep_link = best.get('detail_url')
        if not deep_link:
            bot_username = getattr(telegram_agent, 'bot_username', '')
            title_for_start = (best.get('title') or '').replace(' ', '_')
            if bot_username and title_for_start:
                deep_link = f"https://t.me/{bot_username}?start={title_for_start}"
        if not deep_link and best.get('telegram_message_id'):
            deep_link = f"telegram://message/{best['telegram_message_id']}"

        response_payload = {
            'success': True,
            'available': True,
            'link': deep_link,
            'result': {
                'title': best.get('title'),
                'year': best.get('year'),
                'quality': best.get('quality'),
                'language': best.get('language'),
                'telegram_message_id': best.get('telegram_message_id'),
                'telegram_file_id': best.get('telegram_file_id'),
                'bot_username': getattr(telegram_agent, 'bot_username', ''),
                'deep_link': deep_link,
                'source': 'Telegram'
            },
            'matches': len(results_sorted)
        }
        return jsonify(response_payload)
    except Exception as e:
        logger.error(f"Error in /api/telegram/link: {e}")
        return jsonify({'error': f'Failed to get Telegram link: {str(e)}'}), 500

# Add chat history API routes
@app.route('/api/new-session', methods=['POST'])
def start_new_session():
    """Start a new session by deleting current session and creating a new one"""
    try:
        # Get current session ID
        current_session_id = session.get('session_id')
        
        # Delete current session if it exists
        if current_session_id and current_session_id in session_manager.sessions:
            del session_manager.sessions[current_session_id]
            logger.info(f"Deleted session: {current_session_id}")
        
        # Create new session
        new_session_id = session_manager.create_session()
        session['session_id'] = new_session_id
        logger.info(f"Created new session: {new_session_id}")
        
        # Get new session stats
        session_stats = session_manager.get_session_stats(new_session_id)
        
        return jsonify({
            'success': True,
            'message': 'New session started successfully',
            'session_info': {
                'session_id': new_session_id,
                'conversation_count': 0,
                'time_remaining_minutes': 15
            }
        })
        
    except Exception as e:
        logger.error(f"Error starting new session: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to start new session'
        }), 500

@app.route('/api/chat-history', methods=['GET'])
def get_chat_history():
    """Get chat history for current session"""
    try:
        user_session_id = session.get('session_id')
        if not user_session_id:
            return jsonify({
                'success': True,
                'chat_history': [],
                'session_info': None
            })
        
        session_data = session_manager.get_session(user_session_id)
        if not session_data:
            return jsonify({
                'success': True,
                'chat_history': [],
                'session_info': None
            })
        
        # Format chat history for UI
        chat_history = []
        for conv in session_data['conversation_history']:
            chat_history.append({
                'user_message': conv['user_message'],
                'ai_response': conv['ai_response'],
                'movie_results': conv['movie_results'],
                'timestamp': conv['timestamp']
            })
        
        session_stats = session_manager.get_session_stats(user_session_id)
        
        return jsonify({
            'success': True,
            'chat_history': chat_history,
            'session_info': {
                'session_id': user_session_id,
                'conversation_count': session_stats.get('conversation_count', 0),
                'time_remaining_minutes': session_stats.get('time_remaining_minutes', 15)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load chat history'
        }), 500

if __name__ == '__main__':
    import os
    # Initialize agents on startup
    initialize_agents()
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 8080))
    
    # Run with production settings for Render
    app.run(host='0.0.0.0', port=port, debug=False)
