import os
import pytest
from io import BytesIO
from app.utils.upload import allowed_file, get_safe_filename, save_uploaded_file
from werkzeug.datastructures import FileStorage

def test_allowed_file(app):
    """許可されたファイル拡張子のチェック関数をテスト"""
    with app.app_context():
        assert allowed_file('test.jpg') == True
        assert allowed_file('test.jpeg') == True
        assert allowed_file('test.png') == True
        assert allowed_file('test.gif') == True
        assert allowed_file('test.txt') == False
        assert allowed_file('test') == False
        assert allowed_file('') == False

def test_get_safe_filename():
    """安全なファイル名生成関数をテスト"""
    safe_name = get_safe_filename('test.jpg')
    # UUIDパターンのチェック（正確なUUID形式のチェックではなく、大まかなパターン確認）
    assert len(safe_name.split('.')[0]) == 32  # UUIDのhex表現は32文字
    assert safe_name.endswith('.jpg')
    
    # 拡張子なしの場合
    safe_name_no_ext = get_safe_filename('test')
    assert safe_name_no_ext.endswith('.')  # 拡張子なしの場合は末尾にピリオドがつく

def test_save_uploaded_file(app):
    """ファイル保存関数をテスト"""
    # テスト用のFileStorageオブジェクト作成
    test_data = b'test image data'
    test_file = FileStorage(
        stream=BytesIO(test_data),
        filename='test.jpg',
        content_type='image/jpeg',
    )
    
    with app.app_context():
        # ファイル保存
        relative_path = save_uploaded_file(test_file, app.config['UPLOAD_FOLDER'])
        assert relative_path is not None
        
        # 保存されたファイルパスの確認
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], relative_path)
        assert os.path.exists(full_path)
        
        # ファイル内容の確認
        with open(full_path, 'rb') as f:
            saved_data = f.read()
            assert saved_data == test_data
        
        # テスト後のクリーンアップ
        os.remove(full_path)

def test_save_uploaded_file_invalid(app):
    """無効なファイルの保存テスト"""
    # 無効な拡張子のファイル
    invalid_file = FileStorage(
        stream=BytesIO(b'test data'),
        filename='test.txt',
        content_type='text/plain',
    )
    
    with app.app_context():
        # 無効なファイルは保存されないはず
        result = save_uploaded_file(invalid_file)
        assert result is None
        
        # 空のファイル名
        empty_file = FileStorage(
            stream=BytesIO(b''),
            filename='',
            content_type='',
        )
        result = save_uploaded_file(empty_file)
        assert result is None

def test_upload_route(client):
    """アップロードルートのテスト"""
    # ログイン
    client.post('/auth/login', data={'password': 'test-password'})
    
    # アップロードフォームの表示
    response = client.get('/blog/')
    assert response.status_code == 200
    assert b'upload-form' in response.data
    
    # 画像のアップロード
    test_data = b'test image data'
    test_file = FileStorage(
        stream=BytesIO(test_data),
        filename='test.jpg',
        content_type='image/jpeg',
    )
    
    response = client.post(
        '/blog/upload',
        data={
            'images': test_file
        },
        content_type='multipart/form-data'
    )
    
    # リダイレクト（成功時は生成ページにリダイレクト）
    assert response.status_code == 302
    assert '/blog/generate' in response.location 