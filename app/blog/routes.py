import os
import logging
import json
from flask import render_template, redirect, url_for, request, flash, current_app, session, jsonify
from app.blog import bp
from app.auth.routes import login_required
from app.utils.upload import save_uploaded_file
from app.gemini.generator import BlogGenerator
from werkzeug.utils import secure_filename
from app.utils.image import get_image_url
from app.gemini.extractor import HairStyleExtractor
from app.scraper.stylist import StylistScraper
from app.scraper.coupon import CouponScraper
from app.salon_board import SalonBoardPoster

logger = logging.getLogger(__name__)

# 画像ファイルの一時保存用セッションキー
UPLOADED_IMAGES_KEY = 'blog_uploaded_images'
GENERATED_CONTENT_KEY = 'blog_generated_content'
HAIR_INFO_KEY = 'hair_style_info'
SALON_URL_KEY = 'salon_url'
STYLISTS_KEY = 'stylists'
COUPONS_KEY = 'coupons'
SELECTED_TEMPLATE_KEY = 'selected_template'
SALON_BOARD_USER_ID_KEY = 'salon_board_user_id'
SALON_BOARD_PASSWORD_KEY = 'salon_board_password'
SALON_BOARD_STYLIST_ID_KEY = 'salon_board_stylist_id'
SELECTED_COUPON_NAME_KEY = 'selected_coupon_name'
SUCCESS_SCREENSHOT_KEY = 'success_screenshot'
ROBOT_DETECTED_KEY = 'robot_detected'

@bp.route('/')
@login_required
def index():
    # セッションをクリア
    if UPLOADED_IMAGES_KEY in session:
        session.pop(UPLOADED_IMAGES_KEY)
    if GENERATED_CONTENT_KEY in session:
        session.pop(GENERATED_CONTENT_KEY)
    if HAIR_INFO_KEY in session:
        session.pop(HAIR_INFO_KEY)
    if SUCCESS_SCREENSHOT_KEY in session:
        session.pop(SUCCESS_SCREENSHOT_KEY)
    if ROBOT_DETECTED_KEY in session:
        session.pop(ROBOT_DETECTED_KEY)
    
    return render_template('blog/index.html')

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'images' not in request.files:
        flash('画像が選択されていません', 'error')
        return redirect(url_for('blog.index'))
    
    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        flash('画像が選択されていません', 'error')
        return redirect(url_for('blog.index'))
    
    uploaded_images = []
    for file in files:
        if file and file.filename != '':
            try:
                filename = save_uploaded_file(file)
                if filename:
                    uploaded_images.append(filename)
            except Exception as e:
                logger.error(f"画像アップロードエラー: {str(e)}")
                flash(f'画像のアップロードに失敗しました: {str(e)}', 'error')
    
    if not uploaded_images:
        flash('画像のアップロードに失敗しました', 'error')
        return redirect(url_for('blog.index'))
    
    # アップロードした画像のパスをセッションに保存
    session[UPLOADED_IMAGES_KEY] = uploaded_images
    
    # 最初の画像からヘアスタイル情報を抽出
    try:
        extractor = HairStyleExtractor()
        hair_info = extractor.extract_hair_info(uploaded_images[0])
        if hair_info:
            session[HAIR_INFO_KEY] = hair_info
            logger.info(f"ヘアスタイル情報を抽出しました: {hair_info}")
    except Exception as e:
        logger.error(f"ヘアスタイル情報抽出エラー: {str(e)}")
        # 抽出に失敗しても処理を続行
    
    return redirect(url_for('blog.generate'))

@bp.route('/generate')
@login_required
def generate():
    # アップロードされた画像をチェック
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('最初に画像をアップロードしてください', 'error')
        return redirect(url_for('blog.index'))
    
    # 画像URLを作成
    image_urls = [get_image_url(img) for img in uploaded_images]
    
    # 生成済みコンテンツがあれば取得
    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    
    # ヘアスタイル情報を取得
    hair_info = session.get(HAIR_INFO_KEY, {})
    
    # サロンURL、スタイリスト情報、クーポン情報を取得
    salon_url = session.get(SALON_URL_KEY, '')
    stylists = session.get(STYLISTS_KEY, [])
    coupons = session.get(COUPONS_KEY, [])
    selected_coupon_name = session.get(SELECTED_COUPON_NAME_KEY, '')
    
    # テンプレート情報を取得
    selected_template = session.get(SELECTED_TEMPLATE_KEY, '')
    
    # 投稿成功スクリーンショットを取得（あれば）
    success_screenshot = None
    if SUCCESS_SCREENSHOT_KEY in session:
        screenshot_path = session[SUCCESS_SCREENSHOT_KEY]
        # ファイル名だけを取得して画像URLを生成
        success_screenshot = url_for('uploaded_file', filename=os.path.basename(screenshot_path))
    
    return render_template(
        'blog/generate.html', 
        image_urls=image_urls,
        generated_content=generated_content,
        hair_info=hair_info,
        salon_url=salon_url,
        stylists=stylists,
        coupons=coupons,
        selected_template=selected_template,
        success_screenshot=success_screenshot # スクリーンショットを追加
    )

@bp.route('/generate-content', methods=['POST', 'GET'])
@login_required
def generate_content():
    # アップロードされた画像をチェック
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('最初に画像をアップロードしてください', 'error')
        return redirect(url_for('blog.index'))
    
    # GETリクエストの場合は再生成
    force_regenerate = request.method == 'GET'
    
    # 生成済みのコンテンツが既にあり、かつ再生成でない場合
    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    if generated_content and not force_regenerate:
        return redirect(url_for('blog.generate'))
    
    try:
        # ヘアスタイル情報を取得
        hair_info = session.get(HAIR_INFO_KEY, {})
        
        # ブログコンテンツを生成（構造化データ形式）
        logger.info("構造化ブログデータの生成を開始します")
        generator = BlogGenerator()
        content = generator.generate_structured_blog_from_images(uploaded_images, hair_info)
        
        if not content or not content.get('title'):
            logger.warning("構造化データ生成に失敗したため、従来の方法にフォールバックします")
            # 従来の方法で生成を試みる
            content = generator.generate_blog_from_images(uploaded_images)
            if not content:
                flash('ブログ内容の生成に失敗しました。もう一度お試しください。', 'error')
                return redirect(url_for('blog.generate'))
        
        # 構造化データの詳細をログ出力
        try:
            logger.debug(f"構造化データ: {json.dumps(content, ensure_ascii=False)[:500]}...")
        except Exception as json_err:
            logger.error(f"構造化データのJSONシリアライズエラー: {json_err}")
            
        # 構造化データから従来形式への変換（互換性のため）
        if 'sections' in content and isinstance(content['sections'], list):
            combined_text = ""
            for section in content['sections']:
                if section.get('type') == 'text':
                    combined_text += section.get('content', '') + "\n\n"
            
            # 従来の形式で上書き
            content['content'] = combined_text.strip()
            logger.info(f"構造化データから変換した従来形式のコンテンツ: {len(content['content'])}文字")
        elif 'content' not in content or not content['content']:
            # contentキーがない場合、空文字列を設定
            content['content'] = ""
            logger.warning("生成されたコンテンツが空です")

        # 生成したコンテンツをセッションに保存
        session[GENERATED_CONTENT_KEY] = content
        logger.info(f"ブログ内容生成成功: タイトル '{content.get('title')}', コンテンツ長: {len(content.get('content', ''))}文字, セクション数: {len(content.get('sections', []))}")
        flash('ブログ内容を生成しました', 'success')
    except Exception as e:
        logger.error(f"ブログ生成エラー: {str(e)}", exc_info=True)
        flash(f'ブログ内容の生成中にエラーが発生しました: {str(e)}', 'error')
    
    return redirect(url_for('blog.generate'))

@bp.route('/save-content', methods=['POST'])
@login_required
def save_content():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if not title:
        flash('タイトルは必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    if len(title) > 50:
        flash('タイトルは50文字以内でお願いします', 'error')
        return redirect(url_for('blog.generate'))
    
    if not content:
        flash('内容は必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    # 編集された内容をセッションに保存
    current_content = session.get(GENERATED_CONTENT_KEY, {})
    current_content['title'] = title
    current_content['content'] = content
    session[GENERATED_CONTENT_KEY] = current_content
    
    flash('ブログ内容を保存しました', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/hair-info', methods=['GET'])
@login_required
def hair_info():
    # ヘアスタイル情報を取得
    hair_info = session.get(HAIR_INFO_KEY, {})
    if not hair_info:
        flash('ヘアスタイル情報がありません', 'error')
        return redirect(url_for('blog.generate'))
    
    # アップロードされた画像を取得
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    image_url = get_image_url(uploaded_images[0]) if uploaded_images else None
    
    return render_template(
        'blog/hair_info.html',
        hair_info=hair_info,
        image_url=image_url
    )

@bp.route('/analyze-hair', methods=['POST'])
@login_required
def analyze_hair():
    # アップロードされた画像をチェック
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('最初に画像をアップロードしてください', 'error')
        return redirect(url_for('blog.index'))
    
    try:
        # 最初の画像からヘアスタイル情報を抽出
        extractor = HairStyleExtractor()
        hair_info = extractor.extract_hair_info(uploaded_images[0])
        
        if hair_info:
            # 抽出成功
            session[HAIR_INFO_KEY] = hair_info
            logger.info(f"ヘアスタイル情報を抽出しました: {hair_info}")
            flash('ヘアスタイルの分析が完了しました', 'success')
        else:
            # 抽出結果が空
            flash('ヘアスタイルの特徴を検出できませんでした。別の画像をお試しください。', 'warning')
    except Exception as e:
        logger.error(f"ヘアスタイル情報抽出エラー: {str(e)}")
        flash(f'ヘアスタイルの分析中にエラーが発生しました: {str(e)}', 'error')
    
    return redirect(url_for('blog.generate'))

@bp.route('/fetch-salon-info', methods=['POST'])
@login_required
def fetch_salon_info():
    # サロンURLの取得
    salon_url = request.form.get('salon_url', '').strip()
    
    if not salon_url:
        flash('サロンURLを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    # URLの基本的な検証
    if not salon_url.startswith('https://beauty.hotpepper.jp/'):
        flash('有効なHotPepper Beauty URLを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    try:
        # スタイリスト情報の取得
        stylist_scraper = StylistScraper(salon_url)
        stylists = stylist_scraper.get_stylists()
        
        # クーポン情報の取得
        coupon_scraper = CouponScraper(salon_url)
        coupons_data = coupon_scraper.get_coupons() # 辞書のリストを取得
        
        # クーポン名のリストに変換
        coupons = [coupon['name'] for coupon in coupons_data if 'name' in coupon] 
        
        # セッションに保存
        session[SALON_URL_KEY] = salon_url
        session[STYLISTS_KEY] = stylists
        session[COUPONS_KEY] = coupons # 文字列のリストを保存
        
        flash(f'サロン情報を取得しました。スタイリスト: {len(stylists)}人、クーポン: {len(coupons)}件', 'success')
    except Exception as e:
        logger.error(f"サロン情報取得エラー: {str(e)}")
        flash(f'サロン情報の取得に失敗しました: {str(e)}', 'error')
    
    return redirect(url_for('blog.generate'))

@bp.route('/save-template', methods=['POST'])
@login_required
def save_template():
    template_content = request.form.get('template', '').strip()
    session[SELECTED_TEMPLATE_KEY] = template_content
    flash('テンプレートを保存しました', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/prepare-post', methods=['POST'])
@login_required
def prepare_post():
    # 必要な情報がすべて揃っているか確認
    if not session.get(GENERATED_CONTENT_KEY):
        flash('ブログ内容を生成してください', 'error')
        return redirect(url_for('blog.generate'))
    
    if not session.get(UPLOADED_IMAGES_KEY):
        flash('画像をアップロードしてください', 'error')
        return redirect(url_for('blog.generate'))
    
    # 入力内容を取得
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    stylist_id = request.form.get('stylist_id', '').strip()
    selected_coupon = request.form.get('selected_coupon', '').strip()
    template = request.form.get('template', '').strip()
    
    # 入力内容の検証
    if not title:
        flash('タイトルは必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    if not content:
        flash('本文は必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    # 投稿準備画面に遷移（ここではまだ実装せず、将来の拡張用に置いておく）
    flash('投稿準備が完了しました。サロンボードへのログイン情報を入力してください。', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/post-to-salon-board', methods=['POST'])
@login_required
def post_to_salon_board():
    """サロンボードにブログを投稿する"""
    # 必要な情報がすべて揃っているか確認
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('画像がアップロードされていません', 'error')
        return redirect(url_for('blog.generate'))
    
    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    if not generated_content or not generated_content.get('title') or not generated_content.get('content'):
        flash('ブログ内容が生成されていません', 'error')
        return redirect(url_for('blog.generate'))
    
    # サロンボードのログイン情報
    user_id = request.form.get('salon_board_user_id', '').strip()
    password = request.form.get('salon_board_password', '').strip()
    
    if not user_id or not password:
        flash('サロンボードのユーザーIDとパスワードを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    # スタイリストIDの取得
    stylist_id = request.form.get('stylist_id', '').strip()
    if not stylist_id:
        flash('スタイリストを選択してください', 'error')
        return redirect(url_for('blog.generate'))
    
    # クーポン名の取得
    selected_coupon = request.form.get('selected_coupon', '').strip()
    
    # SalonBoardPosterに渡す形式を調整 (空でなければリストに入れる)
    coupon_names_list = [selected_coupon] if selected_coupon else []
    
    # テンプレートの取得
    template = session.get(SELECTED_TEMPLATE_KEY, '')
    
    # 画像のフルパスを取得
    image_full_paths = [os.path.join(current_app.config['UPLOAD_FOLDER'], img) for img in uploaded_images]
    
    # ブログデータの作成
    # 構造化形式か従来形式かを確認
    if 'sections' in generated_content and isinstance(generated_content['sections'], list):
        logger.info(f"構造化データ形式でブログを投稿します。セクション数: {len(generated_content['sections'])}")
        blog_data = {
            'title': generated_content['title'],
            'sections': generated_content['sections'],  # 構造化データ
            'stylist_id': stylist_id,
            'image_paths': image_full_paths,
            'coupon_names': coupon_names_list,
            'template': template
        }
    else:
        # 従来形式 (フォールバック対応)
        logger.info("従来のデータ形式でブログを投稿します")
        blog_data = {
            'title': generated_content['title'],
            'content': generated_content['content'],
            'stylist_id': stylist_id,
            'image_paths': image_full_paths,
            'coupon_names': coupon_names_list,
            'template': template
        }
    
    # ログイン情報と選択内容をセッションに保存（キーと値を変更）
    session[SALON_BOARD_USER_ID_KEY] = user_id
    session[SALON_BOARD_STYLIST_ID_KEY] = stylist_id
    session[SELECTED_COUPON_NAME_KEY] = selected_coupon
    
    # SalonBoardPosterのインスタンスを作成
    logger.info("SalonBoardPoster インスタンスを作成します")
    poster = SalonBoardPoster(slow_mo=200)
    
    success = False
    try:
        logger.info("ブログ投稿処理を開始します")
        # サロンボードへの投稿を実行
        result = poster.execute_post(user_id, password, blog_data)
        
        if isinstance(result, dict):
            # ロボット認証が検出された場合
            if not result.get('success') and result.get('robot_detected') and result.get('screenshot_path'):
                session[SUCCESS_SCREENSHOT_KEY] = result.get('screenshot_path')
                session[ROBOT_DETECTED_KEY] = True
                flash('サロンボードへの投稿中にロボット認証が検出されました。手動でログインしてください。', 'error')
                return redirect(url_for('blog.generate'))
            
            # 成功した場合
            if result.get('success'):
                # スクリーンショットパスをセッションに保存
                session[SUCCESS_SCREENSHOT_KEY] = result.get('screenshot_path')
                session[ROBOT_DETECTED_KEY] = False
                flash('サロンボードへのブログ投稿が完了しました', 'success')
                success = True
        elif result:
            # 単なる True の場合（スクリーンショットなし)
            session[ROBOT_DETECTED_KEY] = False
            flash('サロンボードへのブログ投稿が完了しました', 'success')
            success = True
        else:
            flash('サロンボードへの投稿に失敗しました。詳細はログを確認してください。', 'error')
    except Exception as e:
        logger.error(f"サロンボード投稿エラー: {str(e)}")
        flash(f'サロンボードへの投稿中にエラーが発生しました: {str(e)}', 'error')
    
    return redirect(url_for('blog.generate')) 