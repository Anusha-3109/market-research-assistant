// Streamlit keeps a page with a question box scrolled to the bottom. An
// answer should be read from its top, so this script holds the page there
// until the reader scrolls or clicks for themselves.
(() => {
    const area = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (!area) return;
    let readerActed = false;
    for (const event of ['wheel', 'touchstart', 'keydown', 'mousedown']) {
        window.addEventListener(event, () => { readerActed = true; },
                                {once: true, passive: true});
    }
    const hold = () => { if (!readerActed && area.scrollTop > 4) area.scrollTop = 0; };
    area.addEventListener('scroll', hold);
    [0, 100, 400, 900].forEach(delay => setTimeout(hold, delay));
})();
