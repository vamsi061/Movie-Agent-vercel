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

    def search_movies(self, movie_name: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Search MovieBox for a title."""
        try:
            url = self.search_url.format(quote(movie_name))
            logger.info(f"MovieBox: searching {url}")
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            results: List[Dict[str, Any]] = []

            # MovieBox layout guess: look for anchors under results with movie cards
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                if not text:
                    # try alt/title
                    img = a.find('img')
                    if img and img.get('alt'):
                        text = img['alt'].strip()
                if not text:
                    continue

                # Heuristic: detail links often contain "/web/" or "/movie/" or similar
                if any(seg in href.lower() for seg in ['web/', 'movie/', '/movies/', '/title/']):
                    detail_url = href if href.startswith('http') else urljoin(self.base_url, href)
                    title = self._clean_title(text)
                    if len(title) < 2:
                        continue
                    item = {
                        'title': title,
                        'detail_url': detail_url,
                        'url': detail_url,
                        'source': 'MovieBox',
                        'language': self._guess_language_from_text(title),
                        'year': self._extract_year(title) or '',
                        'quality': self._extract_qualities(title) or [],
                    }
                    results.append(item)

            # Deduplicate by URL
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
