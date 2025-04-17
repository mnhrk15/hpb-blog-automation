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

    def __init__(self, headless=True, slow_mo=100):
        """
        初期化メソッド
        
        Args:
            headless (bool): ヘッドレスモードで実行するかどうか。デフォルトはTrue（ヘッドレスモード）。
            slow_mo (int): アクションの間に入れる遅延時間（ミリ秒）。デバッグ時に視認性を高めるため。
        """
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
        ロボット認証（CAPTCHA等）が検出されたかどうかを確認
        
        Returns:
            bool: ロボット認証が検出された場合はTrue、そうでない場合はFalse
        """
        # まず、ページのURLやタイトルで判断
        try:
            current_url = self.page.url
            page_title = self.page.title()
            
            # URLやタイトルに認証関連のキーワードがある場合
            auth_keywords = ['captcha', 'recaptcha', 'verify', '認証', 'auth']
            if any(keyword in current_url.lower() for keyword in auth_keywords) or \
               any(keyword in page_title.lower() for keyword in auth_keywords):
                logger.warning(f"URL/タイトルからロボット認証を検出: {current_url} / {page_title}")
                return True
        except Exception as e:
            logger.error(f"URL/タイトル検証中のエラー: {e}")
        
        # 「画像認証」テキストを優先的に検索
        try:
            has_image_auth = self.page.evaluate('''
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
                    return false;
                }
            ''')
            
            if has_image_auth:
                logger.warning("テキスト「画像認証」が検出されました")
                return True
        except Exception as e:
            logger.error(f"画像認証テキスト検証中のエラー: {e}")
        
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
            
            login_texts = self.page.evaluate('''
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
            ''')
            
            # ログイン関連の要素があり、認証関連の要素がない場合は通常のログイン画面と判断
            if login_texts and any(self.page.query_selector(selector) for selector in login_indicators):
                logger.info("通常のログイン画面と判断します")
                return False
        except Exception as e:
            logger.error(f"ログイン画面検証中のエラー: {e}")
            
        return False

    def login(self, user_id, password):
        """
        サロンボードにログインする
        
        Args:
            user_id (str): サロンボードのユーザーID
            password (str): サロンボードのパスワード
            
        Returns:
            bool: ログイン成功でTrue、失敗でFalse
        """
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
                self.page.screenshot(path="login_image_auth_detected.png")
                return False
            
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
                self.page.screenshot(path="login_image_auth_detected.png")
                return False
            
            if not login_result:
                logger.error("JavaScriptによるログイン処理に失敗しました")
                self.page.screenshot(path="js_login_error.png")
                
                logger.info("通常の方法でログインを試みます")
                
                # 定数を使用
                logger.info(f"ユーザーID '{user_id}' を入力します")
                id_input_success = self._set_input_value_by_js(self._LOGIN_USER_ID_INPUT, user_id)
                if not id_input_success:
                    logger.error("ユーザーID入力に失敗しました")
                    self.page.screenshot(path="id_input_error.png")
                    return False
                
                logger.info("パスワードを入力します")
                password_input_success = self._set_input_value_by_js(self._LOGIN_PASSWORD_INPUT_PRIMARY, password)
                if not password_input_success:
                    logger.info("代替セレクタでパスワード入力を試みます")
                    password_input_success = self._set_input_value_by_js(self._LOGIN_PASSWORD_INPUT_ALT, password)
                if not password_input_success:
                    logger.error("パスワード入力に失敗しました")
                    self.page.screenshot(path="password_input_error.png")
                    return False
                
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
                        self.page.screenshot(path="login_button_error.png")
                        return False
            else:
                logger.info("JavaScriptによるログイン処理が成功しました")
            
            # ダッシュボード表示待機前にもう一度認証確認
            time.sleep(1)
            if self.is_robot_detection_present():
                logger.error("ログイン処理後に画像認証が検出されました。処理を中断します。")
                self.page.screenshot(path="post_login_auth_detected.png")
                return False
            
            logger.info("ダッシュボードの表示を待機します...")
            try:
                # 定数を使用
                self.page.wait_for_selector(self._DASHBOARD_GLOBAL_NAVI, timeout=self.default_timeout, state="visible")
                logger.info("ダッシュボードの表示を確認しました")
            except TimeoutError as e:
                current_url = self.page.url
                current_title = self.page.title()
                logger.error(f"ログイン後のダッシュボード表示がタイムアウトしました。現在のURL: {current_url}, タイトル: {current_title}")
                
                # タイムアウト時にも認証確認
                if self.is_robot_detection_present():
                    logger.error("ダッシュボード表示待機中に画像認証が検出されました。")
                    self.page.screenshot(path="dashboard_timeout_auth_detected.png")
                    return False
                
                self.page.screenshot(path="login_timeout_screenshot.png")
                return False
                
            if self.is_robot_detection_present():
                logger.error("ログイン後にロボット認証が検出されました。処理を中断します。")
                return False
                
            logger.info("サロンボードへのログインに成功しました")
            return True
            
        except Exception as e:
            logger.error(f"ログイン処理中にエラーが発生しました: {e}")
            self.page.screenshot(path="login_error_screenshot.png")
            return False
            
    def _set_input_value_by_js(self, selector, value):
        """JavaScriptを使用して入力フィールドに値を設定する内部メソッド"""
        try:
            if not self.page.query_selector(selector):
                logger.warning(f"セレクタ '{selector}' が見つかりません")
                return False
            js_script = f"""
            (function() {{
                var el = document.querySelector("{selector.replace('"', '\\\\"')}");
                if (el) {{
                    el.value = "{value}";
                    var event = new Event('input', {{ bubbles: true }});
                    el.dispatchEvent(event);
                    return true;
                }}
                return false;
            }})()
            """
            result = self.page.evaluate(js_script)
            if result:
                logger.info(f"JavaScriptを使用して値を設定しました: {selector}")
                return True
            return False
        except Exception as e:
            logger.warning(f"JavaScriptによる値設定中にエラー: {e}")
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
            js_script = f"""
            (function() {{
                var form = document.querySelector("{form_selector.replace('"', '\\\\"')}");
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
        for attempt in range(self.max_retries):
            try:
                logger.info(f"ブログ投稿ページへの移動を試行中... (試行 {attempt+1}/{self.max_retries})")
                
                # --- 1. 「掲載管理」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_KEISAI_KANRI):
                    logger.error("「掲載管理」へのナビゲーションに失敗しました。")
                    # エラーが続く場合はリトライループへ
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        self.page.screenshot(path="keisai_kanri_navigation_error.png"); return False
                
                logger.info("掲載管理ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("掲載管理ページでロボット認証が検出されました。処理を中断します。"); return False

                # --- 2. 「ブログ」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_BLOG):
                    logger.error("「ブログ」管理ページへのナビゲーションに失敗しました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        self.page.screenshot(path="blog_navigation_error.png"); return False
                
                logger.info("ブログ管理ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("ブログ管理ページでロボット認証が検出されました。処理を中断します。"); return False

                # --- 3. 「新規投稿」をクリックして待機 ---
                if not self._click_and_wait_navigation(self._NAVI_NEW_POST):
                    logger.error("「新規投稿」ページへのナビゲーションに失敗しました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        self.page.screenshot(path="new_post_navigation_error.png"); return False
                
                logger.info("新規投稿ページの読み込み完了。")
                if self.is_robot_detection_present():
                    logger.error("新規投稿ページでロボット認証が検出されました。処理を中断します。"); return False
                    
                # --- 4. ブログ投稿フォームの表示を確認 ---
                logger.info(f"ブログ投稿フォームの主要素 ({self._BLOG_FORM_STYLIST_SELECT}) を待機します")
                try:
                    self.page.wait_for_selector(self._BLOG_FORM_STYLIST_SELECT, state="visible", timeout=60000)
                    logger.info("ブログ投稿フォームの表示を確認しました。ナビゲーション成功。")
                    return True # 全てのステップが成功
                except TimeoutError:
                    logger.error("ブログ投稿フォームの表示確認がタイムアウトしました。")
                    if attempt < self.max_retries - 1:
                        logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                        self._try_recover_and_wait() # 回復試行
                        continue
                    else:
                        logger.error(f"ブログ投稿フォームの表示確認が{self.max_retries}回タイムアウトしました。")
                        self.page.screenshot(path="blog_form_visible_timeout.png"); return False

            except Exception as e:
                # 予期せぬエラー（クリック失敗、ネットワークエラー以外）
                logger.error(f"ナビゲーション中に予期せぬエラーが発生しました: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    logger.warning(f"リトライします... ({attempt+1}/{self.max_retries})")
                    self._try_recover_and_wait() # 回復試行
                    continue
                else:
                    logger.error(f"ナビゲーション中に{self.max_retries}回予期せぬエラーが発生しました。")
                    self.page.screenshot(path="navigation_unexpected_error.png"); return False
        
        # ループが完了しても成功しなかった場合
        logger.error("最大再試行回数に達しましたが、ブログ投稿ページへの移動に失敗しました。")
        return False

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

    def upload_image(self, image_path):
        """画像をアップロードする"""
        try:
            # 定数を使用
            logger.info("画像アップロードボタンをクリックします")
            self.page.click(self._BLOG_FORM_IMAGE_UPLOAD_BTN)
            
            try:
                logger.info("画像アップロードモーダルの表示を待機します")
                # 定数を使用
                self.page.wait_for_selector(self._BLOG_FORM_IMAGE_MODAL, timeout=10000)
            except TimeoutError:
                logger.error("画像アップロードモーダルの表示がタイムアウトしました"); return False
            
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
                self.page.click(self._BLOG_FORM_IMAGE_SUBMIT_BTN)
            except Exception as button_err:
                logger.warning(f"標準セレクタでの登録ボタンのクリックに失敗しました: {button_err}")
                try:
                    # 定数を使用 (XPath)
                    self.page.click(self._BLOG_FORM_IMAGE_SUBMIT_BTN_XPATH)
                except Exception as xpath_err:
                    logger.warning(f"XPathでの登録ボタンのクリックにも失敗しました: {xpath_err}")
            
            logger.info("モーダルが閉じるのを待機します")
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f"画像アップロード中にエラーが発生しました: {e}"); return False

    def select_stylist(self, stylist_id):
        """スタイリストを選択する"""
        try:
            # 定数を使用
            self.page.select_option(self._BLOG_FORM_STYLIST_SELECT, stylist_id)
            return True
        except Exception as e:
            logger.error(f"スタイリスト選択中にエラーが発生しました: {e}"); return False

    def select_coupon(self, coupon_names):
        """クーポンを選択する (filterメソッド使用版)"""
        try:
            # 定数を使用
            coupon_button_selector = self._BLOG_FORM_COUPON_BTN
            coupon_modal_selectors = [self._BLOG_FORM_COUPON_MODAL_PRIMARY, self._BLOG_FORM_COUPON_MODAL_ALT]

            logger.info(f"クーポン選択ボタン ({coupon_button_selector}) を待機します")
            try:
                coupon_button = self.page.locator(coupon_button_selector)
                coupon_button.wait_for(state="visible", timeout=10000)
            except TimeoutError:
                logger.error(f"クーポン選択ボタン ({coupon_button_selector}) が表示されませんでした")
                self.page.screenshot(path="coupon_button_not_visible.png"); return False

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
                         self.page.screenshot(path="coupon_button_click_failed.png"); return False
            if not clicked: logger.error("クーポン選択ボタンをクリックできませんでした。"); return False

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
                 self.page.screenshot(path="coupon_modal_timeout_screenshot.png"); return False

            logger.info("クーポン選択処理を開始します (filter使用)")
            all_coupons_selected = True
            for coupon_name in coupon_names:
                logger.info(f"クーポン '{coupon_name}' を選択します")
                found_and_clicked = False
                cleaned_coupon_name = coupon_name.strip()
                if not cleaned_coupon_name: logger.warning("空のクーポン名のためスキップ"); continue
                try:
                    # 定数を使用
                    all_labels = self.page.locator(f"{coupon_modal_selectors[0]} {self._BLOG_FORM_COUPON_LABEL}")
                    logger.debug(f"モーダル内のラベル候補数: {all_labels.count()}")
                    for i in range(all_labels.count()):
                        label = all_labels.nth(i)
                        # 定数を使用
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
                        else: logger.debug(f"ラベル {i} に {self._BLOG_FORM_COUPON_TEXT} が見つかりません。")
                    if not found_and_clicked: logger.warning(f"クーポン '{cleaned_coupon_name}' がモーダル内で見つからないか、クリックできませんでした。")
                except Exception as e: logger.error(f"クーポン '{coupon_name}' の選択処理中に予期せぬエラー: {e}", exc_info=True)
                if not found_and_clicked: all_coupons_selected = False

            if not all_coupons_selected:
                 logger.error("一部またはすべてのクーポンの選択に失敗しました。")
                 self.page.screenshot(path="coupon_selection_error_screenshot.png")

            logger.info("「設定する」ボタンをクリックします")
            try:
                # 定数を使用
                setting_button_selector = self._BLOG_FORM_COUPON_SETTING_BTN
                setting_button = self.page.locator(setting_button_selector)
                setting_button.wait_for(state="visible", timeout=10000)
                if "is_disable" not in (setting_button.get_attribute("class") or ""):
                    logger.info("「設定する」ボタンが有効です。クリックします。")
                    setting_button.click(timeout=5000)
                else:
                     logger.warning("「設定する」ボタンが無効状態 (is_disable) です。クリックをスキップします。"); return False
            except Exception as e:
                logger.warning(f"標準セレクタでの設定ボタンのクリックに失敗しました: {e}")
                try:
                    # 定数を使用 (XPath)
                    alt_setting_button_selector = self._BLOG_FORM_COUPON_SETTING_BTN_XPATH
                    alt_setting_button = self.page.locator(alt_setting_button_selector)
                    alt_setting_button.wait_for(state="visible", timeout=5000)
                    if "is_disable" not in (alt_setting_button.get_attribute("class") or ""):
                        alt_setting_button.click(timeout=5000)
                        logger.info("代替セレクタで「設定する」ボタンをクリックしました。")
                    else:
                        logger.warning("代替セレクタでも「設定する」ボタンが無効状態です。"); return False
                except Exception as alt_e:
                    logger.error(f"代替方法での設定ボタンのクリックにも失敗しました: {alt_e}", exc_info=True)
                    self.page.screenshot(path="coupon_setting_button_click_error.png"); return False

            logger.info("モーダルが閉じるのを待機します")
            try:
                for selector in reversed(coupon_modal_selectors): 
                    try:
                        self.page.locator(selector).wait_for(state="hidden", timeout=10000)
                        logger.info(f"クーポン選択モーダル ({selector}) が閉じました"); break
                    except TimeoutError:
                         if selector == coupon_modal_selectors[0]: logger.warning("クーポン選択モーダルが閉じるのを待機中にタイムアウトしました。")
                    except Exception: pass 
            except Exception as wait_close_e: logger.warning(f"モーダルが閉じるのを待機中にエラー: {wait_close_e}")

            if not all_coupons_selected:
                logger.error("クーポン選択に失敗したため、処理全体を失敗とします。"); return False
            return True

        except Exception as e:
            logger.error(f"クーポン選択処理全体でエラーが発生しました: {e}", exc_info=True) 
            self.page.screenshot(path="coupon_selection_overall_error.png"); return False

    def post_blog(self, blog_data):
        """ブログを投稿する"""
        try:
            if not self.select_stylist(blog_data['stylist_id']): return False
            
            # 定数を使用
            self.page.select_option(self._BLOG_FORM_CATEGORY_SELECT, "BL02") # カテゴリIDは固定値のまま
            self.page.fill(self._BLOG_FORM_TITLE_INPUT, blog_data['title'])
            
            full_content = blog_data['content']
            if blog_data.get('template'): full_content += "\\n\\n" + blog_data['template']
            if not self.set_rich_text_content(full_content): return False
            
            if blog_data.get('image_paths'):
                for image_path in blog_data['image_paths']:
                    if not self.upload_image(image_path):
                        logger.warning(f"画像 '{image_path}' のアップロードに失敗しました。続行します。")
            
            if blog_data.get('coupon_names') and len(blog_data['coupon_names']) > 0:
                if not self.select_coupon(blog_data['coupon_names']): return False
            
            # 定数を使用
            logger.info(f"「確認する」ボタン ({self._BLOG_CONFIRM_BTN}) をクリックします")
            try:
                confirm_button = self.page.locator(self._BLOG_CONFIRM_BTN)
                confirm_button.wait_for(state="visible", timeout=10000) 
                confirm_button.click(timeout=5000)
                logger.info("「確認する」ボタンをクリックしました")
            except Exception as confirm_err:
                 logger.error(f"「確認する」ボタンのクリックに失敗: {confirm_err}", exc_info=True)
                 self.page.screenshot(path="confirm_button_click_error.png"); return False

            # 定数を使用
            unreflect_button_selector = self._BLOG_UNREFLECT_BTN
            logger.info(f"確認ページ（「登録・未反映にする」ボタン {unreflect_button_selector}）の表示を待機します") 
            try:
                self.page.wait_for_selector(unreflect_button_selector, state="visible", timeout=60000)
                logger.info("確認ページの表示（「登録・未反映にする」ボタンの存在）を確認しました")
            except TimeoutError:
                logger.error("確認ページの表示がタイムアウトしました (「登録・未反映にする」ボタンが見つかりません)")
                self.page.screenshot(path="unreflect_page_timeout.png"); return False

            if self.is_robot_detection_present():
                logger.error("確認ページでロボット認証が検出されました。処理を中断します。"); return False
                
            logger.info(f"「登録・未反映にする」ボタン ({unreflect_button_selector}) をクリックします")
            try:
                 unreflect_button = self.page.locator(unreflect_button_selector)
                 unreflect_button.click(timeout=10000)
                 logger.info("「登録・未反映にする」ボタンをクリックしました")
            except Exception as unreflect_err:
                 logger.error(f"「登録・未反映にする」ボタンのクリックに失敗: {unreflect_err}", exc_info=True)
                 self.page.screenshot(path="unreflect_button_click_error.png"); return False

            # 定数を使用
            back_button_selector = self._BLOG_BACK_BTN
            logger.info(f"「ブログ一覧へ」ボタン ({back_button_selector}) を待機し、クリックします")
            try:
                back_button = self.page.locator(back_button_selector)
                back_button.wait_for(state="visible", timeout=30000)
                logger.info("「ブログ一覧へ」ボタンが表示されました。クリックします。")
                back_button.click(timeout=10000)
                logger.info("「ブログ一覧へ」ボタンをクリックしました。")
            except Exception as back_err:
                logger.warning(f"「ブログ一覧へ」ボタンのクリックに失敗しました（処理は続行される可能性があります）: {back_err}", exc_info=True)
                self.page.screenshot(path="back_button_click_error.png")
            
            # 定数を使用 (完了確認は新規投稿ボタンの再表示で行う)
            logger.info(f"ブログ一覧ページへの遷移（例: {self._NAVI_NEW_POST} ボタンの再表示）を待機します") 
            try:
                self.page.wait_for_selector(self._NAVI_NEW_POST, state="visible", timeout=60000)
                logger.info("ブログ一覧ページへの遷移（または完了状態）を確認しました")
            except TimeoutError:
                logger.warning("ブログ一覧ページへの遷移確認がタイムアウトしました。成功した可能性もあります。")
                self.page.screenshot(path="unreflect_complete_timeout.png")
            
            if self.is_robot_detection_present(): logger.warning("処理完了後（？）にロボット認証が検出されました。")

            logger.info("ブログの「登録・未反映」処理が完了しました")
            return True
            
        except Exception as e:
            logger.error(f"ブログ投稿処理（未反映登録）中にエラーが発生しました: {e}", exc_info=True)
            try: self.page.screenshot(path="post_blog_unreflect_error.png")
            except Exception as ss_err: logger.error(f"エラー時のスクリーンショット撮影に失敗: {ss_err}")
            return False

    # --- Private Step Methods for execute_post Flow ---

    def _step_login(self, user_id, password):
        """Execute post step: Perform login."""
        logger.info("ステップ1/3: サロンボードへのログインを開始します。")
        if not self.login(user_id, password):
            logger.error("ログインステップで失敗しました。処理を中断します。")
            return False
        logger.info("ステップ1/3: ログイン成功。")
        return True

    def _step_navigate_to_blog_form(self):
        """Execute post step: Navigate to the blog posting form."""
        logger.info("ステップ2/3: ブログ投稿ページへの移動を開始します。")
        if not self.navigate_to_blog_post_page():
            logger.error("ブログ投稿ページへの移動ステップで失敗しました。処理を中断します。")
            return False
        logger.info("ステップ2/3: ブログ投稿ページへの移動成功。")
        return True

    def _step_post_blog_data(self, blog_data):
        """Execute post step: Fill form and post blog data."""
        logger.info("ステップ3/3: ブログデータの入力と投稿（未反映登録）を開始します。")
        if not self.post_blog(blog_data):
            logger.error("ブログデータの入力・投稿ステップで失敗しました。")
            return False
        logger.info("ステップ3/3: ブログデータの入力・投稿（未反映登録）成功。")
        return True

    # --- Public Method ---

    def execute_post(self, user_id, password, blog_data):
        """
        サロンボードへのログインからブログ投稿までの一連の処理を実行
        
        Args:
            user_id (str): サロンボードのユーザーID
            password (str): サロンボードのパスワード
            blog_data (dict): ブログ投稿に必要なデータ
                
        Returns:
            bool or dict: 成功でTrue、失敗でFalse。成功時はスクリーンショットのパスを含む辞書を返す。
                         ロボット認証検出時は失敗でもスクリーンショットのパスを含む辞書を返す。
        """
        success = False
        screenshot_path = None
        robot_detected = False
        start_time = time.time()
        logger.info("=== Salon Boardブログ投稿処理 開始 ===")
        try:
            # --- 1. ブラウザ起動 ---
            if not self.start(): 
                # start内でエラーログ出力済み
                return False 
            
            # --- 2. ログイン実行 ---
            login_result = self._step_login(user_id, password)
            if not login_result:
                # _step_login内でエラーログ出力済み
                # ロボット認証か確認
                if self.is_robot_detection_present():
                    robot_detected = True
                    logger.error("ログイン中にロボット認証が検出されました")
                    # スクリーンショットを撮影
                    try:
                        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'robot_auth_screenshot_{int(time.time())}.png')
                        self.page.screenshot(path=screenshot_path)
                        logger.info(f"ロボット認証のスクリーンショットを保存しました: {screenshot_path}")
                    except Exception as ss_err:
                        logger.error(f"ロボット認証のスクリーンショット撮影時にエラー: {ss_err}")
                        screenshot_path = None
                return {'success': False, 'robot_detected': True, 'screenshot_path': screenshot_path} if screenshot_path else False
            
            # --- 3. ブログ投稿ページへ移動 ---
            if not self._step_navigate_to_blog_form():
                # _step_navigate_to_blog_form内でエラーログ出力済み
                # ロボット認証か確認
                if self.is_robot_detection_present():
                    robot_detected = True
                    logger.error("ページ移動中にロボット認証が検出されました")
                    # スクリーンショットを撮影
                    try:
                        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'robot_auth_screenshot_{int(time.time())}.png')
                        self.page.screenshot(path=screenshot_path)
                        logger.info(f"ロボット認証のスクリーンショットを保存しました: {screenshot_path}")
                    except Exception as ss_err:
                        logger.error(f"ロボット認証のスクリーンショット撮影時にエラー: {ss_err}")
                        screenshot_path = None
                return {'success': False, 'robot_detected': True, 'screenshot_path': screenshot_path} if screenshot_path else False
            
            # --- 4. ブログデータ入力・投稿 --- 
            if not self._step_post_blog_data(blog_data):
                # _step_post_blog_data内でエラーログ出力済み
                # ロボット認証か確認
                if self.is_robot_detection_present():
                    robot_detected = True
                    logger.error("ブログデータ入力・投稿中にロボット認証が検出されました")
                    # スクリーンショットを撮影
                    try:
                        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'robot_auth_screenshot_{int(time.time())}.png')
                        self.page.screenshot(path=screenshot_path)
                        logger.info(f"ロボット認証のスクリーンショットを保存しました: {screenshot_path}")
                    except Exception as ss_err:
                        logger.error(f"ロボット認証のスクリーンショット撮影時にエラー: {ss_err}")
                        screenshot_path = None
                return {'success': False, 'robot_detected': True, 'screenshot_path': screenshot_path} if screenshot_path else False
            
            # 全てのステップが成功した場合
            success = True
            logger.info("=== Salon Boardブログ投稿処理 正常終了 ===")
            
            # 成功時にスクリーンショットを撮る
            try:
                # ページのレンダリングが完了するまで待機（2秒）
                logger.info("スクリーンショット撮影前に2秒待機します...")
                time.sleep(2)
                
                screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'success_screenshot_{int(time.time())}.png')
                self.page.screenshot(path=screenshot_path)
                logger.info(f"投稿成功後のスクリーンショットを保存しました: {screenshot_path}")
            except Exception as ss_err:
                logger.error(f"スクリーンショット撮影時にエラー: {ss_err}")
                screenshot_path = None
            
        except Exception as e:
            #予期せぬエラーのキャッチ
            logger.error(f"ブログ投稿処理の予期せぬエラー: {e}", exc_info=True)
            success = False
            
            # ロボット認証か確認
            if self.page and self.is_robot_detection_present():
                robot_detected = True
                logger.error("予期せぬエラー時にロボット認証が検出されました")
                # スクリーンショットを撮影
                try:
                    screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'robot_auth_screenshot_{int(time.time())}.png')
                    self.page.screenshot(path=screenshot_path)
                    logger.info(f"ロボット認証のスクリーンショットを保存しました: {screenshot_path}")
                except Exception as ss_err:
                    logger.error(f"ロボット認証のスクリーンショット撮影時にエラー: {ss_err}")
                    screenshot_path = None
            # エラー発生時にもスクリーンショットを試みる（ロボット認証でない場合）
            elif self.page and not robot_detected:
                try: 
                    error_screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', f'error_screenshot_{int(time.time())}.png')
                    self.page.screenshot(path=error_screenshot_path)
                    logger.info(f"エラー時のスクリーンショットを保存しました: {error_screenshot_path}")
                    screenshot_path = error_screenshot_path
                except Exception as ss_err: 
                    logger.error(f"予期せぬエラー時のスクリーンショット撮影失敗: {ss_err}")
        finally:
            # --- 5. ブラウザ終了 ---
            logger.info("ブラウザを終了します。")
            self.close()
            end_time = time.time()
            logger.info(f"処理時間: {end_time - start_time:.2f} 秒")
        
        # 結果を返す
        if robot_detected and screenshot_path:
            return {
                'success': False,
                'robot_detected': True,
                'screenshot_path': screenshot_path
            }
        elif success and screenshot_path:
            return {
                'success': True,
                'screenshot_path': screenshot_path
            }
        return success 