import os
import google.generativeai as genai
from flask import current_app
from app.utils.image import encode_image, get_image_mime_type, get_full_image_path, resize_image_if_needed

class GeminiClient:
    """Gemini APIクライアントクラス"""
    
    def __init__(self, api_key=None, model_name=None):
        """
        初期化
        
        Args:
            api_key (str, optional): Gemini API Key。指定されない場合は設定から取得。
            model_name (str, optional): 使用するGeminiモデル名。指定されない場合は設定から取得。
        """
        self.api_key = api_key or current_app.config.get('GEMINI_API_KEY')
        self.model_name = model_name or current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')
        
        if not self.api_key:
            raise ValueError("Gemini API Keyが設定されていません")
        
        # APIクライアントの初期化
        genai.configure(api_key=self.api_key)
        
        # モデルの取得
        self.model = genai.GenerativeModel(self.model_name)
    
    def generate_content_from_images(self, image_paths, prompt):
        """
        画像を解析してコンテンツを生成
        
        Args:
            image_paths (list): 画像ファイルパスのリスト（相対パス）
            prompt (str): 生成プロンプト
            
        Returns:
            str: 生成されたテキスト
        """
        try:
            # 画像パスを絶対パスに変換
            full_paths = [get_full_image_path(path) for path in image_paths]
            
            # 大きすぎる画像をリサイズ
            for path in full_paths:
                resize_image_if_needed(path)
            
            # 画像データとMIMEタイプのリストを作成
            image_parts = []
            for path in full_paths:
                encoded_image = encode_image(path)
                mime_type = get_image_mime_type(path)
                
                if encoded_image and mime_type:
                    image_parts.append({
                        "mime_type": mime_type,
                        "data": encoded_image
                    })
            
            # プロンプトとイメージパーツの準備
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # コンテンツ生成リクエスト
            response = self.model.generate_content(
                [prompt] + [{"inline_data": part} for part in image_parts],
                generation_config=generation_config
            )
            
            return response.text
        
        except Exception as e:
            current_app.logger.error(f"Gemini API エラー: {str(e)}")
            return None
    
    def extract_title_and_content(self, generated_text):
        """
        生成されたテキストからタイトルと本文を抽出
        
        Args:
            generated_text (str): 生成されたテキスト
            
        Returns:
            dict: タイトルと本文を含む辞書
        """
        if not generated_text:
            return {
                "title": "生成に失敗しました",
                "content": "コンテンツを生成できませんでした。もう一度お試しください。"
            }
        
        try:
            # タイトルと本文の抽出
            title = ""
            content = ""
            
            # タイトルの抽出（【タイトル】の後の行を取得）
            title_index = generated_text.find("【タイトル】")
            if title_index >= 0:
                title_start = generated_text.find("\n", title_index) + 1
                title_end = generated_text.find("\n\n", title_start)
                if title_end >= 0:
                    title = generated_text[title_start:title_end].strip()
                else:
                    # 次のセクションが見つからない場合は残りすべてを取得
                    title = generated_text[title_start:].strip()
            
            # 本文の抽出（【本文】の後の行を取得）
            content_index = generated_text.find("【本文】")
            if content_index >= 0:
                content_start = generated_text.find("\n", content_index) + 1
                content = generated_text[content_start:].strip()
            
            # タイトルと本文が見つからない場合はテキスト全体を本文とする
            if not title and not content:
                title = "自動生成タイトル"
                content = generated_text.strip()
            elif not title:
                title = "自動生成タイトル"
            elif not content:
                content = "本文が生成されませんでした。"
            
            return {
                "title": title,
                "content": content
            }
            
        except Exception as e:
            current_app.logger.error(f"テキスト抽出エラー: {str(e)}")
            return {
                "title": "テキスト抽出エラー",
                "content": generated_text or "コンテンツを抽出できませんでした。"
            } 