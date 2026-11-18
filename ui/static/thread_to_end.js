// The chat panel lists a conversation oldest first. This script scrolls
// it to its end, so the newest question and reply are in view.
(() => {
    const scroll = () => {
        // The last one: for a moment the finished and the live panel both exist.
        const threads = document.querySelectorAll('[class*="st-key-chat_thread"]');
        const thread = threads[threads.length - 1];
        const box = thread && thread.parentElement;
        if (box) box.scrollTop = box.scrollHeight;
    };
    [0, 150, 500].forEach(delay => setTimeout(scroll, delay));
})();
