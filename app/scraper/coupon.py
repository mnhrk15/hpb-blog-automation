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
        page_info_elem = soup.select_one("#mainContents > div:nth-child(2) > div.preListHead.mT20 > div > p.pa.bottom0.right0")
        
        max_page = 1  # デフォルトは1ページ
        
        if page_info_elem:
            page_info_text = page_info_elem.text
            print(f"ページ情報: {page_info_text}")
            
            # ページ数を解析
            match = re.search(r'全(\d+)件.*?(\d+)/(\d+)ページ', page_info_text)
            if match:
                total_items = int(match.group(1))
                current_page = int(match.group(2))
                max_page = int(match.group(3))
                print(f"解析結果: 全{total_items}件 {current_page}/{max_page}ページ")
            else:
                print("ページ情報の解析に失敗しました")
        else:
            print("ページ情報要素が見つかりません")
            # テスト用のデータの場合、ページ情報がHTMLに含まれていることがある
            if soup.find(string=re.compile(r'全\d+件.*?\d+/\d+ページ')):
                text = soup.find(string=re.compile(r'全\d+件.*?\d+/\d+ページ')).strip()
                match = re.search(r'全(\d+)件.*?(\d+)/(\d+)ページ', text)
                if match:
                    max_page = int(match.group(3))
                    print(f"ページ情報の代替検索: 全{match.group(1)}件 {match.group(2)}/{max_page}ページ")
        
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
        
        # クーポン要素を抽出
        # 古いセレクタが機能していない場合に新しいセレクタを使用
        print("クーポン要素を様々なセレクタで検索中")
        
        # 標準クーポンセレクタ
        coupon_elems = soup.select("p.couponMenuName")
        print(f"p.couponMenuName で検出: {len(coupon_elems)}件")
        
        # 代替セレクタ1
        if not coupon_elems:
            coupon_elems = soup.select("#mainContents > div:nth-child(2) > div:nth-child(8) > table > tbody > tr > td.bgWhite.pr > div > div:nth-child(1) > div.mT5.b > p")
            print(f"代替セレクタ1で検出: {len(coupon_elems)}件")
        
        # 代替セレクタ2 (メニュー名用)
        if not coupon_elems:
            coupon_elems = soup.select("#mainContents > div.mT10 > table:nth-child(2) > tbody > tr > td.bgWhite > div > div > div.mT5.b.cFix > p.fl.couponMenuName.fs14.w423.mR10")
            print(f"代替セレクタ2で検出: {len(coupon_elems)}件")
            
        # 最も汎用的なセレクタ
        if not coupon_elems:
            coupon_elems = soup.select("#mainContents div.mT5.b p.couponMenuName")
            print(f"汎用セレクタで検出: {len(coupon_elems)}件")
        
        # さらに汎用的なセレクタを試す
        if not coupon_elems:
            print("最後の手段: クーポン名を含む任意の要素を探索")
            coupon_elems = soup.find_all("p", class_=lambda c: c and "couponMenuName" in c)
            print(f"クラス検索で検出: {len(coupon_elems)}件")
        
        # 各クーポン要素から情報を抽出
        for elem in coupon_elems:
            coupon_name = elem.text.strip()
            print(f"抽出されたクーポン: {coupon_name}")
            coupons.append({
                'name': coupon_name
            })
            
        return coupons 