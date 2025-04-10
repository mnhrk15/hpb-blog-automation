"""
HotPepper Beauty スタイリスト情報スクレイピングモジュール
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import urljoin

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
            
            # スタイリスト情報を取得するためのアプローチ
            stylists = []
            
            # 方法1: 表（table）要素からスタイリスト情報を抽出
            tables = soup.find_all('table')
            for table_idx, table in enumerate(tables):
                if table_idx > 2:  # 最初の数テーブルだけを確認（スタイリスト情報は通常最初のテーブルにある）
                    break
                    
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    for cell in cells:
                        # セル内のテキストからスタイリスト名を抽出
                        lines = cell.text.strip().split('\n')
                        if len(lines) >= 3:  # 最低でも名前、フリガナ、役職などの情報があると仮定
                            stylist_name = lines[0].strip()
                            
                            # 明らかに不適切な名前をフィルタリング（「クーポン」「カット」などの単語を含む）
                            if any(keyword in stylist_name for keyword in ['クーポン', 'カット', 'その他', 'ANGEL', '予約', '髪質']):
                                continue
                            
                            # スタイリストページへのリンクを探す
                            stylist_links = cell.find_all('a', href=re.compile(r'/stylist/'))
                            stylist_id = None
                            
                            # リンクから情報を取得
                            if stylist_links:
                                href = stylist_links[0].get('href', '')
                                # スタイリストIDを抽出
                                stylist_id_match = re.search(r'/stylist/([^/]+)/', href)
                                if stylist_id_match:
                                    stylist_id = stylist_id_match.group(1)
                            
                            # サロンのID（slnXXXXXX）からカスタムIDを生成
                            if not stylist_id:
                                salon_id_match = re.search(r'sln([A-Za-z0-9]+)', self.base_url)
                                salon_id = salon_id_match.group(1) if salon_id_match else "Unknown"
                                # カスタムID生成
                                stylist_id = f"stf{salon_id}_{len(stylists)+1}"
                            
                            if stylist_name:
                                # 既に同じ名前のスタイリストが追加されていないかチェック
                                if not any(s['name'] == stylist_name for s in stylists):
                                    stylists.append({
                                        'id': stylist_id,
                                        'name': stylist_name
                                    })
            
            # スタイリストが1人も見つからなかった場合のフォールバック
            if not stylists:
                # タイトルからサロン名を取得
                salon_name = ""
                if soup.title:
                    title_parts = soup.title.string.split('｜')
                    if len(title_parts) > 1:
                        salon_name = title_parts[1].strip()
                
                # サロンのID（slnXXXXXX）を抽出
                salon_id_match = re.search(r'sln([A-Za-z0-9]+)', self.base_url)
                salon_id = salon_id_match.group(1) if salon_id_match else "Unknown"
                
                # デフォルトのスタイリスト情報を追加
                stylists.append({
                    'id': f"stf{salon_id}_default",
                    'name': f"{salon_name}スタイリスト"
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