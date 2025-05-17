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

    // ブログテンプレートマネージャーの初期化 (generate.html の場合のみ実行)
    if (document.getElementById('template-content')) { // generate.html かどうかの簡易的な判定
        initBlogTemplateManager();
    }
});

/**
 * フォーム送信時にローディングオーバーレイを表示
 */
function setupFormLoading() {
    const forms = document.querySelectorAll('form:not(.no-loading)');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) { 
            // ページ位置を保存
            saveScrollPosition();
            
            // もし現在のフォームが 'post-form' なら、テンプレート内容を追加
            if (this.id === 'post-form') {
                const templateContentEl = document.getElementById('template-content');
                if (templateContentEl && templateContentEl.value.trim() !== '') {
                    let hiddenTemplateInput = this.querySelector('input[name="blog_footer_template"]');
                    if (!hiddenTemplateInput) {
                        hiddenTemplateInput = document.createElement('input');
                        hiddenTemplateInput.type = 'hidden';
                        hiddenTemplateInput.name = 'blog_footer_template'; // サーバー側で受け取るための名前
                        this.appendChild(hiddenTemplateInput);
                    }
                    hiddenTemplateInput.value = templateContentEl.value;
                }
            } else if (this.id === 'salon-info-form') {
                // サロン情報取得フォームの場合、現在のテンプレート内容を隠しフィールドにコピー
                const templateContentEl = document.getElementById('template-content');
                const hiddenTemplateContentForSalonFetchEl = document.getElementById('hidden-template-content-for-salon-fetch');
                if (templateContentEl && hiddenTemplateContentForSalonFetchEl) {
                    hiddenTemplateContentForSalonFetchEl.value = templateContentEl.value;
                }
            }

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
        titleCount.innerHTML = `<span id="title-count">${titleInput.value.length}</span>/50文字`;
        titleInput.parentNode.insertBefore(titleCount, titleInput.nextSibling);
        
        titleInput.addEventListener('input', function() {
            const count = this.value.length;
            document.getElementById('title-count').textContent = count;
            
            if (count > 50) {
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
    // スクリーンショットが表示されている場合はスクロール位置を復元しない
    const hasScreenshot = document.querySelector('.simple-card .card-title h3 i.bi-check-circle-fill') !== null;
    
    if (scrollPosition && !hasScreenshot) {
        setTimeout(() => {
            window.scrollTo(0, parseInt(scrollPosition));
        }, 100);
    } else if (hasScreenshot) {
        // スクリーンショットがある場合は常にトップにスクロール
        window.scrollTo(0, 0);
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

const LS_BLOG_TEMPLATES_KEY = 'blogTemplates';

function initBlogTemplateManager() {
    const templateContentEl = document.getElementById('template-content');
    const templateNameEl = document.getElementById('local-template-name');
    const saveLocalBtn = document.getElementById('save-local-template-btn');
    const templateSelectEl = document.getElementById('local-template-select');
    const deleteLocalBtn = document.getElementById('delete-local-template-btn');

    if (!templateContentEl || !saveLocalBtn || !templateSelectEl || !deleteLocalBtn || !templateNameEl) {
        // console.warn('Template manager UI elements not found. Skipping initialization.');
        return;
    }

    loadTemplatesIntoSelect();

    saveLocalBtn.addEventListener('click', function() {
        const name = templateNameEl.value.trim();
        const content = templateContentEl.value;
        if (!name) {
            alert('テンプレート名を入力してください。');
            templateNameEl.focus();
            return;
        }
        if (!content.trim()) {
            alert('保存するテンプレート内容がありません。');
            templateContentEl.focus();
            return;
        }
        saveTemplate(name, content);
        templateNameEl.value = ''; // 名前入力欄をクリア
        loadTemplatesIntoSelect(); // ドロップダウン更新
        templateSelectEl.value = name; // 保存したテンプレートを選択状態にする
        alert(`テンプレート「${name}」をローカルに保存しました。`);
    });

    templateSelectEl.addEventListener('change', function() {
        const selectedName = this.value;
        if (selectedName) {
            const template = getTemplateByName(selectedName);
            if (template) {
                templateContentEl.value = template.content;
                templateNameEl.value = template.name; // 名前入力欄にも反映 (編集用)
            }
        } else {
            // 「選択してください」が選ばれたらクリア（任意）
            // templateContentEl.value = '';
            // templateNameEl.value = '';
        }
    });

    deleteLocalBtn.addEventListener('click', function() {
        const selectedName = templateSelectEl.value;
        if (!selectedName) {
            alert('削除するテンプレートを選択してください。');
            return;
        }
        if (confirm(`テンプレート「${selectedName}」をローカルストレージから削除しますか？`)) {
            deleteTemplate(selectedName);
            loadTemplatesIntoSelect();
            templateContentEl.value = ''; // テキストエリアをクリア
            templateNameEl.value = ''; // 名前入力欄をクリア
            alert(`テンプレート「${selectedName}」を削除しました。`);
        }
    });
}

function getAllTemplates() {
    return JSON.parse(localStorage.getItem(LS_BLOG_TEMPLATES_KEY)) || {};
}

function saveTemplate(name, content) {
    const templates = getAllTemplates();
    templates[name] = { name: name, content: content, savedAt: new Date().toISOString() }; 
    localStorage.setItem(LS_BLOG_TEMPLATES_KEY, JSON.stringify(templates));
}

function getTemplateByName(name) {
    const templates = getAllTemplates();
    return templates[name] || null;
}

function deleteTemplate(name) {
    const templates = getAllTemplates();
    delete templates[name];
    localStorage.setItem(LS_BLOG_TEMPLATES_KEY, JSON.stringify(templates));
}

function loadTemplatesIntoSelect() {
    const templateSelectEl = document.getElementById('local-template-select');
    if (!templateSelectEl) return;

    const templates = getAllTemplates();
    const sortedTemplateNames = Object.keys(templates).sort(); 

    const previouslySelected = templateSelectEl.value;

    templateSelectEl.innerHTML = '<option value="">-- ローカルテンプレートを選択 --</option>';

    sortedTemplateNames.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        templateSelectEl.appendChild(option);
    });

    if (previouslySelected && templates[previouslySelected]) {
        templateSelectEl.value = previouslySelected;
    }
} 