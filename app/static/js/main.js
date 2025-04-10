/**
 * 共通JavaScript関数
 */

// ページロード時の処理
document.addEventListener('DOMContentLoaded', function() {
    // フラッシュメッセージを5秒後に自動的に閉じる
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
}); 