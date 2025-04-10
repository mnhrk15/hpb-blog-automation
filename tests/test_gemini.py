import os
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image
from flask import current_app

from app import create_app
from app.gemini.client import GeminiClient
from app.gemini.generator import BlogGenerator
from app.gemini.extractor import HairStyleExtractor
from app.utils.image import encode_image, get_image_mime_type, resize_image_if_needed
from config import Config

# テスト用の設定クラス
class TestConfig(Config):
    TESTING = True
    GEMINI_API_KEY = 'test_api_key'
    GEMINI_MODEL_NAME = 'test_model'

# 画像ファイルを作成するヘルパー関数
def create_test_image(path, size=(100, 100), color=(255, 0, 0)):
    """テスト用の画像ファイルを作成"""
    img = Image.new('RGB', size, color=color)
    img.save(path)
    return path

# Geminiクライアントのモックレスポンス
MOCK_BLOG_RESPONSE = """
【タイトル】
テスト用ブログタイトル

【本文】
これはテスト用のブログ本文です。
画像の説明が入ります。

[IMAGE_1]

さらに詳細な説明が続きます。
"""

MOCK_HAIR_INFO_RESPONSE = """
ヘアスタイル: ミディアムレイヤー
髪色: アッシュブラウン
特徴: 柔らかい質感, 前髪あり, ナチュラル
顔型: 丸顔, 面長
季節: 春, 夏
"""

@pytest.fixture
def app():
    """テスト用のFlaskアプリケーションインスタンスを作成"""
    app = create_app(TestConfig)
    
    # アプリケーションコンテキストをプッシュ
    with app.app_context():
        yield app

@pytest.fixture
def test_image(tmp_path):
    """テスト用の画像ファイルを作成して返す"""
    image_path = os.path.join(tmp_path, "test_image.jpg")
    return create_test_image(image_path)

@pytest.fixture
def mock_gemini_response():
    """Gemini APIのレスポンスをモック"""
    mock_response = MagicMock()
    mock_response.text = MOCK_BLOG_RESPONSE
    return mock_response

class TestGeminiClient:
    @patch('app.gemini.client.genai.GenerativeModel')
    def test_generate_content_from_images(self, mock_model, test_image, mock_gemini_response, app):
        # モックの設定
        mock_instance = mock_model.return_value
        mock_instance.generate_content.return_value = mock_gemini_response
        
        # テスト対象の初期化
        client = GeminiClient(api_key="test_key", model_name="test_model")
        
        # テスト実行
        with patch('app.gemini.client.current_app'):
            result = client.generate_content_from_images([test_image], "テスト用プロンプト")
        
        # 検証
        assert result == MOCK_BLOG_RESPONSE
        mock_instance.generate_content.assert_called_once()
    
    def test_extract_title_and_content(self, mock_gemini_response):
        client = GeminiClient(api_key="test_key", model_name="test_model")
        result = client.extract_title_and_content(MOCK_BLOG_RESPONSE)
        
        assert result["title"] == "テスト用ブログタイトル"
        assert "これはテスト用のブログ本文です。" in result["content"]

class TestBlogGenerator:
    @patch('app.gemini.generator.GeminiClient')
    def test_generate_blog_from_images(self, mock_client, test_image, app):
        # モックの設定
        mock_instance = mock_client.return_value
        mock_instance.generate_content_from_images.return_value = MOCK_BLOG_RESPONSE
        mock_instance.extract_title_and_content.return_value = {
            "title": "テスト用ブログタイトル",
            "content": "これはテスト用のブログ本文です。\n画像の説明が入ります。\n\n[IMAGE_1]\n\nさらに詳細な説明が続きます。"
        }
        
        # テスト対象の初期化
        generator = BlogGenerator()
        generator.client = mock_instance
        
        # テスト実行
        result = generator.generate_blog_from_images([test_image])
        
        # 検証
        assert result["title"] == "テスト用ブログタイトル"
        assert "[IMAGE_1]" in result["content"]
        mock_instance.generate_content_from_images.assert_called_once()

class TestHairStyleExtractor:
    @patch('app.gemini.extractor.GeminiClient')
    def test_extract_hair_info(self, mock_client, test_image, app):
        # モックの設定
        mock_instance = mock_client.return_value
        mock_instance.generate_content_from_images.return_value = MOCK_HAIR_INFO_RESPONSE
        
        # テスト対象の初期化
        extractor = HairStyleExtractor()
        extractor.client = mock_instance
        
        # クライアントのgenerate_content_from_imagesメソッドをパッチする
        # テスト実行
        with patch('app.gemini.extractor.current_app'):
            try:
                result = extractor.extract_hair_info(test_image)
                
                # 検証（抽出した結果をパースできるか）
                assert "髪色" in result
                assert "アッシュブラウン" in result["髪色"]
                assert "ヘアスタイル" in result
                assert "ミディアムレイヤー" in result["ヘアスタイル"]
            except Exception as e:
                # KeyErrorが発生した場合は、実際の結果を表示して失敗
                print(f"エラー: {str(e)}")
                print(f"実際の結果: {result}")
                raise

class TestImageUtils:
    def test_encode_image(self, test_image):
        # 画像エンコードテスト
        encoded = encode_image(test_image)
        assert isinstance(encoded, str)
        assert len(encoded) > 0
    
    def test_get_image_mime_type(self, test_image):
        # MIMEタイプ取得テスト
        mime_type = get_image_mime_type(test_image)
        assert mime_type == "image/jpeg"
    
    def test_resize_image_if_needed(self, test_image):
        # 画像リサイズテスト（サイズが小さいのでリサイズはされない）
        resized = resize_image_if_needed(test_image)
        assert not resized  # リサイズ不要の場合はFalseが返る 