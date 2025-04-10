import os
from dotenv import load_dotenv

# .envファイルがあれば読み込む
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Flask設定
    SECRET_KEY = os.environ.get('APP_SECRET_KEY') or 'dev-secret-key'
    
    # アプリ認証設定
    APP_PASSWORD = os.environ.get('APP_PASSWORD') or 'default-password'
    
    # アップロード設定
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Gemini API設定
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = 'gemini-2.0-flash'
    
    # 開発・テスト設定
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true' 