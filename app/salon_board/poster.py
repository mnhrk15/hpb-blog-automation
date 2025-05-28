import os
import time
import logging
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError
import re
import json

logger = logging.getLogger(__name__)

class SalonBoardPoster:
    """サロンボードへのブログ投稿を自動化するクラス"""

    # --- セレクタ定義 ---
    _LOGIN_URL = "https://salonboard.com/login/"
    _LOGIN_USER_ID_INPUT = "input[name='userId']"
    _LOGIN_PASSWORD_INPUT_PRIMARY = "#jsiPwInput"
    _LOGIN_PASSWORD_INPUT_ALT = "input[name='password']"
    _LOGIN_BUTTON_PRIMARY = "#idPasswordInputForm > div > div > a"
    _LOGIN_BUTTON_ALT = "a.common-CNCcommon__primaryBtn.loginBtnSize"
    _LOGIN_FORM = "#idPasswordInputForm"
    _DASHBOARD_GLOBAL_NAVI = "#globalNavi"
    
    # --- サロン一覧ページのセレクタ定義 ---
    _SALON_LIST_TABLE = "#biyouStoreInfoArea"
    _SALON_LIST_ROW = "#biyouStoreInfoArea > tbody > tr"
    _SALON_LIST_NAME_CELL = "td.storeName"
    _NAVI_KEISAI_KANRI = "#globalNavi > ul.common-CLPcommon__globalNavi > li:nth-child(2) > a"
    _NAVI_BLOG = "#cmsForm > div > div > ul > li:nth-child(9) > a"
    _NAVI_NEW_POST = "#newPosts"
    _BLOG_FORM_STYLIST_SELECT = "select#stylistId"
    _BLOG_FORM_CATEGORY_SELECT = "select#blogCategoryCd"
    _BLOG_FORM_TITLE_INPUT = "input#blogTitle"
    _BLOG_FORM_CONTENT_TEXTAREA = "textarea#blogContents" # nicEdit用
    _BLOG_FORM_NICEDIT_IFRAME = "iframe[id^='nicEdit']"
    _BLOG_FORM_IMAGE_UPLOAD_BTN = "a#upload"
    _BLOG_FORM_IMAGE_MODAL = "div.imageUploaderModal"
    _BLOG_FORM_IMAGE_INPUT = "input#sendFile"
    _BLOG_FORM_IMAGE_THUMBNAIL = "img.imageUploaderModalThumbnail"
    _BLOG_FORM_IMAGE_SUBMIT_BTN_ACTIVE = "input.imageUploaderModalSubmitButton.isActive"
    _BLOG_FORM_IMAGE_SUBMIT_BTN = "input.imageUploaderModalSubmitButton"
    _BLOG_FORM_IMAGE_SUBMIT_BTN_XPATH = "//input[@value='登録する']"
    _BLOG_FORM_COUPON_BTN = "a.jsc_SB_modal_trigger"
    _BLOG_FORM_COUPON_MODAL_PRIMARY = "div#couponWrap"
    _BLOG_FORM_COUPON_MODAL_ALT = "#couponArea"
    _BLOG_FORM_COUPON_LABEL = "label" # モーダル内で使用
    _BLOG_FORM_COUPON_TEXT = "p.couponText" # ラベル内で使用
    _BLOG_FORM_COUPON_SETTING_BTN = "a.jsc_SB_modal_setting_btn"
    _BLOG_FORM_COUPON_SETTING_BTN_XPATH = "//a[contains(text(), '設定する')]"
    _BLOG_CONFIRM_BTN = "a#confirm"
    _BLOG_UNREFLECT_BTN = "a#unReflect"
    _BLOG_BACK_BTN = "a#back"
    _BLOG_REFLECT_BTN = "a#reflect" # 追加

    # 失敗時のスクリーンショットファイル名プレフィックス
    _FAILURE_SCREENSHOT_PREFIX = "failure_screenshot_"

    _ROBOT_SELECTORS = [
        "iframe[src*='recaptcha']",
        "iframe[src*='captcha']",
        "div.g-recaptcha",
        ".captcha-container",
        "#captcha",
        "input[name*='captcha']",
        "[aria-label*='ロボット']",
        "[aria-label*='認証']",
        "th.th_item[width='40%'][align='center']",  # サロンボードの画像認証テーブルヘッダー
        "table:has(th.th_item)",                    # 画像認証テーブル全体
        "img[alt*='認証']",                         # 認証画像
        "div:has(> img[alt*='認証'])",              # 認証画像を含む要素
        "div.auth-container",                       # 認証コンテナ
        "form[action*='auth']",                     # 認証フォーム
        "input[type='text'][name*='auth']"          # 認証入力フィールド
    ]
    _WIDGET_SELECTORS = [
        '.karte-widget__container',
        '[class*="_reception-Skin"]',
        '[class*="_reception-MinimumWidget"]',
        '[id^="karte-"]'
    ]
    # --- セレクタ定義 終了 ---

    # --- エラータイプ定数 ---
    ET_INIT_FAILED = 'initialization_failed'
    ET_BROWSER_START_FAILED = 'browser_start_failed' # startメソッド内で使用する可能性

    ET_LOGIN_GENERAL = 'login_general_error'
    ET_LOGIN_ROBOT_DETECTED = 'login_robot_detected'
    ET_LOGIN_DASHBOARD_TIMEOUT = 'login_dashboard_timeout'
    ET_LOGIN_EXCEPTION = 'login_exception'
    ET_SALON_SELECT_FAILED = 'salon_select_failed'
    ET_SALON_NOT_FOUND = 'salon_not_found'

    ET_NAV_GENERAL = 'navigation_general_error'
    ET_NAV_KEISAI_KANRI_FAILED = 'navigation_keisai_kanri_failed'
    ET_NAV_ROBOT_DETECTED = 'navigation_robot_detected' # 掲載管理、ブログ管理、新規投稿ページ共通
    ET_NAV_BLOG_FAILED = 'navigation_blog_failed'
    ET_NAV_NEW_POST_FAILED = 'navigation_new_post_failed'
    ET_NAV_FORM_VISIBLE_TIMEOUT = 'navigation_form_visible_timeout'
    ET_NAV_UNEXPECTED_ERROR = 'navigation_unexpected_error'
    ET_NAV_MAX_RETRIES_REACHED = 'navigation_max_retries_reached'

    ET_POST_BLOG_GENERAL = 'post_blog_general_error'
    ET_POST_STYLIST_SELECTION_FAILED = 'post_stylist_selection_failed'
    ET_POST_CONTENT_INIT_FAILED = 'post_content_initialization_failed'
    ET_POST_CONTENT_REINIT_FAILED = 'post_content_reinitialization_failed'
    ET_POST_IMAGE_UPLOAD_FAILED = 'post_image_upload_failed' # 追加 (post_blog内で使用検討)
    ET_POST_FINAL_CONTENT_SETTING_FAILED = 'post_final_content_setting_failed'
    ET_POST_LEGACY_CONTENT_SETTING_FAILED = 'post_legacy_content_setting_failed'
    ET_POST_COUPON_SELECTION_FAILED = 'post_coupon_selection_failed'
    ET_POST_CONFIRM_CLICK_FAILED = 'post_confirm_button_click_failed'
    ET_POST_CONFIRM_PAGE_TIMEOUT = 'post_confirmation_page_timeout'
    ET_POST_ROBOT_DETECTED_ON_CONFIRM = 'post_robot_detected_on_confirm'
    ET_POST_UNREFLECT_CLICK_FAILED = 'post_unreflect_button_click_failed'
    ET_POST_BACK_BUTTON_CLICK_FAILED = 'post_back_button_click_failed' # 追加 (post_blog内で使用検討)
    ET_POST_COMPLETE_TIMEOUT = 'post_complete_timeout' # 追加 (post_blog内で使用検討)
    ET_POST_UNEXPECTED_ERROR = 'post_blog_unexpected_error'
    
    ET_EXEC_POST_UNKNOWN_ERROR = 'execute_post_unknown_error'

    # (select_stylist, select_coupon 用に追加予定)
    ET_STYLIST_SELECT_ELEMENT_NOT_FOUND = 'stylist_select_element_not_found'
    ET_STYLIST_SELECT_OPTION_FAILED = 'stylist_select_option_failed'
    ET_STYLIST_SELECT_UNEXPECTED = 'stylist_select_unexpected_error'

    ET_COUPON_BTN_NOT_VISIBLE = 'coupon_button_not_visible'
    ET_COUPON_BTN_CLICK_FAILED = 'coupon_button_click_failed'
    ET_COUPON_MODAL_TIMEOUT = 'coupon_modal_timeout'
    ET_COUPON_SELECTION_ITEM_NOT_FOUND = 'coupon_selection_item_not_found'
    ET_COUPON_SETTING_BTN_CLICK_FAILED = 'coupon_setting_button_click_failed'
    ET_COUPON_MODAL_CLOSE_TIMEOUT = 'coupon_modal_close_timeout'
    ET_COUPON_SELECTION_UNEXPECTED = 'coupon_selection_unexpected_error'
    # --- エラータイプ定数 終了 ---

    def __init__(self, screenshot_folder_path, salon_name=None, salon_id=None, headless=True, slow_mo=100):
        """
        初期化メソッド
        
        Args:
            screenshot_folder_path (str): スクリーンショットの保存先フォルダパス。
            salon_name (str, optional): 選択すべきサロン名。複数サロンがある場合に使用。
            salon_id (str, optional): 選択すべきサロンID。複数サロンがある場合に優先的に使用。
            headless (bool): ヘッドレスモードで実行するかどうか。デフォルトはTrue（ヘッドレスモード）。
            slow_mo (int): アクションの間に入れる遅延時間（ミリ秒）。デバッグ時に視認性を高めるため。
        """
        self.screenshot_folder_path = screenshot_folder_path
        self.salon_name = salon_name
        self.salon_id = salon_id
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser = None
        self.page = None
        self.login_url = self._LOGIN_URL # 定数を使用
        self.default_timeout = 180000
        self.max_retries = 3

    def start(self):
        """Playwrightとブラウザを起動（自動化隠蔽強化版）"""
        try:
            self.playwright = sync_playwright().start()
            
            # Firefox用に起動引数を一旦空にする
            launch_args = []

            self.browser = self.playwright.firefox.launch( # chromium から firefox に変更
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=launch_args,
                timeout=90000 # 起動タイムアウトは維持
            )
            
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0", # FirefoxのUser-Agentに変更
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                permissions=['geolocation']
            )
            
            # JavaScript実行前の初期設定（webdriver偽装は残す）
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            # Firefoxでの効果は不明だが、他の偽装も一旦残して試す
            context.add_init_script("""
                // プラグイン情報の偽装
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3], // ダミーのプラグイン配列
                });
                // 言語設定の偽装 (コンテキスト設定と合わせる)
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ja-JP', 'ja'],
                });
                // WebGL ベンダーとレンダラー情報 (一般的なものに偽装)
                try {
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) { return 'Mozilla'; } // Firefox向けに調整
                        if (parameter === 37446) { return 'Mozilla'; } // Firefox向けに調整
                        return getParameter.call(this, parameter);
                    };
                } catch (e) { console.error('WebGL spoofing failed:', e); }
            """)

            self.page = context.new_page()
            self.page.set_default_timeout(self.default_timeout)
            
            logger.info(f"ブラウザを起動しました（自動化隠蔽強化）。タイムアウト: {self.default_timeout}ms, スロー設定: {self.slow_mo}ms")
            
            return True
        except Exception as e:
            logger.error(f"ブラウザの起動に失敗しました: {e}", exc_info=True)
            self.close()
            return False

    def close(self):
        """ブラウザとPlaywrightを終了"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"ブラウザの終了に失敗しました: {e}")

    def is_robot_detection_present(self):
        """
        ロボット検出が存在するかを確認する
        
        Returns:
            bool: ロボット検出が存在する場合はTrue、それ以外はFalse
        """
        current_url = self.page.url
        page_title = self.page.title()
        
        # ブログ投稿関連の確認ページはロボット認証の対象外
        if '/blog/blog/confirm' in current_url:
            logger.info(f"ブログ投稿確認ページはロボット認証の対象外です: {current_url}")
            return False
            
        # 投稿関連のページはロボット認証の対象外
        if '/blog/blog/' in current_url and ('確認' in page_title or 'confirm' in current_url.lower()):
            logger.info(f"ブログ関連ページはロボット認証の対象外です: {current_url}, タイトル: {page_title}")
            return False
        
        # URLやタイトルの検査
        auth_keywords = ['認証', 'verification', 'captcha', 'robot']
        if any(keyword in current_url.lower() or keyword in page_title.lower() for keyword in auth_keywords):
            logger.warning(f"認証関連キーワードが検出されました: URL={current_url}, Title={page_title}")
            # ログイン関連ページでない場合は詳細チェック
            if not ('/login' in current_url or '/CLP/login' in current_url):
                logger.info(f"ログイン関連ページではないため、詳細な確認を行います: {current_url}")
                return self._check_detailed_robot_detection()
            return True
            
        # 画像認証というテキストがページ内に存在するか
        return self._check_detailed_robot_detection()
        
    def _check_detailed_robot_detection(self):
        """
        ページ内の要素を詳細に確認し、ロボット認証が存在するか判定する
        
        Returns:
            bool: ロボット認証が存在する場合はTrue、それ以外はFalse
        """
        try:
            has_image_auth = self.page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('th, td, div, p, span, label, h1, h2, h3, h4, h5, h6');
                    for (const el of elements) {
                        if (el.textContent && (
                            el.textContent.includes('画像認証') || 
                            el.textContent.includes('認証画像') || 
                            el.textContent.includes('画像を選択') ||
                            el.textContent.includes('画像を選んでください')
                        )) {
                            return true;
                        }
                    }
                    // reCAPTCHAや他の典型的な認証要素をチェック
                    if (document.querySelector('.g-recaptcha') ||
                        document.querySelector('[data-sitekey]') ||
                        document.querySelector('iframe[src*="recaptcha"]') ||
                        document.querySelector('iframe[src*="captcha"]')) {
                        return true;
                    }
                    return false;
                }
            """)
            
            if has_image_auth:
                logger.warning("テキスト「画像認証」またはreCAPTCHA関連要素が検出されました")
                return True
            return False
        except Exception as e:
            logger.error(f"ロボット認証の詳細チェック中にエラーが発生しました: {e}")
            return False
        
        # 認証フォーム要素の存在チェック
        critical_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='captcha']",
            "div.g-recaptcha",
            "form[action*='auth']",
            "img[alt*='認証']",
            "input[name*='captcha']"
        ]
        
        for selector in critical_selectors:
            try:
                if self.page.query_selector(selector):
                    logger.warning(f"ロボット認証要素が検出されました: {selector}")
                    return True
            except Exception:
                continue
                
        # ログイン画面の場合は認証と判断しない
        try:
            login_indicators = [
                "input[type='password']",
                "button[type='submit']",
                "input[type='submit']"
            ]
            
            # ログイン関連のテキストを確認
            login_texts = self.page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('th, td, div, p, span, label, h1, h2, h3, h4, h5, h6');
                    for (const el of elements) {
                        if (el.textContent && (
                            el.textContent.includes('ログイン') || 
                            el.textContent.includes('サインイン') || 
                            el.textContent.includes('ユーザーID') ||
                            el.textContent.includes('パスワード')
                        )) {
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            # ログイン関連の要素があり、認証関連の要素がない場合は通常のログイン画面と判断
            if login_texts and any(self.page.query_selector(selector) for selector in login_indicators):
                logger.info("通常のログイン画面と判断します")
                return False
        except Exception as e:
            logger.error(f"ログイン画面検証中のエラー: {e}")
            
        return False
            
    def is_salon_list_page(self):
        """
        現在のページがサロン一覧ページかどうかを確認する
        
        Returns:
            bool: サロン一覧ページの場合はTrue、それ以外はFalse
        """
        try:
            # サロン一覧テーブルの存在を確認
            salon_table = self.page.query_selector(self._SALON_LIST_TABLE)
            if salon_table:
                logger.info("サロン一覧ページが検出されました")
                return True
            return False
        except Exception as e:
            logger.error(f"サロン一覧ページの検出中にエラーが発生しました: {e}")
            return False
            
    def select_salon(self):
        """
        サロン一覧ページからサロンを選択する。サロンIDを優先的に使用し、およびサロン名を使用する。
        
        Returns:
            dict: 処理結果を含む辞書
                - success (bool): 成功したかどうか
                - message (str): 処理結果のメッセージ
                - screenshot_path (str): スクリーンショットのパス
                - error_type (str): エラーの種類
        """
        default_success_result = {
            'success': True, 'message': 'サロンの選択に成功しました。', 'screenshot_path': None, 'error_type': None
        }
        default_failure_result = {
            'success': False, 'message': 'サロンの選択に失敗しました。', 'screenshot_path': None, 'error_type': self.ET_SALON_SELECT_FAILED
        }
        
        # サロンIDとサロン名の両方がない場合はエラー
        if not self.salon_id and not self.salon_name:
            logger.error("サロンIDまたはサロン名が指定されていません")
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_id_name_not_specified_")
            return {**default_failure_result, 
                    'message': "サロンIDまたはサロン名が指定されていません。", 
                    'screenshot_path': ss_path, 
                    'error_type': self.ET_SALON_NOT_FOUND}
        
        try:
            # サロン一覧の行を取得
            salon_rows = self.page.query_selector_all(self._SALON_LIST_ROW)
            if not salon_rows:
                logger.error("サロン一覧の行が見つかりませんでした")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_rows_not_found_")
                return {**default_failure_result, 
                        'message': "サロン一覧の行が見つかりませんでした。", 
                        'screenshot_path': ss_path}
            
            # 各行をチェックして一致するサロンを探す
            found = False
            for row in salon_rows:
                # サロンIDを取得
                salon_id_cell = row.query_selector("td.mod_center")
                if not salon_id_cell:
                    continue
                
                salon_id_text = salon_id_cell.text_content().strip()
                
                # サロン名セルを取得
                name_cell = row.query_selector(self._SALON_LIST_NAME_CELL)
                if not name_cell:
                    continue
                    
                # サロン名のリンクを取得
                salon_link = name_cell.query_selector("a")
                if not salon_link:
                    continue
                
                # リンクのID属性を取得
                link_id = salon_link.get_attribute("id")
                
                # リンクのテキストを取得
                link_text = salon_link.text_content().strip()
                logger.info(f"サロン情報を確認: ID={salon_id_text or link_id}, 名前={link_text}")
                
                # サロンIDが一致する場合（最優先）
                if self.salon_id and (self.salon_id == salon_id_text or self.salon_id == link_id):
                    logger.info(f"サロンID '{self.salon_id}' が一致するサロンが見つかりました: {link_text}")
                    salon_link.click()
                    found = True
                    break
                # サロン名が一致する場合（次候補）
                elif self.salon_name and (self.salon_name in link_text or link_text in self.salon_name):
                    logger.info(f"サロン名 '{self.salon_name}' が一致するサロンが見つかりました: {link_text}")
                    salon_link.click()
                    found = True
                    break
            
            if not found:
                # エラーメッセージの設定
                error_message = ""
                if self.salon_id and self.salon_name:
                    error_message = f"指定されたサロンID '{self.salon_id}' またはサロン名 '{self.salon_name}' に一致するサロンが見つかりませんでした。"
                elif self.salon_id:
                    error_message = f"指定されたサロンID '{self.salon_id}' に一致するサロンが見つかりませんでした。"
                else:
                    error_message = f"指定されたサロン名 '{self.salon_name}' に一致するサロンが見つかりませんでした。"
                
                logger.error(error_message)
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_not_found_")
                return {**default_failure_result, 
                        'message': error_message, 
                        'screenshot_path': ss_path, 
                        'error_type': self.ET_SALON_NOT_FOUND}
            
            # クリック後、ページ遷移の完了を待つ
            time.sleep(2)  # 初期の待機
            
            # ダッシュボードの表示を待機
            try:
                self.page.wait_for_selector(self._DASHBOARD_GLOBAL_NAVI, timeout=self.default_timeout, state="visible")
                logger.info("サロン選択後のダッシュボード表示を確認しました")
                return default_success_result
            except TimeoutError:
                logger.error("サロン選択後のダッシュボード表示がタイムアウトしました")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_select_dashboard_timeout_")
                return {**default_failure_result, 
                        'message': "サロン選択後のダッシュボード表示がタイムアウトしました。", 
                        'screenshot_path': ss_path}
                
        except Exception as e:
            logger.error(f"サロン選択中に予期せぬエラーが発生しました: {e}", exc_info=True)
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_select_exception_")
            return {**default_failure_result, 
                    'message': f"サロン選択中に予期せぬエラーが発生しました: {str(e)}", 
                    'screenshot_path': ss_path}

    def login(self, user_id, password):
        """
        サロンボードにログインする
        
        Args:
            user_id (str): サロンボードのユーザーID
            password (str): サロンボードのパスワード
            
        Returns:
            dict: ログイン結果 (success: bool, message: str, screenshot_path: str|None, error_type: str|None, robot_detected: bool)
        """
        default_success_result = {
            'success': True, 'message': 'ログインに成功しました。', 'screenshot_path': None, 
            'error_type': None, 'robot_detected': False
        }
        default_failure_result = {
            'success': False, 'message': 'ログインに失敗しました。', 'screenshot_path': None, 
            'error_type': self.ET_LOGIN_GENERAL, 'robot_detected': False
        }

        try:
            # JavaScript内のセレクタも定数を使うように変更 (f-stringを使用)
            # ウィジェット非表示用JS
            hide_widgets_js = f"""
                (function() {{
                    function hideKarteWidgets() {{
                        const selectors = {json.dumps(self._WIDGET_SELECTORS)}; // 定数リストを使用
                        for (const selector of selectors) {{
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {{
                                console.log('Hiding karte widget:', el);
                                el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.opacity = '0';
                            }}
                        }}
                    }}
                    setTimeout(hideKarteWidgets, 500);
                    const observer = new MutationObserver((mutations) => {{ hideKarteWidgets(); }});
                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', () => {{ observer.observe(document.body, {{ childList: true, subtree: true }}); hideKarteWidgets(); }});
                    }} else {{ observer.observe(document.body, {{ childList: true, subtree: true }}); hideKarteWidgets(); }}
                }})();
            """
            self.page.add_init_script(hide_widgets_js)
            
            logger.info(f"ログインページ({self.login_url})に移動します")
            self.page.goto(self.login_url, wait_until="networkidle")
            logger.info("ログインページの読み込みが完了しました")
            
            time.sleep(2)
            
            # ウィジェット強制非表示
            try:
                widget_exists = False
                # 定数リストを使用
                for selector in self._WIDGET_SELECTORS:
                    try:
                        element = self.page.query_selector(selector)
                        if element:
                            widget_exists = True
                            logger.info(f"ウィジェット '{selector}' を検出しました")
                            break
                    except Exception as selector_err:
                        logger.debug(f"セレクタ '{selector}' のチェック中にエラー: {selector_err}")
                        continue
                
                if widget_exists:
                    logger.info("ウィジェットが検出されました。非表示にします。")
                    # JS内のセレクタも定数を使う (f-string)
                    force_hide_js = f"""
                        const selectors = {json.dumps(self._WIDGET_SELECTORS)};
                        for (const selector of selectors) {{
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {{
                                console.log('Force hiding widget:', el);
                                el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.opacity = '0';
                            }}
                        }}
                    """
                    self.page.evaluate(force_hide_js)
                    logger.info("ウィジェットの強制非表示を実行しました")
                else:
                    logger.info("ウィジェットは検出されませんでした。非表示処理はスキップします。")
            except Exception as e:
                logger.warning(f"ウィジェットの強制非表示中にエラー: {e}")
            
            if self.is_robot_detection_present():
                logger.error("ログイン時にロボット認証が検出されました。処理を中断します。")
                # self.page.screenshot(path="login_image_auth_detected.png")
                # return False
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_robot_initial_")
                return {**default_failure_result,
                        'message': "ログインページ読み込み時にロボット認証が検出されました。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_LOGIN_ROBOT_DETECTED,
                        'robot_detected': True}
            
            logger.info("入力フィールドを検索します")
            
            # JavaScriptログインスクリプト (セレクタを定数化)
            js_login_script = f"""
            (function() {{
                try {{
                    const userIdInput = document.querySelector("{self._LOGIN_USER_ID_INPUT}");
                    const pwInput = document.querySelector("{self._LOGIN_PASSWORD_INPUT_PRIMARY}") || document.querySelector("{self._LOGIN_PASSWORD_INPUT_ALT}");
                    if (!userIdInput || !pwInput) {{ console.error('Login inputs not found'); return false; }}
                    userIdInput.value = "{user_id}"; pwInput.value = "{password}";
                    userIdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    pwInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    const loginForm = document.querySelector("{self._LOGIN_FORM}");
                    const loginButton = document.querySelector("{self._LOGIN_BUTTON_PRIMARY}") || document.querySelector("{self._LOGIN_BUTTON_ALT}");
                    if (loginButton) {{
                        console.log('Clicking login button via JS'); loginButton.click();
                        setTimeout(() => {{ try {{ loginButton.click(); }} catch (e) {{}} }}, 500);
                    }}
                    if (loginForm) {{
                        setTimeout(() => {{ try {{ console.log('Submitting form via JS'); loginForm.submit(); }} catch (e) {{}} }}, 1000);
                    }}
                    return true;
                }} catch (e) {{ console.error('JS login error:', e); return false; }}
            }})()
            """
            
            logger.info("JavaScriptを使用してログイン処理を実行します")
            login_result = self.page.evaluate(js_login_script)
            
            # ログインボタンクリック直後に画像認証の確認
            time.sleep(2)  # 認証画面表示のための短い待機
            if self.is_robot_detection_present():
                logger.error("ログインボタンクリック後に画像認証が検出されました。処理を中断します。")
                # self.page.screenshot(path="login_image_auth_detected.png")
                # return False
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_robot_after_js_click_")
                return {**default_failure_result,
                        'message': "JavaScriptによるログインボタンクリック後にロボット認証が検出されました。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_LOGIN_ROBOT_DETECTED,
                        'robot_detected': True}
            
            if not login_result:
                logger.error("JavaScriptによるログイン処理に失敗しました")
                # 従来のスクリーンショット処理はtake_screenshotに任せる
                
                logger.info("通常の方法でログインを試みます")
                
                # 定数を使用
                logger.info(f"ユーザーID '{user_id}' を入力します")
                id_input_success = self._set_input_value_by_js(self._LOGIN_USER_ID_INPUT, user_id)
                if not id_input_success:
                    logger.error("ユーザーID入力に失敗しました")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_id_input_failed_")
                    return {**default_failure_result,
                            'message': "ユーザーIDの入力に失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_LOGIN_GENERAL} # より具体的なエラータイプを検討しても良い
                
                logger.info("パスワードを入力します")
                password_input_success = self._set_input_value_by_js(self._LOGIN_PASSWORD_INPUT_PRIMARY, password)
                if not password_input_success:
                    logger.info("代替セレクタでパスワード入力を試みます")
                    password_input_success = self._set_input_value_by_js(self._LOGIN_PASSWORD_INPUT_ALT, password)
                if not password_input_success:
                    logger.error("パスワード入力に失敗しました")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_pw_input_failed_")
                    return {**default_failure_result,
                            'message': "パスワードの入力に失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_LOGIN_GENERAL} # より具体的なエラータイプを検討しても良い
                
                time.sleep(1)
                logger.info("ログインボタンをクリックします")
                
                # 定数を使用
                login_click_success = self._click_element(self._LOGIN_BUTTON_PRIMARY)
                if not login_click_success:
                    logger.info("代替セレクタでログインボタンクリックを試みます")
                    login_click_success = self._click_element(self._LOGIN_BUTTON_ALT)
                if not login_click_success:
                    logger.info("フォーム送信を試みます")
                    form_submit_success = self._submit_form_by_js(self._LOGIN_FORM)
                    if not form_submit_success:
                        logger.error("ログインボタンのクリックに失敗しました")
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_btn_click_failed_")
                        return {**default_failure_result,
                                'message': "ログインボタンのクリックまたはフォーム送信に失敗しました。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_LOGIN_GENERAL} # より具体的なエラータイプを検討しても良い
            else:
                logger.info("JavaScriptによるログイン処理が成功しました")
            
            # ダッシュボード表示待機前にもう一度認証確認
            time.sleep(1)
            if self.is_robot_detection_present():
                logger.error("ログイン処理後に画像認証が検出されました。処理を中断します。")
                # self.page.screenshot(path="post_login_auth_detected.png")
                # return False
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_robot_post_login_")
                return {**default_failure_result,
                        'message': "ログイン処理完了後にロボット認証が検出されました。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_LOGIN_ROBOT_DETECTED,
                        'robot_detected': True}
            
            logger.info("ダッシュボードまたはサロン一覧の表示を待機します...")
            
            # まずダッシュボードが表示されるか確認
            try:
                # 定数を使用
                self.page.wait_for_selector(self._DASHBOARD_GLOBAL_NAVI, timeout=10000, state="visible")
                logger.info("ダッシュボードの表示を確認しました")
                
            except TimeoutError:
                logger.info("ダッシュボードが表示されませんでした。サロン一覧ページの確認を行います。")
                
                # ロボット認証の確認
                if self.is_robot_detection_present():
                    logger.error("ダッシュボード表示待機中に画像認証が検出されました。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "dash_timeout_robot_")
                    return {**default_failure_result, 
                            'message': "ダッシュボード表示待機中にロボット認証が検出されました。", 
                            'screenshot_path': ss_path, 
                            'error_type': self.ET_LOGIN_ROBOT_DETECTED, 
                            'robot_detected': True}
                
                # サロン一覧ページか確認
                if self.is_salon_list_page():
                    logger.info("サロン一覧ページが表示されました。サロンの選択を行います。")
                    
                    # サロン選択を実行（サロンIDまたはサロン名を使用）
                    if self.salon_id or self.salon_name:
                        if self.salon_id:
                            logger.info(f"サロンID '{self.salon_id}' に一致するサロンを選択します")
                        else:
                            logger.info(f"サロン名 '{self.salon_name}' に一致するサロンを選択します")
                            
                        salon_select_result = self.select_salon()
                        
                        if not salon_select_result['success']:
                            logger.error("サロンの選択に失敗しました")
                            return salon_select_result  # サロン選択のエラー結果をそのまま返す
                        
                        logger.info("サロンの選択に成功しました")
                    else:
                        logger.error("複数サロンがありますが、サロンIDまたはサロン名が指定されていません")
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "salon_id_name_not_specified_")
                        return {**default_failure_result, 
                                'message': "複数サロンがありますが、サロンIDまたはサロン名が指定されていません。", 
                                'screenshot_path': ss_path, 
                                'error_type': self.ET_SALON_NOT_FOUND}
                else:
                    # ダッシュボードでもサロン一覧でもない場合はエラー
                    current_url = self.page.url
                    current_title = self.page.title()
                    logger.error(f"ログイン後に予期しないページが表示されました。現在のURL: {current_url}, タイトル: {current_title}")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_unexpected_page_")
                    return {**default_failure_result, 
                            'message': f"ログイン後に予期しないページが表示されました。現在のURL: {current_url}, Title: {current_title}", 
                            'screenshot_path': ss_path, 
                            'error_type': self.ET_LOGIN_DASHBOARD_TIMEOUT}
                
            if self.is_robot_detection_present():
                logger.error("ログイン後にロボット認証が検出されました。処理を中断します。")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "final_robot_")
                return {**default_failure_result, 
                        'message': "ログイン成功後にロボット認証が検出されました。", 
                        'screenshot_path': ss_path, 
                        'error_type': self.ET_LOGIN_ROBOT_DETECTED, 
                        'robot_detected': True}
                
            logger.info("サロンボードへのログインに成功しました")
            return default_success_result # 修正点: True から default_success_result へ変更
            
        except Exception as e:
            logger.error(f"ログイン処理中にエラーが発生しました: {e}", exc_info=True)
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "login_exception_")
            return {**default_failure_result, 
                    'message': f"ログイン処理中に予期せぬエラーが発生しました: {str(e)}", 
                    'screenshot_path': ss_path, 
                    'error_type': self.ET_LOGIN_EXCEPTION}
            
    def _set_input_value_by_js(self, selector, value):
        """JavaScriptを使用して入力フィールドに値を設定する内部メソッド"""
        try:
            if not self.page.query_selector(selector):
                logger.warning(f"セレクタ '{selector}' が見つかりません")
                return False
            # セレクタ内のダブルクォートをエスケープ
            escaped_selector = selector.replace('"', '\\\\"')
            js_script = f"""
            (function() {{
                try {{
                    var el = document.querySelector("{escaped_selector}");
                    if (el) {{
                        el.value = "{value}";
                        var event = new Event('input', {{ bubbles: true }});
                        el.dispatchEvent(event);
                        return true;
                    }}
                    return false;
                }} catch(e) {{
                    console.error('値設定エラー:', e);
                    return false;
                }}
            }})();
            """
            result = self.page.evaluate(js_script)
            if result:
                logger.info(f"JavaScriptを使用して値を設定しました: {selector}")
                return True
            return False
        except Exception as e:
            logger.warning(f"JavaScriptによる値設定中にエラー: {e}")
            return False
            
    def _set_cursor_at_end(self):
        """nicEditエディタのカーソルを最後に移動する"""
        try:
            js_script = """
            (function() {
                try {
                    var editorInstance = nicEditors.findEditor('blogContents');
                    if (editorInstance) {
                        var editor = editorInstance.elm;
                        // カーソルを最後に移動
                        var range = document.createRange();
                        range.selectNodeContents(editor);
                        range.collapse(false); // false = 末尾に移動
                        var selection = window.getSelection();
                        selection.removeAllRanges();
                        selection.addRange(range);
                        editor.focus();
                        console.log('カーソルをエディタの最後に移動しました');
                        return true;
                    }
                    console.error('nicEditエディタインスタンスが見つかりません');
                    return false;
                } catch(e) {
                    console.error('カーソル制御エラー:', e);
                    return false;
                }
            })();
            """
            result = self.page.evaluate(js_script)
            if result:
                logger.info("nicEditエディタのカーソルを最後に移動しました")
            else:
                logger.warning("nicEditエディタのカーソル移動に失敗しました")
            return result
        except Exception as e:
            logger.error(f"カーソル制御中にエラーが発生しました: {e}", exc_info=True)
            return False
            
    def _ensure_cursor_at_end(self, max_retries=3):
        """カーソルが確実に最後に位置するように複数回試行する強化メソッド"""
        try:
            # まず線形テキストを挿入してカーソル位置を確実に最後にする
            js_script = """
            (function() {
                try {
                    var editorInstance = nicEditors.findEditor('blogContents');
                    if (editorInstance) {
                        var editor = editorInstance.elm;
                        var selection = window.getSelection();
                        
                        // まずカーソルを最後に移動
                        var range = document.createRange();
                        range.selectNodeContents(editor);
                        range.collapse(false);
                        selection.removeAllRanges();
                        selection.addRange(range);
                        editor.focus();
                        
                        // 安定性向上のために、急ぎすぎる操作を避ける
                        setTimeout(function() {
                            // 必要ならば非表示のマーカーテキストを挿入してカーソル位置を安定させる
                            var div = document.createElement('div');
                            div.appendChild(document.createTextNode('\u200B')); // ゼロ幅スペース
                            
                            // 現在のカーソル位置に挿入
                            range = selection.getRangeAt(0);
                            range.insertNode(div);
                            
                            // 後続の操作のために、再度カーソルを位置づけ
                            range = document.createRange();
                            range.selectNodeContents(editor);
                            range.collapse(false);
                            selection.removeAllRanges();
                            selection.addRange(range);
                            
                            console.log('強化されたカーソル設定が成功しました');
                        }, 100);
                        
                        return true;
                    }
                    console.error('nicEditエディタインスタンスが見つかりません');
                    return false;
                } catch(e) {
                    console.error('強化カーソル制御エラー:', e);
                    return false;
                }
            })();
            """
            
            success = False
            for attempt in range(max_retries):
                try:
                    logger.info(f"強化カーソル制御: 試行 {attempt+1}/{max_retries}")
                    result = self.page.evaluate(js_script)
                    
                    if result:
                        # JavaScriptが実行される時間を確保
                        time.sleep(0.3)
                        success = True
                        logger.info("強化カーソル制御が成功しました")
                        break
                    else:
                        logger.warning(f"強化カーソル制御の試行 {attempt+1} が失敗しました")
                        # 失敗した場合は少し待機してから再試行
                        time.sleep(0.5)
                except Exception as e:
                    logger.error(f"強化カーソル制御の試行 {attempt+1} で例外発生: {e}")
                    time.sleep(0.5)
            
            return success
        except Exception as e:
            logger.error(f"強化カーソル制御でエラーが発生しました: {e}", exc_info=True)
            return False
    def _click_element(self, selector: str, timeout: int = 10000, scroll_if_needed: bool = True) -> bool:
        """指定されたセレクタの要素をクリックする (Locator優先、JSフォールバック付き)"""
        try:
            element = self.page.locator(selector)
            
            # 要素が存在するか短時間で確認
            try:
                element.wait_for(state="attached", timeout=timeout // 2) # attached: DOMに存在するか
            except TimeoutError:
                logger.warning(f"クリック対象の要素が見つかりません: {selector}")
                return False
            
            # スクロールして表示
            if scroll_if_needed:
                try:
                    element.scroll_into_view_if_needed(timeout=timeout // 4)
                    time.sleep(0.5) # スクロール安定待ち
                except Exception as scroll_err:
                     logger.warning(f"要素表示のためのスクロール中にエラー: {scroll_err} (処理は続行)")
            
            # Playwrightのclickを試行
            try:
                element.click(timeout=timeout)
                logger.info(f"要素をクリックしました (Locator): {selector}")
                return True
            except Exception as click_err:
                logger.warning(f"Locatorクリックに失敗: {click_err}。JavaScriptクリックを試みます。")
                # JavaScriptでクリックするフォールバック
                try:
                    element.evaluate("node => node.click()")
                    logger.info(f"要素をクリックしました (JavaScript): {selector}")
                    return True
                except Exception as js_click_err:
                    logger.error(f"JavaScriptクリックにも失敗: {js_click_err}")
                    return False
        except Exception as e:
            logger.error(f"要素クリック処理中に予期せぬエラー ({selector}): {e}", exc_info=True)
            return False

    def _click_and_wait_navigation(self, click_selector: str, click_timeout: int = 10000, wait_timeout: int = 60000) -> bool:
        """要素をクリックし、ページのナビゲーション完了 (networkidle) を待つ"""
        logger.info(f"要素をクリックしてナビゲーションを待ちます: {click_selector}")
        
        # 要素をクリック
        if not self._click_element(click_selector, timeout=click_timeout):
            # _click_element 内でエラーログ出力済み
            return False
            
        # ネットワークアイドル状態を待機
        try:
            logger.info(f"クリック後のネットワークアイドル状態を待機します (最大{wait_timeout}ms)")
            self.page.wait_for_load_state("networkidle", timeout=wait_timeout)
            logger.info("ネットワークアイドル状態に達しました。ナビゲーション完了とみなします。")
            return True
        except TimeoutError:
            logger.error(f"ネットワークアイドル状態への移行がタイムアウトしました ({wait_timeout}ms)。ナビゲーション失敗の可能性があります。")
            # 失敗してもページ遷移している可能性はあるため、呼び出し元でリカバリーを試みることも考慮。
            # ここでは明確に失敗として False を返す。
            return False
        except Exception as e:
             logger.error(f"ネットワークアイドル待機中にエラー: {e}", exc_info=True)
             return False
            
    def _submit_form_by_js(self, form_selector):
        """JavaScriptを使用してフォームを送信する内部メソッド"""
        try:
            # セレクタ内のダブルクォートをエスケープ
            escaped_selector = form_selector.replace('"', '\\\\"')
            js_script = f"""
            (function() {{
                var form = document.querySelector("{escaped_selector}");
                if (form) {{ form.submit(); return true; }}
                return false;
            }})()
            """
            result = self.page.evaluate(js_script)
            if result:
                logger.info(f"JavaScriptを使用してフォームを送信しました: {form_selector}")
                return True
            return False
        except Exception as e:
            logger.warning(f"JavaScriptによるフォーム送信中にエラー: {e}")
            return False

    def navigate_to_blog_post_page(self):
        """ブログ投稿ページに移動する"""
        default_success_result = {
            'success': True, 'message': 'ブログ投稿ページへの移動に成功しました。', 'screenshot_path': None, 'error_type': None
        }
        default_failure_result = {
            'success': False, 'message': 'ブログ投稿ページへの移動に失敗しました。', 'screenshot_path': None, 'error_type': self.ET_NAV_GENERAL
        }

        for attempt in range(self.max_retries):
            try:
                logger.info(f"ブログ投稿ページへの移動を試行中... (試行 {attempt+1}/{self.max_retries})")
                
                # --- 1. 「掲載管理」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_KEISAI_KANRI):
                    logger.error("「掲載管理」へのナビゲーションに失敗しました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_keisai_")
                        return {**default_failure_result, 
                                'message': "「掲載管理」へのナビゲーションに失敗しました。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_NAV_KEISAI_KANRI_FAILED}
                
                logger.info("掲載管理ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("掲載管理ページでロボット認証が検出されました。処理を中断します。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_keisai_robot_")
                    return {**default_failure_result, 
                            'message': "掲載管理ページでロボット認証が検出されました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_NAV_ROBOT_DETECTED}

                # --- 2. 「ブログ」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_BLOG):
                    logger.error("「ブログ」管理ページへのナビゲーションに失敗しました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_blog_")
                        return {**default_failure_result, 
                                'message': "「ブログ」管理ページへのナビゲーションに失敗しました。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_NAV_BLOG_FAILED}
                
                logger.info("ブログ管理ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("ブログ管理ページでロボット認証が検出されました。処理を中断します。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_blog_robot_")
                    return {**default_failure_result, 
                            'message': "ブログ管理ページでロボット認証が検出されました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_NAV_ROBOT_DETECTED}

                # --- 3. 「新規投稿」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_NEW_POST):
                    logger.error("「新規投稿」ページへのナビゲーションに失敗しました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_newpost_")
                        return {**default_failure_result, 
                                'message': "「新規投稿」ページへのナビゲーションに失敗しました。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_NAV_NEW_POST_FAILED}
                
                logger.info("新規投稿ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("新規投稿ページでロボット認証が検出されました。処理を中断します。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_newpost_robot_")
                    return {**default_failure_result, 
                            'message': "新規投稿ページでロボット認証が検出されました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_NAV_ROBOT_DETECTED}

                # --- 4. ブログ投稿フォームの表示を確認 ---
                logger.info(f"ブログ投稿フォームの主要素 ({self._BLOG_FORM_STYLIST_SELECT}) を待機します")
                try:
                    self.page.wait_for_selector(self._BLOG_FORM_STYLIST_SELECT, state="visible", timeout=60000)
                    logger.info("ブログ投稿フォームの表示を確認しました。ナビゲーション成功。")
                    return default_success_result
                except TimeoutError:
                    logger.error("ブログ投稿フォームの表示確認がタイムアウトしました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        logger.error(f"ブログ投稿フォームの表示確認が{self.max_retries}回タイムアウトしました。")
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_form_timeout_")
                        return {**default_failure_result, 
                                'message': f"ブログ投稿フォームの表示確認が{self.max_retries}回タイムアウトしました。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_NAV_FORM_VISIBLE_TIMEOUT}

            except Exception as e:
                # 予期せぬエラー（クリック失敗、ネットワークエラー以外）
                logger.error(f"ナビゲーション中に予期せぬエラーが発生しました: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                    self._try_recover_and_wait() # 回復試行
                    continue
                else:
                    logger.error(f"ナビゲーション中に{self.max_retries}回予期せぬエラーが発生しました。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_exception_")
                    return {**default_failure_result, 
                            'message': f"ナビゲーション中に{self.max_retries}回予期せぬエラーが発生しました: {str(e)}",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_NAV_UNEXPECTED_ERROR}
        
        # ループが完了しても成功しなかった場合
        logger.error("最大再試行回数に達しましたが、ブログ投稿ページへの移動に失敗しました。")
        # この時点で最後に撮影されたスクリーンショットがあればそれを使うか、新たに撮影するか検討。
        # ここでは、ループ内で最後にエラーになった際の詳細なエラーメッセージとスクリーンショットが返されるはずなので、
        # ここで改めて default_failure_result を返す必要性は低いかもしれないが、念のため。
        # ただし、リトライロジックの中で具体的なエラーが返されているので、このパスには到達しづらい。
        final_ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "nav_max_retries_")
        return {**default_failure_result, 
                'message': "最大再試行回数に達しましたが、ブログ投稿ページへの移動に失敗しました。",
                'screenshot_path': final_ss_path, # ループ内の最後のエラーで撮れていればそれが優先される
                'error_type': self.ET_NAV_MAX_RETRIES_REACHED}

    def _try_recover_and_wait(self, wait_seconds=5):
        """エラー発生時にダッシュボードに戻る試行と待機を行う"""
        try:
            logger.info(f"エラー回復試行: ダッシュボードに戻り{wait_seconds}秒待機します...")
            self.page.goto(self._LOGIN_URL.replace("/login/", "/main/"), wait_until="networkidle", timeout=60000) # メインページへ
        except Exception as goto_err:
            logger.warning(f"エラー後のダッシュボードへの移動に失敗: {goto_err}")
        time.sleep(wait_seconds)

    def set_rich_text_content(self, content):
        """nicEditリッチテキストエディタにコンテンツを設定する"""
        try:
            # コンテンツをJavaScript文字列リテラル用にエスケープ
            escaped_content = json.dumps(content)[1:-1]

            # JavaScriptコードのテンプレート文字列
            # JavaScriptの { と } は {{ と }} でエスケープする
            js_script_template = """
(function() {{ // Escaped
    try {{     // Escaped
        var editorInstance = nicEditors.findEditor('blogContents');
        if (editorInstance) {{ // Escaped
            // {0} はプレースホルダーなのでエスケープしない
            editorInstance.setContent(`{0}`);
            return true;
        }} else {{            // Escaped
            console.error('nicEdit editor instance not found for blogContents');
            return false;
        }}                 // Escaped
    }} catch(e) {{        // Escaped
        console.error('nicEdit操作エラー:', e);
        return false;
    }}                 // Escaped
}})()                // Escaped
"""
            # .format() を使ってテンプレートにエスケープ済みコンテンツを挿入
            js_script = js_script_template.format(escaped_content)

            logger.debug("Executing nicEdit script...")
            result = self.page.evaluate(js_script)

            if result:
                logger.info("JavaScriptを使用してnicEditに内容を設定しました")
                return True
            else:
                # === 代替手段 ===
                logger.warning("JavaScriptを使用したnicEditへの内容設定に失敗。代替手段 (iframe fill) を試みます。")
                try:
                    iframe_selector = self._BLOG_FORM_NICEDIT_IFRAME
                    iframe = self.page.frame_locator(iframe_selector)
                    if iframe.count() > 0:
                        iframe.locator("body").fill(content)
                        logger.info("代替手段: iframe内のbodyに内容を設定しました (fill)")
                        return True
                    else:
                        # === さらに代替手段 ===
                        logger.warning(f"nicEditのiframe ({iframe_selector}) が見つかりません。さらに代替手段 (textarea fill) を試みます。")
                        try:
                            textarea_selector = self._BLOG_FORM_CONTENT_TEXTAREA
                            self.page.fill(textarea_selector, content)
                            logger.info(f"さらに代替手段: {textarea_selector} に内容を設定しました (textarea fill)")
                            return True
                        except Exception as textarea_err:
                            logger.error(f"さらに代替手段 (textarea fill) でのエラー: {textarea_err}", exc_info=True)
                            return False
                except Exception as iframe_err:
                    logger.error(f"代替手段 (iframe fill) でのエラー: {iframe_err}", exc_info=True)
                    return False

        except Exception as e:
            logger.error(f"set_rich_text_content全体でエラーが発生しました: {e}", exc_info=True)
            return False
            
    def append_rich_text_content(self, content):
        """nicEditリッチテキストエディタに既存のコンテンツに追加する"""
        try:
            # エスケープ処理
            escaped_content = json.dumps(content)[1:-1]
            
            # JavaScriptのテンプレート - 既存のコンテンツに追加
            js_script_template = """
(function() {{ // Escaped
try {{     // Escaped
    var editorInstance = nicEditors.findEditor('blogContents');
    if (editorInstance) {{ // Escaped
        var currentContent = editorInstance.getContent();
        editorInstance.setContent(currentContent + `{0}`);
        return true;
    }} else {{            // Escaped
        console.error('nicEdit editor instance not found for blogContents');
        return false;
    }}                 // Escaped
}} catch(e) {{        // Escaped
    console.error('nicEdit操作エラー:', e);
    return false;
}}                 // Escaped
}})()                // Escaped
"""
            js_script = js_script_template.format(escaped_content)
            
            logger.debug("Executing nicEdit append script...")
            result = self.page.evaluate(js_script)
            
            if result:
                logger.info("JavaScriptを使用してnicEditに内容を追加しました")
                return True
            else:
                # === 代替手段 ===
                logger.warning("JavaScriptを使用したnicEditへの内容追加に失敗。既存の内容を取得し、結合する代替手段を試みます。")
                try:
                    # 現在の内容を取得するスクリプト
                    get_content_script = """
(function() {
    try {
        var editorInstance = nicEditors.findEditor('blogContents');
        if (editorInstance) {
            return editorInstance.getContent();
        } else {
            return null;
        }
    } catch(e) {
        console.error('nicEdit内容取得エラー:', e);
        return null;
    }
})();
"""
                    current_content = self.page.evaluate(get_content_script)
                    if current_content is not None:
                        # 内容を結合して設定
                        return self.set_rich_text_content(current_content + content)
                    else:
                        logger.error("現在のエディタ内容の取得に失敗しました")
                        return False
                except Exception as get_err:
                    logger.error(f"代替手段での内容追加に失敗: {get_err}", exc_info=True)
                    return False
        except Exception as e:
            logger.error(f"append_rich_text_content全体でエラーが発生しました: {e}", exc_info=True)
            return False

    def upload_image(self, image_path, set_cursor_end=True):
        """画像をアップロードする
        
        Args:
            image_path (str): アップロードする画像のパス
            set_cursor_end (bool): カーソルを最後に設定するかどうか（デフォルトはTrue）
            
        Returns:
            dict: アップロード結果 (success: bool, message: str, screenshot_path: str|None, error_type: str|None)
        """
        default_success_result = {
            'success': True, 
            'message': f'画像 {image_path} のアップロードに成功しました。', 
            'screenshot_path': None, # 成功時は通常SS不要だが、念のためキーは用意
            'error_type': None
        }
        default_failure_result = {
            'success': False, 
            'message': f'画像 {image_path} のアップロードに失敗しました。', 
            'screenshot_path': None, 
            'error_type': self.ET_POST_IMAGE_UPLOAD_FAILED # デフォルトのエラータイプ
        }

        try:
            # カーソル位置を最後に設定してから画像をアップロード
            if set_cursor_end:
                logger.info("カーソル位置を最後に設定します")
                if not self._set_cursor_at_end(): # _set_cursor_at_end は bool を返す
                    logger.warning("カーソル位置の設定に失敗しました。画像が先頭に挿入される可能性があります。")
            
            # 定数を使用
            logger.info("画像アップロードボタンをクリックします")
            # self.page.click(self._BLOG_FORM_IMAGE_UPLOAD_BTN) # _click_element を使う方が堅牢
            if not self._click_element(self._BLOG_FORM_IMAGE_UPLOAD_BTN):
                logger.error("画像アップロードボタンのクリックに失敗しました。")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "img_upload_btn_click_failed_")
                return {**default_failure_result,
                        'message': f'画像アップロードボタンのクリックに失敗しました。',
                        'screenshot_path': ss_path,
                        'error_type': self.ET_POST_IMAGE_UPLOAD_FAILED}

            try:
                logger.info("画像アップロードモーダルの表示を待機します")
                # 定数を使用
                self.page.wait_for_selector(self._BLOG_FORM_IMAGE_MODAL, timeout=10000, state="visible") # state="visible"を追加
            except TimeoutError:
                logger.error("画像アップロードモーダルの表示がタイムアウトしました")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "img_modal_timeout_")
                return {**default_failure_result,
                        'message': f'画像アップロードモーダルの表示がタイムアウトしました。',
                        'screenshot_path': ss_path,
                        'error_type': self.ET_POST_IMAGE_UPLOAD_FAILED} # より具体的なエラータイプも検討可能
            
            logger.info(f"画像ファイル {image_path} を選択します")
            # 定数を使用
            self.page.set_input_files(self._BLOG_FORM_IMAGE_INPUT, image_path)
            
            try:
                logger.info("画像のサムネイルが表示されるのを待機します")
                # 定数を使用
                self.page.wait_for_selector(self._BLOG_FORM_IMAGE_THUMBNAIL, timeout=20000, state="visible")
                self.page.wait_for_selector(self._BLOG_FORM_IMAGE_SUBMIT_BTN_ACTIVE, timeout=10000)
            except TimeoutError:
                logger.warning("画像サムネイルの表示確認がタイムアウトしました。処理を継続します。")
            
            logger.info("「登録する」ボタンをクリックします")
            try:
                # 定数を使用
                # self.page.click(self._BLOG_FORM_IMAGE_SUBMIT_BTN)
                clicked_submit = self._click_element(self._BLOG_FORM_IMAGE_SUBMIT_BTN)
                if not clicked_submit:
                    logger.warning(f"標準セレクタでの登録ボタン({self._BLOG_FORM_IMAGE_SUBMIT_BTN})のクリックに失敗。XPathを試します。")
                    clicked_submit = self._click_element(self._BLOG_FORM_IMAGE_SUBMIT_BTN_XPATH)

                if not clicked_submit:
                    logger.error(f"画像アップロードモーダルの「登録する」ボタンのクリックに失敗しました。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "img_submit_btn_click_failed_")
                    return {**default_failure_result,
                            'message': f'画像アップロードモーダルの「登録する」ボタンのクリックに失敗しました。',
                            'screenshot_path': ss_path,
                            'error_type': self.ET_POST_IMAGE_UPLOAD_FAILED}

            except Exception as button_err: # _click_element内でキャッチされるため、ここは冗長かもしれない
                logger.warning(f"登録ボタンのクリック処理で予期せぬエラー: {button_err}")
                # _click_element が False を返せば上のif not clicked_submit で処理されるはず
            
            logger.info("モーダルが閉じるのを待機します")
            time.sleep(3)
            
            # 画像挿入後にカーソル位置がリセットされるため、強化された方法で再度最後に設定
            if set_cursor_end:
                logger.info("画像挿入後にカーソルを強化方式で最後に移動します")
                time.sleep(0.5)  # DOM更新を待つ
                
                # 強化カーソル制御を使用
                if not self._ensure_cursor_at_end(max_retries=2):
                    # 失敗した場合は当初の方法にフォールバック
                    logger.warning("強化カーソル制御が失敗したため、通常の方法にフォールバックします")
                    self._set_cursor_at_end()
                
                time.sleep(0.5)  # カーソル移動の安定を待つ
            
            return default_success_result # 成功
            
        except Exception as e:
            logger.error(f"画像アップロード中にエラーが発生しました: {e}", exc_info=True)
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "img_upload_exception_")
            return {**default_failure_result, 
                    'message': f'画像 {image_path} のアップロード中に予期せぬエラー: {str(e)}',
                    'screenshot_path': ss_path,
                    'error_type': self.ET_POST_IMAGE_UPLOAD_FAILED # より具体的なエラーメッセージで上書き
                   }

    def select_stylist(self, stylist_id):
        """スタイリストを選択する"""
        default_success_result = {
            'success': True, 
            'message': f'スタイリスト (ID: {stylist_id}) の選択に成功しました。', 
            'screenshot_path': None, 
            'error_type': None
        }
        default_failure_result = {
            'success': False, 
            'message': f'スタイリスト (ID: {stylist_id}) の選択に失敗しました。', 
            'screenshot_path': None, 
            'error_type': self.ET_STYLIST_SELECT_UNEXPECTED # デフォルトの予期せぬエラー
        }

        try:
            logger.info(f"スタイリスト {stylist_id} を選択します")
            # 定数を使用
            stylist_select_locator = self.page.locator(self._BLOG_FORM_STYLIST_SELECT)
            
            # セレクタが存在するか確認
            if not stylist_select_locator.count():
                logger.error(f"スタイリスト選択のセレクト要素 ({self._BLOG_FORM_STYLIST_SELECT}) が見つかりません。")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "stylist_select_notfound_")
                return {**default_failure_result, 
                        'message': f"スタイリスト選択のプルダウンが見つかりませんでした。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_STYLIST_SELECT_ELEMENT_NOT_FOUND}

            self.page.select_option(self._BLOG_FORM_STYLIST_SELECT, stylist_id)
            logger.info(f"スタイリスト {stylist_id} を選択しました。")
            return default_success_result
        except Exception as e:
            logger.error(f"スタイリスト選択中に予期せぬエラーが発生しました: {e}", exc_info=True)
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "stylist_select_exception_")
            # Playwrightのselect_optionは失敗時にエラーを投げるので、それをキャッチ
            # 具体的なエラーメッセージによって error_type を変えることも可能
            return {**default_failure_result, 
                    'message': f"スタイリスト (ID: {stylist_id}) の選択中に予期せぬエラーが発生しました: {str(e)}",
                    'screenshot_path': ss_path,
                    'error_type': self.ET_STYLIST_SELECT_OPTION_FAILED # より具体的なエラータイプ
                   }

    def select_coupon(self, coupon_names):
        """クーポンを選択する (filterメソッド使用版)"""
        default_success_result = {
            'success': True, 
            'message': f'クーポン {coupon_names} の選択に成功しました。', 
            'screenshot_path': None, 
            'error_type': None
        }
        coupon_names_str = ", ".join(coupon_names) if isinstance(coupon_names, list) else str(coupon_names)
        default_failure_result = {
            'success': False, 
            'message': f'クーポン ({coupon_names_str}) の選択に失敗しました。', 
            'screenshot_path': None, 
            'error_type': self.ET_COUPON_SELECTION_UNEXPECTED
        }

        try:
            coupon_button_selector = self._BLOG_FORM_COUPON_BTN
            coupon_modal_selectors = [self._BLOG_FORM_COUPON_MODAL_PRIMARY, self._BLOG_FORM_COUPON_MODAL_ALT]

            logger.info(f"クーポン選択ボタン ({coupon_button_selector}) を待機します")
            try:
                coupon_button = self.page.locator(coupon_button_selector)
                coupon_button.wait_for(state="visible", timeout=10000)
            except TimeoutError:
                logger.error(f"クーポン選択ボタン ({coupon_button_selector}) が表示されませんでした")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_btn_notfound_")
                return {**default_failure_result, 
                        'message': "クーポン選択ボタンが表示されませんでした。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_COUPON_BTN_NOT_VISIBLE}

            logger.info("クーポン選択ボタンをクリックします")
            clicked = False
            try:
                coupon_button.scroll_into_view_if_needed(); time.sleep(0.5)
                coupon_button.click(timeout=5000); clicked = True
                logger.info("Playwrightのclickでクーポン選択ボタンをクリックしました")
            except Exception as e:
                logger.warning(f"Playwrightのclick失敗: {e}。他の方法を試みます。")
                try:
                    logger.info("JavaScript click を試行")
                    coupon_button.evaluate("node => node.click()"); clicked = True
                    logger.info("JavaScript clickでクーポン選択ボタンをクリックしました")
                except Exception as js_e:
                    logger.warning(f"JavaScript click失敗: {js_e}。dispatch_eventを試みます。")
                    try:
                        logger.info("dispatch_event('click') を試行")
                        coupon_button.dispatch_event('click'); clicked = True
                        logger.info("dispatch_event('click')でクーポン選択ボタンをクリックしました")
                    except Exception as dispatch_e:
                         logger.error(f"全てのクリック方法でクーポン選択ボタンのクリックに失敗: {dispatch_e}")
                         ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_btn_click_")
                         return {**default_failure_result, 
                                 'message': "クーポン選択ボタンのクリックに失敗しました。",
                                 'screenshot_path': ss_path,
                                 'error_type': self.ET_COUPON_BTN_CLICK_FAILED}
            if not clicked: 
                logger.error("クーポン選択ボタンをクリックできませんでした（最終確認）。") # この行は前の try-except でカバーされるはず
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_btn_click_final_")
                return {**default_failure_result, 
                        'message': "クーポン選択ボタンのクリックに失敗しました（最終確認）。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_COUPON_BTN_CLICK_FAILED}

            modal_visible = False
            logger.info(f"クーポン選択モーダルの表示を待機します (セレクタ: {coupon_modal_selectors})")
            start_time = time.time()
            while time.time() - start_time < self.default_timeout / 1000:
                for selector in coupon_modal_selectors:
                    try:
                        if self.page.locator(selector).is_visible(timeout=1000):
                             logger.info(f"クーポン選択モーダル ({selector}) が表示されました"); modal_visible = True; break
                    except Exception: continue
                if modal_visible: break
                time.sleep(1)
            if not modal_visible:
                 logger.error(f"クーポン選択モーダルの表示がタイムアウトしました ({self.default_timeout}ms)")
                 ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_modal_timeout_")
                 return {**default_failure_result, 
                         'message': "クーポン選択モーダルの表示がタイムアウトしました。",
                         'screenshot_path': ss_path,
                         'error_type': self.ET_COUPON_MODAL_TIMEOUT}

            logger.info("クーポン選択処理を開始します (filter使用)")
            all_coupons_selected_successfully = True
            for coupon_name in coupon_names:
                logger.info(f"クーポン '{coupon_name}' を選択します")
                found_and_clicked = False
                cleaned_coupon_name = coupon_name.strip()
                if not cleaned_coupon_name: 
                    logger.warning("空のクーポン名のためスキップ")
                    continue
                try:
                    all_labels = self.page.locator(f"{coupon_modal_selectors[0]} {self._BLOG_FORM_COUPON_LABEL}")
                    logger.debug(f"モーダル内のラベル候補数: {all_labels.count()}")
                    for i in range(all_labels.count()):
                        label = all_labels.nth(i)
                        coupon_text_element = label.locator(self._BLOG_FORM_COUPON_TEXT)
                        if coupon_text_element.count() > 0:
                            actual_text = coupon_text_element.first.inner_text().strip()
                            logger.debug(f"ラベル {i} のテキスト: '{actual_text}'")
                            if cleaned_coupon_name.lower() in actual_text.lower():
                                logger.info(f"クーポン '{cleaned_coupon_name}' がテキスト '{actual_text}' にマッチしました。クリックを試みます。")
                                try:
                                    label.scroll_into_view_if_needed(); time.sleep(0.5)
                                    label.click(timeout=5000); found_and_clicked = True
                                    logger.info(f"クーポン '{cleaned_coupon_name}' をクリックしました。"); time.sleep(0.3); break
                                except Exception as click_err:
                                     logger.warning(f"クーポン '{cleaned_coupon_name}' のクリックに失敗: {click_err}。念のため次の候補も探します。")
                        else: 
                            logger.debug(f"ラベル {i} に {self._BLOG_FORM_COUPON_TEXT} が見つかりません。")
                    if not found_and_clicked: 
                        logger.warning(f"クーポン '{cleaned_coupon_name}' がモーダル内で見つからないか、クリックできませんでした。")
                        all_coupons_selected_successfully = False
                except Exception as e: 
                    logger.error(f"クーポン '{coupon_name}' の選択処理中に予期せぬエラー: {e}", exc_info=True)
                    all_coupons_selected_successfully = False
            
            if not all_coupons_selected_successfully:
                 logger.error("一部またはすべてのクーポンの選択に失敗しました。")
                 ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_item_select_")
                 return {**default_failure_result, 
                         'message': "一部または全てのクーポンの選択に失敗しました。",
                         'screenshot_path': ss_path,
                         'error_type': self.ET_COUPON_SELECTION_ITEM_NOT_FOUND}

            logger.info("「設定する」ボタンをクリックします")
            try:
                setting_button_selector = self._BLOG_FORM_COUPON_SETTING_BTN
                setting_button = self.page.locator(setting_button_selector)
                setting_button.wait_for(state="visible", timeout=10000)
                if "is_disable" not in (setting_button.get_attribute("class") or ""):
                    logger.info("「設定する」ボタンが有効です。クリックします。")
                    setting_button.click(timeout=5000)
                else:
                     logger.warning("「設定する」ボタンが無効状態 (is_disable) です。クリックをスキップします。")
                     ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_setting_btn_disabled_")
                     return {**default_failure_result, 
                             'message': "クーポン「設定する」ボタンが無効状態でした。",
                             'screenshot_path': ss_path,
                             'error_type': self.ET_COUPON_SETTING_BTN_CLICK_FAILED}
            except Exception as e:
                logger.warning(f"標準セレクタでの設定ボタンのクリックに失敗しました: {e}")
                try:
                    alt_setting_button_selector = self._BLOG_FORM_COUPON_SETTING_BTN_XPATH
                    alt_setting_button = self.page.locator(alt_setting_button_selector)
                    alt_setting_button.wait_for(state="visible", timeout=5000)
                    if "is_disable" not in (alt_setting_button.get_attribute("class") or ""):
                        alt_setting_button.click(timeout=5000)
                        logger.info("代替セレクタで「設定する」ボタンをクリックしました。")
                    else:
                        logger.warning("代替セレクタでも「設定する」ボタンが無効状態です。")
                        ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_setting_btn_alt_disabled_")
                        return {**default_failure_result, 
                                'message': "クーポン「設定する」ボタンが無効状態でした（代替確認）。",
                                'screenshot_path': ss_path,
                                'error_type': self.ET_COUPON_SETTING_BTN_CLICK_FAILED}
                except Exception as alt_e:
                    logger.error(f"代替方法での設定ボタンのクリックにも失敗しました: {alt_e}", exc_info=True)
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_setting_click_failed_")
                    return {**default_failure_result, 
                            'message': "クーポン「設定する」ボタンのクリックに失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_COUPON_SETTING_BTN_CLICK_FAILED}

            logger.info("モーダルが閉じるのを待機します")
            try:
                for selector in reversed(coupon_modal_selectors): 
                    try:
                        self.page.locator(selector).wait_for(state="hidden", timeout=10000)
                        logger.info(f"クーポン選択モーダル ({selector}) が閉じました"); break
                    except TimeoutError:
                         if selector == coupon_modal_selectors[0]: 
                            logger.warning("クーポン選択モーダルが閉じるのを待機中にタイムアウトしました。")
                            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_modal_close_timeout_")
                            return {**default_failure_result, 
                                    'message': "クーポン選択モーダルが閉じるのを待機中にタイムアウトしました。",
                                    'screenshot_path': ss_path,
                                    'error_type': self.ET_COUPON_MODAL_CLOSE_TIMEOUT}
                    except Exception: pass 
            except Exception as wait_close_e: 
                logger.warning(f"モーダルが閉じるのを待機中にエラー: {wait_close_e}")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_modal_close_exception_")
                return {**default_failure_result, 
                        'message': f"クーポンモーダルを閉じる待機中にエラー: {wait_close_e}",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_COUPON_MODAL_CLOSE_TIMEOUT}

            return default_success_result

        except Exception as e:
            logger.error(f"クーポン選択処理全体でエラーが発生しました: {e}", exc_info=True) 
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "coupon_select_overall_exception_")
            return {**default_failure_result, 
                    'message': f"クーポン選択処理中に予期せぬエラーが発生しました: {str(e)}",
                    'screenshot_path': ss_path,
                    'error_type': self.ET_COUPON_SELECTION_UNEXPECTED}

    def post_blog(self, blog_data):
        """ブログを投稿する"""
        default_success_result = {
            'success': True, 
            'message': 'ブログの投稿処理（確認ページでの最終アクション）に成功しました。', # メッセージを汎用的に変更
            'screenshot_path': None, 
            'error_type': None
        }
        default_failure_result = {
            'success': False, 
            'message': 'ブログの投稿処理（確認ページでの最終アクション）に失敗しました。', # メッセージを汎用的に変更
            'screenshot_path': None, 
            'error_type': self.ET_POST_BLOG_GENERAL
        }

        try:
            # スタイリスト選択
            stylist_select_result = self.select_stylist(blog_data['stylist_id']) # 辞書が返る
            if not stylist_select_result['success']:
                logger.error(f"スタイリストの選択に失敗しました: {stylist_select_result.get('message')}")
                return stylist_select_result

            # 定数を使用
            self.page.select_option(self._BLOG_FORM_CATEGORY_SELECT, "BL02") # カテゴリIDは固定値のまま
            self.page.fill(self._BLOG_FORM_TITLE_INPUT, blog_data['title'])

            # 構造化データ（sections）がある場合、それに基づいて処理
            if 'sections' in blog_data and isinstance(blog_data['sections'], list) and len(blog_data['sections']) > 0:
                logger.info("構造化データ（sections）に基づいてコンテンツを処理します")
                
                if not self.set_rich_text_content(""): 
                    logger.error("初期化用の空コンテンツの設定に失敗しました")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "content_init_")
                    return {**default_failure_result, 
                            'message': "ブログコンテンツの初期化に失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_POST_CONTENT_INIT_FAILED}
                
                logger.info("フラグメント挿入アプローチを実行します")
                
                if not self.set_rich_text_content(""): # 再度初期化
                    logger.error("再初期化用の空コンテンツ設定に失敗しました")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "content_reinit_")
                    return {**default_failure_result, 
                            'message': "ブログコンテンツの再初期化に失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_POST_CONTENT_REINIT_FAILED}

                current_content = ""
                for idx, section_data in enumerate(blog_data['sections_to_process'] if 'sections_to_process' in blog_data else blog_data['sections']): # 互換性
                    section_type = section_data.get('type')
                    section = section_data.get('data', section_data) # 互換性

                    if idx > 0 and current_content:
                        current_content += "<div><br></div>\n"
                    
                    if section_type == 'text':
                        content = section.get('content', '')
                        if content and len(content.strip()) > 0:
                            logger.info(f"テキストセクション {idx+1} を追加: {content[:30]}...")
                            formatted_content = f"<div>{content}</div>"
                            current_content += formatted_content
                    
                    elif section_type == 'image':
                        try:
                            image_index = section.get('imageIndex', 0)
                            if not isinstance(image_index, int):
                                image_index = int(image_index)
                            
                            if blog_data.get('image_paths') and 0 <= image_index < len(blog_data['image_paths']):
                                image_path = blog_data['image_paths'][image_index]
                                logger.info(f"画像セクション {idx+1} を処理: {image_path}")
                                
                                if not self.set_rich_text_content(current_content):
                                    logger.warning(f"中間コンテンツの設定に失敗しました")
                                    continue # 次のセクションへ
                                time.sleep(1.0)
                                
                                if not self.upload_image(image_path, set_cursor_end=True):
                                    logger.warning(f"画像アップロード失敗: {image_path}")
                                    # 失敗しても処理を続けるか、エラーとしてリターンするかは要件次第
                                    # ここでは警告に留め、次のセクション処理へ
                                    continue
                                
                                time.sleep(2.0)
                                
                                js_get_content = """
                                (function() {
                                    try {
                                        var editorInstance = nicEditors.findEditor('blogContents');
                                        if (editorInstance) { return editorInstance.getContent(); }
                                        return "";
                                    } catch(e) { console.error('コンテンツ取得エラー:', e); return ""; }
                                })();
                                """
                                editor_content = self.page.evaluate(js_get_content)
                                
                                if editor_content:
                                    import re
                                    img_match = re.search(r'<img[^>]+>', editor_content)
                                    if img_match:
                                        img_tag = img_match.group(0)
                                        img_div = f"<div>{img_tag}</div>"
                                        current_content += img_div
                                        # 画像挿入後のコンテンツで current_content を更新するのではなく、
                                        # editor_content から画像タグを除いたものを current_content に加えるべきかもしれないが、
                                        # nicEdit の挙動に依存するため、ここでは元のロジックを尊重
                                        if not self.set_rich_text_content(current_content): # 更新されたcurrent_contentでエディタを再設定
                                            logger.warning("画像挿入後のコンテンツ再構成に失敗しました")
                                    else:
                                        logger.warning("挿入された画像タグが見つかりませんでした")
                                else:
                                    logger.warning("エディタから内容を取得できませんでした")
                            else:
                                logger.warning(f"指定された画像が見つかりません: index {image_index}")
                        except Exception as img_err:
                            logger.error(f"画像処理エラー: {img_err}", exc_info=True)
                    time.sleep(1.0)
                
                if current_content and not self.set_rich_text_content(current_content):
                    logger.warning("最終コンテンツの設定に失敗しました")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "final_content_set_")
                    return {**default_failure_result, 
                            'message': "最終的なブログコンテンツの設定に失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_POST_FINAL_CONTENT_SETTING_FAILED}

                logger.info("フラグメント挿入アプローチによる処理が完了しました")
                
                if blog_data.get('template'):
                    logger.info("テンプレートを追加します")
                    if not self.append_rich_text_content("\n\n" + blog_data['template']):
                        logger.warning("テンプレート追加中にエラーが発生しました")
            
            else: # 従来の方法
                logger.info("従来の方法でコンテンツを設定します（構造化データなし）")
                full_content = blog_data['content']
                if blog_data.get('template'): full_content += "\n\n" + blog_data['template']
                if not self.set_rich_text_content(full_content):
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "legacy_content_set_")
                    # 警告に留め、処理を続行する（エラーとして返さない）
                    logger.warning(f"ブログコンテンツ（従来形式）の設定に失敗しました。スクリーンショット: {ss_path}")
                    # return {**default_failure_result, 
                    #         'message': "ブログコンテンツ（従来形式）の設定に失敗しました。",
                    #         'screenshot_path': ss_path,
                    #         'error_type': self.ET_POST_LEGACY_CONTENT_SETTING_FAILED}
                
                if blog_data.get('image_paths'):
                    for image_path in blog_data['image_paths']:
                        upload_result = self.upload_image(image_path, set_cursor_end=True)
                        if not upload_result['success']:
                            logger.warning(f"画像 '{image_path}' のアップロードに失敗しました: {upload_result.get('message')}. スクリーンショット: {upload_result.get('screenshot_path')}")
                            # 処理を中断せず、次の画像の処理へ (または後続処理へ)
                            # return upload_result 
            
            if blog_data.get('coupon_names') and len(blog_data['coupon_names']) > 0:
                coupon_select_result = self.select_coupon(blog_data['coupon_names']) # 辞書が返る
                if not coupon_select_result['success']:
                    logger.error(f"クーポンの選択に失敗しました: {coupon_select_result.get('message')}")
                    return coupon_select_result # 詳細辞書をそのまま返す
            
            logger.info(f"「確認する」ボタン ({self._BLOG_CONFIRM_BTN}) をクリックします")
            try:
                self.page.locator(self._BLOG_CONFIRM_BTN).click(timeout=10000)
                logger.info("「確認する」ボタンをクリックしました")
            except Exception as confirm_err:
                 logger.error(f"「確認する」ボタンのクリックに失敗: {confirm_err}", exc_info=True)
                 ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "confirm_click_")
                 return {**default_failure_result, 
                         'message': f"「確認する」ボタンのクリックに失敗しました: {confirm_err}",
                         'screenshot_path': ss_path,
                         'error_type': self.ET_POST_CONFIRM_CLICK_FAILED}

            logger.info(f"確認ページ（「登録・未反映にする」ボタン {self._BLOG_UNREFLECT_BTN} または「登録・反映する」ボタン {self._BLOG_REFLECT_BTN}）の表示を待機します")
            try:
                # どちらかのボタンが表示されるのを待つ
                # まず「登録・反映する」ボタンを優先的に確認
                reflect_button_selector = self._BLOG_REFLECT_BTN # 修正
                unreflect_button_selector = self._BLOG_UNREFLECT_BTN # 既存の未反映ボタンセレクタ

                # reflectボタンの有無を確認
                reflect_button_visible = False
                try:
                    self.page.wait_for_selector(reflect_button_selector, state="visible", timeout=5000) # 短めのタイムアウトで確認
                    reflect_button_visible = True
                    logger.info("「登録・反映する」ボタンの表示を確認しました")
                except TimeoutError:
                    logger.info(f"「登録・反映する」ボタン({reflect_button_selector})は見つかりませんでした。「登録・未反映にする」ボタン({unreflect_button_selector})を確認します。") # ログ修正

                if reflect_button_visible:
                    # 「登録・反映する」ボタンが存在する場合、それをターゲットにする
                    target_button_selector = reflect_button_selector
                    target_button_name = "登録・反映する"
                else:
                    # 「登録・反映する」ボタンがなければ、「登録・未反映にする」ボタンを待つ
                    self.page.wait_for_selector(unreflect_button_selector, state="visible", timeout=55000) # 残りの時間で待つ
                    target_button_selector = unreflect_button_selector
                    target_button_name = "登録・未反映にする"
                    logger.info(f"「{target_button_name}」ボタンの表示を確認しました")
                
            except TimeoutError:
                logger.error("確認ページ（反映または未反映ボタン）の表示がタイムアウトしました")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "confirm_page_timeout_")
                return {**default_failure_result, 
                        'message': "確認ページ（反映または未反映ボタン）の表示がタイムアウトしました。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_POST_CONFIRM_PAGE_TIMEOUT}

            if self.is_robot_detection_present():
                logger.error("確認ページでロボット認証が検出されました。")
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "confirm_page_robot_")
                return {**default_failure_result, 
                        'message': "確認ページでロボット認証が検出されました。",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_POST_ROBOT_DETECTED_ON_CONFIRM, 
                        'robot_detected': True} # robot_detectedフラグを追加
                
            logger.info(f"「{target_button_name}」ボタン ({target_button_selector}) をクリックします")
            try:
                 self.page.locator(target_button_selector).click(timeout=10000)
                 logger.info(f"「{target_button_name}」ボタンをクリックしました")
            except Exception as reflect_err: # 変数名を reflect_err に変更 (unreflect_err から)
                 logger.error(f"「{target_button_name}」ボタンのクリックに失敗: {reflect_err}", exc_info=True)
                 ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "reflect_click_") # reflect_click に変更
                 return {**default_failure_result, 
                         'message': f"「{target_button_name}」ボタンのクリックに失敗しました: {reflect_err}",
                         'screenshot_path': ss_path,
                         'error_type': self.ET_POST_UNREFLECT_CLICK_FAILED} # エラータイプは既存のものを流用

            logger.info(f"「ブログ一覧へ」ボタン ({self._BLOG_BACK_BTN}) を待機し、クリックします")
            try:
                # self.page.locator(self._BLOG_BACK_BTN).click(timeout=30000) # wait_for visibleは不要な場合がある
                # logger.info("「ブログ一覧へ」ボタンをクリックしました。")
                if not self._click_element(self._BLOG_BACK_BTN, timeout=30000):
                    logger.error(f"「ブログ一覧へ」ボタン({self._BLOG_BACK_BTN})のクリックに失敗しました。")
                    ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "back_button_click_failed_")
                    return {**default_failure_result,
                            'message': f"「ブログ一覧へ」ボタンのクリックに失敗しました。",
                            'screenshot_path': ss_path,
                            'error_type': self.ET_POST_BACK_BUTTON_CLICK_FAILED}
                logger.info("「ブログ一覧へ」ボタンをクリックしました。")

            except Exception as back_err: # _click_element内でエラーが処理されるため、ここは通常通らないはず
                logger.error(f"「ブログ一覧へ」ボタンのクリック中に予期せぬエラー: {back_err}", exc_info=True)
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "back_button_unexpected_fail_")
                return {**default_failure_result,
                        'message': f"「ブログ一覧へ」ボタンのクリック中に予期せぬエラーが発生しました: {str(back_err)}",
                        'screenshot_path': ss_path,
                        'error_type': self.ET_POST_BACK_BUTTON_CLICK_FAILED}
            
            logger.info(f"ブログ一覧ページへの遷移（例: {self._NAVI_NEW_POST} ボタンの再表示）を待機します") 
            try:
                self.page.wait_for_selector(self._NAVI_NEW_POST, state="visible", timeout=60000)
                logger.info("ブログ一覧ページへの遷移（または完了状態）を確認しました")
            except TimeoutError:
                logger.error("ブログ一覧ページへの遷移確認がタイムアウトしました。投稿は完了している可能性がありますが、確認してください。") # メッセージ変更
                ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "post_complete_timeout_warn_") # 警告としてSS
                # ここでエラーとして処理を中断する場合は以下のようにする
                # return {**default_failure_result,
                #         'message': "ブログ一覧ページへの遷移確認がタイムアウトしました。投稿状態を確認してください。",
                #         'screenshot_path': ss_path,
                #         'error_type': self.ET_POST_COMPLETE_TIMEOUT}
                # 現状はタイムアウトしても成功として扱うため、エラーリターンはコメントアウトのまま
                # ただし、呼び出し元での結果判断をより明確にするため、成功とは断定しないメッセージに変更
            
            if self.is_robot_detection_present(): 
                logger.warning("処理完了後（？）にロボット認証が検出されました。")
                # 警告としてSS。robot_detected フラグは立てない（投稿自体は成功している可能性があるため）

            logger.info(f"ブログの「{target_button_name}」処理が完了しました") # target_button_name を使用
            success_ss_path = self.take_screenshot(prefix="post_success_")
            # メッセージを動的に設定
            default_success_result['message'] = f'ブログの「{target_button_name}」処理に成功しました。'
            return {**default_success_result, 'screenshot_path': success_ss_path}
            
        except Exception as e:
            logger.error(f"ブログ投稿処理（確認ページでの最終アクション）中にエラー: {e}", exc_info=True) # メッセージを汎用的に変更
            ss_path = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "post_blog_exception_")
            return {**default_failure_result, 
                    'message': f"ブログ投稿処理中に予期せぬエラー: {str(e)}",
                    'screenshot_path': ss_path,
                    'error_type': self.ET_POST_UNEXPECTED_ERROR}

    # --- Private Step Methods for execute_post Flow ---

    def _step_login(self, user_id, password):
        """Execute post step: Perform login."""
        logger.info("ステップ1/3: サロンボードへのログインを開始します。")
        login_result = self.login(user_id, password) # loginは辞書を返す
        if not login_result['success']:
            logger.error(f"ログインステップで失敗しました: {login_result.get('message')}")
            return login_result # 詳細辞書をそのまま返す
        logger.info("ステップ1/3: ログイン成功。")
        return login_result # 成功時も詳細辞書を返す

    def _step_navigate_to_blog_form(self):
        """Execute post step: Navigate to the blog posting form."""
        logger.info("ステップ2/3: ブログ投稿ページへの移動を開始します。")
        nav_result = self.navigate_to_blog_post_page() # navigate_to_blog_post_pageは辞書を返す
        if not nav_result['success']:
            logger.error(f"ブログ投稿ページへの移動ステップで失敗しました: {nav_result.get('message')}")
            return nav_result # 詳細辞書をそのまま返す
        logger.info("ステップ2/3: ブログ投稿ページへの移動成功。")
        return nav_result # 成功時も詳細辞書を返す

    def _step_post_blog_data(self, blog_data):
        """Execute post step: Fill form and post blog data."""
        logger.info("ステップ3/3: ブログデータの入力と投稿処理を開始します。") # 「（未反映登録）」を削除
        post_result = self.post_blog(blog_data) # post_blogは辞書を返すようになった
        if not post_result['success']:
            logger.error(f"ブログデータの入力・投稿ステップで失敗しました: {post_result.get('message')}")
        else:
            # post_result['message'] に具体的なアクション名が含まれるように変更したため、それを利用
            logger.info(f"ステップ3/3: {post_result.get('message', 'ブログデータの入力・投稿処理が完了しました。')}")
        return post_result # post_blogから返された詳細辞書をそのまま返す

    # --- Public Method ---

    def execute_post(self, user_id, password, blog_data):
        """
        ブログ投稿の一連の処理（ログインから投稿まで）を実行する。
        
        Args:
            user_id (str): サロンボードのユーザーID。
            password (str): サロンボードのパスワード。
            blog_data (dict): ブログ投稿データ。
        
        Returns:
            dict: 処理結果。post_blogメソッドの返り値と同じ構造。
        """
        start_time = time.time()
        logger.info("=== Salon Boardブログ投稿処理 開始 ===")
        
        default_error_result = {
            'success': False,
            'message': 'ブログ投稿処理の初期化に失敗しました。',
            'screenshot_path': None,
            'error_type': self.ET_INIT_FAILED
        }

        if not self.start(): # ブラウザ起動
            default_error_result['message'] = "ブラウザの起動に失敗しました。"
            default_error_result['error_type'] = self.ET_BROWSER_START_FAILED # エラータイプを具体的に
            # self.start()内でエラーログとスクリーンショット(もしpageがあれば)は試みられる
            # self.start() は bool しか返さないので、ここでssは撮れない。
            # ただし、self.page が None の可能性が高いので、撮れたとしても限定的。
            return default_error_result

        try:
            # ステップ1: ログイン
            login_result = self.login(user_id, password)
            if not login_result['success']:
                # loginメソッドが詳細な結果を返すので、それをそのまま返す
                logger.error(f"ログインステップで失敗: {login_result.get('message')}")
                return login_result # 既に詳細なエラー情報とSSパスを含む

            # ステップ2: ブログ投稿ページへ移動
            nav_result = self.navigate_to_blog_post_page()
            if not nav_result['success']:
                logger.error(f"ブログ投稿ページへの移動ステップで失敗: {nav_result.get('message')}")
                return nav_result # 既に詳細なエラー情報とSSパスを含む

            # ステップ3: ブログデータの入力と投稿
            post_result = self.post_blog(blog_data)
            # post_blogは既に期待する辞書形式で結果を返すはず
            
            if post_result['success']:
                logger.info(f"=== Salon Boardブログ投稿処理 正常終了 ===")
            else:
                logger.error(f"ブログ投稿ステップで失敗: {post_result.get('message')}")
                logger.info(f"=== Salon Boardブログ投稿処理 異常終了 ===")
            return post_result

        except Exception as e:
            logger.error(f"ブログ投稿のメイン処理中に予期せぬエラー: {e}", exc_info=True)
            # 予期せぬエラーの場合もスクリーンショットを試みる
            failure_screenshot = self.take_screenshot(prefix=self._FAILURE_SCREENSHOT_PREFIX + "exec_post_exception_")
            return {
                'success': False,
                'message': f"ブログ投稿処理中に予期せぬエラーが発生しました: {str(e)}",
                'screenshot_path': failure_screenshot,
                'error_type': self.ET_EXEC_POST_UNKNOWN_ERROR
            }
        finally:
            end_time = time.time()
            processing_time = end_time - start_time
            logger.info(f"処理時間: {processing_time:.2f} 秒")
            # 成功時スクリーンショットはpost_blog内で撮影されるため、ここでは不要
            # if post_result and post_result.get('success') and not post_result.get('screenshot_path'): # 通常はpost_blogが撮影
            #    logger.info("投稿成功後のスクリーンショットを撮影します (execute_postのfinally)。")
            #    self.take_screenshot(prefix="final_success_screenshot_")

            logger.info("ブラウザを終了します。")
            self.close()

    def take_screenshot(self, prefix="screenshot_") -> str | None:
        """現在のページのスクリーンショットを撮影し、パスを返す"""
        if not self.page:
            logger.warning("ページが初期化されていないため、スクリーンショットを撮影できません。")
            return None
        
        try:
            # コンストラクタで渡された screenshot_folder_path を使用
            screenshot_folder = self.screenshot_folder_path 
            
            os.makedirs(screenshot_folder, exist_ok=True)
            
            timestamp = int(time.time())
            filename = f"{prefix}{timestamp}.png"
            filepath = os.path.join(screenshot_folder, filename)
            
            self.page.screenshot(path=filepath)
            logger.info(f"スクリーンショットを保存しました: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"スクリーンショットの撮影に失敗しました: {e}", exc_info=True)
            return None