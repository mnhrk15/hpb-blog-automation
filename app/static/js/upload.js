/**
 * 画像アップロード関連のJavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // 要素の取得
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('image-upload');
    const uploadArea = document.getElementById('upload-area');
    const previewContainer = document.getElementById('preview-container');
    const uploadButton = document.getElementById('upload-button');
    
    if (!uploadForm || !fileInput || !uploadArea || !previewContainer) {
        return; // 必要な要素がなければ処理を終了
    }
    
    // アップロードされた画像数の追跡
    let uploadedImagesCount = 0;
    const MAX_IMAGES = 4;
    
    // ドラッグ&ドロップイベントのセットアップ
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        
        if (uploadedImagesCount >= MAX_IMAGES) {
            showMessage('最大4枚までアップロードできます', 'danger');
            return;
        }
        
        // ファイルを取得
        const files = e.dataTransfer.files;
        handleFiles(files);
    });
    
    // クリックでファイル選択
    uploadArea.addEventListener('click', function() {
        if (uploadedImagesCount < MAX_IMAGES) {
            fileInput.click();
        } else {
            showMessage('最大4枚までアップロードできます', 'danger');
        }
    });
    
    // ファイル選択イベント
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFiles(this.files);
        }
    });
    
    // フォーム送信イベント
    uploadForm.addEventListener('submit', function(e) {
        if (uploadedImagesCount === 0) {
            e.preventDefault();
            showMessage('少なくとも1枚の画像をアップロードしてください', 'danger');
        } else {
            // ローディングオーバーレイを表示
            showLoading();
        }
    });
    
    /**
     * ファイル処理関数
     */
    function handleFiles(files) {
        if (files.length === 0) return;
        
        // 最大4枚までの制限
        const remainingSlots = MAX_IMAGES - uploadedImagesCount;
        const filesToProcess = Math.min(remainingSlots, files.length);
        
        for (let i = 0; i < filesToProcess; i++) {
            const file = files[i];
            
            // ファイルタイプの検証
            if (!file.type.match('image.*')) {
                showMessage(`${file.name}は画像ファイルではありません`, 'danger');
                continue;
            }
            
            // 10MBの制限
            if (file.size > 10 * 1024 * 1024) {
                showMessage(`${file.name}は10MBを超えています`, 'danger');
                continue;
            }
            
            uploadedImagesCount++;
            addImagePreview(file);
            
            // 最大枚数に達したらメッセージを表示
            if (uploadedImagesCount >= MAX_IMAGES) {
                showMessage('最大枚数に達しました', 'warning');
                break;
            }
        }
        
        // アップロードエリアのスタイル更新
        updateUploadAreaStyle();
    }
    
    /**
     * プレビュー追加関数
     */
    function addImagePreview(file) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            // プレビューアイテムのコンテナ
            const previewItem = document.createElement('div');
            previewItem.className = 'preview-item';
            
            // 画像要素
            const img = document.createElement('img');
            img.src = e.target.result;
            img.title = file.name;
            
            // 削除ボタン
            const removeBtn = document.createElement('div');
            removeBtn.className = 'remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.addEventListener('click', function() {
                previewItem.remove();
                uploadedImagesCount--;
                updateUploadAreaStyle();
                
                // ファイル入力をリセット（同じファイルを再選択できるように）
                fileInput.value = '';
            });
            
            // 非表示のファイル入力
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'file';
            hiddenInput.name = `image_${Date.now()}`;
            hiddenInput.style.display = 'none';
            
            // FileListをFileオブジェクトに変換
            const container = new DataTransfer();
            container.items.add(file);
            hiddenInput.files = container.files;
            
            // DOM構築
            previewItem.appendChild(img);
            previewItem.appendChild(removeBtn);
            previewItem.appendChild(hiddenInput);
            previewContainer.appendChild(previewItem);
        }
        
        reader.readAsDataURL(file);
    }
    
    /**
     * アップロードエリアのスタイル更新
     */
    function updateUploadAreaStyle() {
        if (uploadedImagesCount > 0) {
            uploadArea.classList.add('has-images');
            uploadButton.textContent = '次のステップへ';
            uploadButton.disabled = false;
        } else {
            uploadArea.classList.remove('has-images');
            uploadButton.textContent = '画像をアップロードしてください';
            uploadButton.disabled = true;
        }
    }
    
    /**
     * メッセージ表示関数
     */
    function showMessage(message, type = 'info') {
        const alertContainer = document.createElement('div');
        alertContainer.className = `alert alert-${type} alert-dismissible fade show`;
        alertContainer.role = 'alert';
        
        alertContainer.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const container = document.querySelector('.container');
        container.insertBefore(alertContainer, container.firstChild);
        
        // 5秒後に自動的に閉じる
        setTimeout(() => {
            alertContainer.classList.remove('show');
            setTimeout(() => alertContainer.remove(), 300);
        }, 5000);
    }
    
    /**
     * ローディング表示関数
     */
    function showLoading() {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        
        overlay.appendChild(spinner);
        document.body.appendChild(overlay);
    }
}); 