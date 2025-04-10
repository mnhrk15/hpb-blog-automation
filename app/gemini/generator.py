from flask import current_app
from app.gemini.client import GeminiClient
from app.gemini.prompts import (
    BLOG_GENERATION_PROMPT,
    MULTI_IMAGE_BLOG_PROMPT,
    SIMPLE_BLOG_PROMPT
)

class BlogGenerator:
    """ブログ生成クラス"""
    
    def __init__(self):
        """初期化"""
        self.client = None
    
    def _get_client(self):
        """GeminiClientのインスタンスを取得"""
        if not self.client:
            self.client = GeminiClient()
        return self.client
    
    def generate_blog_from_images(self, image_paths):
        """
        画像からブログを生成
        
        Args:
            image_paths (list): 画像ファイルパスのリスト
            
        Returns:
            dict: タイトルと本文を含む辞書
        """
        if not image_paths:
            return {
                "title": "画像が提供されていません",
                "content": "ブログを生成するには、少なくとも1枚の画像が必要です。"
            }
        
        try:
            client = self._get_client()
            
            # 画像の枚数に応じてプロンプトを選択
            prompt = BLOG_GENERATION_PROMPT
            if len(image_paths) > 1:
                prompt = MULTI_IMAGE_BLOG_PROMPT
            
            # コンテンツ生成
            generated_text = client.generate_content_from_images(image_paths, prompt)
            
            # 生成に失敗した場合、簡易プロンプトで再試行
            if not generated_text:
                current_app.logger.warning("標準プロンプトでの生成に失敗しました。簡易プロンプトで再試行します。")
                generated_text = client.generate_content_from_images(image_paths, SIMPLE_BLOG_PROMPT)
            
            # タイトルと本文を抽出
            result = client.extract_title_and_content(generated_text)
            
            # 複数画像の場合、画像挿入位置の処理
            if len(image_paths) > 1:
                result["content"] = self._process_image_placeholders(result["content"], len(image_paths))
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"ブログ生成エラー: {str(e)}")
            return {
                "title": "エラーが発生しました",
                "content": "ブログ生成中にエラーが発生しました。もう一度お試しください。"
            }
    
    def _process_image_placeholders(self, content, image_count):
        """
        複数画像用の画像プレースホルダを処理
        
        Args:
            content (str): 生成された本文
            image_count (int): 画像の枚数
            
        Returns:
            str: 処理された本文
        """
        # 画像プレースホルダの存在確認
        placeholders_exist = any(f"[IMAGE_{i+1}]" in content for i in range(image_count))
        
        # プレースホルダが存在しない場合、適当な位置に追加
        if not placeholders_exist:
            # 本文を段落に分割
            paragraphs = content.split("\n\n")
            
            # 画像数に応じてプレースホルダを追加
            new_paragraphs = []
            image_index = 0
            
            # 最初のパラグラフは残す
            if paragraphs:
                new_paragraphs.append(paragraphs[0])
            
            # 残りのパラグラフの間に画像を配置
            for i, para in enumerate(paragraphs[1:], 1):
                # 一定間隔で画像を挿入
                if i % 2 == 0 and image_index < image_count:
                    new_paragraphs.append(f"[IMAGE_{image_index+1}]")
                    image_index += 1
                new_paragraphs.append(para)
            
            # 残りの画像があれば最後に追加
            while image_index < image_count:
                new_paragraphs.append(f"[IMAGE_{image_index+1}]")
                image_index += 1
            
            # 段落を結合
            content = "\n\n".join(new_paragraphs)
        
        return content 