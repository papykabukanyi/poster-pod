from app import app, init_app

# Initialize the application for production
init_app(app)

# This is the WSGI entry point that Gunicorn will use
if __name__ == "__main__":
    app.run()
