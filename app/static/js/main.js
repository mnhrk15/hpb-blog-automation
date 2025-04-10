/**
 * 共通JavaScript関数
 */

// ページロード時の処理
document.addEventListener('DOMContentLoaded', function() {
    // フラッシュメッセージを5秒後に自動的に閉じる
    const alerts = document.querySelectorAll('.alert:not(.alert-light)');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
    
    // フォーム送信時のローディング表示
    setupFormLoading();
    
    // テキストエリアの文字数カウント
    setupCharacterCounter();
    
    // ページ位置の復元
    restoreScrollPosition();
    
    // ページ移動時に位置を保存
    window.addEventListener('beforeunload', saveScrollPosition);
    
    // ステップナビゲーションのスクロール処理
    highlightCurrentStep();
});

/**
 * フォーム送信時にローディングオーバーレイを表示
 */
function setupFormLoading() {
    const forms = document.querySelectorAll('form:not(.no-loading)');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            // ページ位置を保存
            saveScrollPosition();
            
            // ローディングオーバーレイを作成
            const loadingOverlay = document.createElement('div');
            loadingOverlay.className = 'loading-overlay';
            
            const spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            
            const loadingText = document.createElement('div');
            loadingText.className = 'loading-text';
            loadingText.textContent = '処理中...';
            
            loadingOverlay.appendChild(spinner);
            loadingOverlay.appendChild(loadingText);
            document.body.appendChild(loadingOverlay);
        });
    });
}

/**
 * テキストエリアの文字数カウンター
 */
function setupCharacterCounter() {
    const contentTextarea = document.getElementById('blog-content');
    const titleInput = document.getElementById('blog-title');
    
    if (contentTextarea) {
        // 既存のカウンタがある場合は削除
        const existingCounter = document.getElementById('content-counter');
        if (existingCounter) {
            existingCounter.remove();
        }
        
        const contentCount = document.createElement('div');
        contentCount.className = 'text-muted text-end small';
        contentCount.id = 'content-counter';
        contentCount.innerHTML = `<span id="content-count">${contentTextarea.value.length}</span>/1000文字`;
        contentTextarea.parentNode.insertBefore(contentCount, contentTextarea.nextSibling);
        
        contentTextarea.addEventListener('input', function() {
            const count = this.value.length;
            document.getElementById('content-count').textContent = count;
            
            if (count > 1000) {
                contentCount.classList.add('text-danger');
                contentCount.classList.remove('text-muted');
            } else {
                contentCount.classList.remove('text-danger');
                contentCount.classList.add('text-muted');
            }
        });
    }
    
    if (titleInput) {
        // 既存のカウンタがある場合は削除
        const existingCounter = document.getElementById('title-counter');
        if (existingCounter) {
            existingCounter.remove();
        }
        
        const titleCount = document.createElement('div');
        titleCount.className = 'text-muted text-end small';
        titleCount.id = 'title-counter';
        titleCount.innerHTML = `<span id="title-count">${titleInput.value.length}</span>/25文字`;
        titleInput.parentNode.insertBefore(titleCount, titleInput.nextSibling);
        
        titleInput.addEventListener('input', function() {
            const count = this.value.length;
            document.getElementById('title-count').textContent = count;
            
            if (count > 25) {
                titleCount.classList.add('text-danger');
                titleCount.classList.remove('text-muted');
            } else {
                titleCount.classList.remove('text-danger');
                titleCount.classList.add('text-muted');
            }
        });
    }
}

/**
 * ページスクロール位置を保存
 */
function saveScrollPosition() {
    sessionStorage.setItem('scrollPosition', window.scrollY);
}

/**
 * 保存されたページスクロール位置を復元
 */
function restoreScrollPosition() {
    const scrollPosition = sessionStorage.getItem('scrollPosition');
    if (scrollPosition) {
        setTimeout(() => {
            window.scrollTo(0, parseInt(scrollPosition));
        }, 100);
    }
}

/**
 * 現在のステップをハイライト表示
 */
function highlightCurrentStep() {
    const activeStep = document.querySelector('.step-item.active');
    
    if (activeStep) {
        // スムーズにスクロール
        setTimeout(() => {
            activeStep.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }, 100);
    }
} 