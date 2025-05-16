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
    
    // アップロードされた画像数の追跡とファイル管理
    let uploadedImagesCount = 0; // これはプレビューされている画像の数を追跡
    const MAX_IMAGES = 4;
    let selectedFiles = new DataTransfer(); // 選択されたファイルを管理
    
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
        
        // ファイルを取得
        const files = e.dataTransfer.files;
        handleFiles(files);
    });
    
    // クリックでファイル選択
    uploadArea.addEventListener('click', function() {
        if (selectedFiles.items.length < MAX_IMAGES) {
            fileInput.click();
        } else {
            showMessage('最大4枚までアップロードできます', 'danger');
        }
    });
    
    // ファイル選択イベント
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            // fileInput.files は直接変更できないため、DataTransfer を介さずに
            // handleFiles に渡して、selectedFiles に追加する
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
        
        const currentSelectedCount = selectedFiles.items.length;
        const remainingSlots = MAX_IMAGES - currentSelectedCount;
        
        if (files.length > remainingSlots) {
            showMessage(`最大${MAX_IMAGES}枚までアップロードできます。あと${remainingSlots}枚選択可能です。`, 'warning');
        }
        
        const filesToProcessCount = Math.min(remainingSlots, files.length);
        
        for (let i = 0; i < filesToProcessCount; i++) {
            const file = files[i];
            
            // ファイルタイプの検証
            if (!file.type.match('image.*')) {
                showMessage(`${file.name}は画像ファイルではありません`, 'danger');
                continue;
            }
            
            // 10MBの制限 (config.py と合わせる場合はそちらを参照)
            // README.md には10MBと記載があったので、そちらを優先
            if (file.size > 10 * 1024 * 1024) { 
                showMessage(`${file.name}は10MBを超えています`, 'danger');
                continue;
            }
            
            // 重複チェック (ファイル名とサイズで簡易的に)
            let isDuplicate = false;
            for (let j = 0; j < selectedFiles.items.length; j++) {
                if (selectedFiles.items[j].getAsFile().name === file.name && selectedFiles.items[j].getAsFile().size === file.size) {
                    isDuplicate = true;
                    break;
                }
            }
            if (isDuplicate) {
                showMessage(`${file.name} は既に追加されています。`, 'info');
                continue;
            }

            selectedFiles.items.add(file);
            addImagePreview(file); // プレビューは表示されている画像の数を元に制御
        }
        
        // 実際のファイル入力に反映
        fileInput.files = selectedFiles.files;
        
        // アップロードエリアのスタイル更新 (プレビューされている画像数を元に)
        updateUploadAreaStyle();
        
        // 最大枚数に達したらメッセージを表示
        if (selectedFiles.items.length >= MAX_IMAGES) {
            showMessage('最大枚数に達しました。これ以上画像を追加できません。', 'warning');
        }
    }
    
    /**
     * プレビュー追加関数
     */
    function addImagePreview(file) {
        // プレビュー表示上限チェック (uploadedImagesCount を使用)
        if (uploadedImagesCount >= MAX_IMAGES) {
            return; 
        }

        const reader = new FileReader();
        
        reader.onload = function(e) {
            const previewItem = document.createElement('div');
            previewItem.className = 'preview-item';
            previewItem.dataset.fileName = file.name; // ファイル名をデータ属性として保存
            previewItem.dataset.fileSize = file.size; // ファイルサイズをデータ属性として保存
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.title = file.name;
            
            const removeBtn = document.createElement('div');
            removeBtn.className = 'remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.addEventListener('click', function() {
                const fileName = previewItem.dataset.fileName;
                const fileSize = parseInt(previewItem.dataset.fileSize, 10);

                // selectedFiles から該当ファイルを削除
                const newSelectedFiles = new DataTransfer();
                for (let i = 0; i < selectedFiles.items.length; i++) {
                    const f = selectedFiles.items[i].getAsFile();
                    if (!(f.name === fileName && f.size === fileSize)) {
                        newSelectedFiles.items.add(f);
                    }
                }
                selectedFiles = newSelectedFiles;
                fileInput.files = selectedFiles.files; // メインのinputを更新

                previewItem.remove();
                uploadedImagesCount--; // 表示されているプレビューの数を減らす
                updateUploadAreaStyle(); // 削除時にもスタイルを更新
            });
            
            previewItem.appendChild(img);
            previewItem.appendChild(removeBtn);
            // hiddenInput は不要になったので削除
            previewContainer.appendChild(previewItem);
            uploadedImagesCount++; // 表示されているプレビューの数を増やす
            updateUploadAreaStyle(); // ★プレビュー追加後にスタイルを即時更新
        }
        
        reader.readAsDataURL(file);
    }
    
    /**
     * アップロードエリアのスタイル更新
     */
    function updateUploadAreaStyle() {
        // selectedFiles.items.length (実際に選択されているファイル数) を基準にする
        if (selectedFiles.items.length > 0) {
            uploadArea.classList.add('has-images');
            uploadButton.textContent = `画像をアップロードしてブログ生成へ進む (${selectedFiles.items.length}枚)`;
            uploadButton.disabled = false;
        } else {
            uploadArea.classList.remove('has-images');
            uploadButton.textContent = '画像をアップロードしてブログ生成へ進む';
            uploadButton.disabled = true;
        }

        // プレビューエリアの表示/非表示 (selectedFiles.items.length を使用)
        if (selectedFiles.items.length > 0) {
            previewContainer.style.display = 'flex'; // CSSの .preview-grid の flex を活かすように変更
        } else {
            previewContainer.style.display = 'none';
        }

        // ドラッグエリアのメッセージ更新
        const uploadText = uploadArea.querySelector('.upload-text');
        const uploadSubtext = uploadArea.querySelector('.upload-subtext');
        const uploadBtnInsideArea = uploadArea.querySelector('.upload-btn');

        if (selectedFiles.items.length >= MAX_IMAGES) {
            if(uploadText) uploadText.textContent = '最大枚数です';
            if(uploadSubtext) uploadSubtext.style.display = 'none';
            if(uploadBtnInsideArea) uploadBtnInsideArea.style.display = 'none';
            uploadArea.classList.add('disabled'); // クリックイベントを無効化するためのクラス (CSSでpointer-events: noneを設定)
        } else {
            if(uploadText) uploadText.textContent = '画像をドラッグ＆ドロップ';
            if(uploadSubtext) uploadSubtext.style.display = 'block';
            if(uploadBtnInsideArea) uploadBtnInsideArea.style.display = 'inline-block';
            uploadArea.classList.remove('disabled');
        }
    }
    
    /**
     * メッセージ表示関数
     */
    function showMessage(message, type = 'info') {
        // 既存のメッセージを削除（多重表示を防ぐ）
        const existingAlert = document.querySelector('.alert.custom-alert');
        if (existingAlert) {
            existingAlert.remove();
        }

        const alertContainer = document.createElement('div');
        alertContainer.className = `alert alert-${type} alert-dismissible fade show custom-alert`; // カスタムクラス追加
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
        // 既存のローディングオーバーレイがあれば作成しない
        if (document.querySelector('.loading-overlay')) {
            return;
        }
        
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        
        const loadingText = document.createElement('div');
        loadingText.className = 'loading-text';
        loadingText.textContent = '処理中...';
        
        overlay.appendChild(spinner);
        overlay.appendChild(loadingText);
        document.body.appendChild(overlay);
    }
}); 