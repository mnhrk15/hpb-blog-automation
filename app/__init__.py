from flask import Flask, redirect, url_for, send_from_directory, session
from config import Config
import os
import logging
from logging.handlers import RotatingFileHandler
from flask_session import Session # Flask-Session をインポート

def create_app(config_class=Config, **kwargs):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # ロガー設定
    log_level_str = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Flask のデフォルトロガーを設定
    if not app.logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        app.logger.addHandler(stream_handler)
    app.logger.setLevel(log_level)
    
    app.logger.info(f'Flask App Logger initialized with level: {log_level_str}')

    # Flask-Session の初期化
    Session(app)
    app.logger.debug("Flask-Session initialized.")
    
    # プロジェクトルートの取得
    project_root = os.path.abspath(os.path.join(app.root_path, os.pardir))

    # アップロードディレクトリの確認・作成 (正規化)
    upload_folder_name = app.config.get('UPLOAD_FOLDER', 'uploads')
    upload_folder_path = upload_folder_name 
    if not os.path.isabs(upload_folder_path):
        upload_folder_path = os.path.join(project_root, upload_folder_name)
    app.config['UPLOAD_FOLDER'] = os.path.normpath(upload_folder_path)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.logger.info(f"Upload folder is set to: {app.config['UPLOAD_FOLDER']}")
    
    # スクリーンショットディレクトリの確認・作成 (正規化)
    screenshot_folder_name = app.config.get('SCREENSHOT_FOLDER')
    if screenshot_folder_name:
        screenshot_folder_path = screenshot_folder_name
        if not os.path.isabs(screenshot_folder_path):
            screenshot_folder_path = os.path.join(project_root, screenshot_folder_name)
        # UPLOAD_FOLDER を基準にする場合は以下のようにするケースもあるが、今回はプロジェクトルート基準で統一
        # if not os.path.isabs(screenshot_folder_path):
        #     screenshot_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(screenshot_folder_name))
        app.config['SCREENSHOT_FOLDER'] = os.path.normpath(screenshot_folder_path)
        os.makedirs(app.config['SCREENSHOT_FOLDER'], exist_ok=True)
        app.logger.info(f"Screenshot folder is set to: {app.config['SCREENSHOT_FOLDER']}")
    else:
        app.logger.warning("SCREENSHOT_FOLDER is not configured.")

    # アップロードされた画像へのアクセスを提供するエンドポイント
    @app.route('/uploads/<path:filename>') # filename を <path:filename> に変更
    def uploaded_file(filename):
        # send_from_directory は絶対パスを期待することがある
        # UPLOAD_FOLDER が相対パスの場合、app.root_path からの相対と解釈される可能性があるため、
        # UPLOAD_FOLDER 設定時に絶対パスに変換しておくのが望ましい
        app.logger.debug(f"Attempting to serve file: {filename} from directory: {app.config['UPLOAD_FOLDER']}")
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # 後で追加するBlueprint登録
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.blog import bp as blog_bp
    app.register_blueprint(blog_bp)
    
    @app.route('/')
    def index():
        return redirect(url_for('blog.index'))
    
    return app 