#!/usr/bin/env python3
"""
MovieBox Agent - Searches and extracts links from moviebox.ph
"""
from typing import Dict, Any, List, Optional
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MovieBoxAgent:
    def __init__(self):
        self.config = self._load_agent_config()
        self.base_url = self.config.get('base_url', 'https://moviebox.ph')
        self.search_url = self.config.get('search_url', f"{self.base_url}/web/searchResult?keyword={{}}&utm_source=")
        # Optional DOM tailoring via config
        self.custom_selectors = {
            'result_container_selectors': self.config.get('result_container_selectors', []),
            'detail_link_selectors': self.config.get('detail_link_selectors', []),
            'title_selectors': self.config.get('title_selectors', []),
            'exclude_link_selectors': self.config.get('exclude_link_selectors', []),
            'exclude_link_classes': self.config.get('exclude_link_classes', ['btn', 'button', 'bookmark', 'favorite', 'share', 'login', 'signup']),
        }
        # Provide sensible defaults if not configured
        if not self.custom_selectors['result_container_selectors']:
            self.custom_selectors['result_container_selectors'] = [
                'div.search-result', 'div.search-results', 'div.search-list', 'ul.search-list',
                'div.result-list', 'div.results', 'div.result-item', 'div.card', 'div.card-item',
                'div.movie-item', 'div.video-item', 'section.search', 'section.results',
                'div.film_list-wrap', 'div.flw-item', 'div.items', 'div.item', 'ul.items', 'li.item',
                'div.grid', 'div.grid-item', 'div.col', 'div.col-4', 'div.col-3', 'div.col-2'
            ]
        if not self.custom_selectors['detail_link_selectors']:
            self.custom_selectors['detail_link_selectors'] = [
                'a[href*="/web/"]', 'a[href*="/movie"]', 'a[href*="/film"]', 'a[href*="/series"]',
                'a[href*="/tv"]', 'a[href*="/watch"]', 'a[href*="/play"]', 'a[href*="/detail"]', 'a[href*="/title"]',
                'a[href*="videoId="]'
            ]
        if not self.custom_selectors['title_selectors']:
            self.custom_selectors['title_selectors'] = [
                '.title', '.name', '.movie-title', '.item-title', '.film-title', '.card-title',
                '.video-title', '.video_name', '.movie-name', '.title-name', 'h1', 'h2', 'h3'
            ]
        self.session = requests.Session()
        self._setup_session()

    def _load_agent_config(self) -> Dict[str, Any]:
        try:
            import os, json
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agent_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                return data.get('agents', {}).get('moviebox', {})
        except Exception as e:
            logger.warning(f"MovieBox: could not load agent config: {e}")
        return {}

    def _setup_session(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)
        self.session.timeout = 30

    def _get_rendered_html(self, url: str, wait: int = 15) -> Optional[str]:
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import time
            options = uc.ChromeOptions()
            options.headless = True
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            driver = None
            try:
                try:
                    driver = uc.Chrome(options=options)
                except Exception as e:
                    # Retry with version_main if mismatch
                    import re as _re
                    m = _re.search(r"Current browser version is\s*(\d+)", str(e))
                    if m:
                        ver = int(m.group(1))
                        options_retry = uc.ChromeOptions()
                        options_retry.headless = True
                        options_retry.add_argument("--no-sandbox")
                        options_retry.add_argument("--disable-dev-shm-usage")
                        options_retry.add_argument("--disable-blink-features=AutomationControlled")
                        options_retry.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                        driver = uc.Chrome(options=options_retry, version_main=ver)
                    else:
                        raise
                driver.set_page_load_timeout(30)
                driver.get(url)
                
                # Wait for initial page load
                time.sleep(3)
                
                # Wait for search results to load (look for movie-like content)
                try:
                    # Try to wait for search results specifically
                    search_selectors = [
                        "[class*='search']", "[class*='result']", "[class*='movie']", 
                        "[class*='film']", "[class*='item']", "[class*='card']"
                    ]
                    
                    for selector in search_selectors:
                        try:
                            WebDriverWait(driver, 4).until(
                                lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) > 5
                            )
                            logger.info(f"MovieBox: Found elements with selector {selector}")
                            break
                        except Exception:
                            continue
                    
                    # Additional wait for dynamic content
                    time.sleep(wait)
                    
                    # Try scrolling to trigger lazy loading
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                except Exception:
                    # If specific wait fails, just use the general wait
                    time.sleep(wait)
                
                return driver.page_source
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            logger.warning(f"MovieBox: headless render failed: {e}")
            return None

    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Search MovieBox for a title."""
        try:
            # Build a list of candidate search URLs to improve robustness against site changes
            q_enc = quote(movie_name)
            base = self.base_url.rstrip('/')
            candidates = []
            # Prefer configured search_url first
            if self.search_url:
                try:
                    # Handle search URLs that might not have {} placeholder
                    if '{}' in self.search_url:
                        candidates.append(self.search_url.format(q_enc))
                    elif 'keyword=' in self.search_url and self.search_url.endswith('='):
                        # Handle URLs ending with 'keyword=' 
                        candidates.append(self.search_url + q_enc)
                    elif 'keyword=' in self.search_url:
                        # Replace existing keyword value
                        candidates.append(re.sub(r'keyword=[^&]*', f'keyword={q_enc}', self.search_url))
                    else:
                        # Fallback: append as query parameter
                        sep = '&' if '?' in self.search_url else '?'
                        candidates.append(f"{self.search_url}{sep}keyword={q_enc}")
                except Exception as e:
                    logger.warning(f"MovieBox: failed to format search_url '{self.search_url}': {e}")
                    pass
            # Common alternatives observed across deployments
            candidates.extend([
                f"{base}/web/searchResult?keyword={q_enc}",
                f"{base}/web/search?keyword={q_enc}",
                f"{base}/searchResult?keyword={q_enc}",
                f"{base}/search?keyword={q_enc}",
                f"{base}/?s={q_enc}",
            ])

            results: List[Dict[str, Any]] = []
            base_host = urlparse(self.base_url).netloc

            def is_internal_href(href: str) -> bool:
                if not href:
                    return False
                if href.startswith('/'):
                    return True
                if href.startswith('http'):
                    try:
                        return urlparse(href).netloc.endswith(base_host)
                    except Exception:
                        return False
                return False

            def is_generic_label(t: str) -> bool:
                t_clean = re.sub(r'[^a-z]', '', (t or '').lower())
                return t_clean in {'tvshow', 'movie', 'animation', 'series', 'documentary', 'episode', 'season'}

            def extract_title_from_container(container) -> str:
                # Known selectors
                for sel in ['.title', '.name', '.movie-title', '.item-title', '.film-title', '.card-title', 'h1', 'h2', 'h3']:
                    el = container.select_one(sel)
                    if el:
                        cand = el.get_text(strip=True)
                        if cand and not is_generic_label(cand):
                            return self._clean_title(cand)
                # Longest meaningful text fallback within container
                texts = []
                try:
                    for s in getattr(container, 'stripped_strings', []) or []:
                        st = str(s).strip()
                        if not st:
                            continue
                        st_l = st.lower()
                        if st_l in {'watch now', 'watch', 'play', 'movies', 'series', 'music', 'all'}:
                            continue
                        if not is_generic_label(st) and len(st) > 2:
                            texts.append(st)
                except Exception:
                    pass
                if texts:
                    texts.sort(key=len, reverse=True)
                    return self._clean_title(texts[0])
                return ''

            def extract_candidates_from_soup(soup: BeautifulSoup) -> List[Dict[str, str]]:
                items: List[Dict[str, str]] = []

                # If custom selectors are provided via config, use them first
                try:
                    cs = self.custom_selectors
                    if cs:
                        # Result containers (optional)
                        if cs.get('result_container_selectors'):
                            for sel in cs['result_container_selectors']:
                                for container in soup.select(sel):
                                    links = []
                                    if cs.get('detail_link_selectors'):
                                        for lsel in cs['detail_link_selectors']:
                                            links.extend(container.select(lsel))
                                    else:
                                        links.extend(container.find_all('a', href=True))
                                    for a in links:
                                        href = a.get('href')
                                        if not href or not is_internal_href(href):
                                            continue
                                        # Exclusions
                                        cls = a.get('class') or []
                                        if any(c in cs.get('exclude_link_classes', []) for c in cls):
                                            continue
                                        if cs.get('exclude_link_selectors'):
                                            bad = False
                                            for ex in cs['exclude_link_selectors']:
                                                try:
                                                    if a.select_one(ex):
                                                        bad = True
                                                        break
                                                except Exception:
                                                    pass
                                            if bad:
                                                continue
                                        title = ''
                                        if cs.get('title_selectors'):
                                            for tsel in cs['title_selectors']:
                                                el = container.select_one(tsel) or a.select_one(tsel)
                                                if el:
                                                    title = el.get_text(strip=True)
                                                    if title:
                                                        break
                                        if not title:
                                            title = (a.get('title') or '').strip()
                                        if not title:
                                            img = container.find('img') or a.find('img')
                                            if img and img.get('alt'):
                                                title = img['alt'].strip()
                                        if not title:
                                            title = (a.get_text(strip=True) or '').strip()
                                        title = self._clean_title(title)
                                        if title and not is_generic_label(title):
                                            items.append({'title': title, 'detail_url': href if href.startswith('http') else urljoin(self.base_url, href)})
                        # If we found any via custom selectors, return early
                        if items:
                            return items
                except Exception as _:
                    pass

                def get_best_title(tag) -> str:
                    # Try common attributes first
                    for attr in ('data-title', 'data-name', 'aria-label', 'title'):
                        v = tag.get(attr)
                        if v and isinstance(v, str) and not is_generic_label(v):
                            return self._clean_title(v)
                    # Try nested elements commonly used for titles
                    for sel in ['.title', '.name', '.movie-title', '.item-title', '.film-title', '.card-title', '.video-title', '.video_name', '.movie-name', '.title-name']:
                        el = tag.select_one(sel)
                        if el:
                            v = el.get_text(strip=True)
                            if v:
                                return self._clean_title(v)
                    # Try image alt
                    img = tag.find('img')
                    if img:
                        for attr in ('alt', 'data-alt', 'title'):
                            v = img.get(attr)
                            if v and isinstance(v, str) and not is_generic_label(v):
                                return self._clean_title(v)
                    # For link text, try to extract movie title from descriptions
                    txt = (tag.get_text(strip=True) or '').strip()
                    
                    # Extract title from patterns like "go to MovieName [Language] detail page"
                    import re
                    if 'go to' in txt.lower() and 'detail page' in txt.lower():
                        match = re.search(r'go to\s+(.+?)\s*\[', txt, re.IGNORECASE)
                        if match:
                            extracted_title = match.group(1).strip()
                            if extracted_title and not is_generic_label(extracted_title):
                                return self._clean_title(extracted_title)
                    
                    return self._clean_title(txt)

                # Strategy A: Buttons or anchors with watch-like labels (when present)
                watch_nodes = []
                for tag in soup.find_all(['a', 'button']):
                    label = (tag.get_text(strip=True) or '').lower()
                    if label in ('watch now', 'watch', 'play'):
                        watch_nodes.append(tag)
                logger.info(f"MovieBox: found watch nodes: {len(watch_nodes)}")
                for node in watch_nodes:
                    container = node
                    for _ in range(4):
                        if container and container.parent:
                            container = container.parent
                            candidates = []
                            for a in container.find_all('a', href=True):
                                if not is_internal_href(a['href']):
                                    continue
                                hl = a['href'].lower()
                                if any(seg in hl for seg in ['/web/', '/movie', '/film', '/series', '/tv', '/watch', '/play', '/detail', '/title']):
                                    candidates.append(a)
                            if candidates:
                                a = candidates[0]
                                title = extract_title_from_container(container) or get_best_title(a)
                                title = self._clean_title(title)
                                if title and not is_generic_label(title):
                                    detail_url = a['href'] if a['href'].startswith('http') else urljoin(self.base_url, a['href'])
                                    items.append({'title': title, 'detail_url': detail_url})
                                break

                # Strategy B: Specific containers commonly seen on MovieBox-like sites
                container_selectors = [
                    # Common movie site patterns
                    'div.search-result', 'div.search-results', 'div.search-list', 'ul.search-list',
                    'div.result-list', 'div.results', 'div.result-item', 'div.card', 'div.card-item',
                    'div.movie-item', 'div.video-item', 'section.search', 'section.results',
                    'div.film_list-wrap', 'div.flw-item', 'div.items', 'div.item', 'ul.items', 'li.item',
                    # MovieBox specific patterns
                    'div.movie-card', 'div.film-card', 'div.content-item', 'div.media-item',
                    'article', 'div.post', 'div.entry', 'div.thumbnail', 'div.poster',
                    # Bootstrap/responsive patterns  
                    'div.row div.col', 'div.container div.row', 'div.card-deck div.card',
                    # List patterns
                    'ul.movie-list li', 'ol.results li', 'div.list-item',
                    # Generic content patterns (broader search)
                    'div[class*="movie"]', 'div[class*="film"]', 'div[class*="video"]',
                    'div[class*="content"]', 'div[class*="media"]', 'div[class*="item"]',
                    # Grid and layout patterns
                    'div.grid', 'div.grid-item', 'div.col', 'div.col-4', 'div.col-3', 'div.col-2',
                    'div.row', 'div.column', 'div.flex-item'
                ]
                for sel in container_selectors:
                    for container in soup.select(sel):
                        # Find internal anchors that likely point to detail/watch pages
                        for a in container.find_all('a', href=True):
                            href = a['href']
                            if not is_internal_href(href):
                                continue
                            hl = href.lower()
                            if not any(seg in hl for seg in ['/web/', '/movie', '/film', '/series', '/tv', '/watch', '/play', '/detail', '/title', '/video', '/subject']):
                                continue
                            title = extract_title_from_container(container) or get_best_title(a)
                            title = self._clean_title(title)
                            if title and not is_generic_label(title):
                                detail_url = href if href.startswith('http') else urljoin(self.base_url, href)
                                items.append({'title': title, 'detail_url': detail_url})

                # Strategy C: Broad direct anchors (works without watch buttons/containers)
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if not is_internal_href(href):
                        continue
                    hl = href.lower()
                    if any(seg in hl for seg in ['/web/', '/movie', '/film', '/series', '/tv', '/watch', '/play', '/detail', '/title', '/video', '/subject', 'videoId=']):
                        title = get_best_title(a)
                        title = self._clean_title(title)
                        if title and not is_generic_label(title):
                            detail_url = href if href.startswith('http') else urljoin(self.base_url, href)
                            items.append({'title': title, 'detail_url': detail_url})

                # Strategy D: Aggressive search - look for ANY links with movie-like patterns
                # This catches cases where movies aren't in standard containers
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if not is_internal_href(href):
                        continue
                    
                    # Look for movie-like URLs or text patterns
                    text = a.get_text(strip=True)
                    href_lower = href.lower()
                    text_lower = text.lower() if text else ''
                    
                    # Check if this looks like a movie link
                    is_movie_link = False
                    
                    # URL patterns that suggest movies
                    if any(pattern in href_lower for pattern in ['/movie', '/film', '/watch', '/play', '/detail', '/title', '/video']):
                        is_movie_link = True
                    
                    # Text patterns that suggest movie titles
                    elif text and len(text) > 3:
                        # Skip obvious navigation
                        if not any(nav in text_lower for nav in ['home', 'about', 'contact', 'login', 'register', 'menu', 'search']):
                            # Look for year patterns or movie-like text
                            if re.search(r'\b(19|20)\d{2}\b', text) or len(text.split()) >= 2:
                                is_movie_link = True
                    
                    if is_movie_link:
                        title = get_best_title(a)
                        title = self._clean_title(title)
                        if title and not is_generic_label(title) and len(title) > 2:
                            detail_url = href if href.startswith('http') else urljoin(self.base_url, href)
                            items.append({'title': title, 'detail_url': detail_url})

                # Strategy E: Look for onclick/data-href/data-url attributes with internal paths
                for tag in soup.find_all(True):
                    for attr in ('onclick', 'data-href', 'data-url'):
                        val = tag.get(attr)
                        if not val or not isinstance(val, str):
                            continue
                        m = re.search(r"['\"](/[^'\"]+)['\"]", val)
                        if m:
                            href = m.group(1)
                            if is_internal_href(href):
                                title = extract_title_from_container(tag) or get_best_title(tag)
                                title = self._clean_title(title)
                                if title and not is_generic_label(title):
                                    detail_url = urljoin(self.base_url, href)
                                    items.append({'title': title, 'detail_url': detail_url})
                return items

            # Warm up session to obtain cookies and reduce bot blocks
            try:
                self.session.get(f"{base}/", timeout=15, headers={'Referer': f'{base}/'})
                self.session.get(f"{base}/web", timeout=10, headers={'Referer': f'{base}/'})
            except Exception:
                pass

            # Try all candidate search URLs until we get items
            for idx, url in enumerate(candidates):
                try:
                    logger.info(f"MovieBox: searching {url}")
                    # Add a referer header for better acceptance
                    headers = {'Referer': f'{base}/', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7'}
                    resp = self.session.get(url, timeout=30, headers=headers)
                    resp.raise_for_status()

                    candidate_items: List[Dict[str, Any]] = []

                    # If JSON, try to parse API-like responses
                    ct = resp.headers.get('Content-Type', '')
                    text = resp.text or ''
                    if 'application/json' in ct or (text and text.strip().startswith(('{', '['))):
                        try:
                            import json
                            data = json.loads(text)
                            def walk(obj):
                                if isinstance(obj, dict):
                                    # Try to extract item-like structures
                                    title = obj.get('title') or obj.get('name') or obj.get('movieTitle')
                                    url_field = obj.get('url') or obj.get('link') or obj.get('href')
                                    slug = obj.get('slug') or obj.get('path')
                                    vid = obj.get('id') or obj.get('videoId') or obj.get('movieId')
                                    if title and (url_field or slug or vid):
                                        if url_field and is_internal_href(url_field):
                                            detail_url = url_field if url_field.startswith('http') else urljoin(self.base_url, url_field)
                                            candidate_items.append({'title': self._clean_title(str(title)), 'detail_url': detail_url})
                                        elif slug:
                                            href = slug if slug.startswith('/') else f'/{slug}'
                                            detail_url = urljoin(self.base_url, href)
                                            candidate_items.append({'title': self._clean_title(str(title)), 'detail_url': detail_url})
                                        elif vid:
                                            # Conservative guess for play/detail endpoints
                                            for pattern in [f"/web/play?videoId={vid}", f"/web/detail?videoId={vid}", f"/detail/{vid}"]:
                                                detail_url = urljoin(self.base_url, pattern)
                                                candidate_items.append({'title': self._clean_title(str(title)), 'detail_url': detail_url})
                                    for k, v in obj.items():
                                        walk(v)
                                elif isinstance(obj, list):
                                    for it in obj:
                                        walk(it)
                            walk(data)
                        except Exception:
                            candidate_items = []

                    # If not enough from JSON, parse HTML
                    if len(candidate_items) == 0:
                        soup = BeautifulSoup(text, 'html.parser')
                        candidate_items = extract_candidates_from_soup(soup)
                        logger.info(f"MovieBox: parsed candidate items (static): {len(candidate_items)}")
                        # Check if we're getting actual search results or just homepage content
                        if candidate_items:
                            # Check if all results are generic/static content
                            generic_patterns = ['trending now', 'disclaimer', 'moviebox official logo', 'free movies', 'right-icon']
                            real_movie_count = 0
                            for item in candidate_items[:20]:  # Check first 20 items
                                title_lower = item['title'].lower()
                                if not any(pattern in title_lower for pattern in generic_patterns) and len(item['title']) < 100:
                                    real_movie_count += 1
                            
                            # If less than 3 real movie titles found, treat as static content
                            if real_movie_count < 3:
                                logger.warning(f"MovieBox: URL {url} returning mostly generic content ({real_movie_count} real titles), forcing JS rendering")
                                candidate_items = []  # Force JavaScript rendering
                        
                        # If none found, try headless-rendered HTML for this candidate URL
                        if len(candidate_items) == 0:
                            rendered = self._get_rendered_html(url)
                            if rendered:
                                soup_r = BeautifulSoup(rendered, 'html.parser')
                                logger.info("MovieBox: attempting rendered HTML parse")
                                candidate_items = extract_candidates_from_soup(soup_r)
                                logger.info(f"MovieBox: parsed candidate items (rendered): {len(candidate_items)}")
                                
                                # Check rendered results too
                                if candidate_items:
                                    # Count real movie titles vs generic content
                                    generic_patterns = ['trending now', 'disclaimer', 'moviebox official logo', 'free movies', 'right-icon']
                                    real_movie_count = 0
                                    for item in candidate_items[:20]:
                                        title_lower = item['title'].lower()
                                        if not any(pattern in title_lower for pattern in generic_patterns) and len(item['title']) < 100:
                                            real_movie_count += 1
                                    
                                    if real_movie_count < 3:
                                        logger.warning(f"MovieBox: Rendered HTML also returning mostly generic content ({real_movie_count} real titles)")
                                        # Try a different approach - look for specific movie result patterns
                                        soup_alt = BeautifulSoup(rendered, 'html.parser')
                                        
                                        # Look for common movie site patterns more aggressively
                                        movie_patterns = [
                                            'img[alt]',  # Movie posters with alt text
                                            'a[title]',  # Links with title attributes
                                            '*[data-title]',  # Elements with data-title
                                            'h1, h2, h3, h4, h5, h6',  # Headings that might be movie titles
                                        ]
                                        
                                        alt_candidates = []
                                        for pattern in movie_patterns:
                                            elements = soup_alt.select(pattern)
                                            for elem in elements:
                                                title = ''
                                                href = elem.get('href', '')
                                                
                                                if pattern == 'img[alt]':
                                                    title = elem.get('alt', '')
                                                elif pattern == 'a[title]':
                                                    title = elem.get('title', '')
                                                    href = elem.get('href', '')
                                                elif pattern == '*[data-title]':
                                                    title = elem.get('data-title', '')
                                                    if elem.name == 'a':
                                                        href = elem.get('href', '')
                                                else:  # headings
                                                    title = elem.get_text(strip=True)
                                                    # Look for nearby link
                                                    parent = elem.parent
                                                    if parent:
                                                        link = parent.find('a', href=True)
                                                        if link:
                                                            href = link.get('href', '')
                                                
                                                if title and len(title) > 3 and len(title) < 100:
                                                    title_clean = self._clean_title(title)
                                                    if title_clean and not is_generic_label(title_clean):
                                                        # Skip obvious generic content
                                                        if not any(pattern in title_clean.lower() for pattern in generic_patterns):
                                                            detail_url = href if href.startswith('http') else urljoin(self.base_url, href) if href else ''
                                                            if detail_url:
                                                                alt_candidates.append({'title': title_clean, 'detail_url': detail_url})
                                        
                                        if alt_candidates:
                                            logger.info(f"MovieBox: Found {len(alt_candidates)} alternative candidates from rendered HTML")
                                            candidate_items = alt_candidates[:50]  # Limit to reasonable number
                                        else:
                                            candidate_items = []

                    # If still none, log a few anchors for troubleshooting
                    if len(candidate_items) == 0:
                        try:
                            soup_dbg = BeautifulSoup(text, 'html.parser')
                            samples = []
                            for a in soup_dbg.find_all('a', href=True)[:20]:
                                samples.append({
                                    'href': a['href'],
                                    'text': (a.get_text(strip=True) or '')[:80],
                                    'classes': ' '.join(a.get('class') or [])
                                })
                            logger.info(f"MovieBox: sample anchors: {samples}")
                        except Exception:
                            pass

                    # Consolidate and break if we found enough
                    if candidate_items:
                        # Filter by query match and build results
                        logger.info(f"MovieBox: filtering {len(candidate_items)} items for query '{movie_name}'")
                        kept_count = 0
                        for i, item in enumerate(candidate_items):
                            title = item['title']
                            
                            # Clean up title patterns like "go to MovieName [Language] detail page"
                            if 'go to' in title.lower() and 'detail page' in title.lower():
                                match = re.search(r'go to\s+(.+?)\s*\[', title, re.IGNORECASE)
                                if match:
                                    extracted_title = match.group(1).strip()
                                    if extracted_title and not is_generic_label(extracted_title):
                                        title = self._clean_title(extracted_title)
                                        # Update the item with cleaned title
                                        item['title'] = title
                            
                            if i < 5:  # Log first 5 titles for debugging
                                logger.info(f"MovieBox: candidate {i}: '{title}'")
                            
                            if movie_name:
                                q = movie_name.lower()
                                t = title.lower()
                                # Check if query matches title (case insensitive)
                                query_matches = False
                                
                                # Direct substring match
                                if q in t:
                                    query_matches = True
                                    logger.info(f"MovieBox: '{title}' matches '{q}' (substring)")
                                
                                # Individual word matching (for multi-word queries)
                                elif any(word.lower() in t for word in q.split() if len(word) >= 2):
                                    query_matches = True
                                    logger.info(f"MovieBox: '{title}' matches '{q}' (word match)")
                                
                                # For very short queries like "rrr", also check if title starts with the query
                                elif len(q) <= 3 and t.startswith(q):
                                    query_matches = True
                                    logger.info(f"MovieBox: '{title}' matches '{q}' (starts with)")
                                
                                if not query_matches:
                                    if i < 3:  # Log why first few were filtered
                                        logger.info(f"MovieBox: filtered out '{title}' - no match for '{q}'")
                                    continue
                            
                            # Skip generic/navigation elements (expanded list)
                            skip_patterns = [
                                'logo', 'icon', 'free movies', 'moviebox', 'menu', 'home', 'contact', 'about',
                                'trending now', 'disclaimer', 'copyright', 'all videos and pictures', 
                                'internet', 'creators', 'webpage services', 'store', 'record', 'upload',
                                'privacy policy', 'terms of service', 'dmca', 'login', 'register', 'sign up',
                                'search', 'browse', 'categories', 'genres', 'latest', 'popular', 'top rated'
                            ]
                            if any(pattern in title.lower() for pattern in skip_patterns):
                                if i < 3:
                                    logger.info(f"MovieBox: skipped generic element '{title}'")
                                continue
                            
                            # Skip very long text (likely disclaimers/descriptions)
                            if len(title) > 100:
                                if i < 3:
                                    logger.info(f"MovieBox: skipped long text '{title[:50]}...'")
                                continue
                                
                            kept_count += 1
                            results.append({
                                'title': item['title'],
                                'detail_url': item['detail_url'],
                                'url': item['detail_url'],
                                'source': 'MovieBox',
                                'language': self._guess_language_from_text(item['title']),
                                'year': self._extract_year(item['title']) or '',
                                'quality': self._extract_qualities(item['title']) or [],
                            })
                        # If we already have some results, stop trying other URLs
                        logger.info(f"MovieBox: kept {kept_count} out of {len(candidate_items)} items from this URL")
                        if results:
                            logger.info(f"MovieBox: found {len(results)} results, stopping further URL attempts")
                            break
                        # If we got a significant number of proper movie titles from a URL, also stop trying more
                        elif kept_count >= 3:
                            logger.info(f"MovieBox: found {kept_count} results, stopping further URL attempts")
                            break
                        # If we found many real movie titles (even if not kept), continue to next URL for better results
                        elif candidate_items:
                            # Count actual movie titles (not generic elements)
                            generic_patterns = ['trending now', 'disclaimer', 'moviebox official logo', 'free movies', 'right-icon']
                            real_titles = [item for item in candidate_items[:10] 
                                         if not any(pattern in item['title'].lower() for pattern in generic_patterns) 
                                         and len(item['title']) < 100]
                            if len(real_titles) >= 3:
                                logger.info(f"MovieBox: found {len(real_titles)} real movie titles from this URL, trying next URL for exact matches")
                                # Don't break here - continue to next URL
                            else:
                                logger.info(f"MovieBox: only found {len(real_titles)} real movie titles, continuing to next URL")
                except Exception as e:
                    logger.warning(f"MovieBox: search candidate failed: {e}")
                    continue

            # Deduplicate by URL and keep best titles (longer first)
            results.sort(key=lambda r: len(r.get('title') or ''), reverse=True)
            seen = set()
            unique = []
            for r in results:
                if r['url'] not in seen:
                    seen.add(r['url'])
                    unique.append(r)

            return {
                'success': True,
                'movies': unique[:per_page],
                'total': len(unique)
            }
        except Exception as e:
            logger.error(f"MovieBox: search failed: {e}")
            return {'success': False, 'movies': [], 'error': str(e)}

    def extract_download_links(self, detail_url: str) -> Dict[str, Any]:
        """Extract potential download/stream links from a detail page."""
        try:
            logger.info(f"MovieBox: extracting from {detail_url}")
            resp = self.session.get(detail_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            title = ''
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            if not title and soup.title:
                title = soup.title.get_text(strip=True)

            links: List[Dict[str, Any]] = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True) or a.get('title', '')
                if not href or href.startswith('javascript:'):
                    continue
                full = href if href.startswith('http') else urljoin(self.base_url, href)
                # Heuristics: keep direct files or known hosts or download/watch buttons
                if self._is_potential_link(full, text):
                    links.append({
                        'text': text or 'Link',
                        'url': full,
                        'host': urlparse(full).netloc,
                        'quality': self._extract_qualities(text) or [],
                        'file_size': None,
                        'service_type': 'Direct' if self._is_direct_file(full) else 'Link'
                    })

            return {
                'title': title or 'Unknown',
                'url': detail_url,
                'download_links': links,
                'total_links': len(links),
                'source': 'MovieBox'
            }
        except Exception as e:
            logger.error(f"MovieBox: extract failed: {e}")
            return {'error': str(e), 'source': 'MovieBox', 'download_links': [], 'total_links': 0}

    def get_download_links(self, detail_url: str) -> Dict[str, Any]:
        return self.extract_download_links(detail_url)

    # --- Helpers ---
    def _clean_title(self, t: str) -> str:
        return re.sub(r"\s+", " ", t).strip()

    def _extract_year(self, text: str) -> Optional[str]:
        m = re.search(r"\b(19\d{2}|20[0-4]\d)\b", text)
        return m.group(1) if m else None

    def _extract_qualities(self, text: str) -> List[str]:
        qualities = []
        for q in ['2160p', '4K', '1080p', '720p', '480p', 'CAM', 'HDRip', 'WEBRip', 'BluRay', 'HD']:
            if re.search(q, text, re.IGNORECASE):
                qualities.append(q.upper())
        return qualities

    def _guess_language_from_text(self, text: str) -> str:
        tl = text.lower()
        for k, v in [('hindi', 'Hindi'), ('english', 'English'), ('tamil', 'Tamil'), ('telugu', 'Telugu'), ('malayalam', 'Malayalam'), ('kannada', 'Kannada')]:
            if k in tl:
                return v
        return ''

    def _is_direct_file(self, url: str) -> bool:
        return any(ext in url.lower() for ext in ['.mp4', '.mkv', '.avi', '.m3u8'])

    def _is_potential_link(self, url: str, text: str) -> bool:
        host = urlparse(url).netloc.lower()
        keywords = ['download', 'watch', 'play', 'server', 'mirror']
        known_hosts = ['gofile.io', 'pixeldrain.com', 'mediafire.com', 'mega.nz', 'drive.google.com', 'dropbox.com', 'streamtape.com', 'doodstream.com', 'mixdrop.co']
        text_l = (text or '').lower()
        if self._is_direct_file(url):
            return True
        if any(k in text_l for k in keywords):
            return True
        if any(h in host for h in known_hosts):
            return True
        return False


def main():
    agent = MovieBoxAgent()
    q = input("Enter movie to search on MovieBox: ").strip()
    res = agent.search_movies(q)
    print(res)
    if res.get('movies'):
        first = res['movies'][0]
        print('Extracting first:', first.get('title'))
        detail_url = first.get('detail_url') or first.get('url')
        details = agent.get_download_links(detail_url)
        print(details)


if __name__ == '__main__':
    main()
