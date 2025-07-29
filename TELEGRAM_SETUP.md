# Telegram Integration Setup Guide

## 🚀 How to Enable Telegram Movie Search

The Movie Agent now supports searching for movies through Telegram bots and channels! Follow these steps to set it up:

### 📋 Prerequisites

1. **Telegram Account** - You need an active Telegram account
2. **API Credentials** - Get from Telegram's official API
3. **Python Dependencies** - Install required packages

### 🔑 Step 1: Get Telegram API Credentials

1. Go to [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your Telegram account
3. Click "Create new application"
4. Fill in the form:
   - **App title**: Movie Agent
   - **Short name**: movie-agent
   - **Platform**: Desktop
   - **Description**: Movie search and download agent
5. Copy your `api_id` and `api_hash`

### ⚙️ Step 2: Configure Telegram Settings

1. Open `telegram_config.json` in the project directory
2. Update the configuration:

```json
{
  "telegram_settings": {
    "enabled": true,
    "api_id": "YOUR_API_ID_HERE",
    "api_hash": "YOUR_API_HASH_HERE", 
    "phone": "+1234567890",
    "session_name": "movie_agent_session"
  }
}
```

**Replace:**
- `YOUR_API_ID_HERE` with your actual API ID (number)
- `YOUR_API_HASH_HERE` with your actual API hash (string)
- `+1234567890` with your phone number (include country code)

### 📦 Step 3: Install Dependencies

```bash
pip install telethon>=1.24.0
```

### 🔐 Step 4: First Time Authentication

1. Start the Movie Agent application
2. When you first search using Telegram, you'll be prompted to:
   - Enter the verification code sent to your Telegram app
   - If you have 2FA enabled, enter your password
3. The session will be saved for future use

### 🎬 Step 5: Movie Sources Available

The Telegram agent searches these sources:

#### **Movie Bots:**
- @MoviesFlixBot - Latest movie releases
- @HDMoviesBot - HD quality movies  
- @BollyFlixBot - Bollywood movies
- @MovieRequestBot - Movie requests
- @NewMoviesBot - New releases
- @LatestMoviesBot - Latest movies

#### **Movie Channels:**
- @MoviesAdda4u - Movie collection
- @HDMoviesHub - HD movies
- @BollywoodMovies - Bollywood content
- @HollywoodMovies4u - Hollywood movies
- @LatestMovies2024 - 2024 releases
- @MovieDownloadHub - Download links

### 🎯 Features

- **Real-time Search** - Search across multiple Telegram sources
- **Quality Detection** - Automatically detects 4K, 1080p, 720p, 480p
- **Language Support** - Hindi, English, Tamil, Telugu, and more
- **Direct Links** - Get direct download links from Telegram
- **File Size Info** - Shows file sizes when available
- **Source Attribution** - Shows which bot/channel provided the link

### 🔧 Troubleshooting

#### **"Telegram search requested but agent not configured"**
- Make sure `enabled: true` in telegram_config.json
- Verify your API credentials are correct
- Check that telethon is installed

#### **Authentication Issues**
- Delete the session file and re-authenticate
- Make sure your phone number includes country code
- Check if your Telegram account has 2FA enabled

#### **No Results Found**
- Try different search terms
- Some bots may be temporarily offline
- Check if the bots/channels are still active

#### **Rate Limiting**
- Telegram has rate limits for API calls
- The agent automatically handles delays
- If you get flood wait errors, wait and try again

### 🛡️ Security Notes

- **API Credentials**: Keep your API credentials secure
- **Session Files**: Don't share session files
- **Rate Limits**: Respect Telegram's rate limits
- **Terms of Service**: Follow Telegram's ToS

### 📱 Usage

1. Open Movie Agent web interface
2. Search for a movie (Telegram will be included automatically)
3. Look for movies with the Telegram source tag (blue with plane icon)
4. Click "Extract Download Links" to get Telegram download links
5. Enjoy direct downloads from Telegram!

### 🎨 Visual Indicators

- **Source Tag**: Blue gradient with Telegram plane icon
- **Direct Links**: Links to Telegram messages or bots
- **Quality Badges**: Shows detected video quality
- **File Size**: Displays file size when available

---

**🎉 That's it! You now have access to Telegram's vast movie collection through your Movie Agent!**

For support or issues, check the logs in the console or create an issue in the repository.