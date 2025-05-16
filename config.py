import os
from dotenv import load_dotenv

# .envファイルがあれば読み込む
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Flask設定
    SECRET_KEY = os.environ.get('APP_SECRET_KEY', 'your_secret_key')
    
    # アプリ認証設定
    APP_PASSWORD = os.environ.get('APP_PASSWORD') or 'default-password'
    
    # アップロード設定
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    SCREENSHOT_FOLDER = os.path.join(UPLOAD_FOLDER, 'screenshots')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Gemini API設定
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL_NAME = os.environ.get('GEMINI_MODEL_NAME', 'gemini-2.0-flash') # デフォルトモデル名
    
    # 開発・テスト設定
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true'

    # スクレイピング設定
    USER_AGENT = os.environ.get('USER_AGENT', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

    # Flask-Session 設定
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'flask_session')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # SESSION_FILE_THRESHOLD = 500 # セッションファイルが多くなった場合の閾値（オプション）

    # ログ設定
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE_PATH = os.environ.get('LOG_FILE_PATH', 'app.log') 