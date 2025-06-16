from app import app, init_app
import logging

# Set up logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Initialize the application for production
try:
    logging.info("Initializing application in production mode...")
    init_app(app)
    logging.info("Application initialization complete")
except Exception as e:
    logging.error(f"Error initializing application: {e}")
    # Continue anyway to let the app handle database initialization on first request

# This is the WSGI entry point that Gunicorn will use
if __name__ == "__main__":
    app.run()
