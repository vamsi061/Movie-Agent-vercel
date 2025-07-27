#!/usr/bin/env python3
"""
SkySetX Agent - Movie search and link extraction from skysetx.rip
Similar to MoviezWap and MovieRulz agents
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from urllib.parse import urljoin, urlparse

class SkySetXAgent:
    def __init__(self, config=None):
        self.base_url = "https://skysetx.rip"
        self.search_url = f"{self.base_url}/?s="
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def search_movies(self, query, limit=10):
        """Search for movies on SkySetX"""
        try:
            search_url = f"{self.search_url}{query}"
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            movies = []
            
            # Parse movie results
            movie_containers = soup.find_all('div', class_='thumb')
            
            for container in movie_containers[:limit]:
                try:
                    # Extract movie link and title
                    link_elem = container.find('a', href=True)
                    if not link_elem:
                        continue
                        
                    movie_url = link_elem['href']
                    title_elem = container.find('p')
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                    
                    # Extract image
                    img_elem = container.find('img')
                    image = img_elem['src'] if img_elem and img_elem.get('src') else ""
                    
                    movies.append({
                        'title': title,
                        'url': movie_url,
                        'image': image,
                        'source': 'SkySetX'
                    })
                except Exception as e:
                    continue
                    
            return movies[:limit]
            
        except Exception as e:
            print(f"Error searching SkySetX: {e}")
            return []
        
    def extract_links(self, movie_url):
        """Extract download links from movie page"""
        try:
            # First try basic HTTP request
            response = self.session.get(movie_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            # Look for download links in various patterns
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link['href']
                text = link.get_text(strip=True).lower()
                
                # Check for external download hosts
                if any(host in href for host in ['drive.google', 'mega.nz', 'mediafire', 'dropbox', 'uploadrar', 'rapidgator']):
                    quality = self._extract_quality_from_text(text)
                    links.append({
                        'url': href,
                        'quality': quality,
                        'size': 'Unknown',
                        'type': 'download'
                    })
                
                # Check for SkySetX internal download pages
                elif 'skysetx.rip' in href and any(word in text for word in ['download', '480p', '720p', '1080p']):
                    quality = self._extract_quality_from_text(text)
                    links.append({
                        'url': href,
                        'quality': quality,
                        'size': 'Unknown',
                        'type': 'page'
                    })
            
            return links
            
        except Exception as e:
            print(f"Error extracting links from SkySetX: {e}")
            return []
    
    def _extract_quality_from_text(self, text):
        """Extract quality from link text"""
        if '1080p' in text:
            return '1080p'
        elif '720p' in text:
            return '720p'
        elif '480p' in text:
            return '480p'
        elif '4k' in text.lower():
            return '4K'
        return 'Unknown'

if __name__ == "__main__":
    agent = SkySetXAgent()
    print("SkySetX Agent initialized successfully!")