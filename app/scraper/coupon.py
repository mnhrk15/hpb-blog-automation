"""
HotPepper Beauty クーポン情報取得用スクレイパー
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ロガーの設定
logger = logging.getLogger(__name__)

class CouponScraper:
    """
    HotPepper Beauty のサロンページからクーポン情報を取得するスクレイパー
    """
    
    def __init__(self, base_url=None):
        """
        クーポンスクレイパーの初期化
        
        Parameters:
        -----------
        base_url : str
            スクレイピング対象のサロンURL（例: https://beauty.hotpepper.jp/slnH000123456/）
        """
        self.base_url = base_url
        self._coupons = []
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def set_base_url(self, base_url):
        """
        スクレイピング対象のベースURLを設定
        
        Parameters:
        -----------
        base_url : str
            スクレイピング対象のサロンURL
        """
        self.base_url = base_url
        # URLが変更されたらキャッシュをクリア
        self._coupons = []
    
    def get_coupons(self):
        """
        サロンで利用可能なクーポン情報を取得
        
        Returns:
        --------
        list
            クーポン情報のリスト。各要素は辞書型で、以下のキーを含む:
            - name: クーポン名
        """
        if not self.base_url:
            raise ValueError("base_url が設定されていません。set_base_url() を使用して設定してください。")
            
        if self._coupons:
            return self._coupons
        
        # クーポンページのURL
        print("クーポン取得を開始します")
        coupon_url = urljoin(self.base_url, "coupon/")
        
        # 初回リクエスト
        print(f"クーポンページへリクエスト: {coupon_url}")
        response = requests.get(coupon_url, headers=self._headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ページ情報を取得（全X件（Y/Zページ）のような形式）
        print("ページ情報の解析")
        
        # ページネーション情報を探す方法を改善
        max_page = 1  # デフォルトは1ページ
        
        # 方法1: 標準的なページネーション要素
        page_info_elem = soup.select_one(".preListHead div.fs10")
        
        if not page_info_elem:
            # 方法2: 別の場所にあるページネーション要素
            page_info_elem = soup.select_one("#mainContents div.pa.bottom0.right0")
            
        if not page_info_elem:
            # 方法3: テキストで検索
            page_info_elem = soup.find(string=re.compile(r'\d+/\d+ページ'))
            
        if page_info_elem:
            page_info_text = page_info_elem.strip() if isinstance(page_info_elem, str) else page_info_elem.text.strip()
            print(f"ページ情報: {page_info_text}")
            
            # ページ数を解析
            match = re.search(r'(\d+)/(\d+)ページ', page_info_text)
            if match:
                current_page = int(match.group(1))
                max_page = int(match.group(2))
                print(f"解析結果: {current_page}/{max_page}ページ")
            else:
                print("ページ情報の解析に失敗しました")
        else:
            print("ページ情報要素が見つかりません")
        
        # クーポンを抽出
        print(f"ページ1からクーポンを抽出します")
        coupons = self._extract_coupons_from_soup(soup)
        print(f"ページ1から{len(coupons)}件のクーポンを抽出しました")
        
        # 複数ページがある場合、2ページ目以降も取得
        if max_page > 1:
            print(f"複数ページが検出されました。全{max_page}ページの処理を開始します")
            for page in range(2, max_page + 1):
                print(f"ページ{page}の処理を開始します")
                page_url = urljoin(self.base_url, f"coupon/PN{page}.html")
                print(f"URL: {page_url}")
                
                response = requests.get(page_url, headers=self._headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                page_coupons = self._extract_coupons_from_soup(soup)
                print(f"ページ{page}から{len(page_coupons)}件のクーポンを抽出しました")
                
                coupons.extend(page_coupons)
        
        print(f"合計{len(coupons)}件のクーポンを取得しました")
        self._coupons = coupons
        return self._coupons
    
    def _extract_coupons_from_soup(self, soup):
        """
        BeautifulSoupオブジェクトからクーポン情報を抽出
        
        Parameters:
        -----------
        soup : BeautifulSoup
            解析対象のHTMLを表すBeautifulSoupオブジェクト
            
        Returns:
        --------
        list
            クーポン情報のリスト
        """
        coupons = []
        
        # クーポン領域の特定 - クーポン専用のセクションを特定
        coupon_sections = []
        
        # 1. クーポンセクションのヘッダーを探す
        coupon_headers = soup.find_all(['h3', 'h2', 'div'], string=re.compile(r'クーポン|キャンペーン'))
        if coupon_headers:
            print(f"クーポンセクションのヘッダーを{len(coupon_headers)}個検出")
            for header in coupon_headers:
                # ヘッダーの次の要素（テーブル）をクーポンセクションとして追加
                section = header.find_next('table')
                if section:
                    coupon_sections.append(section)
        
        # 2. クーポンページ専用のコンテナを探す
        if not coupon_sections:
            coupon_containers = soup.select("#mainContents > div.bgLightOrange, #mainContents > div.mT20 > div.bgLightOrange")
            if coupon_containers:
                print(f"クーポン専用コンテナを{len(coupon_containers)}個検出")
                coupon_sections.extend(coupon_containers)
        
        # 3. クーポンURL内の場合、ページ全体をクーポンセクションとみなす
        if 'coupon' in soup.select_one('link[rel="canonical"]').get('href', '') if soup.select_one('link[rel="canonical"]') else '':
            print("クーポン専用ページを検出")
            coupon_sections = [soup.select_one('#mainContents')]
        
        # クーポン要素の抽出
        extracted_coupons = []
        
        if coupon_sections:
            print(f"{len(coupon_sections)}個のクーポンセクションを処理")
            
            for section in coupon_sections:
                # クーポン名を含む要素を探す（クーポン用のクラスに限定）
                coupon_elems = section.select("p.couponMenuName:not(.fl)")
                
                if not coupon_elems:
                    # 代替: クーポンページ特有のレイアウト
                    coupon_elems = section.select("div.mT5.b > p.couponMenuName")
                
                print(f"セクションから{len(coupon_elems)}個のクーポンを検出")
                extracted_coupons.extend(coupon_elems)
        else:
            # フォールバック: 通常メニューと区別できるクーポン要素を探す
            print("クーポンセクションが見つからないため、クーポン特有の要素を検索")
            
            # クーポン専用のクラスパターンで検索（通常メニューは fl クラスを含むことが多い）
            coupon_elems = soup.select("p.couponMenuName:not(.fl)")
            if coupon_elems:
                print(f"クーポン特有のクラスパターンで{len(coupon_elems)}個検出")
                extracted_coupons.extend(coupon_elems)
            
            # クーポンコンテナ内の要素
            coupon_elems = soup.select(".bgLightOrange p.couponMenuName")
            if coupon_elems:
                print(f"クーポンコンテナ内で{len(coupon_elems)}個検出")
                extracted_coupons.extend(coupon_elems)
        
        # 重複を除去
        unique_coupon_names = set()
        
        # 各クーポン要素から情報を抽出
        for elem in extracted_coupons:
            coupon_name = elem.text.strip()
            
            # 明らかにクーポンでない要素をフィルタリング
            if any(keyword in coupon_name for keyword in ['↓↓↓', '===', '***']):
                print(f"フィルタリング: {coupon_name}")
                continue
                
            # 重複チェック
            if coupon_name in unique_coupon_names:
                continue
                
            unique_coupon_names.add(coupon_name)
            print(f"有効なクーポン: {coupon_name}")
            
            coupons.append({
                'name': coupon_name
            })
            
        return coupons 