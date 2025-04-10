import os
import base64
from PIL import Image
from io import BytesIO
from flask import current_app, url_for

def encode_image(image_path):
    """
    画像ファイルをbase64エンコードする
    
    Args:
        image_path (str): 画像ファイルのパス
        
    Returns:
        str: base64エンコードされた画像データ
    """
    if not os.path.exists(image_path):
        return None
    
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_image_url(filename):
    """
    画像ファイル名からURLを生成する
    
    Args:
        filename (str): 画像ファイル名
        
    Returns:
        str: 画像の公開URL
    """
    # filenameが絶対パスの場合はファイル名だけを抽出
    filename = os.path.basename(filename)
    return url_for('uploaded_file', filename=filename)

def get_image_mime_type(image_path):
    """
    画像ファイルのMIMEタイプを取得する
    
    Args:
        image_path (str): 画像ファイルのパス
        
    Returns:
        str: 画像のMIMEタイプ
    """
    if not os.path.exists(image_path):
        return None
    
    # 拡張子からMIMEタイプを判定（簡易的な方法）
    ext = os.path.splitext(image_path)[1].lower()
    if ext == '.jpg' or ext == '.jpeg':
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    elif ext == '.gif':
        return 'image/gif'
    else:
        # 拡張子から判断できない場合はPillowを使用
        try:
            with Image.open(image_path) as img:
                if img.format == 'JPEG':
                    return 'image/jpeg'
                elif img.format == 'PNG':
                    return 'image/png'
                elif img.format == 'GIF':
                    return 'image/gif'
                else:
                    return 'application/octet-stream'
        except:
            return 'application/octet-stream'

def get_full_image_path(relative_path):
    """
    相対パスから画像の絶対パスを取得する
    
    Args:
        relative_path (str): アップロードディレクトリからの相対パス
        
    Returns:
        str: 画像ファイルの絶対パス
    """
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # 相対パスが直接ファイル名の場合
    if os.path.sep not in relative_path:
        return os.path.join(upload_folder, relative_path)
        
    # 相対パスが既にアップロードディレクトリからの相対パスの場合
    return os.path.join(upload_folder, relative_path)

def resize_image_if_needed(image_path, max_size=5*1024*1024):
    """
    画像ファイルが指定サイズを超える場合にリサイズする
    Gemini APIには画像サイズの制限があるため
    
    Args:
        image_path (str): 画像ファイルのパス
        max_size (int): 最大ファイルサイズ（バイト）
        
    Returns:
        bool: リサイズした場合はTrue、しなかった場合はFalse
    """
    if not os.path.exists(image_path):
        return False
        
    file_size = os.path.getsize(image_path)
    if file_size <= max_size:
        return False  # リサイズ不要
        
    try:
        # 画像を開いてリサイズ
        with Image.open(image_path) as img:
            # 現在のサイズを取得
            width, height = img.size
            
            # 新しいサイズを計算（単純に縮小）
            scale = (max_size / file_size) ** 0.5  # 面積の縮小率から辺の縮小率を計算
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # リサイズして保存
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            resized_img.save(image_path, quality=85, optimize=True)
            
            return True
    except Exception as e:
        print(f"画像リサイズエラー: {e}")
        return False 