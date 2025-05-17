import re
import json
import logging
from flask import current_app
from app.gemini.client import GeminiClient
from app.gemini.prompts import (
    BLOG_GENERATION_PROMPT,
    MULTI_IMAGE_BLOG_PROMPT,
    SIMPLE_BLOG_PROMPT,
    STRUCTURED_BLOG_PROMPT_BASE,
    PROMPT_FOR_1_IMAGE,
    PROMPT_FOR_2_IMAGES,
    PROMPT_FOR_3_IMAGES,
    PROMPT_FOR_4_IMAGES,
    HAIR_INFO_PROMPT_SUFFIX
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
            num_images = len(image_paths)
            
            # 画像の枚数に応じたプロンプトを選択
            image_specific_prompt_part = ""
            if num_images == 1:
                image_specific_prompt_part = PROMPT_FOR_1_IMAGE
            elif num_images == 2:
                image_specific_prompt_part = PROMPT_FOR_2_IMAGES
            elif num_images == 3:
                image_specific_prompt_part = PROMPT_FOR_3_IMAGES
            elif num_images == 4:
                image_specific_prompt_part = PROMPT_FOR_4_IMAGES
            else:
                # 0枚または5枚以上の画像の場合 (現状のプロンプトは4枚までを想定)
                # ここでは単純に1枚用のプロンプトを流用するか、エラーメッセージを返すことを検討
                # 今回は、最大4枚という仕様に基づき、予期せぬ枚数の場合はログに警告を出し、
                # デフォルトとして1枚用の指示（またはエラーを示す固定JSON）を返すことを想定する。
                # より堅牢にするには、専用のエラー処理や5枚以上に対応したプロンプトが必要。
                logger.warning(f"予期しない画像枚数です: {num_images}枚。1枚用のプロンプトで試行します。")
                image_specific_prompt_part = PROMPT_FOR_1_IMAGE 
                # または、以下のようにエラーを示すJSONを返すこともできる
                # return {
                #     "title": "エラー：対応していない画像枚数です",
                #     "sections": [{"type": "text", "content": f"{num_images}枚の画像には対応していません。1～4枚の画像をアップロードしてください。"}]
                # }

            # ベースプロンプト、枚数別指示、ヘアスタイル情報サフィックスを結合
            prompt = STRUCTURED_BLOG_PROMPT_BASE + "\n\n" + \
                       image_specific_prompt_part + "\n\n" + \
                       HAIR_INFO_PROMPT_SUFFIX
            
            # ヘアスタイル情報がある場合、プロンプトを拡張 (この部分は枚数別パーツより後に結合する)
            # ※ HAIR_INFO_PROMPT_SUFFIX がヘアスタイル情報の扱いを定義しているので、
            #   この _enhance_prompt_with_hair_info は不要になるか、
            #   HAIR_INFO_PROMPT_SUFFIX の内容と重複しないように調整が必要。
            #   今回は HAIR_INFO_PROMPT_SUFFIX に寄せ、元の _enhance_prompt_with_hair_info の呼び出しはコメントアウトする。
            if hair_info and isinstance(hair_info, dict) and len(hair_info) > 0:
                logger.info("ヘアスタイル情報をプロンプトに含めます (HAIR_INFO_PROMPT_SUFFIXにより処理)")
                # prompt = self._enhance_prompt_with_hair_info(prompt, hair_info) # 元の処理はコメントアウト
            
            # コンテンツ生成
            logger.info("構造化ブログコンテンツの生成を開始します")
            # logger.debug(f"最終プロンプト:\n{prompt}") # デバッグ用に最終プロンプトを出力
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
                
                # 生成されたJSONの画像セクション数とimageIndexを検証・修正する処理
                if "sections" in structured_data and isinstance(structured_data["sections"], list):
                    actual_image_sections = [s for s in structured_data["sections"] if isinstance(s, dict) and s.get("type") == "image"]
                    num_actual_image_sections = len(actual_image_sections)

                    if num_actual_image_sections != num_images:
                        logger.warning(f"APIからの画像セクション数({num_actual_image_sections})がアップロード枚数({num_images})と異なります。調整を試みます。")
                        
                        # 足りない画像セクションを補完する (imageIndex が連番になるように)
                        # まず、現在の imageIndex の最大値を確認
                        existing_indices = {s.get("imageIndex") for s in actual_image_sections if isinstance(s.get("imageIndex"), int)}
                        
                        # 新しいセクションリストを作成
                        new_sections = []
                        output_image_index_counter = 0
                        # 既存のテキストセクションと、期待される枚数分の画像セクションを交互に配置するイメージ
                        # ただし、Geminiが生成したテキストセクションは尊重する
                        
                        temp_sections = [] # 一時的にセクションを保持
                        # 既存のテキストを保持しつつ、画像を期待数分挿入
                        # imageIndexの重複や欠番を修正し、期待する数の画像を配置
                        # セクションの順番を保持しつつ、imageIndexを0から再割り当てし、不足分を追加
                        
                        # 既存のセクションをベースに再構築
                        current_img_idx = 0
                        for sec in structured_data["sections"]:
                            if sec.get("type") == "image":
                                if current_img_idx < num_images: # 画像の枚数上限を超えないように
                                    new_sections.append({"type": "image", "imageIndex": current_img_idx})
                                    current_img_idx += 1
                                else:
                                    logger.warning(f"期待枚数({num_images})を超える画像セクションをスキップ: {sec}")
                            else:
                                new_sections.append(sec) # テキストセクションはそのまま追加
                        
                        # それでも画像セクションが足りない場合、末尾に追加
                        while current_img_idx < num_images:
                            logger.info(f"画像セクションが不足しているため、imageIndex: {current_img_idx} を末尾に追加します。")
                            new_sections.append({"type": "image", "imageIndex": current_img_idx})
                            # 足りない画像の後にはデフォルトのテキストセクションも追加しておく（任意）
                            new_sections.append({"type": "text", "content": f"(画像 {current_img_idx + 1} の説明)"}) 
                            current_img_idx += 1
                        
                        structured_data["sections"] = new_sections
                        logger.info(f"調整後のセクション数: {len(structured_data['sections'])}. うち画像セクション数: {len([s for s in structured_data['sections'] if s.get('type')=='image'])}個")

                # 必須フィールドの確認とデフォルト値の設定 (この部分は元のままでも良いが、上記調整でカバーされる部分もある)
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
        
    def _enhance_prompt_with_hair_info(self, prompt, hair_info):
        """
        ヘアスタイル情報を使用してプロンプトを拡張
        
        Args:
            prompt (str): 元のプロンプト
            hair_info (dict): ヘアスタイル情報
            
        Returns:
            str: 拡張されたプロンプト
        """
        # 英語キーと日本語キーの対応を確認
        hairstyle = hair_info.get('ヘアスタイル') or hair_info.get('hairstyle', '')
        color = hair_info.get('髪色') or hair_info.get('color', '')
        features = hair_info.get('特徴') or hair_info.get('features', [])
        face_shape = hair_info.get('顔型') or hair_info.get('face_shape', '')
        season = hair_info.get('季節') or hair_info.get('season', '')
        
        # 特徴を文字列に変換
        if isinstance(features, list):
            features_text = '、'.join(features)
        else:
            features_text = str(features)
        
        # ヘアスタイル情報テキストを作成
        hair_info_text = "\n\n--- ヘアスタイル分析情報 ---\n"
        if hairstyle:
            hair_info_text += f"ヘアスタイル: {hairstyle}\n"
        if color:
            hair_info_text += f"カラー: {color}\n"
        if features_text:
            hair_info_text += f"特徴: {features_text}\n"
        if face_shape:
            hair_info_text += f"似合う顔型: {face_shape}\n"
        if season:
            hair_info_text += f"季節・トレンド: {season}\n"
        hair_info_text += "\nこの分析情報を参考にして、特徴やカラーを具体的に説明し、読者に分かりやすく伝えてください。\n---\n"
        
        # プロンプトの最後（注意事項の前）に挿入
        if "注意:" in prompt:
            parts = prompt.split("注意:", 1)
            enhanced_prompt = parts[0] + hair_info_text + "\n注意:" + parts[1]
        else:
            enhanced_prompt = prompt + hair_info_text
        
        return enhanced_prompt
    
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