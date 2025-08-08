#!/usr/bin/env python3
"""
Helper script to add movies to Telegram database
"""

from agents.telegram_agent import telegram_agent

def add_sample_movies():
    """Add sample movies for testing"""
    sample_movies = [
        {
            "title": "Avengers: Endgame",
            "message_id": 1001,
            "file_info": {
                "year": "2019",
                "quality": "1080p",
                "language": "English",
                "file_type": "video",
                "file_size": 3500000000  # 3.5GB
            }
        },
        {
            "title": "The Dark Knight",
            "message_id": 1002,
            "file_info": {
                "year": "2008",
                "quality": "720p",
                "language": "English",
                "file_type": "video",
                "file_size": 2100000000  # 2.1GB
            }
        },
        {
            "title": "Inception",
            "message_id": 1003,
            "file_info": {
                "year": "2010",
                "quality": "1080p",
                "language": "English",
                "file_type": "video",
                "file_size": 2800000000  # 2.8GB
            }
        },
        {
            "title": "Spider-Man: No Way Home",
            "message_id": 1004,
            "file_info": {
                "year": "2021",
                "quality": "1080p",
                "language": "English",
                "file_type": "video",
                "file_size": 3200000000  # 3.2GB
            }
        },
        {
            "title": "Top Gun: Maverick",
            "message_id": 1005,
            "file_info": {
                "year": "2022",
                "quality": "4K",
                "language": "English",
                "file_type": "video",
                "file_size": 4500000000  # 4.5GB
            }
        }
    ]
    
    print("📚 Adding sample movies to Telegram database...")
    
    for movie in sample_movies:
        success = telegram_agent.add_movie(
            movie["title"],
            movie["message_id"],
            movie["file_info"]
        )
        
        if success:
            print(f"✅ Added: {movie['title']} (Message ID: {movie['message_id']})")
        else:
            print(f"❌ Failed to add: {movie['title']}")

def add_custom_movie():
    """Add a custom movie interactively"""
    print("\n🎬 Add Custom Movie")
    print("=" * 30)
    
    title = input("Movie Title: ").strip()
    if not title:
        print("❌ Title is required")
        return
    
    try:
        message_id = int(input("Message ID in Telegram channel: ").strip())
    except ValueError:
        print("❌ Invalid message ID")
        return
    
    year = input("Year (optional): ").strip() or "Unknown"
    quality = input("Quality (e.g., 1080p, 720p, 4K): ").strip() or "Unknown"
    language = input("Language (optional): ").strip() or "English"
    
    file_info = {
        "year": year,
        "quality": quality,
        "language": language,
        "file_type": "video"
    }
    
    success = telegram_agent.add_movie(title, message_id, file_info)
    
    if success:
        print(f"✅ Added: {title} (Message ID: {message_id})")
    else:
        print(f"❌ Failed to add: {title}")

def list_movies():
    """List all movies in database"""
    try:
        cursor = telegram_agent.conn.cursor()
        cursor.execute('''
            SELECT title, year, quality, language, message_id, access_count 
            FROM telegram_movies 
            ORDER BY added_date DESC
        ''')
        
        movies = cursor.fetchall()
        
        if not movies:
            print("📭 No movies in database")
            return
        
        print(f"\n📚 Movies in Database ({len(movies)} total):")
        print("=" * 60)
        
        for movie in movies:
            title, year, quality, language, message_id, access_count = movie
            print(f"🎬 {title} ({year})")
            print(f"   Quality: {quality} | Language: {language}")
            print(f"   Message ID: {message_id} | Access Count: {access_count}")
            print()
            
    except Exception as e:
        print(f"❌ Error listing movies: {e}")

def test_search():
    """Test movie search functionality"""
    print("\n🔍 Test Movie Search")
    print("=" * 25)
    
    query = input("Enter movie title to search: ").strip()
    if not query:
        print("❌ Query is required")
        return
    
    movies = telegram_agent.search_movies(query)
    
    if movies:
        print(f"✅ Found {len(movies)} result(s):")
        for i, movie in enumerate(movies, 1):
            print(f"{i}. {movie['title']} ({movie['year']}) - {movie['quality']}")
            print(f"   Deep Link: {movie['detail_url']}")
    else:
        print("❌ No movies found")

def main():
    """Main menu"""
    while True:
        print("\n🤖 Telegram Movie Database Manager")
        print("=" * 40)
        print("1. Add sample movies (for testing)")
        print("2. Add custom movie")
        print("3. List all movies")
        print("4. Test search")
        print("5. Show statistics")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == "1":
            add_sample_movies()
        elif choice == "2":
            add_custom_movie()
        elif choice == "3":
            list_movies()
        elif choice == "4":
            test_search()
        elif choice == "5":
            stats = telegram_agent.get_stats()
            print(f"\n📊 Statistics:")
            print(f"Total Movies: {stats.get('total_movies', 0)}")
            print(f"Recent Searches (24h): {stats.get('recent_searches_24h', 0)}")
            print(f"Success Rate: {stats.get('success_rate', 0):.1f}%")
        elif choice == "6":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    print("🤖 Telegram Agent Status:")
    print(f"Enabled: {telegram_agent.enabled}")
    print(f"Bot Token: {'✅ Set' if telegram_agent.bot_token else '❌ Missing'}")
    print(f"Channel ID: {'✅ Set' if telegram_agent.channel_id else '❌ Missing'}")
    
    if not telegram_agent.enabled:
        print("❌ Telegram agent is disabled. Enable it in admin panel first.")
        exit(1)
    
    if not telegram_agent.bot_token or not telegram_agent.channel_id:
        print("❌ Bot token or channel ID missing. Configure in admin panel first.")
        exit(1)
    
    main()