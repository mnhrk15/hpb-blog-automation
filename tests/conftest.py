import pytest
import os
from app import create_app
from config import Config

class TestConfig(Config):
    TESTING = True
    # テスト用DBやその他設定を追加する場合はここに記述
    APP_PASSWORD = 'test-password'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'test_uploads')

@pytest.fixture
def app():
    """テスト用のFlaskアプリケーションを作成"""
    app = create_app(TestConfig)
    
    # テスト用のクライアントコンテキスト
    with app.app_context():
        # テスト用のアップロードディレクトリがなければ作成
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        yield app
    
    # テスト後のクリーンアップ処理
    # 必要に応じてテスト用のファイルやディレクトリを削除

@pytest.fixture
def client(app):
    """テスト用のクライアント"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """テスト用のCLIランナー"""
    return app.test_cli_runner() 