#!/usr/bin/env python3
"""
MoviezWap Agent - Source 2 for Movie Agent
Handles movie search and download link extraction from moviezwap.pink
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MoviezWapAgent:
    def __init__(self):
        # Load configuration from admin panel
        self.config = self._load_agent_config()
        self.base_url = self.config.get('base_url', "https://www.moviezwap.pink")
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        # Do not auto-resolve during extraction by default (stabilizes extraction)
        self.auto_resolve_during_extraction = bool(self.config.get('auto_resolve_during_extraction', False))
        
    def _load_agent_config(self):
        """Load agent configuration from admin panel"""
        try:
            import os
            import json
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agent_config.json')
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            return config_data.get('agents', {}).get('moviezwap', {})
        except Exception as e:
            logger.warning(f"Could not load agent config: {e}")
            return {}

    def setup_session(self):
        """Setup session with proper headers and configurations"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)
        self.session.timeout = 30
        
    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Search for movies on moviezwap.pink
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching MoviezWap for: {movie_name} (page {page}) - Attempt {attempt + 1}")
                
                # Try multiple search approaches for MoviezWap
                search_urls = [
                    f"{self.base_url}/search.php?q={quote(movie_name)}",
                    f"{self.base_url}/?s={quote(movie_name)}",
                    f"{self.base_url}/category/Telugu-(2025)-Movies.html",  # Fallback to category
                ]
                
                response = None
                for search_url in search_urls:
                    try:
                        logger.info(f"Trying search URL: {search_url}")
                        response = self.session.get(search_url, timeout=30)
                        if response.status_code == 200:
                            # Check if we got actual search results
                            if movie_name.lower() in response.text.lower() or "movie" in response.text.lower():
                                break
                    except:
                        continue
                
                if not response or response.status_code != 200:
                    # If search fails, try browsing recent movies
                    search_url = f"{self.base_url}/category/Telugu-(2025)-Movies.html"
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close'
                })
                
                response = self.session.get(search_url, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                error_str = str(e)
                logger.warning(f"Connection error on attempt {attempt + 1}: {error_str}")
                
                # Don't retry for timeout errors - site is unreachable
                if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
                    logger.error(f"Timeout error detected - skipping retries for unreachable site")
                    raise e
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Reset session for fresh connection
                    self.session.close()
                    self.session = requests.Session()
                    self.setup_session()
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    raise e
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_movies = []
            
            # Extract movie links from search results - improved for MoviezWap
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for actual movie page links (not download links)
                if (text and len(text) > 15 and 
                    self._is_movie_page_link(href, text) and
                    self._is_relevant_to_search(text, movie_name)):
                    
                    # Ensure URL is properly formatted
                    full_url = urljoin(self.base_url, href)
                    
                    # Extract additional info from the link's container
                    container = link.find_parent(['div', 'li', 'article'])
                    
                    movie_data = {
                        'title': text,
                        'detail_url': full_url,
                        'year': self.extract_year(text),
                        'language': self.extract_language(text),
                        'quality': self.extract_quality(text),
                        'image': self._extract_image_from_container(container) if container else None,
                        'source': 'MoviezWap'
                    }
                    all_movies.append(movie_data)
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_movies = []
            for movie in all_movies:
                if movie['detail_url'] not in seen_urls:
                    seen_urls.add(movie['detail_url'])
                    unique_movies.append(movie)
            
            # Calculate pagination
            total_movies = len(unique_movies)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            movies_page = unique_movies[start_index:end_index]
            
            total_pages = (total_movies + per_page - 1) // per_page
            
            logger.info(f"Found {total_movies} total movies from MoviezWap, showing page {page}/{total_pages}")
            
            return {
                'movies': movies_page,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_movies': total_movies,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                },
                'source': 'MoviezWap'
            }
            
        except Exception as e:
            logger.error(f"Error searching MoviezWap: {str(e)}")
            return {
                'movies': [],
                'pagination': {
                    'current_page': 1,
                    'per_page': per_page,
                    'total_movies': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                },
                'source': 'MoviezWap'
            }
    
    def _is_movie_page_link(self, href: str, text: str) -> bool:
        """Check if a link points to a movie page (not a download link)"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Must be a movie page URL pattern
        movie_page_patterns = [
            '/movie/', '.html'
        ]
        
        has_movie_url = any(pattern in href_lower for pattern in movie_page_patterns)
        
        # Must have movie-like text (title with year, quality, etc.)
        movie_text_indicators = [
            '(20', '(19',  # Year patterns
            'hdrip', 'webrip', 'bluray', 'dvdrip', 'camrip',
            'telugu', 'tamil', 'hindi', 'english', 'malayalam',
            'original', 'dubbed'
        ]
        
        has_movie_text = any(indicator in text_lower for indicator in movie_text_indicators)
        
        # Exclude navigation, category, and other non-movie links
        exclude_patterns = [
            'category/', 'search.php', 'contact', 'about', 'privacy', 'terms',
            'telegram', 'facebook', 'twitter', 'instagram', 'bookmark',
            'join', 'download', 'movies download', 'new movies'
        ]
        
        is_excluded = any(pattern in href_lower or pattern in text_lower for pattern in exclude_patterns)
        
        # Must be a proper movie title (reasonable length)
        is_proper_length = 20 <= len(text) <= 200
        
        return has_movie_url and has_movie_text and not is_excluded and is_proper_length
    
    def _is_relevant_to_search(self, text: str, search_term: str) -> bool:
        """Check if the link text is relevant to the search term"""
        text_lower = text.lower()
        search_lower = search_term.lower()
        
        # Check if search words appear in the text
        search_words = search_lower.split()
        text_words = text_lower.split()
        
        matching_words = sum(1 for word in search_words if any(word in text_word for text_word in text_words))
        return matching_words >= len(search_words) * 0.4  # 40% match threshold
    
    def _extract_image_from_container(self, container) -> Optional[str]:
        """Extract image URL from container"""
        img = container.find('img')
        if img:
            return img.get('src') or img.get('data-src')
        return None
    
    def extract_year(self, text: str) -> Optional[str]:
        """Extract year from text"""
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        return year_match.group() if year_match else None
    
    def extract_language(self, text: str) -> str:
        """Extract language from text"""
        text_lower = text.lower()
        if 'hindi' in text_lower:
            return 'Hindi'
        elif 'english' in text_lower:
            return 'English'
        elif 'tamil' in text_lower:
            return 'Tamil'
        elif 'telugu' in text_lower:
            return 'Telugu'
        elif 'malayalam' in text_lower:
            return 'Malayalam'
        elif 'kannada' in text_lower:
            return 'Kannada'
        elif 'punjabi' in text_lower:
            return 'Punjabi'
        else:
            return 'Unknown'
    
    def extract_quality(self, text: str) -> List[str]:
        """Extract quality information from text"""
        qualities = []
        quality_patterns = [r'480p', r'720p', r'1080p', r'4K', r'HD', r'CAM', r'DVDRip', r'BluRay', r'WebRip']
        
        for pattern in quality_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                qualities.append(pattern.upper())
                
        return qualities if qualities else ['Unknown']
    
    def get_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Extract download links from movie detail page
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Extracting MoviezWap download links from: {movie_url} - Attempt {attempt + 1}")
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close'
                })
                
                response = self.session.get(movie_url, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    ConnectionResetError) as e:
                error_str = str(e)
                logger.warning(f"Connection error on attempt {attempt + 1}: {error_str}")
                
                # Don't retry for timeout errors - site is unreachable
                if 'timed out' in error_str.lower() or 'timeout' in error_str.lower():
                    logger.error(f"Timeout error detected - skipping retries for unreachable site")
                    return {'error': f'Site unreachable (timeout): {error_str}'}
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
                    # Reset session for fresh connection
                    self.session.close()
                    self.session = requests.Session()
                    self.setup_session()
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    return {'error': f'Connection failed after {max_retries} attempts: {error_str}'}
                    
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract movie title
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Find download links
            download_links = self.extract_download_links(soup)
            
            # Extract additional metadata
            metadata = self.extract_page_metadata(soup)
            
            result = {
                'title': title,
                'url': movie_url,
                'metadata': metadata,
                'download_links': download_links,
                'total_links': len(download_links),
                'source': 'MoviezWap'
            }
            
            logger.info(f"Extracted {len(download_links)} download links from MoviezWap")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting MoviezWap download links: {str(e)}")
            return {'error': str(e), 'source': 'MoviezWap'}
    
    def extract_download_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract download links from MoviezWap movie page - handles quality selection"""
        links = []
        all_links = soup.find_all('a', href=True)
        
        logger.info(f"MoviezWap: Found {len(all_links)} total links on page")
        
        # First, look for quality selection links (320p, 480p, 720p, etc.)
        quality_links = []
        direct_download_links = []
        
        # Debug: Show all links found on page
        logger.info("MoviezWap: All links on page:")
        for i, link in enumerate(all_links[:15]):  # Show first 15 links
            href = link.get('href', '')
            text = link.get_text(strip=True)
            logger.info(f"  {i+1}. Text: '{text[:40]}' -> URL: '{href[:60]}'")
        
        # Extract movie title from page for filtering
        page_title = soup.title.get_text() if soup.title else ""
        h1_title = soup.find('h1')
        main_title = h1_title.get_text(strip=True) if h1_title else ""
        
        # Get the main movie name from the page
        movie_context = (page_title + " " + main_title).lower()
        logger.info(f"MoviezWap: Page context: {movie_context[:100]}")
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Check for quality selection links (320p, 480p, 720p, etc.)
            if self._is_quality_selection_link(href, text):
                # Additional filtering: ensure link is related to current movie
                if self._is_relevant_to_current_movie(text, movie_context, href):
                    quality_links.append(link)
                    logger.info(f"MoviezWap: Found quality link: {text[:50]} -> {href}")
                else:
                    logger.debug(f"MoviezWap: Filtered out unrelated link: {text[:30]}")
            
            # Also check for direct download links
            elif self._is_download_link(href, text):
                if self._is_relevant_to_current_movie(text, movie_context, href):
                    direct_download_links.append(link)
                    logger.info(f"MoviezWap: Found direct download link: {text[:50]} -> {href}")
                else:
                    logger.debug(f"MoviezWap: Filtered out unrelated download: {text[:30]}")
        
        # Process quality selection links first (these are what we want to show)
        for link in quality_links:
            link_data = self.process_quality_link(link)
            if link_data:
                links.append(link_data)
                logger.info(f"MoviezWap: Added quality link: {link_data['text'][:50]}")
        
        # If no quality links found, process direct download links
        if not links:
            for link in direct_download_links:
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
                    logger.info(f"MoviezWap: Added download link: {link_data['text'][:50]}")
        
        logger.info(f"MoviezWap: Found {len(quality_links)} quality links, {len(direct_download_links)} direct links, processed {len(links)} total links")
        return links
    
    def _is_download_link(self, href: str, text: str) -> bool:
        """Check if a link is a download link - improved for MoviezWap"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Skip internal navigation links
        skip_patterns = [
            'category/', 'search.php', 'contact', 'about', 'privacy', 'terms',
            'telegram.me', 'facebook.com', 'twitter.com', 'instagram.com',
            '/category/', 'moviezwap.pink', 'bookmark', 'join'
        ]
        
        if any(pattern in href_lower for pattern in skip_patterns):
            return False
        
        # Priority 1: Direct file hosting services
        direct_hosts = [
            'drive.google.com', 'mega.nz', 'mediafire.com', 'dropbox.com',
            'uploadrar.com', 'rapidgator.net', 'nitroflare.com', 'uptobox.com',
            'gofile.io', 'pixeldrain.com', 'anonfiles.com', 'zippyshare.com'
        ]
        
        if any(host in href_lower for host in direct_hosts):
            return True
        
        # Priority 2: Shortlink services
        shortlink_services = [
            'shortlinkto.onl', 'shortlinkto.biz', 'uptobhai.blog', 'shortlink.to',
            'linkvertise.com', 'adf.ly', 'bit.ly', 'tinyurl.com'
        ]
        
        if any(service in href_lower for service in shortlink_services):
            return True
        
        # Priority 3: Download-related text patterns (be more flexible)
        download_text_patterns = [
            'download link', 'server 1', 'server 2', 'mirror 1', 'mirror 2',
            'watch online', 'stream', 'direct link', 'file link',
            'download', 'link', 'server', 'mirror', 'watch'
        ]
        
        # Check if text contains download-related words and is not too long (avoid paragraphs)
        if (any(pattern in text_lower for pattern in download_text_patterns) and 
            len(text) < 100 and len(text) > 3):
            return True
        
        # Priority 4: URLs that look like download endpoints
        download_url_patterns = [
            '/download/', '/link/', '/server/', '/mirror/', '/watch/', '/stream/'
        ]
        
        if any(pattern in href_lower for pattern in download_url_patterns):
            return True
        
        return False
    
    def _is_quality_selection_link(self, href: str, text: str) -> bool:
        """Check if a link is a quality selection link (320p, 480p, 720p, etc.)"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Priority 1: Look for direct download links with /dwload.php pattern
        if '/dwload.php' in href_lower and text and len(text) > 10:
            logger.info(f"MoviezWap: Found direct download link: {text[:50]} -> {href}")
            return True
        
        # Priority 2: Look for quality patterns in text
        quality_patterns = [
            '320p', '480p', '720p', '1080p', '4k', 'hd',
            'cam', 'dvdrip', 'webrip', 'bluray', 'hdrip'
        ]
        
        has_quality = any(pattern in text_lower for pattern in quality_patterns)
        
        # Must be a movie-related link (not navigation)
        is_movie_link = (
            '/movie/' in href_lower or 
            '.html' in href_lower or
            '/dwload.php' in href_lower
        )
        
        # Exclude navigation and category links
        exclude_patterns = [
            'category/', 'search.php', 'contact', 'about', 'privacy',
            'telegram', 'facebook', 'twitter', 'instagram', 'share', 'sharer'
        ]
        
        is_excluded = any(pattern in href_lower for pattern in exclude_patterns)
        
        # Should have reasonable length (movie title + quality)
        is_reasonable_length = 10 <= len(text) <= 150
        
        # Must not be a different movie (check if text contains current movie context)
        # This is a basic check - we'll improve this
        
        return has_quality and is_movie_link and not is_excluded and is_reasonable_length
    
    def _is_relevant_to_current_movie(self, link_text: str, movie_context: str, href: str) -> bool:
        """Check if a link is relevant to the current movie page"""
        link_text_lower = link_text.lower()
        href_lower = href.lower()
        
        # For /dwload.php links, they're usually relevant if they exist on the page
        if '/dwload.php' in href_lower:
            return True
        
        # Extract key words from movie context (title)
        context_words = movie_context.split()
        significant_words = [word for word in context_words if len(word) > 3 and 
                           word not in ['movie', 'download', 'watch', 'online', 'free', 'hd', 'quality']]
        
        # Check if link text contains significant words from the movie title
        if significant_words:
            matching_words = sum(1 for word in significant_words if word in link_text_lower)
            # At least 30% of significant words should match
            relevance_threshold = max(1, len(significant_words) * 0.3)
            
            if matching_words >= relevance_threshold:
                return True
        
        # If no significant words match, check for exact movie name patterns
        # This is a fallback for cases where the title extraction didn't work well
        if any(word in link_text_lower for word in ['rrr', 'behind', 'beyond'] if word in movie_context):
            return True
        
        # Exclude links that clearly point to different movies
        exclude_movies = ['jersey', 'money heist', 'bahubali', 'avengers']
        if any(movie in link_text_lower for movie in exclude_movies if movie not in movie_context):
            return False
        
        return True
    
    def process_quality_link(self, link_elem) -> Optional[Dict[str, Any]]:
        """Process quality selection link element"""
        try:
            href = link_elem.get('href')
            if not href:
                return None
            
            # Skip non-download links
            skip_patterns = ['javascript:', 'mailto:', '#', 'tel:']
            if any(pattern in href.lower() for pattern in skip_patterns):
                return None
            
            # Get link text
            link_text = link_elem.get_text(strip=True)
            
            # Extract quality from text
            quality = self.extract_quality(link_text)
            
            # Handle relative URLs
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            
            # Convert dwload.php to download.php and resolve final download URL
            download_url = href
            if '/dwload.php' in href:
                download_url = href.replace('/dwload.php', '/download.php')
                logger.info(f"MoviezWap: Converted dwload.php to download.php: {download_url}")
                
                # Optionally resolve the final download URL by clicking "Fast Download Server"
                if self.auto_resolve_during_extraction:
                    final_url = self.resolve_fast_download_server(download_url)
                    if final_url:
                        download_url = final_url
                        logger.info(f"MoviezWap: Resolved final download URL: {download_url}")
            
            # Determine host type based on URL
            if '/dwload.php' in href or 'moviezzwaphd.xyz' in download_url:
                host_type = 'MoviezWap Direct Download'
                display_text = f"{link_text} - Direct Download"
            else:
                host_type = 'MoviezWap Quality Selection'
                display_text = f"{link_text} - Download"
            
            return {
                'text': display_text,
                'url': download_url,
                'original_url': href,
                'host': host_type,
                'quality': quality,
                'file_size': None,
                'source': 'MoviezWap',
                'type': 'direct_download' if '/dwload.php' in href else 'quality_selection'
            }
            
        except Exception as e:
            logger.error(f"Error processing MoviezWap quality link: {str(e)}")
            return None
    
    def process_download_link(self, link_elem) -> Optional[Dict[str, Any]]:
        """Process individual download link element"""
        try:
            href = link_elem.get('href')
            if not href:
                return None
            
            # Skip non-download links
            skip_patterns = ['javascript:', 'mailto:', '#', 'tel:']
            if any(pattern in href.lower() for pattern in skip_patterns):
                return None
            
            # Get link text
            link_text = link_elem.get_text(strip=True)
            
            # Determine host
            host = self.get_host_name(href)
            
            # Extract quality and file size from link text
            quality = self.extract_quality(link_text)
            file_size = self.extract_file_size(link_text)
            
            # Handle relative URLs
            if href.startswith('/'):
                href = urljoin(self.base_url, href)
            
            # Convert dwload.php to download.php and resolve final download URL
            download_url = href
            if '/dwload.php' in href:
                download_url = href.replace('/dwload.php', '/download.php')
                logger.info(f"MoviezWap: Converted dwload.php to download.php: {download_url}")
                
                # Optionally resolve the final download URL by clicking "Fast Download Server"
                if self.auto_resolve_during_extraction:
                    final_url = self.resolve_fast_download_server(download_url)
                    if final_url:
                        download_url = final_url
                        host = 'MoviezWap Direct Download'
                        logger.info(f"MoviezWap: Resolved final download URL: {download_url}")
            
            return {
                'text': link_text,
                'url': download_url,
                'original_url': href,
                'host': host,
                'quality': quality,
                'file_size': file_size,
                'source': 'MoviezWap'
            }
            
        except Exception as e:
            logger.error(f"Error processing MoviezWap download link: {str(e)}")
            return None
    
    def get_host_name(self, url: str) -> str:
        """Extract host name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Map common hosts
            host_mapping = {
                'drive.google.com': 'Google Drive',
                'mega.nz': 'Mega',
                'mediafire.com': 'MediaFire',
                'dropbox.com': 'Dropbox',
                '1fichier.com': '1Fichier',
                'rapidgator.net': 'RapidGator',
                'uploadrar.com': 'UploadRar',
                'nitroflare.com': 'NitroFlare'
            }
            
            for domain_key, host_name in host_mapping.items():
                if domain_key in domain:
                    return host_name
            
            return domain
            
        except:
            return 'Unknown'
    
    def extract_file_size(self, text: str) -> Optional[str]:
        """Extract file size from text"""
        size_pattern = r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)'
        match = re.search(size_pattern, text, re.IGNORECASE)
        return match.group() if match else None
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from movie page"""
        metadata = {}
        
        # Extract description
        desc_elem = soup.find('div', class_=re.compile(r'content|description|summary', re.I))
        if desc_elem:
            metadata['description'] = desc_elem.get_text(strip=True)[:500]
        
        # Extract genre, year, etc. from meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '')
            
            if name in ['description', 'keywords']:
                metadata[name] = content
        
        return metadata
    
    def resolve_fast_download_server(self, download_php_url: str) -> Optional[str]:
        """
        Automatically resolve MoviezWap URLs (download.php or extlinks_) by finding download servers
        Returns the final direct download URL
        """
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
            
            logger.info(f"MoviezWap: Resolving Fast Download Server for: {download_php_url}")
            
            # Setup Chrome options
            options = uc.ChromeOptions()
            options.headless = True
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            driver = None
            try:
                logger.info("MoviezWap: Starting Chrome driver for Fast Download Server resolution")
                try:
                    # First attempt: let UC auto-manage
                    driver = uc.Chrome(options=options)
                except Exception as e:
                    # If Chrome/Driver version mismatch, parse current browser version and retry with version_main
                    msg = str(e)
                    logger.error(f"MoviezWap: Initial Chrome start failed: {msg}")
                    import re as _re
                    m = _re.search(r"Current browser version is\s*(\d+)", msg)
                    if m:
                        ver = int(m.group(1))
                        logger.info(f"MoviezWap: Retrying Chrome with version_main={ver} using fresh options")
                        # Create a fresh ChromeOptions instance; UC may forbid reusing the same object
                        options_retry = uc.ChromeOptions()
                        options_retry.headless = True
                        options_retry.add_argument("--no-sandbox")
                        options_retry.add_argument("--disable-dev-shm-usage")
                        options_retry.add_argument("--disable-blink-features=AutomationControlled")
                        options_retry.add_argument("--disable-extensions")
                        options_retry.add_argument("--disable-plugins")
                        options_retry.add_argument("--disable-images")
                        options_retry.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                        driver = uc.Chrome(options=options_retry, version_main=ver)
                    else:
                        raise
                driver.set_page_load_timeout(30)
                driver.implicitly_wait(10)
                
                # Handle URL conversion for extlinks_ to getlinks_
                final_url = download_php_url
                if 'extlinks_' in download_php_url:
                    final_url = download_php_url.replace('extlinks_', 'getlinks_')
                    logger.info(f"MoviezWap: Converting extlinks_ to getlinks_: {final_url}")
                
                # Navigate to the final URL
                logger.info(f"MoviezWap: Navigating to: {final_url}")
                driver.get(final_url)
                time.sleep(3)
                
                # Look for download links (different patterns for download.php vs getlinks_)
                if 'getlinks_' in final_url:
                    logger.info("MoviezWap: Looking for external hosting service links on getlinks_ page...")
                else:
                    logger.info("MoviezWap: Looking for download server links on download.php page...")
                
                # Different selectors based on URL type
                if 'getlinks_' in final_url:
                    # For getlinks_ pages, look for external hosting service links
                    fast_server_selectors = [
                        # External hosting service URLs
                        "//a[contains(@href, 'drive.google.com')]",
                        "//a[contains(@href, 'mega.nz')]", 
                        "//a[contains(@href, 'mediafire.com')]",
                        "//a[contains(@href, 'dropbox.com')]",
                        "//a[contains(@href, 'onedrive.live.com')]",
                        "//a[contains(@href, 'gofile.io')]",
                        "//a[contains(@href, 'pixeldrain.com')]",
                        "//a[contains(@href, 'krakenfiles.com')]",
                        "//a[contains(@href, 'workupload.com')]",
                        "//a[contains(@href, 'racaty.io')]",
                        "//a[contains(@href, 'send.now')]",
                        "//a[contains(@href, 'sendspace.com')]",
                        "//a[contains(@href, 'zippyshare.com')]",
                        
                        # External hosting service text
                        "//a[contains(text(), 'Google Drive')]",
                        "//a[contains(text(), 'Mega')]",
                        "//a[contains(text(), 'MediaFire')]", 
                        "//a[contains(text(), 'Dropbox')]",
                        "//a[contains(text(), 'OneDrive')]",
                        "//a[contains(text(), 'GoFile')]",
                        "//a[contains(text(), 'PixelDrain')]",
                        
                        # Fallback patterns
                        "//a[contains(@href, 'moviezzwaphd.xyz')]",
                        "//a[contains(@href, '.mkv')]",
                        "//a[contains(@href, '.mp4')]",
                        "//a[contains(@href, '.avi')]"
                    ]
                else:
                    # For download.php pages, look for "Fast Download Server"
                    fast_server_selectors = [
                        "//a[contains(text(), 'Fast Download Server')]",
                        "//a[contains(text(), 'Fast Server')]", 
                        "//a[contains(text(), 'Download Server')]",
                        "//button[contains(text(), 'Fast Download Server')]",
                        "//button[contains(text(), 'Fast Server')]",
                        "//a[contains(@class, 'download') and contains(text(), 'Server')]",
                        "//a[contains(@href, 'moviezzwaphd.xyz')]"
                    ]
                
                fast_server_link = None
                for selector in fast_server_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        if elements:
                            # Filter out ad links
                            for element in elements:
                                href = element.get_attribute('href') or ''
                                onclick = element.get_attribute('onclick') or ''
                                text = element.text.strip()
                                
                                # Skip ad-related links
                                if any(ad in href.lower() for ad in ['betspintrack', 'ads', 'popup']):
                                    continue
                                if any(ad in onclick.lower() for ad in ['betspintrack', 'ads', 'popup']):
                                    continue
                                
                                logger.info(f"MoviezWap: Found Fast Download Server link: '{text}' -> {href}")
                                fast_server_link = element
                                break
                        
                        if fast_server_link:
                            break
                    except Exception as e:
                        continue
                
                if not fast_server_link:
                    logger.warning("MoviezWap: No 'Fast Download Server' link found")
                    return None
                
                # Get the href before clicking (in case it's a direct link)
                fast_server_href = fast_server_link.get_attribute('href')
                logger.info(f"MoviezWap: Fast Download Server href: {fast_server_href}")
                
                # If href already contains moviezzwaphd.xyz or direct download, return it
                if fast_server_href and ('moviezzwaphd.xyz' in fast_server_href or any(ext in fast_server_href.lower() for ext in ['.mp4', '.mkv', '.avi'])):
                    logger.info(f"MoviezWap: Direct download URL found in href: {fast_server_href}")
                    return fast_server_href
                
                # Click the Fast Download Server link
                logger.info("MoviezWap: Clicking Fast Download Server link...")
                current_url = driver.current_url
                
                try:
                    # Scroll to element and click
                    driver.execute_script("arguments[0].scrollIntoView(true);", fast_server_link)
                    time.sleep(1)
                    fast_server_link.click()
                except:
                    # Fallback to JavaScript click
                    driver.execute_script("arguments[0].click();", fast_server_link)
                
                # Wait for navigation or popup
                time.sleep(5)
                
                # Check for popup windows
                all_windows = driver.window_handles
                logger.info(f"MoviezWap: Found {len(all_windows)} browser windows after click")
                
                if len(all_windows) > 1:
                    # Switch to popup window
                    driver.switch_to.window(all_windows[-1])
                    popup_url = driver.current_url
                    logger.info(f"MoviezWap: Popup window URL: {popup_url}")
                    
                    # Look for continue/download button in popup
                    try:
                        continue_selectors = [
                            "//button[contains(text(), 'Continue')]",
                            "//a[contains(text(), 'Continue')]",
                            "//button[contains(text(), 'Download')]",
                            "//a[contains(text(), 'Download')]",
                            "//a[contains(@href, 'moviezzwaphd.xyz')]"
                        ]
                        
                        for selector in continue_selectors:
                            try:
                                continue_elements = driver.find_elements(By.XPATH, selector)
                                if continue_elements:
                                    continue_btn = continue_elements[0]
                                    continue_href = continue_btn.get_attribute('href')
                                    
                                    logger.info(f"MoviezWap: Found continue button, clicking...")
                                    continue_btn.click()
                                    time.sleep(3)
                                    
                                    final_url = driver.current_url
                                    logger.info(f"MoviezWap: Final URL after continue: {final_url}")
                                    
                                    if 'moviezzwaphd.xyz' in final_url or any(ext in final_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                                        return final_url
                                    elif continue_href and ('moviezzwaphd.xyz' in continue_href or any(ext in continue_href.lower() for ext in ['.mp4', '.mkv', '.avi'])):
                                        return continue_href
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.warning(f"MoviezWap: Error handling popup: {str(e)}")
                    
                    # If popup URL itself is the download URL
                    if 'moviezzwaphd.xyz' in popup_url or any(ext in popup_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                        return popup_url
                
                # Check main window for URL change
                final_url = driver.current_url
                if final_url != current_url:
                    logger.info(f"MoviezWap: Main window URL changed to: {final_url}")
                    if 'moviezzwaphd.xyz' in final_url or any(ext in final_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                        return final_url
                
                # Look for any moviezzwaphd.xyz links that appeared after clicking
                try:
                    moviezzwap_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'moviezzwaphd.xyz')]")
                    if moviezzwap_links:
                        final_download_url = moviezzwap_links[0].get_attribute('href')
                        logger.info(f"MoviezWap: Found moviezzwaphd.xyz link: {final_download_url}")
                        return final_download_url
                except:
                    pass
                
                logger.warning("MoviezWap: Could not resolve final download URL")
                return None
                
            except Exception as e:
                logger.error(f"MoviezWap: Error during Fast Download Server resolution: {str(e)}")
                return None
            
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                        
        except ImportError:
            logger.error("MoviezWap: Selenium not available for Fast Download Server resolution")
            return None
        except Exception as e:
            logger.error(f"MoviezWap: Unexpected error in Fast Download Server resolution: {str(e)}")
            return None

def main():
    """Main function for testing the MoviezWap agent"""
    agent = MoviezWapAgent()
    
    # Example usage
    movie_name = input("Enter movie name to search on MoviezWap: ").strip()
    
    if not movie_name:
        print("Please enter a valid movie name")
        return
    
    # Search for movies
    print(f"\nSearching MoviezWap for '{movie_name}'...")
    search_results = agent.search_movies(movie_name)
    
    movies = search_results.get('movies', [])
    if not movies:
        print("No movies found on MoviezWap!")
        return
    
    # Display search results
    print(f"\nFound {len(movies)} movies on MoviezWap:")
    for i, movie in enumerate(movies, 1):
        print(f"{i}. {movie['title']} ({movie['year']}) - {movie['language']} - {movie['quality']}")
    
    # Get user selection
    try:
        choice = int(input(f"\nSelect movie (1-{len(movies)}): ")) - 1
        if 0 <= choice < len(movies):
            selected_movie = movies[choice]
            
            # Extract download links
            print(f"\nExtracting download links for: {selected_movie['title']}")
            download_data = agent.get_download_links(selected_movie['detail_url'])
            
            # Save results to JSON
            output_file = f"moviezwap_results_{movie_name.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(download_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nMoviezWap results saved to: {output_file}")
            print(f"Total download links found: {download_data.get('total_links', 0)}")
            
            # Display some links
            links = download_data.get('download_links', [])
            if links:
                print("\nSample download links from MoviezWap:")
                for i, link in enumerate(links[:5], 1):
                    print(f"{i}. {link['text']} - {link['host']} ({link['quality']})")
        else:
            print("Invalid selection!")
            
    except ValueError:
        print("Please enter a valid number!")

if __name__ == "__main__":
    main()