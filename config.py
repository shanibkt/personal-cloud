import os
from dotenv import load_dotenv

# Load environment variables
from dotenv import load_dotenv

class Config:
    basedir = os.path.abspath(os.path.dirname(__file__))
    env_path = os.path.join(basedir, '.env')
    DOTENV_LOADED = load_dotenv(env_path)
    DOTENV_EXISTS = os.path.exists(env_path)
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    # If DATABASE_URL is set (like on Render), use it. Otherwise use SQLite.
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or f'sqlite:///{os.path.join(basedir, "instance", "file_storage.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Credentials
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH')
    PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
    SESSION_STRING = os.environ.get('TELEGRAM_SESSION_STRING')
    SESSION_NAME = 'cloud_backup_v4'
    
    # Upload/Download Config
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')

    # PythonAnywhere Proxy Settings
    IS_PYTHONANYWHERE = os.path.exists('/var/www') and ('pythonanywhere' in os.getcwd().lower() or 'Shanib' in os.getcwd())
    PROXY_HOST = 'proxy.server'
    PROXY_PORT = 3128
