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
        self.default_timeout = 60000  # デフォルトのタイムアウトを60秒に設定

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
            # ログインページに移動
            logger.info(f"ログインページ({self.login_url})に移動します")
            self.page.goto(self.login_url, wait_until="networkidle")
            logger.info("ログインページの読み込みが完了しました")
            
            # 少し待機してページが完全に読み込まれるのを待つ
            time.sleep(2)
            
            # ロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("ログイン時にロボット認証が検出されました。処理を中断します。")
                return False
            
            # ユーザーID入力
            logger.info(f"ユーザーID '{user_id}' を入力します")
            self.page.fill("input[name='userId']", user_id)
            
            # パスワード入力
            logger.info("パスワードを入力します")
            self.page.fill("input#jsiPwInput", password)
            
            # ログインボタンクリック
            logger.info("ログインボタンをクリックします")
            self.page.click("a.common-CNCcommon__primaryBtn.loginBtnSize")
            
            # ダッシュボードが表示されるまで待機
            logger.info("ダッシュボードの表示を待機します...")
            try:
                # より長いタイムアウト時間を設定し、ネットワークのアイドル状態を待つ
                self.page.wait_for_selector("#globalNavi", timeout=self.default_timeout, state="visible")
                logger.info("ダッシュボードの表示を確認しました")
            except TimeoutError as e:
                # タイムアウトした場合、現在のURLとタイトルを記録しておく
                current_url = self.page.url
                current_title = self.page.title()
                logger.error(f"ログイン後のダッシュボード表示がタイムアウトしました。現在のURL: {current_url}, タイトル: {current_title}")
                
                # スクリーンショットを撮影して保存
                try:
                    screenshot_path = "login_timeout_screenshot.png"
                    self.page.screenshot(path=screenshot_path)
                    logger.info(f"スクリーンショットを保存しました: {screenshot_path}")
                except Exception as ss_err:
                    logger.error(f"スクリーンショット撮影に失敗しました: {ss_err}")
                
                return False
                
            # ログイン後にロボット認証が検出されたら中断
            if self.is_robot_detection_present():
                logger.error("ログイン後にロボット認証が検出されました。処理を中断します。")
                return False
                
            logger.info("サロンボードへのログインに成功しました")
            return True
            
        except Exception as e:
            logger.error(f"ログイン処理中にエラーが発生しました: {e}")
            # スクリーンショットを撮影して保存
            try:
                screenshot_path = "login_error_screenshot.png"
                self.page.screenshot(path=screenshot_path)
                logger.info(f"エラー時のスクリーンショットを保存しました: {screenshot_path}")
            except Exception as ss_err:
                logger.error(f"スクリーンショット撮影に失敗しました: {ss_err}")
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
            content (str): 設定するHTML内容
            
        Returns:
            bool: 成功でTrue、失敗でFalse
        """
        try:
            # JavaScriptを使用してnicEditエディタの内容を設定
            js_script = """
            (function() {
                try {
                    var editorInstance = nicEditors.findEditor('blogContents');
                    if (editorInstance) {
                        editorInstance.setContent(arguments[0]);
                        return true;
                    }
                    return false;
                } catch(e) {
                    console.error('nicEdit操作エラー:', e);
                    return false;
                }
            })()
            """
            result = self.page.evaluate(js_script, content)
            
            if not result:
                # 代替手段: 通常のテキストエリアとして操作を試みる
                self.page.fill("textarea#blogContents", content)
                
            return True
            
        except Exception as e:
            logger.error(f"リッチテキストエディタの操作中にエラーが発生しました: {e}")
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
            self.page.click("a#upload")
            
            # 画像アップロードモーダルの表示を待機
            try:
                self.page.wait_for_selector("div.jscImageUploaderModal", timeout=10000)
            except TimeoutError:
                logger.error("画像アップロードモーダルの表示がタイムアウトしました")
                return False
            
            # ファイルインプットに画像を設定
            self.page.set_input_files("input#sendFile", image_path)
            
            # アップロード完了を待機（適切なセレクタに要調整）
            try:
                self.page.wait_for_selector("div.upload-complete", timeout=20000)
            except TimeoutError:
                logger.warning("アップロード完了の検出がタイムアウトしました。処理を継続します。")
            
            # アップロード後の「設定する」ボタンをクリック
            try:
                if self.page.query_selector("button.insert-image"):
                    self.page.click("button.insert-image")
                elif self.page.query_selector("a.insert-button"):
                    self.page.click("a.insert-button")
                # その他のボタンパターンがあれば追加
            except Exception as e:
                logger.warning(f"画像挿入ボタンのクリックに失敗しました: {e}")
            
            # モーダルが閉じるのを待つ
            time.sleep(2)
            
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
            self.page.click("a.jsc_SB_modal_trigger")
            
            # クーポン選択モーダルの表示を待機
            try:
                self.page.wait_for_selector("div#couponWrap", timeout=10000)
            except TimeoutError:
                logger.error("クーポン選択モーダルの表示がタイムアウトしました")
                return False
            
            # 各クーポンを選択
            for coupon_name in coupon_names:
                # クーポンに関連するチェックボックスを探す（テキスト内容で検索）
                try:
                    # XPathを使用して、テキストを含む要素を見つけ、その近くのチェックボックスを選択
                    self.page.check(f"//label[contains(text(), '{coupon_name}')]/preceding-sibling::input[@type='checkbox']")
                except Exception as e:
                    logger.warning(f"クーポン '{coupon_name}' の選択に失敗しました: {e}")
            
            # 「設定する」ボタンをクリック
            self.page.click("a.jsc_SB_modal_setting_btn")
            
            # モーダルが閉じるのを待つ
            time.sleep(2)
            
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