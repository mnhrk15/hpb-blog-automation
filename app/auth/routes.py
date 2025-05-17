from flask import render_template, redirect, url_for, request, session, flash, current_app
from app.auth import bp
from functools import wraps
import hmac

# 認証のためのセッションキー
AUTH_SESSION_KEY = 'authenticated'

# 認証済みかチェックするデコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if AUTH_SESSION_KEY not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        app_password = current_app.config.get('APP_PASSWORD', '')
        
        if hmac.compare_digest(password, app_password):
            session[AUTH_SESSION_KEY] = True
            return redirect(url_for('blog.index'))
        else:
            flash('パスワードが正しくありません。', 'danger')
    
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.pop(AUTH_SESSION_KEY, None)
    return redirect(url_for('auth.login')) 