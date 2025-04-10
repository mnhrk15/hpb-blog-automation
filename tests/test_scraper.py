"""
HotPepper Beauty スクレイピング機能のテスト
"""

import unittest
from unittest.mock import patch, MagicMock, call
import pytest
from bs4 import BeautifulSoup
import os
import requests
import logging
import sys

from app.scraper.stylist import StylistScraper
from app.scraper.coupon import CouponScraper

# デバッグ用にロガーを設定
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

logger = logging.getLogger(__name__)

# テスト用のHTMLデータ
SAMPLE_STYLIST_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="mainContents">
        <div class="mT20">
            <div class="oh w745 mT20 pH10">
                <table>
                    <tbody>
                        <tr>
                            <td></td>
                            <td>
                                <div>
                                    <p class="mT10 fs16 b"><a href="/slnH000123456/stylist/stfT000000001/">山田 花子</a></p>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td></td>
                            <td>
                                <div>
                                    <p class="mT10 fs16 b"><a href="/slnH000123456/stylist/stfT000000002/">佐藤 一郎</a></p>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_COUPON_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="mainContents">
        <div>
            <div class="preListHead mT20">
                <div>
                    <p class="pa bottom0 right0">全6件（1/2ページ）</p>
                </div>
            </div>
        </div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div>
            <div>
                <table>
                    <tbody>
                        <tr>
                            <td class="bgWhite pr">
                                <div>
                                    <div>
                                        <div class="mT5 b">
                                            <p class="couponMenuName fs14 w423">初回限定20%オフクーポン</p>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="bgWhite pr">
                                <div>
                                    <div>
                                        <div class="mT5 b">
                                            <p class="couponMenuName fs14 w423">平日限定5%オフクーポン</p>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_COUPON_PAGE2_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="mainContents">
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
        <div>
            <div>
                <table>
                    <tbody>
                        <tr>
                            <td class="bgWhite pr">
                                <div>
                                    <div>
                                        <div class="mT5 b">
                                            <p class="couponMenuName fs14 w423">学割クーポン</p>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td class="bgWhite pr">
                                <div>
                                    <div>
                                        <div class="mT5 b">
                                            <p class="couponMenuName fs14 w423">誕生日特典クーポン</p>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

class TestStylistScraper(unittest.TestCase):
    """
    スタイリストスクレイパーのテスト
    """
    
    def setUp(self):
        self.scraper = StylistScraper("https://beauty.hotpepper.jp/slnH000123456/")
        
    @patch('app.scraper.stylist.requests.get')
    def test_get_stylists(self, mock_get):
        # モックレスポンスの設定
        mock_response = MagicMock()
        mock_response.text = SAMPLE_STYLIST_HTML
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # テスト実行
        stylists = self.scraper.get_stylists()
        
        # 検証
        self.assertEqual(len(stylists), 2)
        self.assertEqual(stylists[0]['name'], '山田 花子')
        self.assertEqual(stylists[0]['id'], 'stfT000000001')
        self.assertEqual(stylists[1]['name'], '佐藤 一郎')
        self.assertEqual(stylists[1]['id'], 'stfT000000002')
        
        # リクエストが正しいURLで呼ばれたことを確認
        mock_get.assert_called_once_with(
            "https://beauty.hotpepper.jp/slnH000123456/stylist/",
            headers=self.scraper._headers
        )
    
    def test_set_base_url(self):
        self.scraper._stylists = [{'id': 'dummy', 'name': 'dummy'}]
        self.scraper.set_base_url("https://beauty.hotpepper.jp/slnH000654321/")
        
        # URLが更新され、キャッシュがクリアされたことを確認
        self.assertEqual(self.scraper.base_url, "https://beauty.hotpepper.jp/slnH000654321/")
        self.assertEqual(self.scraper._stylists, [])
    
    def test_no_base_url(self):
        self.scraper.base_url = None
        with self.assertRaises(ValueError):
            self.scraper.get_stylists()

class TestCouponScraper(unittest.TestCase):
    """
    クーポンスクレイパーのテスト
    """
    
    def setUp(self):
        self.scraper = CouponScraper("https://beauty.hotpepper.jp/slnH000123456/")
    
    @patch('app.scraper.coupon.requests.get')
    def test_get_coupons_multi_page(self, mock_get):
        # テスト用のデバッグ
        print("\n*********** STARTING TEST: test_get_coupons_multi_page ***********")
        
        # 各ページのモックレスポンスを設定
        mock_page1 = MagicMock()
        mock_page1.text = SAMPLE_COUPON_HTML
        mock_page1.raise_for_status = MagicMock()
        
        mock_page2 = MagicMock()
        mock_page2.text = SAMPLE_COUPON_PAGE2_HTML
        mock_page2.raise_for_status = MagicMock()
        
        # モックレスポンスの内容を検証
        print("--- Page 1 HTML Preview ---")
        soup1 = BeautifulSoup(mock_page1.text, 'html.parser')
        page_info = soup1.select_one('#mainContents > div:nth-child(2) > div.preListHead.mT20 > div > p.pa.bottom0.right0')
        print(f"Page info element found: {page_info is not None}")
        if page_info:
            print(f"Page info text: '{page_info.text}'")
        
        coupons_p1 = soup1.select('p.couponMenuName')
        print(f"Page 1 coupons found with 'p.couponMenuName': {len(coupons_p1)}")
        for i, c in enumerate(coupons_p1):
            print(f"Coupon {i+1}: {c.text.strip()}")
            
        print("--- Page 2 HTML Preview ---")
        soup2 = BeautifulSoup(mock_page2.text, 'html.parser')
        coupons_p2 = soup2.select('p.couponMenuName')
        print(f"Page 2 coupons found with 'p.couponMenuName': {len(coupons_p2)}")
        for i, c in enumerate(coupons_p2):
            print(f"Coupon {i+1}: {c.text.strip()}")
        
        # 呼び出し結果を格納するリスト
        called_urls = []
        
        # モックの設定を修正: 固定の応答を返すようにする
        def mock_get_side_effect(url, headers):
            called_urls.append(url)
            print(f"Mock GET request to URL: {url}")
            if "PN2.html" in url:
                print("Returning page 2 mock response")
                return mock_page2
            else:
                print("Returning page 1 mock response")
                return mock_page1
        
        mock_get.side_effect = mock_get_side_effect
        
        # テスト実行
        print("\n--- Executing get_coupons() ---")
        coupons = self.scraper.get_coupons()
        
        # 検証
        print("\n--- Test Results ---")
        print(f"抽出されたクーポン数: {len(coupons)}")
        for i, coupon in enumerate(coupons):
            print(f"クーポン {i+1}: {coupon['name']}")
        
        # リクエスト呼び出し確認
        print(f"request.get の呼び出し回数: {mock_get.call_count}")
        for i, url in enumerate(called_urls):
            print(f"呼び出し {i+1}: URL={url}")
        
        # この時点で 2 ページ分あるはずなのに 1 ページ分しか取得できていない可能性がある
        # mock_get.call_count と len(coupons) の関係を確認
        print(f"Request count = {mock_get.call_count}, Coupon count = {len(coupons)}")
        if mock_get.call_count == 2 and len(coupons) < 4:
            print("*** 問題検出: 2ページ目のリクエストは発生しているが、クーポンが抽出されていない")
            print("- 2ページ目のHTMLのセレクタが正しく検出されていない可能性あり")
            print("- そのため _extract_coupons_from_soup が2ページ目で0件を返している可能性あり")
        
        # 検証
        self.assertEqual(len(coupons), 4, "4つのクーポンが抽出されるべきです (各ページ2つずつ)")
        self.assertEqual(coupons[0]['name'], '初回限定20%オフクーポン')
        self.assertEqual(coupons[1]['name'], '平日限定5%オフクーポン')
        self.assertEqual(coupons[2]['name'], '学割クーポン')
        self.assertEqual(coupons[3]['name'], '誕生日特典クーポン')
        
        # リクエストが正しいURLで呼ばれたことを確認
        expected_calls = [
            call("https://beauty.hotpepper.jp/slnH000123456/coupon/", headers=self.scraper._headers),
            call("https://beauty.hotpepper.jp/slnH000123456/coupon/PN2.html", headers=self.scraper._headers)
        ]
        mock_get.assert_has_calls(expected_calls, any_order=False)
        print("*********** TEST COMPLETED ***********")
    
    @patch('app.scraper.coupon.requests.get')
    def test_get_coupons_single_page(self, mock_get):
        # ページ情報を含まないHTMLを作成
        html_no_paging = SAMPLE_COUPON_HTML.replace('<p class="pa bottom0 right0">全6件（1/2ページ）</p>', '')
        
        mock_response = MagicMock()
        mock_response.text = html_no_paging
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # テスト実行
        coupons = self.scraper.get_coupons()
        
        # 検証
        self.assertEqual(len(coupons), 2)
        
        # 2ページ目へのリクエストが行われていないことを確認
        self.assertEqual(mock_get.call_count, 1)
    
    def test_set_base_url(self):
        self.scraper._coupons = [{'id': 'dummy', 'name': 'dummy'}]
        self.scraper.set_base_url("https://beauty.hotpepper.jp/slnH000654321/")
        
        # URLが更新され、キャッシュがクリアされたことを確認
        self.assertEqual(self.scraper.base_url, "https://beauty.hotpepper.jp/slnH000654321/")
        self.assertEqual(self.scraper._coupons, [])
    
    def test_no_base_url(self):
        self.scraper.base_url = None
        with self.assertRaises(ValueError):
            self.scraper.get_coupons() 