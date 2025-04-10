from flask import Flask
from config import Config
import os

def create_app(config_class=Config, **kwargs):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # アップロードディレクトリの確認
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 後で追加するBlueprint登録
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.blog import bp as blog_bp
    app.register_blueprint(blog_bp)
    
    @app.route('/')
    def index():
        return 'HotPepper Beauty ブログ自動生成・投稿アプリ'
    
    return app 