"""
HotPepper Beauty スタイリスト情報スクレイピングモジュール
"""

import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

class StylistScraper:
    """
    HotPepper Beauty サイトからスタイリスト情報をスクレイピングするクラス
    """
    
    def __init__(self, base_url=None):
        """
        初期化
        
        Args:
            base_url (str, optional): HPBサロンのベースURL。例: https://beauty.hotpepper.jp/slnH000xxxxxx/
        """
        self.base_url = base_url
        self._stylists = []
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def set_base_url(self, base_url):
        """
        ベースURLを設定する
        
        Args:
            base_url (str): HPBサロンのベースURL
        """
        self.base_url = base_url
        self._stylists = []  # URLが変わったら結果をリセット
    
    def get_stylists(self, force_refresh=False):
        """
        スタイリスト情報を取得する
        
        Args:
            force_refresh (bool, optional): キャッシュがある場合も強制的に再取得するかどうか
            
        Returns:
            list: スタイリスト情報のリスト。各要素は辞書形式で {'id': 'スタイリストID', 'name': 'スタイリスト名'}
        """
        if not self.base_url:
            raise ValueError("ベースURLが設定されていません。set_base_url()メソッドで設定してください。")
        
        # キャッシュがあり強制更新でない場合はキャッシュを返す
        if self._stylists and not force_refresh:
            return self._stylists
        
        # スタイリストページのURL
        stylist_url = f"{self.base_url.rstrip('/')}/stylist/"
        
        try:
            logger.info(f"スタイリスト情報の取得を開始: {stylist_url}")
            response = requests.get(stylist_url, headers=self._headers)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # セレクタを使用してスタイリスト情報を取得
            # 要件定義のセレクタ例を使用
            stylists = []
            stylist_elements = soup.select('#mainContents > div.mT20 > div.oh.w745.mT20.pH10 > table > tbody > tr > td:nth-child(2) > div:nth-child(1) > p.mT10.fs16.b > a')
            
            for element in stylist_elements:
                stylist_name = element.text.strip()
                href = element.get('href', '')
                
                # スタイリストIDを抽出（/slnH000xxxxxx/stylist/stfT00000000/ から stfT00000000 を取得）
                stylist_id_match = re.search(r'/stylist/([^/]+)/', href)
                stylist_id = stylist_id_match.group(1) if stylist_id_match else None
                
                if stylist_id:
                    stylists.append({
                        'id': stylist_id,
                        'name': stylist_name
                    })
            
            logger.info(f"スタイリスト情報を {len(stylists)} 件取得しました")
            self._stylists = stylists
            return stylists
            
        except requests.exceptions.RequestException as e:
            logger.error(f"スタイリスト情報の取得に失敗: {e}")
            raise
        except Exception as e:
            logger.error(f"スタイリスト情報の解析に失敗: {e}")
            raise 