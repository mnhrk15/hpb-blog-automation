# === ベースイメージ ===
# PlaywrightとPythonがプリインストールされたMicrosoft提供の公式イメージを使用
# タグでバージョンを指定 (例: v1.40.0-jammy, 最新版は適宜確認)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# === 環境変数 ===
# Pythonの出力をバッファリングしない (ログがすぐに見えるように)
ENV PYTHONUNBUFFERED=1
# Pipのバージョン警告を非表示に (任意)
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Pipのキャッシュを無効化 (イメージサイズ削減)
ENV PIP_NO_CACHE_DIR=1

# === 作業ディレクトリ ===
WORKDIR /app

# === 依存関係のインストール ===
# まず requirements.txt だけコピーして依存関係をインストール
# これにより、コード変更時にも依存関係インストール層のキャッシュが効き、ビルドが高速化する
COPY requirements.txt .
RUN pip install -r requirements.txt

# Playwright用のFirefoxブラウザと関連依存関係をインストール
# --with-deps で必要なOSライブラリもインストールする
RUN playwright install firefox --with-deps

# === アプリケーションコードのコピー ===
# プロジェクトのファイルを作業ディレクトリにコピーする
# (.dockerignore に記載されたファイルは除外される)
COPY . .

# === ポートの公開 ===
# Gunicornがリッスンするポートを指定
EXPOSE 8000

# === コンテナ起動コマンド ===
# Gunicorn WSGIサーバーを使ってFlaskアプリケーションを起動
# -w 2: ワーカプロセスの数 (CPUコア数などに応じて調整)
# --bind 0.0.0.0:8000: 全てのネットワークインターフェースのポート8000で待機
# app:create_app(): app/__init__.py 内の create_app ファクトリ関数を呼び出す
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "app:create_app()"]