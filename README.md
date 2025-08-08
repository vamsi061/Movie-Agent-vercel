# Movie Web Interface

A Flask-based web application for searching and streaming movies from various sources.

## Features

- **Movie Search**: Search for movies using intelligent fuzzy matching
- **Multiple Sources**: Supports various movie hosting sites
- **Video Streaming**: Direct video streaming with CORS bypass
- **Download Links**: Extract download links from movie pages
- **Responsive UI**: Clean and modern web interface

## Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd movie_web_interface
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python web_interface.py
```

5. **Access the application**
Open your browser and go to: `http://localhost:8080`

## Dependencies

- Flask - Web framework
- Selenium - Web scraping with Chrome automation
- BeautifulSoup4 - HTML parsing
- Requests - HTTP requests
- Levenshtein - Fuzzy string matching
- undetected-chromedriver - Bot detection bypass

## Configuration

Edit `config.json` to customize:
- Base URLs for movie sites
- Selenium settings
- Quality and language filters
- Output preferences

## API Endpoints

- `GET /` - Main interface
- `POST /search` - Search for movies
- `POST /extract` - Extract download links
- `GET /status/<id>` - Check extraction status
- `GET /proxy_video` - Stream videos via proxy
- `GET /health` - Health check
- `POST /api/telegram/link` - Get a Telegram deep link for a movie (if available) by title/year/language

## Usage

1. Enter a movie name in the search box
2. Apply filters for language, year, or quality
3. Browse search results
4. Click on a movie to extract streaming/download links
5. Use the built-in player or download links

## License

This project is for educational purposes only.