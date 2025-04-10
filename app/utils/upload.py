import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    """
    アップロードされたファイルが許可された拡張子を持つかチェックする
    
    Args:
        filename (str): チェックするファイル名
        
    Returns:
        bool: 許可された拡張子ならTrue、そうでなければFalse
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def get_safe_filename(filename):
    """
    安全なファイル名を生成する
    
    Args:
        filename (str): 元のファイル名
        
    Returns:
        str: UUIDとオリジナルのファイル拡張子を組み合わせた安全なファイル名
    """
    # オリジナルの拡張子を取得
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    else:
        ext = ''
    
    # ランダムなUUIDを生成して拡張子と組み合わせる
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    return safe_name

def save_uploaded_file(file, destination=None):
    """
    アップロードされたファイルを保存する
    
    Args:
        file: FileStorage オブジェクト
        destination: 保存先ディレクトリのパス（Noneの場合はデフォルトのアップロードフォルダを使用）
        
    Returns:
        str: 保存されたファイルのパス（相対パス）
        または None（ファイルが無効な場合）
    """
    if file is None or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    if destination is None:
        destination = current_app.config['UPLOAD_FOLDER']
    
    # ディレクトリが存在しない場合は作成
    os.makedirs(destination, exist_ok=True)
    
    # 安全なファイル名を生成
    filename = get_safe_filename(file.filename)
    filepath = os.path.join(destination, filename)
    
    # ファイルを保存
    file.save(filepath)
    
    # アップロードディレクトリからの相対パスを返す
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if filepath.startswith(upload_folder):
        return filepath[len(upload_folder):].lstrip(os.path.sep)
    else:
        return filename 