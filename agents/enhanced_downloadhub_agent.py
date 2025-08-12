#!/usr/bin/env python3
"""
Cursor AI Agent for DownloadHub.legal Movie Search and Download Link Extraction

This agent automatically:
1. Searches for movies on downloadhub.legal
2. Extracts search results with metadata
3. Navigates to specific movie pages
4. Bypasses ads and redirections
5. Extracts direct download links
6. Returns clean JSON data
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedDownloadHubAgent:
    def __init__(self, config_path="agent_config.json"):
        self.config_path = config_path
        self.base_url, self.search_url = self._load_urls_from_config()
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        
    def _load_urls_from_config(self):
        """Load base URL and search URL from admin panel configuration"""
        try:
            import os
            config_file = self.config_path
            if not os.path.exists(config_file):
                config_file = os.path.join("..", self.config_path)
            if not os.path.exists(config_file):
                config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.config_path)
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    downloadhub_config = config.get('agents', {}).get('downloadhub', {})
                    admin_base_url = downloadhub_config.get('base_url')
                    admin_search_url = downloadhub_config.get('search_url')
                    
                    if admin_base_url and admin_base_url.strip():
                        base_url = admin_base_url.rstrip('/')
                        if admin_search_url and admin_search_url.strip():
                            search_url = admin_search_url
                            logger.info(f"Using URLs from admin panel - Base: {base_url}, Search: {search_url}")
                        else:
                            search_url = f"{base_url}/?s="
                            logger.info(f"Using base URL from admin panel, constructed search URL: {base_url}, {search_url}")
                        return base_url, search_url
                    else:
                        logger.warning("No base URL found in admin config, using fallback")
            else:
                logger.warning(f"Config file not found: {config_file}, using fallback URLs")
        except Exception as e:
            logger.error(f"Error loading config: {e}, using fallback URLs")
        
        fallback_base_url = "https://downloadhub.legal"
        fallback_search_url = f"{fallback_base_url}/?s="
        logger.info(f"Using fallback URLs - Base: {fallback_base_url}, Search: {fallback_search_url}")
        return fallback_base_url, fallback_search_url
        
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
        
    def _is_same_domain(self, url):
        """Check if URL belongs to the same domain as base_url"""
        try:
            from urllib.parse import urlparse
            base_domain = urlparse(self.base_url).netloc.lower()
            url_domain = urlparse(url).netloc.lower()
            return base_domain == url_domain
        except:
            return False
        
    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Search for movies using the correct downloadhub.legal format with pagination
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching for movie: {movie_name} (page {page}) - Attempt {attempt + 1}")
                
                # Use the exact format you specified
                # Use the search URL from admin panel configuration
                if '{}' in self.search_url:
                    search_url = self.search_url.format(movie_name.replace(' ', '+'))
                elif self.search_url.endswith('?s=') or self.search_url.endswith('&s='):
                    search_url = f"{self.search_url}{movie_name.replace(' ', '+')}"
                else:
                    # Fallback: construct search URL from base URL
                    search_url = f"{self.base_url}/?s={movie_name.replace(' ', '+')}"
                
                # Add retry-specific headers
                self.session.headers.update({
                    'User-Agent': self.ua.random,
                    'Connection': 'close'  # Force new connection each time
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
            
            # Extract movie links directly from the search results
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for actual movie download links
                if (text and len(text) > 20 and 
                    self._is_same_domain(href) and
                    any(keyword in text.lower() for keyword in ['download', 'hdrip', 'bluray', 'webrip', 'dvdrip', 'web-dl', 'hdtv', 'brrip']) and
                    self._is_relevant_to_search(text, movie_name)):
                    
                    # Ensure URL is properly formatted
                    formatted_url = self._format_movie_url(text, href)
                    
                    movie_data = {
                        'title': text,
                        'detail_url': formatted_url,
                        'year': self.extract_year(text),
                        'language': self.extract_language(text),
                        'quality': self.extract_quality(text),
                        'image': None,
                        'source': 'downloadhub'
                    }
                    all_movies.append(movie_data)
            
            # Calculate pagination
            total_movies = len(all_movies)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            movies_page = all_movies[start_index:end_index]
            
            total_pages = (total_movies + per_page - 1) // per_page  # Ceiling division
            
            logger.info(f"Found {total_movies} total movies, showing page {page}/{total_pages}")
            
            return {
                'movies': movies_page,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_movies': total_movies,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error searching movies: {str(e)}")
            return {
                'movies': [],
                'pagination': {
                    'current_page': 1,
                    'per_page': per_page,
                    'total_movies': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                }
            }
    
    def _is_relevant_to_search(self, text: str, search_term: str) -> bool:
        """Check if the link text is relevant to the search term"""
        text_lower = text.lower()
        search_lower = search_term.lower()
        
        # Check if search words appear in the text
        search_words = search_lower.split()
        text_words = text_lower.split()
        
        matching_words = sum(1 for word in search_words if any(word in text_word for text_word in text_words))
        return matching_words >= len(search_words) * 0.5
    
    def _format_movie_url(self, title: str, original_url: str) -> str:
        """Format movie URL using the correct downloadhub.legal pattern"""
        try:
            # If the original URL is already properly formatted, use it
            if original_url.endswith('/') and self._is_same_domain(original_url):
                return original_url
            
            # Generate URL from title using the pattern you specified
            # Example: "Lies My Babysitter Told 2024 English 1080p | 720p | 480p HDRip ESub Download"
            # Should become: "lies-my-babysitter-told-2024-english-1080p-720p-480p-hdrip-esub-download"
            
            # Clean the title
            clean_title = title.lower()
            
            # Remove common words and characters
            clean_title = re.sub(r'\s*\|\s*', '-', clean_title)  # Replace " | " with "-"
            clean_title = re.sub(r'[^\w\s-]', '', clean_title)   # Remove special chars except spaces and hyphens
            clean_title = re.sub(r'\s+', '-', clean_title)       # Replace spaces with hyphens
            clean_title = re.sub(r'-+', '-', clean_title)        # Replace multiple hyphens with single
            clean_title = clean_title.strip('-')                 # Remove leading/trailing hyphens
            
            # Construct the proper URL
            formatted_url = f"{self.base_url}/{clean_title}/"
            
            logger.info(f"Formatted URL: {original_url} -> {formatted_url}")
            return formatted_url
            
        except Exception as e:
            logger.error(f"Error formatting URL: {e}")
            return original_url
    
    def extract_movie_metadata(self, container) -> Optional[Dict[str, Any]]:
        """Extract movie metadata from search result container"""
        try:
            # Extract title
            title_elem = container.find('h2') or container.find('h3') or container.find('a')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"
            
            # Extract link
            link_elem = container.find('a', href=True)
            link = urljoin(self.base_url, link_elem['href']) if link_elem else None
            
            # Extract year (from title or separate element)
            year = self.extract_year(title)
            
            # Extract language and quality from title or description
            language = self.extract_language(title)
            quality = self.extract_quality(title)
            
            # Extract image
            img_elem = container.find('img')
            image = img_elem.get('src') or img_elem.get('data-src') if img_elem else None
            
            return {
                'title': title,
                'year': year,
                'language': language,
                'quality': quality,
                'detail_url': link,
                'image': image,
                'source': 'downloadhub'
            }
            
        except Exception as e:
            logger.error(f"Error extracting movie metadata: {str(e)}")
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
        elif 'punjabi' in text_lower:
            return 'Punjabi'
        else:
            return 'Unknown'
    
    def extract_quality(self, text: str) -> List[str]:
        """Extract quality information from text"""
        qualities = []
        quality_patterns = [r'480p', r'720p', r'1080p', r'4K', r'HD', r'CAM', r'DVDRip', r'BluRay']
        
        for pattern in quality_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                qualities.append(pattern.upper())
                
        return qualities if qualities else ['Unknown']
    
    def get_download_links(self, movie_url: str) -> Dict[str, Any]:
        """
        Extract download links from movie detail page
        
        Args:
            movie_url: URL of the movie detail page
            
        Returns:
            Dictionary with movie info and download links
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Extracting download links from: {movie_url} - Attempt {attempt + 1}")
                
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
                'total_links': len(download_links)
            }
            
            logger.info(f"Extracted {len(download_links)} download links")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting download links: {str(e)}")
            return {'error': str(e)}
    
    def extract_download_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract download and streaming links for the selected movie"""
        links = []
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Pattern 1: Links with quality + file size pattern (like "1080P [ 2.8GB ] Link 1")
            if re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE):
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
            
            # Pattern 2: External download/streaming hosts
            elif any(host in href.lower() for host in [
                'uptobhai.blog', 'shortlinkto.onl', 'drive.google.com', 'mega.nz', 'mediafire.com',
                'dropbox.com', 'streamtape.com', 'doodstream.com', 'mixdrop.co', 'upstream.to'
            ]):
                if not self._is_other_movie_link(text, href):
                    link_data = self.process_download_link(link)
                    if link_data:
                        links.append(link_data)
            
            # Pattern 3: Download/Stream links with specific quality or server indicators
            elif (text and len(text) > 5 and len(text) < 50 and
                  (any(keyword in text.lower() for keyword in [
                      'link 1', 'link 2', 'server 1', 'server 2', 'mirror', 'watch online',
                      '480p download', '720p download', '1080p download'
                  ]) or
                   re.search(r'(server|link|mirror)\s*\d+', text, re.IGNORECASE) or
                   re.search(r'(480p|720p|1080p).*?(download|link)', text, re.IGNORECASE)) and
                  not self._is_other_movie_link(text, href) and
                  not self._is_same_domain(href)):  # Exclude internal navigation
                
                link_data = self.process_download_link(link)
                if link_data:
                    links.append(link_data)
            
            # Pattern 4: Links with specific quality indicators and download context
            elif (re.search(r'\b(480p|720p|1080p)\b.*?(download|link|server)', text, re.IGNORECASE) and 
                  len(text) < 50 and len(text) > 8):
                if not self._is_other_movie_link(text, href) and not self._is_same_domain(href):
                    link_data = self.process_download_link(link)
                    if link_data:
                        links.append(link_data)
        
        return links
    
    def _is_other_movie_link(self, text: str, href: str) -> bool:
        """Check if this is a link to another movie or promotional site (not a download link)"""
        text_lower = text.lower()
        href_lower = href.lower()
        
        # Skip promotional/advertisement sites and unwanted links
        unwanted_sites_and_links = [
            '7starhd', 'hdhub4u', 'filmywap', 'moviesflix', 'worldfree4u',
            'khatrimaza', 'filmyzilla', 'pagalmovies', 'bolly4u', 'moviescounter',
            '4khdhub', '4k hd hub', 'hd movies', 'how to download', 'download guide',
            'telegram', 'whatsapp', 'facebook', 'twitter', 'instagram'
        ]
        
        if any(site in text_lower or site in href_lower for site in unwanted_sites_and_links):
            return True
        
        # Skip generic/vague download text without specific quality or file info
        generic_download_texts = [
            'download', 'hd movies', 'full movie', 'watch online', 'stream',
            'click here', 'get link', 'file', 'link'
        ]
        
        # If text is too generic and short, skip it
        if (len(text) < 15 and 
            any(generic in text_lower for generic in generic_download_texts) and
            not re.search(r'(480p|720p|1080p|\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE)):
            return True
        
        # Skip links that look like other movie titles
        other_movie_indicators = [
            'smurfs', 'octopus', 'star trek', 'untamed', 'sakamoto', 'mirchi', 
            'varisu', 'pechi', 'tanvi', 'nikita', 'saiyaara', 'masti', 'bhama',
            'kaliyugam', 'solo boy', 'journey'
        ]
        
        # If text contains other movie names and doesn't have download pattern, skip it
        if (any(indicator in text_lower for indicator in other_movie_indicators) and
            not re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE)):
            return True
        
        # Skip if it's a link to another movie page on the same domain
        if (self._is_same_domain(href) and 
            len(text) > 50 and 
            'download' in text_lower and
            not re.search(r'(480p|720p|1080p).*?\[.*?(\d+(?:\.\d+)?\s*(?:GB|MB))', text, re.IGNORECASE)):
            return True
            
        return False
    
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
            
            # Follow redirects to get actual download URL
            actual_url = self.resolve_redirects(href)
            
            return {
                'text': link_text,
                'url': actual_url,
                'original_url': href,
                'host': host,
                'quality': quality,
                'file_size': file_size,
                'type': 'Download'
            }
            
        except Exception as e:
            logger.error(f"Error processing download link: {str(e)}")
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
    
    def resolve_taazabull_link(self, url: str) -> str:
        """Automate taazabull24.com shortlink resolution: Click to Continue -> Wait 10s -> Get links"""
        if 'taazabull24.com' not in url.lower():
            return url
            
        try:
            logger.info(f"Resolving taazabull24.com shortlink: {url}")
            
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
            
            # Setup headless Chrome with better options
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.set_page_load_timeout(30)
            
            try:
                # Load the taazabull shortlink page directly
                logger.info(f"Loading taazabull shortlink: {url}")
                driver.get(url)
                
                # Wait for page to load completely
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(3)  # Allow page to fully render
                
                current_url = driver.current_url
                logger.info(f"Current URL after loading: {current_url}")
                
                # Debug: Log page title and some content
                try:
                    page_title = driver.title
                    logger.info(f"Page title: {page_title}")
                    
                    # Check if we're already redirected to final destination
                    if 'hblinks.dad' in current_url or 'archives' in current_url:
                        logger.info(f"Already redirected to final URL: {current_url}")
                        return current_url
                        
                except Exception as e:
                    logger.warning(f"Error getting page info: {e}")
                
                # If we're redirected to homelander page, wait a bit more for it to fully load
                if '/homelander/' in current_url:
                    logger.info("Detected homelander page, waiting for full load...")
                    time.sleep(3)
                
                # Step 1: Look for and click "Click to Continue" or similar button
                continue_selectors = [
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
                    "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
                    "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
                    "//*[@id='continue']",
                    "//*[@class*='continue']",
                    "//*[contains(@onclick, 'continue')]",
                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click')]",
                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click')]"
                ]
                
                continue_button = None
                # Try multiple times to find the button to handle dynamic loading
                for attempt in range(3):
                    logger.info(f"Looking for continue button (attempt {attempt + 1})...")
                    
                    for selector in continue_selectors:
                        try:
                            elements = driver.find_elements(By.XPATH, selector)
                            for elem in elements:
                                if elem.is_displayed() and elem.is_enabled():
                                    elem_text = elem.text.strip()
                                    logger.info(f"Found potential continue button: '{elem_text}' using selector: {selector}")
                                    continue_button = elem
                                    break
                            if continue_button:
                                break
                        except Exception as e:
                            continue
                    
                    if continue_button:
                        break
                    else:
                        logger.info("Continue button not found yet, waiting 2 seconds...")
                        time.sleep(2)
                
                # Track if we've already clicked continue to avoid clicking again after going back
                continue_clicked = False
                
                if continue_button:
                    try:
                        # Store button info before clicking to avoid stale element
                        button_text = continue_button.text.strip()
                        button_selector = None
                        
                        # Find which selector worked for this button
                        for selector in continue_selectors:
                            try:
                                elements = driver.find_elements(By.XPATH, selector)
                                for elem in elements:
                                    if elem.is_displayed() and elem.is_enabled() and elem.text.strip() == button_text:
                                        button_selector = selector
                                        break
                                if button_selector:
                                    break
                            except:
                                continue
                        
                        # Re-find the element to avoid stale reference
                        fresh_button = None
                        if button_selector:
                            try:
                                elements = driver.find_elements(By.XPATH, button_selector)
                                for elem in elements:
                                    if elem.is_displayed() and elem.is_enabled() and elem.text.strip() == button_text:
                                        fresh_button = elem
                                        break
                            except:
                                pass
                        
                        if fresh_button:
                            # Scroll to button and click
                            driver.execute_script("arguments[0].scrollIntoView(true);", fresh_button)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", fresh_button)
                            logger.info(f"Clicked continue button: '{button_text}'")
                            continue_clicked = True
                        else:
                            # Fallback: try to click the original element
                            driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", continue_button)
                            logger.info(f"Clicked continue button (fallback): '{button_text}'")
                            continue_clicked = True
                        
                        # Step 2: Wait for countdown (10-15 seconds)
                        logger.info("Waiting for countdown timer (12 seconds)...")
                        time.sleep(12)
                        
                        # Check if URL changed after clicking continue
                        new_url = driver.current_url
                        if new_url != current_url:
                            logger.info(f"URL changed after continue click: {new_url}")
                            
                            # Check if we're redirected to final destination
                            if 'hblinks.dad' in new_url or 'archives' in new_url:
                                return new_url
                            
                            # Check if we're redirected to an intermediate ad page
                            if 'stake.bet' in new_url or 'taazabull24.com' not in new_url:
                                logger.info("Detected intermediate ad page, waiting for redirect back...")
                                # Wait for potential redirect back to taazabull or final destination
                                for wait_attempt in range(2):  # Wait up to 4 seconds
                                    time.sleep(2)
                                    current_check_url = driver.current_url
                                    logger.info(f"Checking URL (attempt {wait_attempt + 1}): {current_check_url}")
                                    
                                    # Check if we're back on taazabull or at final destination
                                    if 'hblinks.dad' in current_check_url or 'archives' in current_check_url:
                                        logger.info(f"Redirected to final destination: {current_check_url}")
                                        return current_check_url
                                    elif 'taazabull24.com' in current_check_url:
                                        logger.info(f"Redirected back to taazabull: {current_check_url}")
                                        new_url = current_check_url
                                        break
                                    
                                # If still on ad page, try to close it or go back
                                if 'taazabull24.com' not in driver.current_url:
                                    logger.info("Still on ad page, trying to go back...")
                                    try:
                                        driver.back()
                                        time.sleep(3)
                                        new_url = driver.current_url
                                        logger.info(f"After going back: {new_url}")
                                        
                                        # If we're back on homelander page, we need to wait for countdown again
                                        if '/homelander/' in new_url:
                                            logger.info("Back on homelander page after ad redirect...")
                                            
                                            # Check if continue button is still there (meaning countdown hasn't started)
                                            continue_still_there = False
                                            try:
                                                continue_elements = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]")
                                                for elem in continue_elements:
                                                    if elem.is_displayed() and elem.is_enabled():
                                                        continue_still_there = True
                                                        break
                                            except:
                                                pass
                                            
                                            if continue_still_there:
                                                logger.info("Continue button still present, clicking it again...")
                                                # Click continue button again since we're back to initial state
                                                try:
                                                    continue_elements = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]")
                                                    for elem in continue_elements:
                                                        if elem.is_displayed() and elem.is_enabled():
                                                            driver.execute_script("arguments[0].click();", elem)
                                                            logger.info("Clicked continue button after going back")
                                                            break
                                                except Exception as e:
                                                    logger.warning(f"Could not click continue button after going back: {e}")
                                            else:
                                                logger.info("Continue button not found, countdown may already be running")
                                            
                                            logger.info("Waiting for countdown to complete...")
                                            # Wait for countdown timer to complete (usually 10-15 seconds)
                                            time.sleep(15)
                                            
                                    except:
                                        logger.warning("Could not go back from ad page")
                                        return url
                        
                        # Step 3: Look for "Get Links" or download button
                        # First check if we're now on the final page after redirect handling
                        final_check_url = driver.current_url
                        if 'hblinks.dad' in final_check_url or 'archives' in final_check_url:
                            logger.info(f"Already at final destination after redirect handling: {final_check_url}")
                            return final_check_url
                        
                        get_links_selectors = [
                            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'link')]",
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'link')]",
                            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]",
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download')]",
                            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'proceed')]",
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'proceed')]",
                            "//*[@id='getlink']",
                            "//*[@id='download']",
                            "//*[@class*='getlink']",
                            "//*[@class*='download']",
                            "//input[@type='submit']",
                            "//button[@type='submit']"
                        ]
                        
                        get_links_button = None
                        # Wait a bit more for the button to appear and become enabled
                        for attempt in range(3):
                            logger.info(f"Looking for Get Links button (attempt {attempt + 1})...")
                            
                            for selector in get_links_selectors:
                                try:
                                    elements = driver.find_elements(By.XPATH, selector)
                                    for elem in elements:
                                        if elem.is_displayed() and elem.is_enabled():
                                            elem_text = elem.text.strip()
                                            logger.info(f"Found enabled button: '{elem_text}' using: {selector}")
                                            get_links_button = elem
                                            break
                                    if get_links_button:
                                        break
                                except:
                                    continue
                            
                            if get_links_button:
                                break
                            else:
                                logger.info("Button not found yet, waiting 2 more seconds...")
                                time.sleep(2)
                        
                        if get_links_button:
                            try:
                                # Store button info to avoid stale element
                                get_button_text = get_links_button.text.strip()
                                get_button_selector = None
                                
                                # Find which selector worked for this button
                                for selector in get_links_selectors:
                                    try:
                                        elements = driver.find_elements(By.XPATH, selector)
                                        for elem in elements:
                                            if elem.is_displayed() and elem.is_enabled() and elem.text.strip() == get_button_text:
                                                get_button_selector = selector
                                                break
                                        if get_button_selector:
                                            break
                                    except:
                                        continue
                                
                                # Re-find the element to avoid stale reference
                                fresh_get_button = None
                                if get_button_selector:
                                    try:
                                        elements = driver.find_elements(By.XPATH, get_button_selector)
                                        for elem in elements:
                                            if elem.is_displayed() and elem.is_enabled() and elem.text.strip() == get_button_text:
                                                fresh_get_button = elem
                                                break
                                    except:
                                        pass
                                
                                if fresh_get_button:
                                    driver.execute_script("arguments[0].scrollIntoView(true);", fresh_get_button)
                                    time.sleep(1)
                                    driver.execute_script("arguments[0].click();", fresh_get_button)
                                    logger.info(f"Clicked get links button: '{get_button_text}'")
                                else:
                                    # Fallback: try original element
                                    driver.execute_script("arguments[0].scrollIntoView(true);", get_links_button)
                                    time.sleep(1)
                                    driver.execute_script("arguments[0].click();", get_links_button)
                                    logger.info(f"Clicked get links button (fallback): '{get_button_text}'")
                                
                                # Wait for final redirect
                                time.sleep(5)
                                
                                final_url = driver.current_url
                                if final_url != url and final_url != current_url:
                                    logger.info(f"Successfully resolved taazabull shortlink: {url} -> {final_url}")
                                    return final_url
                                else:
                                    # Look for any download links on the page
                                    download_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'hblinks') or contains(@href, 'archives') or contains(@href, 'download')]")
                                    for link in download_links:
                                        href = link.get_attribute('href')
                                        if href and href != url:
                                            logger.info(f"Found download link: {href}")
                                            return href
                                            
                            except Exception as e:
                                logger.error(f"Error clicking get links button: {e}")
                        else:
                            logger.warning("Could not find 'Get Links' button after countdown")
                            
                            # Debug: Log what's actually on the page
                            try:
                                all_buttons = driver.find_elements(By.XPATH, "//button | //input[@type='button'] | //input[@type='submit']")
                                all_links = driver.find_elements(By.XPATH, "//a[@href]")
                                
                                logger.info(f"DEBUG: Found {len(all_buttons)} buttons on page:")
                                for i, btn in enumerate(all_buttons[:5]):
                                    try:
                                        btn_text = btn.text.strip()
                                        btn_id = btn.get_attribute('id')
                                        btn_class = btn.get_attribute('class')
                                        btn_enabled = btn.is_enabled()
                                        btn_displayed = btn.is_displayed()
                                        logger.info(f"  Button {i+1}: text='{btn_text}', id='{btn_id}', class='{btn_class}', enabled={btn_enabled}, displayed={btn_displayed}")
                                    except:
                                        pass
                                
                                logger.info(f"DEBUG: Found {len(all_links)} links on page:")
                                for i, link in enumerate(all_links[:5]):
                                    try:
                                        link_text = link.text.strip()
                                        link_href = link.get_attribute('href')
                                        logger.info(f"  Link {i+1}: text='{link_text}', href='{link_href}'")
                                    except:
                                        pass
                            except Exception as debug_e:
                                logger.error(f"Error during debug logging: {debug_e}")
                                
                    except Exception as e:
                        logger.error(f"Error clicking continue button: {e}")
                else:
                    logger.warning("Could not find 'Click to Continue' button")
                    
                    # Debug: Log what buttons are available
                    try:
                        all_buttons = driver.find_elements(By.XPATH, "//button | //input[@type='button'] | //input[@type='submit'] | //a")
                        logger.info(f"DEBUG: Found {len(all_buttons)} clickable elements:")
                        for i, btn in enumerate(all_buttons[:10]):
                            try:
                                btn_text = btn.text.strip()
                                btn_tag = btn.tag_name
                                btn_id = btn.get_attribute('id')
                                btn_class = btn.get_attribute('class')
                                if btn_text and len(btn_text) < 50:
                                    logger.info(f"  Element {i+1}: {btn_tag} text='{btn_text}', id='{btn_id}', class='{btn_class}'")
                            except:
                                pass
                    except Exception as debug_e:
                        logger.error(f"Error during initial debug logging: {debug_e}")
                
                return url
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error resolving taazabull shortlink: {e}")
            return url

    def resolve_redirects(self, url: str, max_redirects: int = 5) -> str:
        """Follow redirects to get actual download URL"""
        try:
            # Skip taazabull24.com resolution during extraction - will be resolved on-demand when user clicks
            if 'taazabull24.com' in url.lower():
                logger.info(f"Taazabull24.com link detected, will resolve on-demand: {url}")
                return url  # Return as-is, resolve later when user clicks
            
            for _ in range(max_redirects):
                response = self.session.head(url, allow_redirects=False, timeout=10)
                
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location')
                    if location:
                        url = urljoin(url, location)
                    else:
                        break
                else:
                    break
            
            return url
            
        except:
            return url
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from movie page"""
        metadata = {}
        
        # Extract description
        desc_elem = soup.find('div', class_=re.compile(r'content|description|summary', re.I))
        if desc_elem:
            metadata['description'] = desc_elem.get_text(strip=True)[:500]
        
        # Extract genre, year, etc. from meta tags or structured data
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name', '').lower()
            content = tag.get('content', '')
            
            if name in ['description', 'keywords']:
                metadata[name] = content
        
        return metadata
    
    def bypass_ads_and_redirects(self, url: str) -> str:
        """Attempt to bypass common ad redirects and get direct link"""
        try:
            # Common ad bypass patterns
            bypass_patterns = [
                r'go\.php\?url=([^&]+)',
                r'redirect\.php\?url=([^&]+)',
                r'link\.php\?url=([^&]+)',
                r'url=([^&]+)',
            ]
            
            for pattern in bypass_patterns:
                match = re.search(pattern, url)
                if match:
                    import urllib.parse
                    decoded_url = urllib.parse.unquote(match.group(1))
                    return decoded_url
            
            return url
            
        except:
            return url

def main():
    """Main function for testing the agent"""
    agent = DownloadHubAgent()
    
    # Example usage
    movie_name = input("Enter movie name to search: ").strip()
    
    if not movie_name:
        print("Please enter a valid movie name")
        return
    
    # Search for movies
    print(f"\nSearching for '{movie_name}'...")
    search_results = agent.search_movies(movie_name)
    
    if not search_results:
        print("No movies found!")
        return
    
    # Display search results
    print(f"\nFound {len(search_results)} movies:")
    for i, movie in enumerate(search_results, 1):
        print(f"{i}. {movie['title']} ({movie['year']}) - {movie['language']} - {movie['quality']}")
    
    # Get user selection
    try:
        choice = int(input(f"\nSelect movie (1-{len(search_results)}): ")) - 1
        if 0 <= choice < len(search_results):
            selected_movie = search_results[choice]
            
            # Extract download links
            print(f"\nExtracting download links for: {selected_movie['title']}")
            download_data = agent.get_download_links(selected_movie['detail_url'])
            
            # Save results to JSON
            output_file = f"downloadhub_results_{movie_name.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(download_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nResults saved to: {output_file}")
            print(f"Total download links found: {download_data.get('total_links', 0)}")
            
            # Display some links
            links = download_data.get('download_links', [])
            if links:
                print("\nSample download links:")
                for i, link in enumerate(links[:5], 1):
                    print(f"{i}. {link['text']} - {link['host']} ({link['quality']})")
        else:
            print("Invalid selection!")
            
    except ValueError:
        print("Please enter a valid number!")

if __name__ == "__main__":
    main()