import re
import json
import logging
from flask import current_app
from app.gemini.client import GeminiClient
from app.gemini.prompts import (
    BLOG_GENERATION_PROMPT,
    MULTI_IMAGE_BLOG_PROMPT,
    SIMPLE_BLOG_PROMPT,
    STRUCTURED_BLOG_PROMPT
)

logger = logging.getLogger(__name__)

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
    
    def generate_structured_blog_from_images(self, image_paths, hair_info=None):
        """
        画像から構造化されたブログ（JSON形式）を生成
        
        Args:
            image_paths (list): 画像ファイルパスのリスト
            hair_info (dict, optional): ヘアスタイル情報
            
        Returns:
            dict: 構造化されたブログデータ（title, sectionsを含む）
        """
        if not image_paths:
            return {
                "title": "画像が提供されていません",
                "sections": [{"type": "text", "content": "ブログを生成するには、少なくとも1枚の画像が必要です。"}]
            }
        
        try:
            client = self._get_client()
            
            # 構造化プロンプトを使用
            prompt = STRUCTURED_BLOG_PROMPT
            
            # コンテンツ生成
            logger.info("構造化ブログコンテンツの生成を開始します")
            generated_text = client.generate_content_from_images(image_paths, prompt)
            
            # 生成結果のログ出力を強化
            if generated_text:
                # ライブでは長いログを避けるためにトリミング
                truncated_response = generated_text[:1000] + ("..." if len(generated_text) > 1000 else "")
                logger.debug(f"Gemini APIレスポンス: {truncated_response}")
            
            # 生成に失敗した場合
            if not generated_text:
                logger.warning("構造化プロンプトでの生成に失敗しました。通常のプロンプトで再試行しフォールバックを試みます。")
                # 通常のブログ生成にフォールバック
                standard_result = self.generate_blog_from_images(image_paths)
                
                # 結果を構造化データ形式に変換
                return self._convert_to_structured_format(standard_result, len(image_paths))
            
            # JSONデータの抽出を試みる
            try:
                # JSONブロックを抽出するパターン
                json_pattern = r'```json\s*([\s\S]*?)\s*```'
                json_match = re.search(json_pattern, generated_text)
                
                if json_match:
                    json_str = json_match.group(1).strip()
                    logger.info("JSONブロックを検出しました")
                else:
                    # JSONブロックがない場合、テキスト全体をJSONとして処理
                    json_str = generated_text.strip()
                    logger.warning("JSONブロックが見つからないため、テキスト全体をJSONとして処理します")
                
                # 抽出したJSON文字列をログ出力
                truncated_json = json_str[:500] + ("..." if len(json_str) > 500 else "")
                logger.debug(f"解析前のJSON文字列: {truncated_json}")
                
                # JSONデータをパース
                structured_data = json.loads(json_str)
                logger.info(f"JSON解析成功: title={structured_data.get('title', 'None')}, セクション数={len(structured_data.get('sections', []))}")
                
                # 必須フィールドの確認とデフォルト値の設定
                if "title" not in structured_data:
                    structured_data["title"] = "ヘアスタイルブログ"
                
                if "sections" not in structured_data or not structured_data["sections"]:
                    # セクションがない場合、デフォルトセクションを作成
                    structured_data["sections"] = [
                        {"type": "text", "content": "このブログはヘアスタイルについて紹介しています。"}
                    ]
                    # 画像ごとにセクションを追加
                    for i in range(len(image_paths)):
                        structured_data["sections"].append({"type": "image", "imageIndex": i})
                        structured_data["sections"].append({"type": "text", "content": f"画像{i+1}の説明文です。"})
                
                logger.info("構造化ブログデータの生成に成功しました")
                return structured_data
                
            except (json.JSONDecodeError, ValueError) as json_err:
                logger.error(f"JSONデータの解析に失敗しました: {json_err}")
                # 通常のブログ生成にフォールバック
                standard_result = self.generate_blog_from_images(image_paths)
                return self._convert_to_structured_format(standard_result, len(image_paths))
            
        except Exception as e:
            logger.error(f"構造化ブログ生成エラー: {str(e)}")
            return {
                "title": "エラーが発生しました",
                "sections": [{"type": "text", "content": "ブログ生成中にエラーが発生しました。もう一度お試しください。"}]
            }
    
    def _convert_to_structured_format(self, standard_result, image_count):
        """
        標準形式の結果を構造化データ形式に変換
        
        Args:
            standard_result (dict): タイトルと本文を含む辞書
            image_count (int): 画像の数
            
        Returns:
            dict: 構造化されたブログデータ
        """
        title = standard_result.get("title", "ヘアスタイルブログ")
        content = standard_result.get("content", "")
        
        # 画像プレースホルダが含まれている場合、それを使用してセクションを作成
        sections = []
        
        if any(f"[IMAGE_{i+1}]" in content for i in range(image_count)):
            # プレースホルダを使用して分割
            parts = re.split(r'\[IMAGE_(\d+)\]', content)
            
            # 最初のテキスト部分
            if parts[0].strip():
                sections.append({"type": "text", "content": parts[0].strip()})
            
            # 画像とそれに続くテキスト
            for i in range(1, len(parts), 2):
                if i < len(parts):
                    try:
                        img_index = int(parts[i]) - 1  # [IMAGE_1] → インデックス0
                        sections.append({"type": "image", "imageIndex": img_index})
                    except ValueError:
                        # 無効な画像インデックスの場合
                        pass
                        
                if i + 1 < len(parts) and parts[i + 1].strip():
                    sections.append({"type": "text", "content": parts[i + 1].strip()})
        else:
            # プレースホルダがない場合、本文を段落に分割して画像を挿入
            paragraphs = content.split("\n\n")
            image_index = 0
            
            # 最初のパラグラフ
            if paragraphs and paragraphs[0].strip():
                sections.append({"type": "text", "content": paragraphs[0].strip()})
            
            # 残りのパラグラフと画像を交互に配置
            for i, para in enumerate(paragraphs[1:], 1):
                # 一定間隔で画像を挿入
                if i % 2 == 0 and image_index < image_count:
                    sections.append({"type": "image", "imageIndex": image_index})
                    image_index += 1
                    
                if para.strip():
                    sections.append({"type": "text", "content": para.strip()})
            
            # 残りの画像を追加
            while image_index < image_count:
                sections.append({"type": "image", "imageIndex": image_index})
                image_index += 1
        
        # セクションが空の場合のデフォルト
        if not sections:
            sections = [{"type": "text", "content": content}]
        
        return {
            "title": title,
            "sections": sections
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