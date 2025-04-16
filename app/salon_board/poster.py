import os
import time
import logging
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError
import re
import json

logger = logging.getLogger(__name__)

class SalonBoardPoster:
    """サロンボードへのブログ投稿を自動化するクラス"""

    def __init__(self, headless=False, slow_mo=100):
        """
        初期化メソッド
        
        Args:
            headless (bool): ヘッドレスモードで実行するかどうか。デフォルトはFalse（ブラウザ表示あり）。
            slow_mo (int): アクションの間に入れる遅延時間（ミリ秒）。デバッグ時に視認性を高めるため。
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser = None
        self.page = None
        self.login_url = "https://salonboard.com/login/"
        self.default_timeout = 180000  # デフォルトのタイムアウトを180秒に設定
        self.max_retries = 3  # 追加: 最大再試行回数を設定

    def start(self):
        """Playwrightとブラウザを起動（自動化隠蔽強化版）"""
        try:
            self.playwright = sync_playwright().start()
            
            # 自動化回避のためのオプションを強化
            launch_args = [
                "--disable-blink-features=AutomationControlled",  # 重要: 自動化検出を回避
                "--disable-infobars",                         # 「自動テスト...」のバーを非表示
                "--disable-extensions",
                "--disable-dev-shm-usage", 
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                # "--start-maximized" # ヘッドレスでは不要な場合あり
                # "--window-size=1920,1080" # viewport設定でカバー
            ]
            
            # ユーザーデータディレクトリを指定して永続コンテキストを使うことも検討できるが、
            # まずは通常のコンテキストで隠蔽を試みる
            # self.browser = self.playwright.chromium.launch_persistent_context(...) 

            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo, # slow_mo は検知回避に役立つ場合がある
                args=launch_args
            )
            
            # 一般的なブラウザの特性を持つコンテキストを作成
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", # より新しいバージョンに更新
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                # accept_downloads=True, # 必要に応じて
                # geolocation={"longitude": 139.6917, "latitude": 35.6895}, # 必要に応じて
                permissions=['geolocation'] # 必要に応じて通知などの権限も設定
            )
            
            # JavaScript実行前の初期設定（自動化を隠す）
            # navigator.webdriver を偽装
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            # その他の検知ポイントを偽装 (例: プラグイン、言語など)
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
                        // UNMASKED_VENDOR_WEBGL と UNMASKED_RENDERER_WEBGL を偽装
                        if (parameter === 37445) { // VENDOR
                            return 'Google Inc. (Intel)';
                        }
                        if (parameter === 37446) { // RENDERER
                            return 'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 640, OpenGL 4.1)';
                        }
                        return getParameter.call(this, parameter);
                    };
                } catch (e) {
                    console.error('WebGL spoofing failed:', e);
                }
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
        # よく使われるCAPTCHAのセレクタをチェック
        selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='captcha']",
            "div.g-recaptcha",
            ".captcha-container",
            "#captcha",
            "input[name*='captcha']",
            "[aria-label*='ロボット']",
            "[aria-label*='認証']"
        ]
        
        for selector in selectors:
            try:
                if self.page.query_selector(selector):
                    logger.warning(f"ロボット認証が検出されました: {selector}")
                    return True
            except:
                continue
                
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
            # ログインページに移動する前に、ページに到着したら実行するJavaScriptを準備
            # これにより、ウィジェットが表示される前に非表示にする処理を仕込む
            self.page.add_init_script("""
                // MutationObserverを使用してDOM変更を監視し、ウィジェットを即座に非表示にする
                (function() {
                    function hideKarteWidgets() {
                        // karteウィジェットの候補となるセレクタ
                        const selectors = [
                            '.karte-widget__container',
                            '[class*="_reception-Skin"]',
                            '[class*="_reception-MinimumWidget"]',
                            '[id^="karte-"]'
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {
                                console.log('Hiding karte widget:', el);
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                                el.style.opacity = '0';
                            }
                        }
                    }
                    
                    // 初期実行
                    setTimeout(hideKarteWidgets, 500);
                    
                    // DOM変更を監視して実行
                    const observer = new MutationObserver((mutations) => {
                        hideKarteWidgets();
                    });
                    
                    // ページ読み込み完了後にオブザーバーを設定
                    if (document.readyState === 'loading') {
                        document.addEventListener('DOMContentLoaded', () => {
                            observer.observe(document.body, { childList: true, subtree: true });
                            hideKarteWidgets();
                        });
                    } else {
                        observer.observe(document.body, { childList: true, subtree: true });
                        hideKarteWidgets();
                    }
                })();
            """)
            
            # ログインページに移動
            logger.info(f"ログインページ({self.login_url})に移動します")
            self.page.goto(self.login_url, wait_until="networkidle")
            logger.info("ログインページの読み込みが完了しました")
            
            # 少し待機してページが完全に読み込まれるのを待つ
            time.sleep(2)
            
            # ウィジェットを強制的に非表示にする（追加分）
            try:
                # 変更: 要素の存在をチェックするシンプルな方法に変更
                widget_exists = False
                widget_selectors = [
                    '.karte-widget__container',
                    '[class*="_reception-Skin"]',
                    '[class*="_reception-MinimumWidget"]',
                    '[id^="karte-"]'
                ]
                
                for selector in widget_selectors:
                    try:
                        # タイムアウトを短く設定して存在チェック（100ms）
                        # ノンブロッキングでチェックするため待ち時間を最小化
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
                    self.page.evaluate("""
                        const selectors = [
                            '.karte-widget__container',
                            '[class*="_reception-Skin"]',
                            '[class*="_reception-MinimumWidget"]',
                            '[id^="karte-"]'
                        ];
                        
                        for (const selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            for (const el of elements) {
                                console.log('Force hiding widget:', el);
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                                el.style.opacity = '0';
                            }
                        }
                    """)
                    logger.info("ウィジェットの強制非表示を実行しました")
                else:
                    logger.info("ウィジェットは検出されませんでした。非表示処理はスキップします。")
            except Exception as e:
                logger.warning(f"ウィジェットの強制非表示中にエラー: {e}")
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("ログイン時にロボット認証が検出されました。処理を中断します。")
                return False
            
            # フォームの存在のみチェック（visible状態は要求しない）
            logger.info("入力フィールドを検索します")
            
            # --- ここから完全にJavaScriptでログイン処理を実行 ---
            js_login_script = f"""
            (function() {{
                try {{
                    // ユーザーIDとパスワードをセット
                    const userIdInput = document.querySelector("input[name='userId']");
                    const pwInput = document.querySelector("#jsiPwInput") || document.querySelector("input[name='password']");
                    
                    if (!userIdInput || !pwInput) {{
                        console.error('Login inputs not found');
                        return false;
                    }}
                    
                    // 値を設定
                    userIdInput.value = "{user_id}";
                    pwInput.value = "{password}";
                    
                    // イベントを発火
                    userIdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    pwInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    
                    // 強制的にフォーム送信（複数の方法を試す）
                    const loginForm = document.querySelector("#idPasswordInputForm");
                    const loginButton = document.querySelector("#idPasswordInputForm > div > div > a") || 
                                      document.querySelector("a.common-CNCcommon__primaryBtn.loginBtnSize");
                    
                    if (loginButton) {{
                        // 1. まずボタンクリックを試みる
                        console.log('Clicking login button via JS');
                        loginButton.click();
                        
                        // 念のため少し待って再度クリック
                        setTimeout(() => {{
                            try {{
                                loginButton.click();
                            }} catch (e) {{}}
                        }}, 500);
                    }}
                    
                    if (loginForm) {{
                        // 2. フォーム送信も試みる
                        setTimeout(() => {{
                            try {{
                                console.log('Submitting form via JS');
                                loginForm.submit();
                            }} catch (e) {{}}
                        }}, 1000);
                    }}
                    
                    return true;
                }} catch (e) {{
                    console.error('JS login error:', e);
                    return false;
                }}
            }})()
            """
            
            # JavaScriptによるログイン実行
            logger.info("JavaScriptを使用してログイン処理を実行します")
            login_result = self.page.evaluate(js_login_script)
            
            if not login_result:
                logger.error("JavaScriptによるログイン処理に失敗しました")
                self.page.screenshot(path="js_login_error.png")
                
                # 通常の方法も試してみる（バックアップとして既存のコードを残す）
                logger.info("通常の方法でログインを試みます")
                
                # ユーザーID入力 - JavaScriptによる直接操作
                logger.info(f"ユーザーID '{user_id}' を入力します")
                id_input_success = self._set_input_value_by_js("input[name='userId']", user_id)
                
                if not id_input_success:
                    logger.error("ユーザーID入力に失敗しました")
                    self.page.screenshot(path="id_input_error.png")
                    return False
                
                # パスワード入力 - JavaScriptによる直接操作
                logger.info("パスワードを入力します")
                password_input_success = self._set_input_value_by_js("#jsiPwInput", password)
                
                if not password_input_success:
                    # 代替セレクタを試す
                    logger.info("代替セレクタでパスワード入力を試みます")
                    password_input_success = self._set_input_value_by_js("input[name='password']", password)
                    
                if not password_input_success:
                    logger.error("パスワード入力に失敗しました")
                    self.page.screenshot(path="password_input_error.png")
                    return False
                
                # 入力値を確認
                time.sleep(1)  # 入力完了を待つ
                logger.info("ログインボタンをクリックします")
                
                # ログインボタンクリック
                login_click_success = self._click_element_by_js("#idPasswordInputForm > div > div > a")
                
                if not login_click_success:
                    # 代替セレクタを試す
                    logger.info("代替セレクタでログインボタンクリックを試みます")
                    login_click_success = self._click_element_by_js("a.common-CNCcommon__primaryBtn.loginBtnSize")
                    
                if not login_click_success:
                    # フォーム送信を試す
                    logger.info("フォーム送信を試みます")
                    form_submit_success = self._submit_form_by_js("#idPasswordInputForm")
                    
                    if not form_submit_success:
                        logger.error("ログインボタンのクリックに失敗しました")
                        self.page.screenshot(path="login_button_error.png")
                        return False
            else:
                logger.info("JavaScriptによるログイン処理が成功しました")
            
            # ダッシュボードが表示されるまで待機
            logger.info("ダッシュボードの表示を待機します...")
            try:
                self.page.wait_for_selector("#globalNavi", timeout=self.default_timeout, state="visible")
                logger.info("ダッシュボードの表示を確認しました")
            except TimeoutError as e:
                # タイムアウトした場合、現在のURLとタイトルを記録
                current_url = self.page.url
                current_title = self.page.title()
                logger.error(f"ログイン後のダッシュボード表示がタイムアウトしました。現在のURL: {current_url}, タイトル: {current_title}")
                
                # スクリーンショット撮影
                self.page.screenshot(path="login_timeout_screenshot.png")
                return False
                
            # ログイン後にロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("ログイン後にロボット認証が検出されました。処理を中断します。")
                return False
                
            logger.info("サロンボードへのログインに成功しました")
            return True
            
        except Exception as e:
            logger.error(f"ログイン処理中にエラーが発生しました: {e}")
            # スクリーンショット撮影
            self.page.screenshot(path="login_error_screenshot.png")
            return False
            
    def _set_input_value_by_js(self, selector, value):
        """JavaScriptを使用して入力フィールドに値を設定する内部メソッド"""
        try:
            # セレクタが存在するか確認
            if not self.page.query_selector(selector):
                logger.warning(f"セレクタ '{selector}' が見つかりません")
                return False
                
            # JavaScriptを使用して値を設定
            js_script = f"""
            (function() {{
                var el = document.querySelector("{selector.replace('"', '\\"')}");
                if (el) {{
                    el.value = "{value}";
                    // イベントを発火させる
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
            
    def _click_element_by_js(self, selector):
        """JavaScriptを使用して要素をクリックする内部メソッド"""
        try:
            # セレクタが存在するか確認
            if not self.page.query_selector(selector):
                logger.warning(f"セレクタ '{selector}' が見つかりません")
                return False
                
            # まず通常のクリックを試す
            try:
                self.page.click(selector)
                logger.info(f"セレクタ '{selector}' を使用して要素をクリックしました")
                return True
            except Exception as click_err:
                logger.warning(f"通常クリックに失敗: {click_err}")
                
                # JavaScriptを使用してクリック
                js_script = f"""
                (function() {{
                    var el = document.querySelector("{selector.replace('"', '\\"')}");
                    if (el) {{
                        el.click();
                        return true;
                    }}
                    return false;
                }})()
                """
                result = self.page.evaluate(js_script)
                
                if result:
                    logger.info(f"JavaScriptを使用して要素をクリックしました: {selector}")
                    return True
                    
                return False
        except Exception as e:
            logger.warning(f"JavaScriptによるクリック中にエラー: {e}")
            return False
            
    def _submit_form_by_js(self, form_selector):
        """JavaScriptを使用してフォームを送信する内部メソッド"""
        try:
            js_script = f"""
            (function() {{
                var form = document.querySelector("{form_selector.replace('"', '\\"')}");
                if (form) {{
                    form.submit();
                    return true;
                }}
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
        """
        ブログ投稿ページに移動する
        
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"ブログ投稿ページへの移動を試行中... (試行 {attempt+1}/{self.max_retries})")
                
                # 「掲載管理」ボタンのセレクタ
                keisai_kanri_selector = "#globalNavi > ul.common-CLPcommon__globalNavi > li:nth-child(2) > a"

                # --- 「掲載管理」ボタンクリック処理の改善 ---
                logger.info(f"「掲載管理」ボタン ({keisai_kanri_selector}) を待機し、クリックします")
                try:
                    # ボタンが表示され、有効になるまで待機 (タイムアウトを少し長めに設定)
                    self.page.wait_for_selector(
                        keisai_kanri_selector, 
                        state="visible", 
                        timeout=60000 # ダッシュボード読み込み完了まで待つため長めに
                    )
                    logger.info("「掲載管理」ボタンが表示されました")

                    # Locatorを使用してクリック (より推奨される方法)
                    keisai_kanri_button = self.page.locator(keisai_kanri_selector)
                    
                    # クリック前に要素を確実に表示させる
                    keisai_kanri_button.scroll_into_view_if_needed()
                    time.sleep(1) # スクロールや描画の安定待ち

                    # クリック実行
                    keisai_kanri_button.click(timeout=10000) # クリック自体のタイムアウト
                    logger.info("「掲載管理」ボタンをクリックしました (Locator)")

                except Exception as click_err:
                    logger.warning(f"Locatorによる「掲載管理」ボタンのクリックに失敗: {click_err}。JavaScriptでのクリックを試みます。")
                    try:
                        # JavaScriptでクリックするフォールバック
                        self.page.evaluate(f"document.querySelector('{keisai_kanri_selector}').click()")
                        logger.info("「掲載管理」ボタンをクリックしました (JavaScript)")
                    except Exception as js_click_err:
                        logger.error(f"JavaScriptによる「掲載管理」ボタンのクリックにも失敗: {js_click_err}")
                        # エラーが続く場合は再試行ループへ
                        if attempt < self.max_retries - 1:
                            logger.warning(f"「掲載管理」ボタンのクリックに失敗しました。再試行します... ({attempt+1}/{self.max_retries})")
                            time.sleep(3) # 再試行前に少し待つ
                            continue
                        else:
                            self.page.screenshot(path="keisai_kanri_click_error.png")
                            return False
                # --- 「掲載管理」ボタンクリック処理の改善 終了 ---

                # ネットワークアクティビティが落ち着くまで待機 (クリック後のページ遷移完了を待つ)
                logger.info("掲載管理ページへの遷移（ネットワークアイドル）を待機します")
                self.page.wait_for_load_state("networkidle", timeout=60000) 
                logger.info("掲載管理ページの読み込みが完了しました")

                # ロボット認証が検出されたら中断
                if self.is_robot_detection_present():
                    logger.error("掲載管理ページでロボット認証が検出されました。処理を中断します。")
                    return False
                
                # 「ブログ」ボタンのセレクタ
                blog_button_selector = "#cmsForm > div > div > ul > li:nth-child(9) > a"
                
                # 「ブログ」ボタンをクリック
                logger.info(f"「ブログ」ボタン ({blog_button_selector}) を待機し、クリックします")
                try:
                    self.page.wait_for_selector(
                        blog_button_selector, 
                        state="visible", 
                        timeout=30000
                    )
                    # Locator使用を推奨するが一貫性のためpage.clickでも可
                    self.page.locator(blog_button_selector).click(timeout=10000)
                    logger.info("「ブログ」ボタンをクリックしました")

                except Exception as blog_click_err:
                     logger.error(f"「ブログ」ボタンのクリックに失敗: {blog_click_err}")
                     if attempt < self.max_retries - 1:
                         logger.warning(f"「ブログ」ボタンのクリックに失敗しました。再試行します... ({attempt+1}/{self.max_retries})")
                         time.sleep(3)
                         continue
                     else:
                         self.page.screenshot(path="blog_button_click_error.png")
                         return False

                # ネットワークアクティビティが落ち着くまで待機
                logger.info("ブログ管理ページへの遷移（ネットワークアイドル）を待機します")
                self.page.wait_for_load_state("networkidle", timeout=60000)
                logger.info("ブログ管理ページの読み込みが完了しました")
                
                # ロボット認証が検出されたら中断
                if self.is_robot_detection_present():
                    logger.error("ブログ管理ページでロボット認証が検出されました。処理を中断します。")
                    return False
                
                # 「新規投稿」ボタンのセレクタ
                new_post_button_selector = "#newPosts"

                # 「新規投稿」ボタンをクリック
                logger.info(f"「新規投稿」ボタン ({new_post_button_selector}) を待機し、クリックします")
                try:
                    self.page.wait_for_selector(new_post_button_selector, state="visible", timeout=30000)
                    self.page.locator(new_post_button_selector).click(timeout=10000)
                    logger.info("「新規投稿」ボタンをクリックしました")

                except Exception as new_post_click_err:
                    logger.error(f"「新規投稿」ボタンのクリックに失敗: {new_post_click_err}")
                    if attempt < self.max_retries - 1:
                         logger.warning(f"「新規投稿」ボタンのクリックに失敗しました。再試行します... ({attempt+1}/{self.max_retries})")
                         time.sleep(3)
                         continue
                    else:
                         self.page.screenshot(path="new_post_button_click_error.png")
                         return False

                # ネットワークアクティビティが落ち着くまで待機
                logger.info("新規投稿ページへの遷移（ネットワークアイドル）を待機します")
                self.page.wait_for_load_state("networkidle", timeout=60000)
                logger.info("新規投稿ページの読み込みが完了しました")
                
                # 投稿フォームの主要要素（スタイリスト選択）が表示されるまで待機
                logger.info("ブログ投稿フォームの主要素 (select#stylistId) を待機します")
                try:
                    self.page.wait_for_selector("select#stylistId", state="visible", timeout=60000)
                    logger.info("ブログ投稿フォームの表示を確認しました")
                except TimeoutError:
                    # 最終試行でなければ再試行
                    if attempt < self.max_retries - 1:
                        logger.warning(f"ブログ投稿フォームの表示がタイムアウトしました。再試行します... ({attempt+1}/{self.max_retries})")
                        # 念のためダッシュボードに戻って再試行
                        try:
                            logger.info("ダッシュボードに戻ります...")
                            self.page.goto("https://salonboard.com/main/", wait_until="networkidle", timeout=60000)
                        except Exception as goto_err:
                            logger.warning(f"ダッシュボードへの移動に失敗: {goto_err}")
                            time.sleep(5) # 失敗したら少し長めに待つ
                        continue
                    else:
                        logger.error(f"ブログ投稿フォームの表示が{self.max_retries}回タイムアウトしました。処理を中断します。")
                        # 現在の状態をスクリーンショット
                        self.page.screenshot(path="blog_form_timeout.png")
                        return False
                
                # ロボット認証が検出されたら中断
                if self.is_robot_detection_present():
                    logger.error("新規投稿ページでロボット認証が検出されました。処理を中断します。")
                    return False
                    
                logger.info("ブログ投稿ページへの移動に成功しました")
                return True # 成功したらループを抜ける
                
            except Exception as e:
                # 最終試行でなければ再試行
                if attempt < self.max_retries - 1:
                    logger.warning(f"ブログ投稿ページへの移動中に予期せぬエラーが発生しました: {e}。再試行します... ({attempt+1}/{self.max_retries})", exc_info=True)
                    time.sleep(5)  # 少し長めに待機してから再試行
                    # エラー発生時はダッシュボードに戻ることを試みる
                    try:
                        logger.info("エラー発生のため、ダッシュボードに戻ります...")
                        self.page.goto("https://salonboard.com/main/", wait_until="networkidle", timeout=60000)
                    except Exception as goto_err:
                        logger.warning(f"エラー後のダッシュボードへの移動に失敗: {goto_err}")
                        time.sleep(5)
                    continue
                else:
                    logger.error(f"ブログ投稿ページへの移動中に{self.max_retries}回エラーが発生しました: {e}", exc_info=True)
                    # 現在の状態をスクリーンショット
                    self.page.screenshot(path="blog_navigation_error.png")
                    return False
        
        # ループが完了しても成功しなかった場合 (通常はループ内でreturnされるはず)
        logger.error("最大再試行回数に達しましたが、ブログ投稿ページへの移動に失敗しました。")
        return False

    def set_rich_text_content(self, content):
        """
        nicEditリッチテキストエディタにコンテンツを設定する
        
        Args:
            content (str): 設定するHTML内容（またはプレーンテキスト）
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # content 文字列を適切にエスケープしてJSリテラルにする
            # テンプレートリテラル内で安全に使えるようにエスケープ
            escaped_content = content.replace('\\\\', '\\\\\\\\').replace('`', '\\`').replace('$', '\\$')
            
            # JavaScriptを使用してnicEditエディタの内容を設定
            # 変更: evaluateの第2引数を使わず、直接JSコードに埋め込む
            js_script = f"""
            (function() {{
                try {{
                    var editorInstance = nicEditors.findEditor('blogContents');
                    if (editorInstance) {{
                        // 確実に文字列として渡す
                        editorInstance.setContent(`{escaped_content}`); 
                        return true;
                    }} else {{
                        console.error('nicEdit editor instance not found for blogContents');
                        return false;
                    }}
                }} catch(e) {{
                    console.error('nicEdit操作エラー:', e);
                    return false;
                }}
            }})()
            """
            logger.debug(f"Executing nicEdit script with content: {escaped_content[:100]}...") # デバッグ用に最初の100文字だけログ出力
            result = self.page.evaluate(js_script) # evaluateの第2引数は削除
            
            if result:
                logger.info("JavaScriptを使用してnicEditに内容を設定しました")
                return True
            else:
                logger.warning("JavaScriptを使用したnicEditへの内容設定に失敗しました。代替手段を試みます。")
                # 代替手段: より直接的にiframeを操作
                try:
                    logger.info("代替方法でエディタに本文を設定します")
                    # nicEditが生成するiframeのセレクタを確認 (実際のサイトで確認が必要な場合あり)
                    iframe_selector = "iframe[id^='nicEdit']" # 一般的なnicEditのiframeセレクタ
                    iframe = self.page.frame_locator(iframe_selector) 
                    
                    if iframe.count() > 0: # iframeが存在するか確認
                        # iframe内のbody要素に直接コンテンツを設定 (fillはテキスト入力向き)
                        iframe.locator("body").fill(content) 
                        # 必要であればHTMLとして設定:
                        # iframe.locator("body").evaluate(f'element => element.innerHTML = `{escaped_content}`')
                        logger.info("iframe内のbodyに内容を設定しました")
                    else:
                        logger.warning(f"nicEditのiframe ({iframe_selector}) が見つかりません。通常のテキストエリアとして操作を試みます。")
                        # 通常のテキストエリアとして操作を試みる
                        self.page.fill("textarea#blogContents", content)
                        logger.info("textarea#blogContentsに内容を設定しました")
                    return True # 代替手段が成功したとみなす (エラーが出なければ)

                except Exception as inner_e:
                    logger.error(f"代替方法での本文設定中にエラー: {inner_e}", exc_info=True)
                    return False # 代替手段も失敗
                
        except Exception as e:
            logger.error(f"リッチテキストエディタの操作中にエラーが発生しました: {e}", exc_info=True)
            return False

    def upload_image(self, image_path):
        """
        画像をアップロードする
        
        Args:
            image_path (str): アップロードする画像のパス
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # 「画像アップロード」ボタンをクリック
            logger.info("画像アップロードボタンをクリックします")
            self.page.click("a#upload")
            
            # 画像アップロードモーダルの表示を待機
            try:
                logger.info("画像アップロードモーダルの表示を待機します")
                self.page.wait_for_selector("div.imageUploaderModal", timeout=10000)
            except TimeoutError:
                logger.error("画像アップロードモーダルの表示がタイムアウトしました")
                return False
            
            # ファイルインプットに画像を設定
            logger.info(f"画像ファイル {image_path} を選択します")
            self.page.set_input_files("input#sendFile", image_path)
            
            # 画像が選択されたことを確認
            try:
                logger.info("画像のサムネイルが表示されるのを待機します")
                self.page.wait_for_selector("img.imageUploaderModalThumbnail", timeout=20000, state="visible")
                # 登録するボタンが有効になるのを待つ
                self.page.wait_for_selector("input.imageUploaderModalSubmitButton.isActive", timeout=10000)
            except TimeoutError:
                logger.warning("画像サムネイルの表示確認がタイムアウトしました。処理を継続します。")
            
            # 登録するボタンをクリック
            logger.info("「登録する」ボタンをクリックします")
            try:
                self.page.click("input.imageUploaderModalSubmitButton")
            except Exception as button_err:
                logger.warning(f"標準セレクタでの登録ボタンのクリックに失敗しました: {button_err}")
                try:
                    # XPathを使用した代替アプローチ
                    self.page.click("//input[@value='登録する']")
                except Exception as xpath_err:
                    logger.warning(f"XPathでの登録ボタンのクリックにも失敗しました: {xpath_err}")
            
            # モーダルが閉じるのを待つ
            logger.info("モーダルが閉じるのを待機します")
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"画像アップロード中にエラーが発生しました: {e}")
            return False

    def select_stylist(self, stylist_id):
        """
        スタイリストを選択する
        
        Args:
            stylist_id (str): 選択するスタイリストのID
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # スタイリストドロップダウンからスタイリストを選択
            self.page.select_option("select#stylistId", stylist_id)
            return True
        except Exception as e:
            logger.error(f"スタイリスト選択中にエラーが発生しました: {e}")
            return False

    def select_coupon(self, coupon_names):
        """
        クーポンを選択する (filterメソッド使用版)
        
        Args:
            coupon_names (list): 選択するクーポン名のリスト
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            coupon_button_selector = "a.jsc_SB_modal_trigger"
            coupon_modal_selectors = ["div#couponWrap", "#couponArea"] # メインと代替セレクタ

            # --- クーポン選択ボタン クリック処理 (強化) ---
            logger.info(f"クーポン選択ボタン ({coupon_button_selector}) を待機します")
            try:
                coupon_button = self.page.locator(coupon_button_selector)
                coupon_button.wait_for(state="visible", timeout=10000)
                # クリック可能になるまで待機（例: enabled状態を待つ）
                # coupon_button.wait_for(state="enabled", timeout=5000) # 有効状態を待つ場合
            except TimeoutError:
                logger.error(f"クーポン選択ボタン ({coupon_button_selector}) が表示されませんでした")
                self.page.screenshot(path="coupon_button_not_visible.png")
                return False

            logger.info("クーポン選択ボタンをクリックします")
            clicked = False
            try:
                coupon_button.scroll_into_view_if_needed()
                time.sleep(0.5)
                coupon_button.click(timeout=5000)
                clicked = True
                logger.info("Playwrightのclickでクーポン選択ボタンをクリックしました")
            except Exception as e:
                logger.warning(f"Playwrightのclick失敗: {e}。他の方法を試みます。")
                try:
                    logger.info("JavaScript click を試行")
                    coupon_button.evaluate("node => node.click()")
                    clicked = True
                    logger.info("JavaScript clickでクーポン選択ボタンをクリックしました")
                except Exception as js_e:
                    logger.warning(f"JavaScript click失敗: {js_e}。dispatch_eventを試みます。")
                    try:
                        logger.info("dispatch_event('click') を試行")
                        coupon_button.dispatch_event('click')
                        clicked = True
                        logger.info("dispatch_event('click')でクーポン選択ボタンをクリックしました")
                    except Exception as dispatch_e:
                         logger.error(f"全てのクリック方法でクーポン選択ボタンのクリックに失敗: {dispatch_e}")
                         self.page.screenshot(path="coupon_button_click_failed.png")
                         return False

            if not clicked:
                 logger.error("クーポン選択ボタンをクリックできませんでした。")
                 return False

            # --- モーダル表示待機 (変更なし部分も含む) ---
            modal_visible = False
            logger.info(f"クーポン選択モーダルの表示を待機します (セレクタ: {coupon_modal_selectors})")
            start_time = time.time()
            while time.time() - start_time < self.default_timeout / 1000: # 設定されたタイムアウト時間まで待つ
                for selector in coupon_modal_selectors:
                    try:
                        # ページ上に存在し、かつ表示されているかを確認
                        if self.page.locator(selector).is_visible(timeout=1000): # 短いタイムアウトでチェック
                             logger.info(f"クーポン選択モーダル ({selector}) が表示されました")
                             modal_visible = True
                             break # モーダルが見つかったらループを抜ける
                    except Exception:
                        # is_visible でエラーが出ても無視して次のセレクタへ
                        continue
                if modal_visible:
                    break # モーダルが見つかったら待機ループも抜ける
                time.sleep(1) # 1秒待って再試行

            if not modal_visible:
                 logger.error(f"クーポン選択モーダルの表示がタイムアウトしました ({self.default_timeout}ms)")
                 self.page.screenshot(path="coupon_modal_timeout_screenshot.png")
                 return False

            # --- クーポン選択処理 (filterメソッド使用) ---
            logger.info("クーポン選択処理を開始します (filter使用)")
            all_coupons_selected = True
            for coupon_name in coupon_names:
                logger.info(f"クーポン '{coupon_name}' を選択します")
                found_and_clicked = False
                cleaned_coupon_name = coupon_name.strip()
                if not cleaned_coupon_name:
                    logger.warning("空のクーポン名のためスキップ")
                    continue

                try:
                    # モーダル内のすべてのラベルを取得
                    all_labels = self.page.locator(f"{coupon_modal_selectors[0]} label") # モーダルが表示されている前提
                    logger.debug(f"モーダル内のラベル候補数: {all_labels.count()}")

                    # 各ラベルをループしてテキストを比較
                    for i in range(all_labels.count()):
                        label = all_labels.nth(i)
                        # ラベル内のp.couponText要素を取得
                        coupon_text_element = label.locator("p.couponText")

                        if coupon_text_element.count() > 0:
                            # テキスト内容を取得して比較 (前後の空白無視、部分一致、大文字小文字無視)
                            actual_text = coupon_text_element.first.inner_text().strip()
                            logger.debug(f"ラベル {i} のテキスト: '{actual_text}'")
                            if cleaned_coupon_name.lower() in actual_text.lower():
                                logger.info(f"クーポン '{cleaned_coupon_name}' がテキスト '{actual_text}' にマッチしました。クリックを試みます。")
                                try:
                                    label.scroll_into_view_if_needed()
                                    time.sleep(0.5)
                                    label.click(timeout=5000)
                                    found_and_clicked = True
                                    logger.info(f"クーポン '{cleaned_coupon_name}' をクリックしました。")
                                    time.sleep(0.3)
                                    break # マッチしてクリックしたらこのクーポンのループは終了
                                except Exception as click_err:
                                     logger.warning(f"クーポン '{cleaned_coupon_name}' のクリックに失敗: {click_err}。念のため次の候補も探します。")
                                     # JavaScriptクリックなどを試すことも可能
                        else:
                             logger.debug(f"ラベル {i} に p.couponText が見つかりません。")

                    if not found_and_clicked:
                        logger.warning(f"クーポン '{cleaned_coupon_name}' がモーダル内で見つからないか、クリックできませんでした。")

                except Exception as e:
                    logger.error(f"クーポン '{coupon_name}' の選択処理中に予期せぬエラー: {e}", exc_info=True)

                if not found_and_clicked:
                     all_coupons_selected = False

            if not all_coupons_selected:
                 logger.error("一部またはすべてのクーポンの選択に失敗しました。")
                 self.page.screenshot(path="coupon_selection_error_screenshot.png")
                 # return False # 失敗しても設定ボタンは試す

            # --- 「設定する」ボタンクリック処理 (変更なし部分も含む) ---
            logger.info("「設定する」ボタンをクリックします")
            try:
                # ボタンが表示されるまで待つ
                setting_button_selector = "a.jsc_SB_modal_setting_btn"
                setting_button = self.page.locator(setting_button_selector)
                setting_button.wait_for(state="visible", timeout=10000) # 少し長めに待つ
                
                # is_disableクラスがないことを確認 (クリック可能か)
                if "is_disable" not in (setting_button.get_attribute("class") or ""):
                    logger.info("「設定する」ボタンが有効です。クリックします。")
                    setting_button.click(timeout=5000)
                else:
                     logger.warning("「設定する」ボタンが無効状態 (is_disable) です。クリックをスキップします。")
                     # クーポン選択に失敗している可能性が高い
                     return False # 設定できないので失敗とする

            except Exception as e:
                logger.warning(f"標準セレクタでの設定ボタンのクリックに失敗しました: {e}")
                try:
                    # 代替セレクタで試行
                    alt_setting_button_selector = "//a[contains(text(), '設定する')]"
                    alt_setting_button = self.page.locator(alt_setting_button_selector)
                    alt_setting_button.wait_for(state="visible", timeout=5000)
                    
                    if "is_disable" not in (alt_setting_button.get_attribute("class") or ""):
                        alt_setting_button.click(timeout=5000)
                        logger.info("代替セレクタで「設定する」ボタンをクリックしました。")
                    else:
                        logger.warning("代替セレクタでも「設定する」ボタンが無効状態です。")
                        return False

                except Exception as alt_e:
                    logger.error(f"代替方法での設定ボタンのクリックにも失敗しました: {alt_e}", exc_info=True)
                    self.page.screenshot(path="coupon_setting_button_click_error.png")
                    return False # 設定ボタンが押せない場合は失敗

            # モーダルが閉じるのを待つ
            logger.info("モーダルが閉じるのを待機します")
            try:
                # モーダルが非表示になるのを待つ
                for selector in reversed(coupon_modal_selectors): 
                    try:
                        self.page.locator(selector).wait_for(state="hidden", timeout=10000) # 閉じるのを長めに待つ
                        logger.info(f"クーポン選択モーダル ({selector}) が閉じました")
                        break
                    except TimeoutError:
                         if selector == coupon_modal_selectors[0]: 
                             logger.warning("クーポン選択モーダルが閉じるのを待機中にタイムアウトしました。")
                    except Exception:
                        pass 
            except Exception as wait_close_e:
                 logger.warning(f"モーダルが閉じるのを待機中にエラー: {wait_close_e}")

            # 変更: クーポン選択が1つでも失敗したら最終的にFalseを返すようにする
            if not all_coupons_selected:
                logger.error("クーポン選択に失敗したため、処理全体を失敗とします。")
                return False

            return True # 全て成功した場合のみTrue

        except Exception as e:
            logger.error(f"クーポン選択処理全体でエラーが発生しました: {e}", exc_info=True) 
            self.page.screenshot(path="coupon_selection_overall_error.png")
            return False

    def post_blog(self, blog_data):
        """
        ブログを投稿する
        
        Args:
            blog_data (dict): ブログ投稿に必要なデータ
                {
                    'title': ブログタイトル,
                    'content': ブログ本文,
                    'stylist_id': スタイリストID,
                    'image_paths': アップロードする画像パスのリスト,
                    'coupon_names': 選択するクーポン名のリスト,
                    'template': 追加するテンプレート内容
                }
                
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # スタイリスト選択
            if not self.select_stylist(blog_data['stylist_id']):
                return False
            
            # カテゴリ選択（「おすすめスタイル」固定）
            self.page.select_option("select#blogCategoryCd", "BL02")
            
            # タイトル入力
            self.page.fill("input#blogTitle", blog_data['title'])
            
            # 本文とテンプレートを結合
            full_content = blog_data['content']
            if blog_data.get('template'):
                full_content += "\n\n" + blog_data['template']
            
            # 本文をエディタに設定
            if not self.set_rich_text_content(full_content):
                return False
            
            # 画像のアップロード
            if blog_data.get('image_paths'):
                for image_path in blog_data['image_paths']:
                    if not self.upload_image(image_path):
                        logger.warning(f"画像 '{image_path}' のアップロードに失敗しました。続行します。")
            
            # クーポンの選択
            if blog_data.get('coupon_names') and len(blog_data['coupon_names']) > 0:
                if not self.select_coupon(blog_data['coupon_names']):
                    return False
            
            # 「確認する」ボタンをクリック
            logger.info("「確認する」ボタン (#confirm) をクリックします")
            try:
                confirm_button = self.page.locator("a#confirm")
                confirm_button.wait_for(state="visible", timeout=10000) 
                confirm_button.click(timeout=5000)
                logger.info("「確認する」ボタンをクリックしました")
            except Exception as confirm_err:
                 logger.error(f"「確認する」ボタンのクリックに失敗: {confirm_err}", exc_info=True)
                 self.page.screenshot(path="confirm_button_click_error.png")
                 return False

            # --- 変更箇所: 「登録・未反映にする」ボタンの処理 --- 
            # 確認ページ（「登録・未反映にする」ボタン）の表示を待機
            unreflect_button_selector = "a#unReflect"
            logger.info(f"確認ページ（「登録・未反映にする」ボタン {unreflect_button_selector}）の表示を待機します") 
            try:
                self.page.wait_for_selector(
                    unreflect_button_selector, 
                    state="visible", 
                    timeout=60000
                )
                logger.info("確認ページの表示（「登録・未反映にする」ボタンの存在）を確認しました")
            except TimeoutError:
                logger.error("確認ページの表示がタイムアウトしました (「登録・未反映にする」ボタンが見つかりません)")
                self.page.screenshot(path="unreflect_page_timeout.png") # スクショ追加
                return False

            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("確認ページでロボット認証が検出されました。処理を中断します。")
                return False
                
            # 「登録・未反映にする」ボタンをクリック
            logger.info(f"「登録・未反映にする」ボタン ({unreflect_button_selector}) をクリックします")
            try:
                 unreflect_button = self.page.locator(unreflect_button_selector)
                 unreflect_button.click(timeout=10000)
                 logger.info("「登録・未反映にする」ボタンをクリックしました")
            except Exception as unreflect_err:
                 logger.error(f"「登録・未反映にする」ボタンのクリックに失敗: {unreflect_err}", exc_info=True)
                 self.page.screenshot(path="unreflect_button_click_error.png")
                 return False

            # --- 追加箇所: 「ブログ一覧へ」ボタンの処理 --- 
            back_button_selector = "a#back"
            logger.info(f"「ブログ一覧へ」ボタン ({back_button_selector}) を待機し、クリックします")
            try:
                back_button = self.page.locator(back_button_selector)
                back_button.wait_for(state="visible", timeout=30000) # 少し待つ
                logger.info("「ブログ一覧へ」ボタンが表示されました。クリックします。")
                back_button.click(timeout=10000)
                logger.info("「ブログ一覧へ」ボタンをクリックしました。")
            except Exception as back_err:
                # このボタンは必須ではないかもしれないので、エラーは警告レベルに留める
                logger.warning(f"「ブログ一覧へ」ボタンのクリックに失敗しました（処理は続行される可能性があります）: {back_err}", exc_info=True)
                self.page.screenshot(path="back_button_click_error.png")
                # return False # ここでは処理を止めない
            # --- 追加箇所 終了 ---
            
            # 完了（ブログ一覧ページへの遷移など）を待機
            # 仮にブログ一覧ページに戻るとして、再度「新規投稿」ボタンが表示されるのを待つ
            # 実際の挙動に合わせて変更が必要な場合あり
            logger.info("ブログ一覧ページへの遷移（例: #newPosts ボタンの再表示）を待機します") 
            try:
                self.page.wait_for_selector("#newPosts", state="visible", timeout=60000)
                logger.info("ブログ一覧ページへの遷移（または完了状態）を確認しました")
            except TimeoutError:
                logger.warning("ブログ一覧ページへの遷移確認がタイムアウトしました。成功した可能性もあります。")
                self.page.screenshot(path="unreflect_complete_timeout.png")
                # タイムアウトしても成功とみなす場合があるため、ここでは return False しない
            
            # ロボット認証が再度検出されたら念のため報告 (通常は遷移後)
            if self.is_robot_detection_present():
                logger.warning("処理完了後（？）にロボット認証が検出されました。")
                # return False # 完了はしている可能性があるので中断しない

            # --- 変更箇所 終了 --- 
                
            logger.info("ブログの「登録・未反映」処理が完了しました")
            return True
            
        except Exception as e:
            logger.error(f"ブログ投稿処理（未反映登録）中にエラーが発生しました: {e}", exc_info=True) # エラーログ修正
            # 失敗時のスクリーンショット (メソッドの最後で撮るよりここで撮る方が状況が分かりやすい)
            try:
                self.page.screenshot(path="post_blog_unreflect_error.png")
            except Exception as ss_err:
                 logger.error(f"エラー時のスクリーンショット撮影に失敗: {ss_err}")
            return False

    def execute_post(self, user_id, password, blog_data):
        """
        サロンボードへのログインからブログ投稿までの一連の処理を実行
        
        Args:
            user_id (str): サロンボードのユーザーID
            password (str): サロンボードのパスワード
            blog_data (dict): ブログ投稿に必要なデータ
                
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        success = False
        
        try:
            # ブラウザを起動
            if not self.start():
                return False
            
            # サロンボードにログイン
            if not self.login(user_id, password):
                return False
            
            # ブログ投稿ページに移動
            if not self.navigate_to_blog_post_page():
                return False
            
            # ブログを投稿
            success = self.post_blog(blog_data)
            
        except Exception as e:
            logger.error(f"ブログ投稿処理全体でエラーが発生しました: {e}")
            success = False
            
        finally:
            # ブラウザを終了
            self.close()
            
        return success 