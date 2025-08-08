# 🤖 Telegram Movie Bot Setup Guide

## 📋 Overview

The Telegram agent allows users to get movie files instantly forwarded from your private Telegram channel. Here's how it works:

1. **You store movie files** in a private Telegram channel
2. **Bot maps movie titles** to message IDs in the database
3. **Users search for movies** via bot or web interface
4. **Bot forwards files** directly to users

## 🚀 Complete Setup Process

### Step 1: Create Telegram Bot

1. **Message @BotFather** on Telegram
2. **Create new bot**: `/newbot`
3. **Choose bot name**: `Movies Agent Bot`
4. **Choose username**: `MoviesAgent123bot` (must end with 'bot')
5. **Save the bot token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Create Private Channel

1. **Create new channel** in Telegram
2. **Make it private** (important!)
3. **Add your bot** as administrator
4. **Give bot permissions**:
   - ✅ Post messages
   - ✅ Edit messages
   - ✅ Delete messages
   - ✅ Pin messages

### Step 3: Get Channel ID

1. **Forward any message** from your channel to @userinfobot
2. **Copy the channel ID** (looks like: `-1001234567890`)
3. **Or use this method**:
   - Add @RawDataBot to your channel
   - Send any message
   - Bot will show channel ID in `"chat":{"id":-1001234567890}`

### Step 4: Configure in Admin Panel

1. **Start your application**: `python web_interface.py`
2. **Open admin panel**: `http://localhost:5000/admin`
3. **Scroll to Telegram Agent section**
4. **Fill in configuration**:
   - Bot Token: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
   - Channel ID: `-1001234567890`
   - Bot Username: `MoviesAgent123bot`
   - Enable Telegram Agent: ✅
5. **Test connection** - Should show bot info and channel access
6. **Save configuration**

### Step 5: Add Movies to Database

**Option A: Add Sample Movies (for testing)**
```bash
python add_telegram_movies.py
# Choose option 1 to add sample movies
```

**Option B: Add Real Movies**
1. **Upload movie files** to your private channel
2. **Note the message ID** of each movie (right-click → Copy Message Link)
3. **Add to database**:
   ```bash
   python add_telegram_movies.py
   # Choose option 2 to add custom movies
   ```

**Option C: Use Admin API**
```bash
curl -X POST http://localhost:5000/admin/api/telegram/add-movie \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Avengers Endgame",
    "message_id": 123,
    "file_info": {
      "year": "2019",
      "quality": "1080p",
      "language": "English"
    }
  }'
```

### Step 6: Test the System

1. **Check database**: `python add_telegram_movies.py` → option 3
2. **Test search**: `python add_telegram_movies.py` → option 4
3. **Test via web**: `http://localhost:5000/telegram`
4. **Test via bot**: Message your bot directly

## 🔧 How to Get Message IDs

### Method 1: From Message Link
1. **Right-click on message** in your channel
2. **Copy Message Link**
3. **Extract ID from URL**: `https://t.me/c/1234567890/123` → Message ID is `123`

### Method 2: Using Bot
1. **Forward message** from channel to @userinfobot
2. **Look for** `"message_id": 123`

### Method 3: Using Raw Data Bot
1. **Add @RawDataBot** to your channel
2. **Forward any message** to the bot
3. **Check response** for message ID

## 📱 Usage Examples

### Deep Links
Users can access movies directly via links:
- `https://t.me/MoviesAgent123bot?start=Avengers_Endgame`
- `https://t.me/MoviesAgent123bot?start=The_Dark_Knight`

### Bot Commands
Users can message your bot:
- `/start` - Welcome message
- `Avengers Endgame` - Search for movie
- `latest movies` - Search for recent releases

### Web Interface
- `http://localhost:5000/telegram` - Generate deep links
- Search and forward movies directly

## 🛠️ Troubleshooting

### Bot Not Working
1. **Check bot token** - Verify it's correct
2. **Check permissions** - Bot must be admin in channel
3. **Test connection** - Use admin panel test button

### Movies Not Found
1. **Check database** - Run `python add_telegram_movies.py` → option 3
2. **Add movies** - Use the helper script
3. **Check message IDs** - Verify they're correct

### Forwarding Fails
1. **Check channel access** - Bot must have admin rights
2. **Check message exists** - Verify message ID is valid
3. **Check user permissions** - User must have started bot

### Database Issues
1. **Check file permissions** - `data/telegram_movies.db` must be writable
2. **Recreate database** - Delete file and restart application
3. **Check disk space** - Ensure enough space available

## 📊 Monitoring

### Admin Panel Statistics
- Total movies in database
- Recent searches (24 hours)
- Success rate percentage
- Popular movies list

### Database Queries
```python
from agents.telegram_agent import telegram_agent

# Get statistics
stats = telegram_agent.get_stats()
print(f"Total movies: {stats['total_movies']}")

# Search movies
movies = telegram_agent.search_movies("Avengers")
print(f"Found {len(movies)} movies")

# Test connection
result = telegram_agent.test_connection()
print(f"Connection: {result['success']}")
```

## 🔐 Security Notes

1. **Keep bot token secret** - Never share publicly
2. **Use private channel** - Don't make it public
3. **Limit bot permissions** - Only give necessary rights
4. **Monitor usage** - Check logs regularly
5. **Backup database** - Save `data/telegram_movies.db`

## 🎯 Best Practices

1. **Organize channel** - Use clear naming for movies
2. **Regular backups** - Save database and config
3. **Monitor performance** - Check success rates
4. **Update mappings** - Keep database current
5. **Test regularly** - Verify bot functionality

## 📞 Support

If you encounter issues:
1. **Check logs** - Look for error messages
2. **Test components** - Use helper scripts
3. **Verify configuration** - Double-check all settings
4. **Check Telegram limits** - API rate limits may apply

---

**Happy movie sharing! 🎬✨**