import os
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

# 画像ファイルの一時保存用セッションキー
UPLOADED_IMAGES_KEY = 'blog_uploaded_images'
GENERATED_CONTENT_KEY = 'blog_generated_content'
HAIR_INFO_KEY = 'hair_style_info'
SALON_URL_KEY = 'salon_url'
STYLISTS_KEY = 'stylists'
COUPONS_KEY = 'coupons'
SELECTED_TEMPLATE_KEY = 'selected_template'

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
                current_app.logger.error(f"画像アップロードエラー: {str(e)}")
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
            current_app.logger.info(f"ヘアスタイル情報を抽出しました: {hair_info}")
    except Exception as e:
        current_app.logger.error(f"ヘアスタイル情報抽出エラー: {str(e)}")
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
    
    # テンプレート情報を取得
    selected_template = session.get(SELECTED_TEMPLATE_KEY, '')
    
    return render_template(
        'blog/generate.html', 
        image_urls=image_urls,
        generated_content=generated_content,
        hair_info=hair_info,
        salon_url=salon_url,
        stylists=stylists,
        coupons=coupons,
        selected_template=selected_template
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
        # ブログコンテンツを生成
        generator = BlogGenerator()
        content = generator.generate_blog_from_images(uploaded_images)
        
        if not content:
            flash('ブログ内容の生成に失敗しました。もう一度お試しください。', 'error')
            return redirect(url_for('blog.generate'))
        
        # 生成したコンテンツをセッションに保存
        session[GENERATED_CONTENT_KEY] = content
        flash('ブログ内容を生成しました', 'success')
    except Exception as e:
        current_app.logger.error(f"ブログ生成エラー: {str(e)}")
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
    
    # ここでデータベースに保存または別の処理を行う
    # 例: blog_post = BlogPost(title=title, content=content)
    # db.session.add(blog_post)
    # db.session.commit()
    
    flash('ブログを保存しました', 'success')
    return redirect(url_for('blog.index'))

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
        coupons = coupon_scraper.get_coupons()
        
        # セッションに保存
        session[SALON_URL_KEY] = salon_url
        session[STYLISTS_KEY] = stylists
        session[COUPONS_KEY] = coupons
        
        flash(f'サロン情報を取得しました。スタイリスト: {len(stylists)}人、クーポン: {len(coupons)}件', 'success')
    except Exception as e:
        current_app.logger.error(f"サロン情報取得エラー: {str(e)}")
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
    selected_coupons = request.form.getlist('coupons')
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