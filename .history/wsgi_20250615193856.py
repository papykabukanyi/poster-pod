from app import app, init_app
import logging

# Set up logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Force initialization of all services
try:
    logging.info("Initializing application in production mode...")
    
    # Initialize app with database
    init_app(app)
    
    # Import and initialize news service
    from services.news_service import NewsService
    NewsService.fetch_news(force_breaking=True)
    logging.info("News service initialized and fetched initial news")
    
    # Import and initialize scheduler
    from services.scheduler_service import SchedulerService
    scheduler = SchedulerService.get_instance()
    scheduler.start()
    logging.info("Scheduler service started successfully")
    
    # Test Twitter connection
    from services.twitter_service import TwitterService
    twitter = TwitterService()
    if twitter.check_connection():
        logging.info("Twitter connection successful")
    else:
        logging.warning("Twitter connection failed - check credentials")
    
    logging.info("Application initialization complete")
except Exception as e:
    logging.error(f"Error initializing application: {e}")
    # Continue anyway to let the app handle initialization on first request
    
# This is the WSGI entry point that Gunicorn will use
if __name__ == "__main__":
    app.run()
