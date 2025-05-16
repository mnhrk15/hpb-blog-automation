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

# logger = logging.getLogger(__name__)

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
POST_SUCCESS_KEY = 'post_success'
FAILURE_MESSAGE_KEY = 'failure_message'
FAILURE_SCREENSHOT_KEY = 'failure_screenshot'
ERROR_TYPE_KEY = 'error_type'

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
    if FAILURE_MESSAGE_KEY in session:
        session.pop(FAILURE_MESSAGE_KEY)
    if FAILURE_SCREENSHOT_KEY in session:
        session.pop(FAILURE_SCREENSHOT_KEY)
    if ERROR_TYPE_KEY in session:
        session.pop(ERROR_TYPE_KEY)
    
    # サロン情報関連のセッションもクリアした方が良いかもしれない
    session.pop(SALON_URL_KEY, None)
    session.pop(STYLISTS_KEY, None)
    session.pop(COUPONS_KEY, None)
    session.modified = True # クリアした場合も変更を通知
    
    return render_template('blog/index.html', active_step=1)

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    logger = current_app.logger
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
    
    session[UPLOADED_IMAGES_KEY] = uploaded_images
    logger.debug(f"Uploaded images saved to session ({UPLOADED_IMAGES_KEY}): {session.get(UPLOADED_IMAGES_KEY)}")
    
    if uploaded_images: # 画像が1枚以上アップロードされている場合のみ実行
        try:
            extractor = HairStyleExtractor()
            # uploaded_images[0] はファイル名なので、フルパスを生成して渡す
            first_image_filename = uploaded_images[0]
            first_image_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], first_image_filename)
            logger.debug(f"Extracting hair info from: {first_image_full_path}")
            hair_info = extractor.extract_hair_info(first_image_full_path)
            if hair_info:
                session[HAIR_INFO_KEY] = hair_info
                logger.info(f"ヘアスタイル情報を抽出しました: {hair_info}")
                logger.debug(f"Hair info saved to session ({HAIR_INFO_KEY}): {session.get(HAIR_INFO_KEY)}")
            else:
                logger.warning("ヘアスタイル情報の抽出に失敗しました。hair_info is None or empty.")
                # セッションにキーが存在しない場合や空の場合の挙動を明確にするため、Noneを意図的に入れるか、キー自体を削除することも検討
                session.pop(HAIR_INFO_KEY, None) # 抽出失敗時はクリア
        except Exception as e:
            logger.error(f"ヘアスタイル情報抽出エラー: {str(e)}")
            session.pop(HAIR_INFO_KEY, None) # エラー時もクリア
    
    return redirect(url_for('blog.generate'))

@bp.route('/generate')
@login_required
def generate():
    logger = current_app.logger
    logger.debug(f"Entering generate route. Session ID: {session.sid if hasattr(session, 'sid') else 'N/A - default session'}")
    logger.debug(f"Session keys available: {list(session.keys())}")

    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    logger.debug(f"Retrieved from session ({UPLOADED_IMAGES_KEY}): {uploaded_images}")
    if not uploaded_images:
        flash('最初に画像をアップロードしてください', 'error')
        return redirect(url_for('blog.index'))
    
    image_urls = [get_image_url(img) for img in uploaded_images]
    logger.debug(f"Generated image_urls: {image_urls}")

    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    logger.debug(f"Retrieved from session ({GENERATED_CONTENT_KEY}): {generated_content}")

    hair_info = session.get(HAIR_INFO_KEY, {})
    logger.debug(f"Retrieved from session ({HAIR_INFO_KEY}): {hair_info}")
    
    salon_url = session.get(SALON_URL_KEY, '')
    stylists = session.get(STYLISTS_KEY, [])
    coupons = session.get(COUPONS_KEY, [])
    logger.debug(f"STYLISTS_KEY in generate: {stylists}")
    logger.debug(f"COUPONS_KEY in generate: {coupons}")
    logger.debug(f"SALON_URL_KEY in generate: {salon_url}")

    selected_template = session.get(SELECTED_TEMPLATE_KEY, '')
    
    success_screenshot = None
    if SUCCESS_SCREENSHOT_KEY in session:
        absolute_screenshot_path = session[SUCCESS_SCREENSHOT_KEY]
        if absolute_screenshot_path:
            try:
                # UPLOAD_FOLDERからの相対パスに変換
                relative_screenshot_path = os.path.relpath(absolute_screenshot_path, current_app.config['UPLOAD_FOLDER'])
                success_screenshot = url_for('uploaded_file', filename=relative_screenshot_path)
                logger.info(f"Success screenshot URL: {success_screenshot}, Relative path: {relative_screenshot_path}")
            except ValueError as e:
                logger.error(f"Error creating relative path for success screenshot: {e}. Absolute: {absolute_screenshot_path}, Upload folder: {current_app.config['UPLOAD_FOLDER']}")
    
    failure_message = session.get(FAILURE_MESSAGE_KEY)
    failure_screenshot = None
    if FAILURE_SCREENSHOT_KEY in session:
        absolute_screenshot_path = session[FAILURE_SCREENSHOT_KEY]
        if absolute_screenshot_path:
            try:
                # UPLOAD_FOLDERからの相対パスに変換
                relative_screenshot_path = os.path.relpath(absolute_screenshot_path, current_app.config['UPLOAD_FOLDER'])
                failure_screenshot = url_for('uploaded_file', filename=relative_screenshot_path)
                logger.info(f"Failure screenshot URL: {failure_screenshot}, Relative path: {relative_screenshot_path}")
            except ValueError as e:
                logger.error(f"Error creating relative path for failure screenshot: {e}. Absolute: {absolute_screenshot_path}, Upload folder: {current_app.config['UPLOAD_FOLDER']}")
    
    if session.get(POST_SUCCESS_KEY, False):
        active_step = 4
    elif generated_content:
        active_step = 3
    else:
        active_step = 2
    
    return render_template(
        'blog/generate.html', 
        image_urls=image_urls,
        generated_content=generated_content,
        hair_info=hair_info,
        salon_url=salon_url,
        stylists=stylists,
        coupons=coupons,
        selected_template=selected_template,
        success_screenshot=success_screenshot,
        failure_message=failure_message,
        failure_screenshot=failure_screenshot,
        active_step=active_step
    )

@bp.route('/generate-content', methods=['POST', 'GET'])
@login_required
def generate_content():
    logger = current_app.logger
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('最初に画像をアップロードしてください', 'error')
        return redirect(url_for('blog.index'))
    
    force_regenerate = request.method == 'GET'
    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    if generated_content and not force_regenerate:
        return redirect(url_for('blog.generate'))
    
    try:
        hair_info = session.get(HAIR_INFO_KEY, {})
        logger.info("構造化ブログデータの生成を開始します")
        generator = BlogGenerator()
        image_full_paths = [os.path.join(current_app.config['UPLOAD_FOLDER'], img) for img in uploaded_images]
        logger.debug(f"Image full paths for blog generation: {image_full_paths}")

        content = generator.generate_structured_blog_from_images(image_full_paths, hair_info)
        
        if not content or not content.get('title'):
            logger.warning("構造化データ生成に失敗したため、従来の方法にフォールバックします")
            content = generator.generate_blog_from_images(image_full_paths)
            if not content:
                flash('ブログ内容の生成に失敗しました。もう一度お試しください。', 'error')
                return redirect(url_for('blog.generate'))
        
        try:
            logger.debug(f"構造化データ: {json.dumps(content, ensure_ascii=False)[:500]}...")
        except Exception as json_err:
            logger.error(f"構造化データのJSONシリアライズエラー: {json_err}")
            
        if 'sections' in content and isinstance(content['sections'], list):
            combined_text = ""
            for section in content['sections']:
                if section.get('type') == 'text':
                    combined_text += section.get('content', '') + "\n\n"
            content['content'] = combined_text.strip()
            logger.info(f"構造化データから変換した従来形式のコンテンツ: {len(content['content'])}文字")
        elif 'content' not in content or not content['content']:
            content['content'] = ""
            logger.warning("生成されたコンテンツが空です")

        session[GENERATED_CONTENT_KEY] = content
        session.modified = True # 明示的に変更を通知
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
    
    current_content = session.get(GENERATED_CONTENT_KEY, {})
    current_content['title'] = title
    current_content['content'] = content
    session[GENERATED_CONTENT_KEY] = current_content
    session.modified = True # 明示的に変更を通知
    
    flash('ブログ内容を保存しました', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/hair-info', methods=['GET'])
@login_required
def hair_info():
    hair_info_data = session.get(HAIR_INFO_KEY, {})
    if not hair_info_data:
        flash('ヘアスタイル情報がありません', 'error')
        return redirect(url_for('blog.generate'))
    return render_template('blog/hair_info.html', hair_info=hair_info_data, active_step=2)

@bp.route('/analyze-hair', methods=['POST'])
@login_required
def analyze_hair():
    logger = current_app.logger
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('画像がアップロードされていません', 'error')
        return redirect(url_for('blog.generate'))

    image_to_analyze = request.form.get('image_filename')
    if not image_to_analyze or image_to_analyze not in uploaded_images:
        flash('分析対象の画像が見つかりません', 'error')
        return redirect(url_for('blog.generate'))

    try:
        extractor = HairStyleExtractor()
        analysis_result = extractor.analyze_hair_style_from_image(image_to_analyze)
        if analysis_result:
            session[HAIR_INFO_KEY] = analysis_result
            session.modified = True # 明示的に変更を通知
            logger.info(f"ヘアスタイル分析結果を更新: {analysis_result}")
            flash('ヘアスタイル分析が完了しました', 'success')
        else:
            flash('ヘアスタイル分析に失敗しました', 'error')
    except Exception as e:
        logger.error(f"ヘアスタイル分析エラー: {e}", exc_info=True)
        flash(f'ヘアスタイル分析中にエラーが発生しました: {e}', 'error')
    return redirect(url_for('blog.generate'))

@bp.route('/save-hair-info', methods=['POST'])
@login_required
def save_hair_info():
    logger = current_app.logger
    hairstyle = request.form.get('hairstyle', '').strip()
    color = request.form.get('color', '').strip()
    features_str = request.form.get('features', '').strip()
    face_shape = request.form.get('face_shape', '').strip()
    season = request.form.get('season', '').strip()

    hair_info = session.get(HAIR_INFO_KEY, {})
    if not hair_info: # 万が一HAIR_INFO_KEYがなければ初期化
        hair_info = {}
        
    hair_info['hairstyle'] = hairstyle
    hair_info['ヘアスタイル'] = hairstyle # 互換性のため両方保持
    hair_info['color'] = color
    hair_info['髪色'] = color
    hair_info['features'] = [f.strip() for f in features_str.split(',') if f.strip()]
    hair_info['特徴'] = [f.strip() for f in features_str.split(',') if f.strip()]
    hair_info['face_shape'] = face_shape
    hair_info['顔型'] = face_shape
    hair_info['season'] = season
    hair_info['季節'] = season
    
    session[HAIR_INFO_KEY] = hair_info
    session.modified = True # 明示的に変更を通知
    logger.info(f"ヘアスタイル情報を更新しました: {hair_info}")
    flash('ヘアスタイル情報を保存しました', 'success')
    
    return redirect(url_for('blog.generate'))

@bp.route('/fetch-salon-info', methods=['POST'])
@login_required
def fetch_salon_info():
    logger = current_app.logger
    salon_url = request.form.get('salon_url', '').strip()
    
    if not salon_url:
        flash('サロンURLを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    if not salon_url.startswith('https://beauty.hotpepper.jp/'):
        flash('有効なHotPepper Beauty URLを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    try:
        logger.info(f"サロン情報取得開始: {salon_url}")
        stylist_scraper = StylistScraper(salon_url)
        stylists = stylist_scraper.get_stylists()
        
        coupon_scraper = CouponScraper(salon_url)
        coupons_data = coupon_scraper.get_coupons()
        coupons = [coupon['name'] for coupon in coupons_data if 'name' in coupon]
        
        logger.debug(f"STYLISTS_KEY fetched: {stylists}")
        logger.debug(f"COUPONS_KEY fetched: {coupons}") # 変更: (full) を削除、ログメッセージをシンプルに
        
        # セッションに保存するクーポン数の制限を解除
        # MAX_COUPONS_IN_SESSION = 20 # 削除
        # session_coupons = coupons[:MAX_COUPONS_IN_SESSION] # 削除
        # if len(coupons) > MAX_COUPONS_IN_SESSION: # 削除
        #     logger.warning(f"セッションに保存するクーポンが多すぎるため、最初の{MAX_COUPONS_IN_SESSION}件に制限しました。全{len(coupons)}件") # 削除

        session[SALON_URL_KEY] = salon_url
        session[STYLISTS_KEY] = stylists
        session[COUPONS_KEY] = coupons # 変更: session_coupons から coupons に戻す
        session.modified = True # 明示的にセッション変更を通知
        
        logger.debug(f"STYLISTS_KEY in session after set: {session.get(STYLISTS_KEY)}")
        logger.debug(f"COUPONS_KEY in session after set: {session.get(COUPONS_KEY)}")
        logger.debug(f"SALON_URL_KEY in session after set: {session.get(SALON_URL_KEY)}")
        
        flash(f'サロン情報を取得しました。スタイリスト: {len(stylists)}人、クーポン: {len(coupons)}件', 'success') # 変更: flashメッセージを元に戻す
    except Exception as e:
        logger.error(f"サロン情報取得エラー: {str(e)}", exc_info=True)
        flash(f'サロン情報の取得に失敗しました: {str(e)}', 'error')
    
    return redirect(url_for('blog.generate'))

@bp.route('/save-template', methods=['POST'])
@login_required
def save_template():
    template_content = request.form.get('template', '').strip()
    session[SELECTED_TEMPLATE_KEY] = template_content
    session.modified = True # 明示的に変更を通知
    flash('テンプレートを保存しました', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/prepare-post', methods=['POST'])
@login_required
def prepare_post():
    if not session.get(GENERATED_CONTENT_KEY):
        flash('ブログ内容を生成してください', 'error')
        return redirect(url_for('blog.generate'))
    
    if not session.get(UPLOADED_IMAGES_KEY):
        flash('画像をアップロードしてください', 'error')
        return redirect(url_for('blog.generate'))
    
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    stylist_id = request.form.get('stylist_id', '').strip()
    selected_coupon = request.form.get('selected_coupon', '').strip()
    template = request.form.get('template', '').strip()
    
    if not title:
        flash('タイトルは必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    if not content:
        flash('本文は必須です', 'error')
        return redirect(url_for('blog.generate'))
    
    flash('投稿準備が完了しました。サロンボードへのログイン情報を入力してください。', 'success')
    return redirect(url_for('blog.generate'))

@bp.route('/post-to-salon-board', methods=['POST'])
@login_required
def post_to_salon_board():
    logger = current_app.logger
    """サロンボードにブログを投稿する"""
    uploaded_images = session.get(UPLOADED_IMAGES_KEY, [])
    if not uploaded_images:
        flash('画像がアップロードされていません', 'error')
        return redirect(url_for('blog.generate'))
    
    generated_content = session.get(GENERATED_CONTENT_KEY, {})
    if not generated_content or not generated_content.get('title') or not generated_content.get('content'):
        flash('ブログ内容が生成されていません', 'error')
        return redirect(url_for('blog.generate'))
    
    user_id = request.form.get('salon_board_user_id', '').strip()
    password = request.form.get('salon_board_password', '').strip()
    
    if not user_id or not password:
        flash('サロンボードのユーザーIDとパスワードを入力してください', 'error')
        return redirect(url_for('blog.generate'))
    
    stylist_id = request.form.get('stylist_id', '').strip()
    if not stylist_id:
        flash('スタイリストを選択してください', 'error')
        return redirect(url_for('blog.generate'))
    
    selected_coupon = request.form.get('selected_coupon', '').strip()
    coupon_names_list = [selected_coupon] if selected_coupon else []
    template = session.get(SELECTED_TEMPLATE_KEY, '')
    image_full_paths = [os.path.join(current_app.config['UPLOAD_FOLDER'], img) for img in uploaded_images]
    
    if 'sections' in generated_content and isinstance(generated_content['sections'], list):
        logger.info(f"構造化データ形式でブログを投稿します。セクション数: {len(generated_content['sections'])}")
        blog_data = {
            'title': generated_content['title'],
            'sections': generated_content['sections'],
            'stylist_id': stylist_id,
            'image_paths': image_full_paths,
            'coupon_names': coupon_names_list,
            'template': template
        }
    else:
        logger.info("従来のデータ形式でブログを投稿します")
        blog_data = {
            'title': generated_content['title'],
            'content': generated_content['content'],
            'stylist_id': stylist_id,
            'image_paths': image_full_paths,
            'coupon_names': coupon_names_list,
            'template': template
        }
    
    session[SALON_BOARD_USER_ID_KEY] = user_id
    session[SALON_BOARD_STYLIST_ID_KEY] = stylist_id
    session[SELECTED_COUPON_NAME_KEY] = selected_coupon
    session.modified = True # 明示的に変更を通知
    
    logger.info("SalonBoardPoster インスタンスを作成します")
    # スクリーンショット保存パスをConfigから取得して渡す
    screenshot_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_app.config.get('SCREENSHOT_SUBFOLDER', 'screenshots')) 
    # ConfigにSCREENSHOT_FOLDERが直接定義されている場合はそれを使う
    if 'SCREENSHOT_FOLDER' in current_app.config:
        screenshot_path = current_app.config['SCREENSHOT_FOLDER']
    else: # ない場合はUPLOAD_FOLDERの下にscreenshotsを作成
        screenshot_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'screenshots')
        os.makedirs(screenshot_path, exist_ok=True) # フォルダがなければ作成

    poster = SalonBoardPoster(screenshot_folder_path=screenshot_path, slow_mo=200)
    
    # 結果表示のためのセッションキーをクリア
    session.pop(POST_SUCCESS_KEY, None)
    session.pop(SUCCESS_SCREENSHOT_KEY, None)
    session.pop(FAILURE_MESSAGE_KEY, None)
    session.pop(FAILURE_SCREENSHOT_KEY, None)
    session.pop(ROBOT_DETECTED_KEY, None)
    session.pop(ERROR_TYPE_KEY, None)
    session.modified = True

    try:
        logger.info("ブログ投稿処理を開始します")
        result = poster.execute_post(user_id, password, blog_data)
        
        # result は必ず辞書であることを期待 (poster.py の修正による)
        if not isinstance(result, dict):
            logger.error(f"poster.execute_post から予期しない形式の返り値: {result}")
            flash('ブログ投稿処理で内部エラーが発生しました。管理者にご連絡ください。', 'error')
            session[POST_SUCCESS_KEY] = False
            return redirect(url_for('blog.generate'))

        if result.get('success'):
            session[POST_SUCCESS_KEY] = True
            if result.get('screenshot_path'):
                session[SUCCESS_SCREENSHOT_KEY] = result.get('screenshot_path')
            flash(result.get('message', 'ブログ投稿が完了しました。'), 'success')
        else:
            session[POST_SUCCESS_KEY] = False
            error_message = result.get('message', 'ブログ投稿に失敗しました。詳細はログを確認してください。')
            flash(error_message, 'error')
            session[FAILURE_MESSAGE_KEY] = error_message
            if result.get('screenshot_path'):
                session[FAILURE_SCREENSHOT_KEY] = result.get('screenshot_path')
            if result.get('error_type') == 'robot_detected':
                session[ROBOT_DETECTED_KEY] = True
            session[ERROR_TYPE_KEY] = result.get('error_type', 'unknown')
            
    except Exception as e:
        logger.error(f"サロンボード投稿のルート処理中にエラー: {str(e)}", exc_info=True)
        flash(f'サロンボードへの投稿処理中に予期せぬエラーが発生しました: {str(e)}', 'error')
        session[POST_SUCCESS_KEY] = False
        session[FAILURE_MESSAGE_KEY] = f'サロンボードへの投稿処理中に予期せぬエラーが発生しました: {str(e)}'
    
    session.modified = True # 確実にセッション変更を通知
    return redirect(url_for('blog.generate'))

@bp.route('/test-screenshot-path')
@login_required
def test_screenshot_path():
    """スクリーンショットパスのテスト用（デバッグ用）"""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    screenshot_subfolder = current_app.config.get('SCREENSHOT_SUBFOLDER', 'screenshots')
    screenshot_folder_from_config = current_app.config.get('SCREENSHOT_FOLDER')

    path_constructed = os.path.join(upload_folder, screenshot_subfolder)
    
    final_path = "N/A"
    if screenshot_folder_from_config:
        final_path = screenshot_folder_from_config
    else:
        final_path = path_constructed
        os.makedirs(final_path, exist_ok=True)

    return jsonify({
        "UPLOAD_FOLDER": upload_folder,
        "SCREENSHOT_SUBFOLDER_from_get": screenshot_subfolder,
        "SCREENSHOT_FOLDER_from_config": screenshot_folder_from_config,
        "path_constructed_from_upload_and_subfolder": path_constructed,
        "final_path_used_for_poster": final_path,
        "final_path_exists_after_makedirs": os.path.exists(final_path)
    }) 