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
    
    def get_coupons(self, full=False):
        """
        サロンで利用可能なクーポン情報を取得
        
        Args:
            full (bool, optional): 詳細情報まで取得するかどうか (現在はクーポン名のみサポート)

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
        logger.info(f"クーポンの取得を開始します: {self.base_url}")
        coupon_url = urljoin(self.base_url, "coupon/")
        
        try:
            # 初回リクエスト
            logger.debug(f"クーポンページへリクエスト: {coupon_url}")
            response = requests.get(coupon_url, headers=self._headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ページ情報を取得（全X件（Y/Zページ）のような形式）
            logger.debug("ページ情報の解析を開始")
            
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
                logger.info(f"ページ情報: {page_info_text}")
                
                # ページ数を解析
                match = re.search(r'(\d+)/(\d+)ページ', page_info_text)
                if match:
                    current_page = int(match.group(1))
                    max_page = int(match.group(2))
                    logger.info(f"クーポンページ情報: {current_page}/{max_page}ページ (URL: {coupon_url})")
                else:
                    logger.warning(f"クーポンページ情報の解析に失敗しました (URL: {coupon_url})")
            else:
                logger.info(f"クーポンページ情報要素が見つかりません (URL: {coupon_url}, シングルページの可能性)")
        
            # クーポンを抽出
            logger.debug(f"ページ1 ({coupon_url}) からクーポンを抽出します")
            coupons = self._extract_coupons_from_soup(soup)
            logger.info(f"ページ1 ({coupon_url}) から{len(coupons)}件のクーポンを抽出しました")
            
            # 複数ページがある場合、2ページ目以降も取得
            if max_page > 1:
                logger.info(f"複数ページが検出されました。全{max_page}ページの処理を開始します")
                for page in range(2, max_page + 1):
                    logger.debug(f"ページ{page}の処理を開始します")
                    page_url = urljoin(self.base_url, f"coupon/PN{page}.html")
                    logger.debug(f"クーポンページ {page}/{max_page} へリクエスト: {page_url}")
                    
                    page_response = requests.get(page_url, headers=self._headers, timeout=10)
                    page_response.raise_for_status()
                    
                    page_soup = BeautifulSoup(page_response.text, 'html.parser')
                    page_coupons = self._extract_coupons_from_soup(page_soup)
                    logger.info(f"ページ{page} ({page_url}) から{len(page_coupons)}件のクーポンを抽出しました")
                    
                    coupons.extend(page_coupons)
            
            logger.info(f"合計{len(coupons)}件のクーポンを {self.base_url} から取得しました")
            self._coupons = coupons
            return self._coupons
        
        except requests.exceptions.RequestException as e:
            logger.error(f"クーポン情報の取得中にネットワークエラーが発生しました (URL: {coupon_url}): {e}")
            # エラー時は空のリストを返すか、例外を再raiseするか選択。ここでは空リストを返す。
            return []
        except Exception as e:
            logger.error(f"クーポン情報の取得中に予期せぬエラーが発生しました (URL: {coupon_url}): {e}")
            return []
    
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
            logger.debug(f"クーポンセクションのヘッダーを{len(coupon_headers)}個検出")
            for header in coupon_headers:
                # ヘッダーの次の要素（テーブル）をクーポンセクションとして追加
                section = header.find_next('table')
                if section:
                    coupon_sections.append(section)
        
        # 2. クーポンページ専用のコンテナを探す
        if not coupon_sections:
            coupon_containers = soup.select("#mainContents > div.bgLightOrange, #mainContents > div.mT20 > div.bgLightOrange")
            if coupon_containers:
                logger.debug(f"クーポン専用コンテナを{len(coupon_containers)}個検出")
                coupon_sections.extend(coupon_containers)
        
        # 3. クーポンURL内の場合、ページ全体をクーポンセクションとみなす
        canonical_link_tag = soup.select_one('link[rel="canonical"]')
        canonical_link = canonical_link_tag.get('href', '') if canonical_link_tag else ''
        if 'coupon' in canonical_link:
            logger.debug(f"クーポン専用ページを検出 (canonical: {canonical_link})")
            coupon_main_content = soup.select_one('#mainContents')
            if coupon_main_content:
                 coupon_sections = [coupon_main_content]
            else:
                logger.warning("クーポン専用ページで #mainContents が見つかりませんでした")
                coupon_sections = [soup] # フォールバックとして全体を対象
        
        # クーポン要素の抽出
        extracted_coupons = []
        
        if coupon_sections:
            logger.debug(f"{len(coupon_sections)}個のクーポンセクションを処理")
            
            for section_idx, section in enumerate(coupon_sections):
                # クーポン名を含む要素を探す（クーポン用のクラスに限定）
                coupon_elems = section.select("p.couponMenuName:not(.fl)")
                
                if not coupon_elems:
                    # 代替: クーポンページ特有のレイアウト
                    coupon_elems = section.select("div.mT5.b > p.couponMenuName")
                
                logger.debug(f"セクション {section_idx+1} から{len(coupon_elems)}個のクーポン候補を検出")
                extracted_coupons.extend(coupon_elems)
        else:
            # フォールバック: 通常メニューと区別できるクーポン要素を探す
            logger.debug("クーポンセクションが見つからないため、ページ全体からクーポン特有の要素を検索")
            
            # クーポン専用のクラスパターンで検索（通常メニューは fl クラスを含むことが多い）
            coupon_elems_fallback1 = soup.select("p.couponMenuName:not(.fl)")
            if coupon_elems_fallback1:
                logger.debug(f"フォールバック1: クーポン特有のクラスパターンで{len(coupon_elems_fallback1)}個検出")
                extracted_coupons.extend(coupon_elems_fallback1)
            
            # クーポンコンテナ内の要素
            coupon_elems_fallback2 = soup.select(".bgLightOrange p.couponMenuName")
            if coupon_elems_fallback2:
                logger.debug(f"フォールバック2: クーポンコンテナ内で{len(coupon_elems_fallback2)}個検出")
                extracted_coupons.extend(coupon_elems_fallback2)
        
        # 重複を除去
        unique_coupon_names = set()
        
        # 各クーポン要素から情報を抽出
        for elem in extracted_coupons:
            coupon_name = elem.text.strip()
            
            # 明らかにクーポンでない要素をフィルタリング
            if any(keyword in coupon_name for keyword in ['↓↓↓', '===', '***']):
                logger.debug(f"フィルタリングされたクーポン名候補: {coupon_name}")
                continue
                
            # 重複チェック
            if coupon_name in unique_coupon_names:
                continue
                
            unique_coupon_names.add(coupon_name)
            logger.debug(f"有効なクーポンとして追加: {coupon_name}")
            
            coupons.append({
                'name': coupon_name
            })
            
        return coupons 