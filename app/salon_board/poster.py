import os
import time
import logging
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError

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
        self.default_timeout = 120000  # デフォルトのタイムアウトを120秒に設定

    def start(self):
        """Playwrightとブラウザを起動"""
        try:
            self.playwright = sync_playwright().start()
            
            # macOSの場合は特別なオプションを追加してブラウザを起動
            launch_args = [
                "--disable-dev-shm-usage",  # 共有メモリ使用を無効化（安定性向上）
                "--disable-gpu",            # GPUハードウェアアクセラレーションを無効化
                "--no-sandbox",             # サンドボックスを無効化（必要に応じて）
                "--disable-setuid-sandbox", # setuidサンドボックスを無効化
            ]
            
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=launch_args
            )
            
            self.page = self.browser.new_page()
            self.page.set_default_timeout(self.default_timeout)  # ページのタイムアウトを設定
            logger.info(f"ブラウザを起動しました。タイムアウト: {self.default_timeout}ms, スロー設定: {self.slow_mo}ms")
            
            return True
        except Exception as e:
            logger.error(f"ブラウザの起動に失敗しました: {e}")
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
        try:
            # 「掲載管理」ボタンをクリック
            self.page.click("#globalNavi > ul.common-CLPcommon__globalNavi > li:nth-child(2) > a")
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("掲載管理ページでロボット認証が検出されました。処理を中断します。")
                return False
            
            # 「ブログ」ボタンをクリック
            self.page.click("#cmsForm > div > div > ul > li:nth-child(9) > a")
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("ブログ管理ページでロボット認証が検出されました。処理を中断します。")
                return False
            
            # 「新規投稿」ボタンをクリック
            self.page.click("#newPosts")
            
            # 投稿フォームの読み込みを待機
            try:
                self.page.wait_for_selector("select#stylistId", timeout=10000)
            except TimeoutError:
                logger.error("ブログ投稿フォームの表示がタイムアウトしました")
                return False
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("新規投稿ページでロボット認証が検出されました。処理を中断します。")
                return False
                
            logger.info("ブログ投稿ページへの移動に成功しました")
            return True
            
        except Exception as e:
            logger.error(f"ブログ投稿ページへの移動中にエラーが発生しました: {e}")
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
        クーポンを選択する
        
        Args:
            coupon_names (list): 選択するクーポン名のリスト
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # クーポン選択ボタンをクリック
            logger.info("クーポン選択ボタンをクリックします")
            self.page.click("a.jsc_SB_modal_trigger")
            
            # クーポン選択モーダルの表示を待機
            try:
                logger.info("クーポン選択モーダルの表示を待機します")
                self.page.wait_for_selector("div#couponWrap", timeout=10000)
                if not self.page.is_visible("div#couponWrap"):
                    # 代替セレクタで再試行
                    logger.info("代替セレクタでクーポンモーダルの表示を確認します")
                    self.page.wait_for_selector("#couponArea", timeout=5000)
            except TimeoutError:
                logger.error("クーポン選択モーダルの表示がタイムアウトしました")
                return False
            
            # 各クーポンを選択
            for coupon_name in coupon_names:
                logger.info(f"クーポン '{coupon_name}' を選択します")
                try:
                    # より柔軟な方法でクーポンを探してチェック
                    # まず、クーポン名を含むテキスト要素を探す
                    coupon_elements = self.page.query_selector_all("p.couponText")
                    found = False
                    
                    for elem in coupon_elements:
                        text = elem.inner_text()
                        if coupon_name in text:
                            # クーポン名が見つかったら、親要素を遡ってチェックボックスを見つける
                            logger.info(f"クーポン '{coupon_name}' が見つかりました: {text}")
                            # 関連するチェックボックスをクリック
                            closest_label = elem.evaluate("node => node.closest('label')")
                            if closest_label:
                                closest_label.click()
                                found = True
                                logger.info(f"クーポン '{coupon_name}' を選択しました")
                                break
                    
                    if not found:
                        # 代替的な方法: XPathを使用してテキストを部分一致で検索
                        logger.info(f"代替方法でクーポン '{coupon_name}' を検索します")
                        self.page.click(f"//p[contains(text(), '{coupon_name}')]/ancestor::label")
                        logger.info(f"代替方法でクーポン '{coupon_name}' を選択しました")
                        
                except Exception as e:
                    logger.warning(f"クーポン '{coupon_name}' の選択に失敗しました: {e}")
            
            # 「設定する」ボタンをクリック
            logger.info("「設定する」ボタンをクリックします")
            try:
                self.page.click("a.jsc_SB_modal_setting_btn")
            except Exception as e:
                logger.warning(f"標準セレクタでの設定ボタンのクリックに失敗しました: {e}")
                try:
                    # 代替セレクタで試行
                    self.page.click("//a[contains(text(), '設定する')]")
                except Exception as alt_e:
                    logger.warning(f"代替方法での設定ボタンのクリックにも失敗しました: {alt_e}")
            
            # モーダルが閉じるのを待つ
            logger.info("モーダルが閉じるのを待機します")
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"クーポン選択中にエラーが発生しました: {e}")
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
            self.page.click("a#confirm")
            
            # 確認ページの表示を待機
            try:
                self.page.wait_for_selector("a#regist", timeout=10000)  # 登録ボタンのセレクタは要確認
            except TimeoutError:
                logger.error("確認ページの表示がタイムアウトしました")
                return False
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("確認ページでロボット認証が検出されました。処理を中断します。")
                return False
                
            # 「登録する」ボタンをクリック
            self.page.click("a#regist")  # 登録ボタンのセレクタは要確認
            
            # 完了ページの表示を待機
            try:
                # 成功メッセージや完了ページの特徴的な要素を待機
                self.page.wait_for_selector("div.completeMessage", timeout=10000)  # 完了メッセージのセレクタは要確認
            except TimeoutError:
                logger.error("完了ページの表示がタイムアウトしました")
                return False
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("完了ページでロボット認証が検出されました。処理を中断します。")
                return False
                
            logger.info("ブログの投稿に成功しました")
            return True
            
        except Exception as e:
            logger.error(f"ブログ投稿中にエラーが発生しました: {e}")
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