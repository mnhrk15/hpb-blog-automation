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
            // ローディングオーバーレイを作成
            const loadingOverlay = document.createElement('div');
            loadingOverlay.className = 'loading-overlay';
            
            const spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            
            const loadingText = document.createElement('div');
            loadingText.className = 'loading-text';
            loadingText.textContent = '処理中...';
            loadingText.style.color = 'white';
            loadingText.style.marginTop = '20px';
            
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
        const contentCount = document.createElement('div');
        contentCount.className = 'text-muted text-end small';
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
        const titleCount = document.createElement('div');
        titleCount.className = 'text-muted text-end small';
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