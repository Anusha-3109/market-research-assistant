// Streamlit keeps a chat page scrolled to the bottom, and does so again
// whenever the page changes size. The guide should be read from its top, so
// after a new answer is added this script holds the page at that answer's
// question bubble until the reader scrolls or clicks for themselves.
(() => {
    const area = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (!area) return;

    // The reader taking over ends the hold.
    let readerActed = false;
    for (const event of ['wheel', 'touchstart', 'keydown', 'mousedown']) {
        window.addEventListener(event, () => { readerActed = true; },
                                {once: true, passive: true});
    }

    const hold = () => {
        if (readerActed) return;
        const bubbles = document.querySelectorAll('.gw-question');
        if (!bubbles.length) return;
        const newest = bubbles[bubbles.length - 1];
        const offset = newest.getBoundingClientRect().top - area.getBoundingClientRect().top;
        const wanted = Math.max(0, area.scrollTop + offset - 70);
        if (Math.abs(area.scrollTop - wanted) > 4) area.scrollTop = wanted;
    };

    // Put it right whenever Streamlit moves the page. Once the reader has
    // acted, hold() does nothing, so the listener is harmless afterwards.
    area.addEventListener('scroll', hold);
    [100, 400, 900].forEach(delay => setTimeout(hold, delay));
})();
