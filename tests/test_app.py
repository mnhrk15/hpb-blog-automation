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

def test_login_process(client):
    """ログインプロセスが機能するかテスト"""
    # 誤ったパスワードでログイン
    response = client.post('/auth/login', data={'password': 'wrong-password'})
    assert b'\xe3\x83\xad\xe3\x82\xb0\xe3\x82\xa4\xe3\x83\xb3' in response.data
    
    # 正しいパスワードでログイン
    response = client.post('/auth/login', data={'password': 'test-password'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'\xe3\x83\x96\xe3\x83\xad\xe3\x82\xb0' in response.data
    
    # ログアウト
    response = client.get('/auth/logout', follow_redirects=True)
    assert b'\xe3\x83\xad\xe3\x82\xb0\xe3\x82\xa4\xe3\x83\xb3' in response.data 