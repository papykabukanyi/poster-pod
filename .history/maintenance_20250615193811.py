#!/usr/bin/env python
# maintenance.py - Command line utility to check and fix common issues

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_environment():
    """Set up the environment for the maintenance script"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logging.info("Environment loaded")
        return True
    except ImportError:
        logging.error("python-dotenv not installed. Install with: pip install python-dotenv")
        return False

def check_twitter():
    """Check Twitter connection and credentials"""
    try:
        from services.twitter_service import TwitterService
        
        twitter = TwitterService()
        if twitter.check_connection():
            logging.info("✅ Twitter connection successful")
            return True
        else:
            logging.error("❌ Twitter connection failed - check credentials")
            return False
    except Exception as e:
        logging.error(f"❌ Error checking Twitter: {e}")
        return False

def force_news_update():
    """Force a news update"""
    try:
        from services.news_service import NewsService
        
        logging.info("Forcing news update...")
        if NewsService.fetch_news(force_breaking=True):
            logging.info("✅ News update successful")
            
            # Check what was fetched
            news = NewsService.get_cached_news()
            if news and news.get('breaking'):
                logging.info(f"Breaking news: {news['breaking'].title}")
                logging.info(f"Total articles: {news.get('total', 0)}")
            else:
                logging.warning("⚠️ No breaking news found after update")
                
            return True
        else:
            logging.error("❌ News update failed")
            return False
    except Exception as e:
        logging.error(f"❌ Error updating news: {e}")
        return False

def force_tweet():
    """Force sending a tweet"""
    try:
        from services.twitter_service import TwitterService
        from services.news_service import NewsService
        
        # First check Twitter connection
        twitter = TwitterService()
        if not twitter.check_connection():
            logging.error("❌ Twitter connection failed - check credentials")
            return False
            
        # Then get news to tweet
        news = NewsService.get_cached_news()
        if not news or not news.get('breaking'):
            logging.warning("⚠️ No breaking news found, forcing news update")
            if not NewsService.fetch_news(force_breaking=True):
                logging.error("❌ Could not fetch news to tweet")
                return False
            news = NewsService.get_cached_news()
            
        if news and news.get('breaking'):
            article = news['breaking']
            logging.info(f"Attempting to tweet: {article.title}")
            
            # Try to post
            if twitter.post_article(article):
                logging.info("✅ Tweet sent successfully")
                return True
            else:
                logging.error("❌ Tweet failed")
                return False
        else:
            logging.error("❌ No article available to tweet")
            return False
    except Exception as e:
        logging.error(f"❌ Error sending tweet: {e}")
        return False

def check_scheduler():
    """Check if the scheduler is running"""
    try:
        from services.scheduler_service import SchedulerService
        
        scheduler = SchedulerService.get_instance()
        if scheduler.running and scheduler.thread and scheduler.thread.is_alive():
            logging.info("✅ Scheduler is running")
            
            # Check next update times
            now = datetime.utcnow()
            next_news = scheduler.next_news_update
            next_twitter = scheduler.next_twitter_update
            
            if next_news:
                time_to_news = (next_news - now).total_seconds() / 60
                logging.info(f"Next news update in {time_to_news:.1f} minutes")
            
            if next_twitter:
                time_to_twitter = (next_twitter - now).total_seconds() / 60
                logging.info(f"Next Twitter post in {time_to_twitter:.1f} minutes")
                
            return True
        else:
            logging.error("❌ Scheduler is not running")
            return False
    except Exception as e:
        logging.error(f"❌ Error checking scheduler: {e}")
        return False

def restart_scheduler():
    """Restart the scheduler"""
    try:
        from services.scheduler_service import SchedulerService
        
        scheduler = SchedulerService.get_instance()
        
        # Stop if running
        if scheduler.running:
            scheduler.stop()
            logging.info("Stopped existing scheduler")
            
        # Start new instance
        scheduler.start()
        logging.info("✅ Scheduler restarted")
        return True
    except Exception as e:
        logging.error(f"❌ Error restarting scheduler: {e}")
        return False

def check_database():
    """Check database connectivity and tables"""
    try:
        from models.base import engine, Base
        from sqlalchemy import inspect
        
        # Check connection
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        logging.info(f"Connected to database, found {len(table_names)} tables:")
        for table in table_names:
            logging.info(f"  - {table}")
            
        # Check specific tables
        expected_tables = ['news_articles', 'videos', 'activity_logs']
        missing = [t for t in expected_tables if t not in table_names]
        
        if missing:
            logging.error(f"❌ Missing tables: {', '.join(missing)}")
            return False
        else:
            logging.info("✅ All expected tables present")
            return True
    except Exception as e:
        logging.error(f"❌ Database error: {e}")
        return False

def run_all_checks():
    """Run all checks and report status"""
    results = {}
    
    logging.info("Running all system checks...")
    results['database'] = check_database()
    results['twitter'] = check_twitter()
    results['scheduler'] = check_scheduler()
    
    # Force a news update
    results['news_update'] = force_news_update()
    
    # Print summary
    logging.info("\n----- SYSTEM CHECK SUMMARY -----")
    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logging.info(f"{check}: {status}")
    
    # Return overall status
    return all(results.values())

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Poster Pod Maintenance Utility')
    parser.add_argument('--all', action='store_true', help='Run all checks')
    parser.add_argument('--twitter', action='store_true', help='Check Twitter connection')
    parser.add_argument('--news', action='store_true', help='Force news update')
    parser.add_argument('--tweet', action='store_true', help='Force sending a tweet')
    parser.add_argument('--scheduler', action='store_true', help='Check scheduler')
    parser.add_argument('--restart-scheduler', action='store_true', help='Restart scheduler')
    parser.add_argument('--database', action='store_true', help='Check database')
    
    args = parser.parse_args()
    
    if not setup_environment():
        sys.exit(1)
        
    # If no args specified, show help
    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)
        
    # Run requested checks
    if args.all:
        success = run_all_checks()
        sys.exit(0 if success else 1)
        
    if args.twitter:
        check_twitter()
        
    if args.news:
        force_news_update()
        
    if args.tweet:
        force_tweet()
        
    if args.scheduler:
        check_scheduler()
        
    if args.restart_scheduler:
        restart_scheduler()
        
    if args.database:
        check_database()

if __name__ == '__main__':
    main()
