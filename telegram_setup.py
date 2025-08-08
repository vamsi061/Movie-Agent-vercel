#!/usr/bin/env python3
"""
Telegram Bot Setup Script
Helps configure and test the Telegram movie bot
"""

import os
import json
import requests
from telegram_backend import telegram_bot

def setup_webhook(webhook_url: str = None):
    """Setup webhook for Telegram bot"""
    if not telegram_bot.bot_token:
        print("❌ Bot token not found. Please set TELEGRAM_BOT_TOKEN environment variable.")
        return False
    
    try:
        if webhook_url:
            # Set webhook
            url = f"{telegram_bot.base_url}/setWebhook"
            data = {"url": webhook_url}
            response = requests.post(url, json=data)
            result = response.json()
            
            if result.get('ok'):
                print(f"✅ Webhook set successfully: {webhook_url}")
                return True
            else:
                print(f"❌ Failed to set webhook: {result.get('description')}")
                return False
        else:
            # Remove webhook (for development)
            url = f"{telegram_bot.base_url}/deleteWebhook"
            response = requests.post(url)
            result = response.json()
            
            if result.get('ok'):
                print("✅ Webhook removed (polling mode enabled)")
                return True
            else:
                print(f"❌ Failed to remove webhook: {result.get('description')}")
                return False
                
    except Exception as e:
        print(f"❌ Error setting up webhook: {e}")
        return False

def get_bot_info():
    """Get bot information"""
    if not telegram_bot.bot_token:
        print("❌ Bot token not found.")
        return None
    
    try:
        url = f"{telegram_bot.base_url}/getMe"
        response = requests.get(url)
        result = response.json()
        
        if result.get('ok'):
            bot_info = result.get('result')
            print("🤖 Bot Information:")
            print(f"   Name: {bot_info.get('first_name')}")
            print(f"   Username: @{bot_info.get('username')}")
            print(f"   ID: {bot_info.get('id')}")
            print(f"   Can Join Groups: {bot_info.get('can_join_groups')}")
            print(f"   Can Read All Group Messages: {bot_info.get('can_read_all_group_messages')}")
            return bot_info
        else:
            print(f"❌ Failed to get bot info: {result.get('description')}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
        return None

def test_channel_access():
    """Test if bot has access to the channel"""
    if not telegram_bot.channel_id:
        print("❌ Channel ID not found. Please set TELEGRAM_CHANNEL_ID environment variable.")
        return False
    
    try:
        url = f"{telegram_bot.base_url}/getChat"
        data = {"chat_id": telegram_bot.channel_id}
        response = requests.post(url, json=data)
        result = response.json()
        
        if result.get('ok'):
            chat_info = result.get('result')
            print("📺 Channel Information:")
            print(f"   Title: {chat_info.get('title')}")
            print(f"   Type: {chat_info.get('type')}")
            print(f"   ID: {chat_info.get('id')}")
            
            # Test if bot is admin
            url = f"{telegram_bot.base_url}/getChatMember"
            data = {
                "chat_id": telegram_bot.channel_id,
                "user_id": telegram_bot.bot_token.split(':')[0]  # Bot ID from token
            }
            response = requests.post(url, json=data)
            member_result = response.json()
            
            if member_result.get('ok'):
                member_info = member_result.get('result')
                status = member_info.get('status')
                print(f"   Bot Status: {status}")
                
                if status == 'administrator':
                    print("✅ Bot has admin access to channel")
                    return True
                else:
                    print("⚠️ Bot is not an admin in the channel")
                    return False
            else:
                print(f"❌ Failed to check bot status: {member_result.get('description')}")
                return False
                
        else:
            print(f"❌ Failed to access channel: {result.get('description')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing channel access: {e}")
        return False

def add_sample_movies():
    """Add sample movies to database for testing"""
    sample_movies = [
        {
            "title": "Avengers: Endgame",
            "message_id": 1001,
            "file_info": {
                "year": "2019",
                "quality": "1080p",
                "language": "English"
            }
        },
        {
            "title": "The Dark Knight",
            "message_id": 1002,
            "file_info": {
                "year": "2008",
                "quality": "720p",
                "language": "English"
            }
        },
        {
            "title": "Inception",
            "message_id": 1003,
            "file_info": {
                "year": "2010",
                "quality": "1080p",
                "language": "English"
            }
        }
    ]
    
    print("📚 Adding sample movies to database...")
    
    for movie in sample_movies:
        success = telegram_bot.add_movie_to_database(
            movie["title"],
            movie["message_id"],
            movie["file_info"]
        )
        
        if success:
            print(f"✅ Added: {movie['title']}")
        else:
            print(f"❌ Failed to add: {movie['title']}")

def test_search():
    """Test movie search functionality"""
    print("\n🔍 Testing movie search...")
    
    test_queries = ["Avengers", "Dark Knight", "Inception", "Nonexistent Movie"]
    
    for query in test_queries:
        print(f"\nSearching for: '{query}'")
        movies = telegram_bot.search_movie_in_database(query)
        
        if movies:
            print(f"✅ Found {len(movies)} result(s):")
            for movie in movies[:3]:  # Show first 3 results
                print(f"   - {movie['title']} ({movie['year']}) - {movie['quality']}")
        else:
            print("❌ No results found")

def main():
    """Main setup function"""
    print("🚀 Telegram Movie Bot Setup")
    print("=" * 40)
    
    # Check environment variables
    print("\n1. Checking Environment Variables...")
    
    if telegram_bot.bot_token:
        print("✅ TELEGRAM_BOT_TOKEN is set")
    else:
        print("❌ TELEGRAM_BOT_TOKEN is missing")
        print("   Get your bot token from @BotFather on Telegram")
        return
    
    if telegram_bot.channel_id:
        print("✅ TELEGRAM_CHANNEL_ID is set")
    else:
        print("❌ TELEGRAM_CHANNEL_ID is missing")
        print("   Set your private channel ID (e.g., -1001234567890)")
        return
    
    # Get bot info
    print("\n2. Getting Bot Information...")
    bot_info = get_bot_info()
    
    if not bot_info:
        return
    
    # Test channel access
    print("\n3. Testing Channel Access...")
    channel_access = test_channel_access()
    
    if not channel_access:
        print("\n⚠️ Setup Instructions:")
        print("1. Add your bot to the private channel")
        print("2. Make the bot an administrator")
        print("3. Give the bot permissions to post, edit, and delete messages")
        return
    
    # Initialize database and add sample data
    print("\n4. Setting up Database...")
    add_sample_movies()
    
    # Test search functionality
    print("\n5. Testing Search Functionality...")
    test_search()
    
    # Setup webhook (optional)
    print("\n6. Webhook Setup...")
    webhook_url = os.getenv('TELEGRAM_WEBHOOK_URL')
    
    if webhook_url:
        print(f"Setting up webhook: {webhook_url}")
        setup_webhook(webhook_url)
    else:
        print("No webhook URL provided. Using polling mode for development.")
        setup_webhook()  # Remove webhook
    
    # Show bot statistics
    print("\n7. Bot Statistics...")
    stats = telegram_bot.get_movie_stats()
    print(f"   Total Movies: {stats.get('total_movies', 0)}")
    print(f"   Recent Searches: {stats.get('recent_searches_24h', 0)}")
    
    print("\n✅ Setup Complete!")
    print("\nNext Steps:")
    print("1. Start your Flask application")
    print("2. Test the bot by messaging @MoviesAgent123bot")
    print("3. Try deep links: https://t.me/MoviesAgent123bot?start=Avengers")
    print("4. Access the web interface at /telegram")

if __name__ == "__main__":
    main()