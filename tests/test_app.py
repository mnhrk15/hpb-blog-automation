import pytest
from flask import session, url_for
from app import create_app
from config import Config
import os
from unittest.mock import patch, MagicMock

class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test_secret_key'
    APP_PASSWORD = 'test_password'
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app():
    """アプリケーションのテスト用フィクスチャ"""
    app = create_app(TestConfig)
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    """アプリケーションのテストクライアント"""
    return app.test_client()

@pytest.fixture
def authenticated_client(client):
    """認証済みテストクライアント"""
    with client.session_transaction() as sess:
        sess['authenticated'] = True
    return client
    
def test_app_creation(app):
    """アプリケーションが正しく作成されるかテスト"""
    assert app is not None
    assert app.config['TESTING'] is True

def test_index_route(client):
    """インデックスルートが正しく動作するかテスト"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'HotPepper Beauty' in response.data

def test_auth_routes(client):
    """認証関連のルートが存在するかテスト"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'\xe3\x83\xad\xe3\x82\xb0\xe3\x82\xa4\xe3\x83\xb3' in response.data
    
def test_blog_routes_require_auth(client):
    """ブログ関連のルートが認証を要求するかテスト"""
    response = client.get('/blog/')
    assert response.status_code == 302  # リダイレクト
    assert '/auth/login' in response.location

def test_login_form(client):
    """ログインフォームが表示されるかテスト"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert 'パスワード' in response.data.decode('utf-8')

def test_login_success(client):
    """ログイン成功時のリダイレクトテスト"""
    response = client.post('/auth/login', data={'password': 'test_password'}, follow_redirects=True)
    assert response.status_code == 200

def test_login_failure(client):
    """ログイン失敗時のエラーメッセージテスト"""
    response = client.post('/auth/login', data={'password': 'wrong_password'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'パスワードが正しくありません' in response.data.decode('utf-8')

def test_logout(client):
    """ログアウト機能のテスト"""
    with client.session_transaction() as sess:
        sess['authenticated'] = True
    
    response = client.get('/auth/logout', follow_redirects=True)
    assert 'ログイン' in response.data.decode('utf-8')

def test_blog_index_clears_session(authenticated_client):
    """ブログインデックスページがセッションをクリアするかテスト"""
    with authenticated_client.session_transaction() as sess:
        sess['blog_uploaded_images'] = ['test.jpg']
        sess['blog_generated_content'] = {'title': 'Test', 'content': 'Test content'}
    
    response = authenticated_client.get('/blog/')
    assert response.status_code == 200
    
    with authenticated_client.session_transaction() as sess:
        assert 'blog_uploaded_images' not in sess
        assert 'blog_generated_content' not in sess

def test_blog_generate_without_images(authenticated_client):
    """画像がない状態でブログ生成ページにアクセスするとリダイレクトされるかテスト"""
    response = authenticated_client.get('/blog/generate')
    assert response.status_code == 302
    assert '/blog/' in response.location

@patch('app.scraper.stylist.StylistScraper.get_stylists')
@patch('app.scraper.coupon.CouponScraper.get_coupons')
def test_fetch_salon_info(mock_get_coupons, mock_get_stylists, authenticated_client):
    """サロン情報取得機能のテスト"""
    # モックの設定
    mock_stylists = [{'id': 'stf123', 'name': 'テストスタイリスト'}]
    mock_coupons = [{'name': 'テストクーポン'}]
    mock_get_stylists.return_value = mock_stylists
    mock_get_coupons.return_value = mock_coupons
    
    # リクエスト実行
    response = authenticated_client.post('/blog/fetch-salon-info', data={
        'salon_url': 'https://beauty.hotpepper.jp/slnH000123456/'
    }, follow_redirects=True)
    
    # 検証
    assert response.status_code == 200
    with authenticated_client.session_transaction() as sess:
        assert sess['salon_url'] == 'https://beauty.hotpepper.jp/slnH000123456/'
        assert sess['stylists'] == mock_stylists
        assert sess['coupons'] == mock_coupons
    
    # モックが正しく呼び出されたか確認
    mock_get_stylists.assert_called_once()
    mock_get_coupons.assert_called_once()

def test_fetch_salon_info_invalid_url(authenticated_client):
    """無効なサロンURLでの情報取得テスト"""
    response = authenticated_client.post('/blog/fetch-salon-info', data={
        'salon_url': 'https://example.com/'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert '有効なHotPepper Beauty URLを入力してください' in response.data.decode('utf-8')

def test_save_template(authenticated_client):
    """テンプレート保存機能のテスト"""
    template_content = "テスト署名\nお問い合わせ: 03-xxxx-xxxx"
    
    response = authenticated_client.post('/blog/save-template', data={
        'template': template_content
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with authenticated_client.session_transaction() as sess:
        assert sess['selected_template'] == template_content
    assert 'テンプレートを保存しました' in response.data.decode('utf-8')

def test_prepare_post_with_missing_content(authenticated_client):
    """ブログ内容がない状態で投稿準備をテスト"""
    response = authenticated_client.post('/blog/prepare-post', data={
        'title': 'テストタイトル',
        'content': 'テスト内容',
        'stylist_id': 'stf123',
        'coupons': ['テストクーポン'],
        'template': 'テスト署名'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert 'ブログ内容を生成してください' in response.data.decode('utf-8')

@patch('app.blog.routes.session')
def test_prepare_post_with_valid_data(mock_session, authenticated_client):
    """有効なデータでの投稿準備テスト"""
    # セッションのモック設定を修正
    mock_session.get = MagicMock(side_effect=lambda key, default=None: {
        'blog_generated_content': {'title': 'テストタイトル', 'content': 'テスト内容'},
        'blog_uploaded_images': ['test.jpg']
    }.get(key, default))
    
    # リクエスト実行
    response = authenticated_client.post('/blog/prepare-post', data={
        'title': 'テストタイトル',
        'content': 'テスト内容',
        'stylist_id': 'stf123',
        'coupons': ['テストクーポン'],
        'template': 'テスト署名'
    }, follow_redirects=True)
    
    # 検証
    assert response.status_code == 200
    assert '投稿準備が完了しました' in response.data.decode('utf-8')

def test_hair_info_without_data(authenticated_client):
    """ヘアスタイル情報がない状態でアクセスするテスト"""
    response = authenticated_client.get('/blog/hair-info', follow_redirects=True)
    
    assert response.status_code == 200
    assert 'ヘアスタイル情報がありません' in response.data.decode('utf-8')

@patch('app.blog.routes.session')
@patch('app.blog.routes.get_image_url')
def test_hair_info_with_data(mock_get_image_url, mock_session, authenticated_client):
    """ヘアスタイル情報がある状態でアクセスするテスト"""
    # 画像URL取得関数のモック
    mock_get_image_url.return_value = '/static/uploads/test.jpg'
    
    # セッションのモック
    mock_hair_info = {
        'hair_type': 'ボブ',
        'color': 'ブラウン',
        'features': ['ナチュラル', '前髪あり'],
        'face_shape': '丸顔',
        'season': '春'
    }
    mock_session.get = MagicMock(side_effect=lambda key, default=None: {
        'hair_style_info': mock_hair_info,
        'blog_uploaded_images': ['test.jpg']
    }.get(key, default))
    
    # リクエスト実行
    response = authenticated_client.get('/blog/hair-info')
    
    # 検証
    assert response.status_code == 200
    content = response.data.decode('utf-8')
    assert 'ボブ' in content
    assert 'ブラウン' in content 