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
SALON_NAME_KEY = 'salon_name'
SALON_ID_KEY = 'salon_id'
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
    session.pop(SALON_NAME_KEY, None)
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
    salon_name = session.get(SALON_NAME_KEY, '')
    stylists = session.get(STYLISTS_KEY, [])
    coupons = session.get(COUPONS_KEY, [])
    logger.debug(f"SALON_NAME_KEY in generate: {salon_name}")
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
                logger.info(f"Success screenshot URL: {success_screenshot}, Relative path: {relative_screenshot_path}, Absolute: {absolute_screenshot_path}")
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
                logger.info(f"Failure screenshot URL: {failure_screenshot}, Relative path: {relative_screenshot_path}, Absolute: {absolute_screenshot_path}")
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
        salon_name=salon_name,
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
        
        if not content or not content.get('title') or not content.get('sections'): # sectionsもチェック対象に追加
            logger.warning("構造化データ生成に失敗したか、内容が不十分なため、従来の方法にフォールバックします")
            content = generator.generate_blog_from_images(image_full_paths)
            if not content or not content.get('title'): # フォールバック結果もチェック
                flash('ブログ内容の生成に失敗しました。もう一度お試しください。', 'error')
                logger.error("フォールバックによるブログ生成も失敗しました。")
                return redirect(url_for('blog.generate'))
            # フォールバック成功時は、contentを構造化に近い形に整形するか検討 (現在はBlogGenerator側で一部対応)
            logger.info(f"フォールバックによるブログ生成成功: {content.get('title')}")
        
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
    
    # タイトルの文字数制限を設定ファイルから読み込むように変更する (例)
    # max_title_length = current_app.config.get('MAX_BLOG_TITLE_LENGTH', 50)
    # if len(title) > max_title_length:
    #     flash(f'タイトルは{max_title_length}文字以内でお願いします', 'error')
    #     return redirect(url_for('blog.generate'))
    # 現状は直接50文字でチェック (将来的に設定ファイル化を検討)
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
    if request.method == 'POST':
        salon_url = request.form.get('salon_url')
        hidden_template_content = request.form.get('hidden_template_content')
        
        if not salon_url:
            flash('サロンURLが入力されていません', 'error')
            return redirect(url_for('blog.generate'))
        
        if not salon_url.startswith('https://beauty.hotpepper.jp/'):
             flash('有効なHotPepper Beauty URLを入力してください', 'error')
             return redirect(url_for('blog.generate'))

        session[SALON_URL_KEY] = salon_url
        if hidden_template_content is not None:
            session[SELECTED_TEMPLATE_KEY] = hidden_template_content
            logger.info(f"サロン情報取得時にテンプレート内容をセッションに保存しました: {len(hidden_template_content)}文字")
        
        try:
            logger.info(f"サロン情報を取得します: {salon_url}")
            stylist_scraper = StylistScraper(salon_url)
            
            # サロン名を取得
            salon_name = stylist_scraper.get_salon_name()
            logger.info(f"サロン名を取得しました: {salon_name}")
            
            # サロンIDを取得
            salon_id = stylist_scraper.get_salon_id()
            logger.info(f"サロンIDを取得しました: {salon_id}")
            
            # スタイリスト情報を取得
            stylists = stylist_scraper.get_stylists()
            
            coupon_scraper = CouponScraper(salon_url)
            coupons_data = coupon_scraper.get_coupons(full=True) # 辞書のリストが返る
            coupons = [c.get('name') for c in coupons_data if c.get('name')] # クーポン名のリストに変換
            
            logger.debug(f"SALON_NAME_KEY fetched: {salon_name}")
            logger.debug(f"SALON_ID_KEY fetched: {salon_id}")
            logger.debug(f"STYLISTS_KEY fetched: {stylists}")
            logger.debug(f"COUPONS_KEY fetched (names only): {coupons}")
            
            # セッションに保存
            session[SALON_NAME_KEY] = salon_name
            session[SALON_ID_KEY] = salon_id
            session[STYLISTS_KEY] = stylists
            session[COUPONS_KEY] = coupons # クーポン名のリストをセッションに保存
            session.modified = True
            
            logger.debug(f"SALON_NAME_KEY in session after set: {session.get(SALON_NAME_KEY)}")
            logger.debug(f"SALON_ID_KEY in session after set: {session.get(SALON_ID_KEY)}")
            logger.debug(f"STYLISTS_KEY in session after set: {session.get(STYLISTS_KEY)}")
            logger.debug(f"COUPONS_KEY in session after set: {session.get(COUPONS_KEY)}")
            logger.debug(f"SALON_URL_KEY in session after set: {session.get(SALON_URL_KEY)}")
            
            flash(f'サロン情報を取得しました。サロン名: {salon_name}、サロンID: {salon_id}、スタイリスト: {len(stylists)}人、クーポン: {len(coupons)}件', 'success')
        except Exception as e:
            logger.error(f"サロン情報取得エラー: {str(e)}", exc_info=True)
            flash(f'サロン情報の取得中にエラーが発生しました: {str(e)}', 'error')
            # エラーが発生した場合でも、入力されたURLとテンプレートはセッションに残す（generateページで再表示されるため）
    
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
    logger.info("サロンボードへの投稿処理を開始します")
    session[POST_SUCCESS_KEY] = False # 初期化
    session.pop(SUCCESS_SCREENSHOT_KEY, None)
    session.pop(FAILURE_MESSAGE_KEY, None)
    session.pop(FAILURE_SCREENSHOT_KEY, None)
    session.pop(ROBOT_DETECTED_KEY, None)
    session.pop(ERROR_TYPE_KEY, None)

    generated_content_from_session = session.get(GENERATED_CONTENT_KEY)
    if not generated_content_from_session or not generated_content_from_session.get('title'):
        flash('ブログのタイトルがありません。内容を生成または確定してください。', 'error')
        logger.warning("投稿試行：ブログのタイトルがセッションにありません")
        return redirect(url_for('blog.generate'))

    # content または sections の存在確認
    has_content_key = 'content' in generated_content_from_session and generated_content_from_session['content']
    has_sections_key = 'sections' in generated_content_from_session and isinstance(generated_content_from_session['sections'], list) and generated_content_from_session['sections']

    if not has_content_key and not has_sections_key:
        flash('ブログの本文データがありません。内容を生成または確定してください。', 'error')
        logger.warning("投稿試行：ブログの本文データ(content/sections)がセッションにありません")
        return redirect(url_for('blog.generate'))

    salon_board_user_id = request.form.get('salon_board_user_id')
    salon_board_password = request.form.get('salon_board_password')
    stylist_id = request.form.get('stylist_id')
    selected_coupon_name = request.form.get('selected_coupon', '')
    blog_footer_template = request.form.get('blog_footer_template', '')

    if not all([salon_board_user_id, salon_board_password, stylist_id]):
        flash('サロンボードのログイン情報と投稿者を選択してください', 'error')
        logger.warning("投稿試行：サロンボードログイン情報または投稿者が不足しています")
        return redirect(url_for('blog.generate'))

    session[SALON_BOARD_USER_ID_KEY] = salon_board_user_id
    session[SALON_BOARD_STYLIST_ID_KEY] = stylist_id
    session[SELECTED_COUPON_NAME_KEY] = selected_coupon_name
    session.modified = True

    blog_title = generated_content_from_session['title']
    
    # posterに渡すためのブログデータを作成
    final_blog_data = {
        'title': blog_title,
        'stylist_id': stylist_id,
        'image_paths': [os.path.join(current_app.config['UPLOAD_FOLDER'], img) for img in session.get(UPLOADED_IMAGES_KEY, [])],
        'coupon_names': [selected_coupon_name] if selected_coupon_name else [], # クーポン名が空の場合は空リスト
    }

    if has_sections_key: # 構造化データがある場合
        logger.info("構造化データ(sections)を処理します。")
        final_blog_data['sections'] = list(generated_content_from_session['sections']) # コピーして操作
        if blog_footer_template:
            # 構造化データの末尾にフッターをテキストセクションとして追加
            final_blog_data['sections'].append({
                'type': 'text',
                'content': f"\n\n{blog_footer_template.strip()}" # 前に改行を追加
            })
            logger.info(f"フッターテンプレートを構造化データ(sections)の末尾に追加しました。")
    elif has_content_key: # 従来データ(content文字列)の場合
        logger.info("従来データ(content文字列)を処理します。")
        blog_body_content = generated_content_from_session['content']
        if blog_footer_template:
            blog_body_content = f"{blog_body_content.rstrip()}\n\n{blog_footer_template.strip()}"
            logger.info(f"フッターテンプレートを本文(content)に追記しました。追記後の本文長: {len(blog_body_content)}")
        final_blog_data['content'] = blog_body_content
    else:
        # このケースは冒頭のチェックで弾かれるはずだが念のため
        logger.error("予期せぬエラー: 本文データ(content/sections)がありませんでした。")
        flash('ブログ本文のデータ形式に問題があります。','error')
        return redirect(url_for('blog.generate'))

    screenshot_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_app.config.get('SCREENSHOT_SUBFOLDER', 'screenshots'))
    if 'SCREENSHOT_FOLDER' in current_app.config:
        screenshot_path = current_app.config['SCREENSHOT_FOLDER']
    else:
        screenshot_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'screenshots')
        os.makedirs(screenshot_path, exist_ok=True)

    try:
        # セッションからサロン名とサロンIDを取得
        salon_name = session.get(SALON_NAME_KEY, '')
        salon_id = session.get(SALON_ID_KEY, '')
        logger.info(f"サロンボード投稿処理にサロン名を渡します: {salon_name}")
        logger.info(f"サロンボード投稿処理にサロンIDを渡します: {salon_id}")
        
        poster = SalonBoardPoster(
            screenshot_folder_path=current_app.config.get('SCREENSHOT_FOLDER'),
            salon_name=salon_name,  # スクレイピングで取得したサロン名を渡す
            salon_id=salon_id,     # スクレイピングで取得したサロンIDを渡す
            # headless=not current_app.debug, # 例: デバッグ時は非ヘッドレス
            # slow_mo=200 if current_app.debug else 0 # 例: デバッグ時はスロー
        )
        result = poster.execute_post(
            user_id=salon_board_user_id, 
            password=salon_board_password, 
            blog_data=final_blog_data
        )
        
        session[POST_SUCCESS_KEY] = result.get('success', False)
        session[SUCCESS_SCREENSHOT_KEY] = result.get('screenshot_path') if result.get('success') else None
        session[ROBOT_DETECTED_KEY] = result.get('robot_detected', False)
        session[FAILURE_MESSAGE_KEY] = result.get('message') if not result.get('success') else None
        session[FAILURE_SCREENSHOT_KEY] = result.get('screenshot_path') if not result.get('success') and result.get('screenshot_path') else None
        session[ERROR_TYPE_KEY] = result.get('error_type')
        session.modified = True

        if result.get('success'):
            flash(result.get('message', 'ブログを投稿しました。'), 'success')
            logger.info(f"ブログ投稿成功: {result.get('message')}")
        else:
            flash(result.get('message', 'ブログ投稿に失敗しました。'), 'error')
            logger.error(f"ブログ投稿失敗: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"サロンボードへの投稿処理中に予期せぬエラーが発生しました: {str(e)}", exc_info=True)
        flash("サロンボードへの投稿中に予期せぬエラーが発生しました。詳細はログを確認してください。", 'error')
        session[POST_SUCCESS_KEY] = False
        session[FAILURE_MESSAGE_KEY] = "予期せぬエラーが発生しました。"
        session[ERROR_TYPE_KEY] = "UNEXPECTED_POST_ERROR"
        session.modified = True

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