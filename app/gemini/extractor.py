import os
import logging
from flask import current_app
from app.gemini.client import GeminiClient
from app.gemini.prompts import HAIR_ANALYSIS_PROMPT
from app.utils.image import get_full_image_path, resize_image_if_needed

logger = logging.getLogger(__name__)

class HairStyleExtractor:
    """
    ヘアスタイル情報抽出クラス
    Gemini APIを使用して画像からヘアスタイルの特徴を抽出します
    """
    
    def __init__(self):
        """初期化"""
        self.client = None
        
    def _get_client(self):
        """GeminiClientのインスタンスを取得"""
        if self.client is None:
            self.client = GeminiClient()
        return self.client
    
    def extract_hair_info(self, image_path):
        """
        画像からヘアスタイル情報を抽出
        
        Args:
            image_path (str): 画像ファイルのパス
            
        Returns:
            dict: 抽出された髪型情報の辞書
                {
                    'hairstyle': str,  # ヘアスタイルの種類
                    'color': str,      # 髪色
                    'features': list,  # 特徴のリスト
                    'face_shape': str, # 適した顔の形
                    'season': str      # 季節のトレンド
                }
        """
        try:
            # 画像パスの完全パスを取得
            full_path = get_full_image_path(image_path)
            
            # 画像サイズが大きい場合はリサイズ
            resized_path = resize_image_if_needed(full_path)
            image_to_use = resized_path if resized_path else full_path
            
            # Gemini APIでヘアスタイル情報を抽出
            client = self._get_client()
            response = client.generate_content_from_images(
                [image_to_use], 
                HAIR_ANALYSIS_PROMPT
            )
            
            # レスポンスがなければ空の辞書を返す
            if not response:
                logger.warning(f"画像 {image_path} からヘアスタイル情報を抽出できませんでした")
                return {}
            
            # 抽出結果をパース
            hair_info = self._parse_hair_info(response)
            return hair_info
            
        except Exception as e:
            logger.error(f"ヘアスタイル情報抽出エラー: {str(e)}")
            return {}
    
    def _parse_hair_info(self, response_text):
        """
        APIレスポンスからヘアスタイル情報を解析
        
        Args:
            response_text (str): APIからのレスポンステキスト
            
        Returns:
            dict: 解析されたヘアスタイル情報
        """
        # 初期値を設定
        hair_info = {
            'hairstyle': '',
            'color': '',
            'features': [],
            'face_shape': '',
            'season': '',
            # 日本語キーの初期値も設定
            'ヘアスタイル': '',
            '髪色': '',
            '特徴': [],
            '顔型': '',
            '季節': ''
        }
        
        # レスポンスが空の場合は初期値を返す
        if not response_text:
            return hair_info
        
        try:
            # 行ごとに処理
            lines = response_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # キーとなる文字列をチェック
                if "ヘアスタイル:" in line or "髪型:" in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        hair_info['hairstyle'] = value
                        hair_info['ヘアスタイル'] = value
                elif "髪色:" in line or "カラー:" in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        hair_info['color'] = value
                        hair_info['髪色'] = value
                elif "特徴:" in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        features_text = parts[1].strip()
                        # カンマや箇条書きで分割
                        features = [f.strip() for f in features_text.replace('・', ',').split(',')]
                        cleaned_features = [f for f in features if f]
                        hair_info['features'] = cleaned_features
                        hair_info['特徴'] = cleaned_features
                elif "顔型:" in line or "似合う顔型:" in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        hair_info['face_shape'] = value
                        hair_info['顔型'] = value
                elif "季節:" in line or "トレンド:" in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        hair_info['season'] = value
                        hair_info['季節'] = value
            
            return hair_info
            
        except Exception as e:
            logger.error(f"ヘアスタイル情報の解析エラー: {str(e)}")
            return hair_info 