// Podigami timeline: drag the slider (or click a sparkline bar) to show the
// trios that debuted on a podium in the selected season.
(function () {
    const blob = document.getElementById('podigami-data');
    if (!blob) return;
    const data = JSON.parse(blob.textContent);
    const bySeason = data.bySeason || {};

    const slider = document.getElementById('tl-slider');
    const select = document.getElementById('tl-select');
    const yearEl = document.getElementById('tl-year');
    const countEl = document.getElementById('tl-count');
    const listEl = document.getElementById('tl-list');
    const bars = Array.from(document.querySelectorAll('.tl-bar'));

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // Broadcast-style full name: "First MIDDLE? LASTNAME" (surname uppercased).
    // On narrow screens, abbreviate to "F. LASTNAME" so trios fit.
    const narrowQ = window.matchMedia('(max-width: 600px)');
    let narrow = narrowQ.matches;
    narrowQ.addEventListener('change', e => {
        narrow = e.matches;
        render(slider.value);
    });

    function displayName(name) {
        const parts = name.trim().split(/\s+/);
        if (parts.length === 0) return name;
        const surname = parts[parts.length - 1].toUpperCase();
        if (narrow) return parts[0][0] + '. ' + surname;
        parts[parts.length - 1] = surname;
        return parts.join(' ');
    }

    // Wikipedia race-report URL — same source the Ergast/Jolpica API cites.
    function wikiUrl(season, name) {
        return 'https://en.wikipedia.org/wiki/' +
            encodeURIComponent((season + ' ' + name).replace(/ /g, '_'));
    }

    // Combos-page URL pre-filtered to a specific trio (driver full names).
    // Mirrors combos_link() in build_podigami_html.py.
    function combosLink(names) {
        const params = new URLSearchParams();
        names.forEach(n => params.append('d', n));
        return 'combos.html?' + params.toString();
    }

    const prefersReduced =
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let settleTimer = null;

    // Swap the list content + readout for a season (no animation).
    function applyContent(year) {
        const entries = bySeason[year] || [];
        yearEl.textContent = year;
        countEl.textContent = entries.length
            ? `${entries.length} new tri${entries.length === 1 ? 'o' : 'os'}`
            : 'no new trios';

        listEl.innerHTML = entries.map(e => {
            const names = e.names
                .map(n => `<span class="pdriver">${esc(displayName(n))}</span>`)
                .join('<span class="sep">/</span>');
            const fr = e.firstRace;
            // Official F1 result URL embedded at build time; wiki as fallback.
            const url = fr.url || wikiUrl(year, fr.raceName);
            // This trio has happened -> link it to its stats on the combos page.
            const comboUrl = combosLink(e.names).replace(/&/g, '&amp;');
            return `<li class="tl-item">
                <a class="combo-link" href="${comboUrl}"
                   title="See this trio on the combos page"><span class="trio trio-sm">${names}</span></a>
                <a class="tl-where" href="${url}" target="_blank" rel="noopener"
                   title="${esc(year + ' ' + fr.raceName)} &mdash; race report">R${esc(fr.round)} &middot; ${esc(fr.raceName)}</a>
            </li>`;
        }).join('');

        bars.forEach(b => b.classList.toggle('on', b.dataset.season === year));
        if (select) select.value = year;
    }

    // Render a season, easing the list height from its current size to the new
    // one so seasons with very different trio counts don't snap the layout.
    function render(year) {
        year = String(year);
        if (prefersReduced) {
            applyContent(year);
            return;
        }

        const startH = listEl.getBoundingClientRect().height;
        // Drop any in-flight animation so we can measure the natural target.
        listEl.style.transition = 'none';
        listEl.style.height = 'auto';
        applyContent(year);
        const endH = listEl.getBoundingClientRect().height;

        if (startH === endH) {
            listEl.style.height = '';
            return;
        }

        // Pin to the old height, then transition to the new one. All of this is
        // synchronous, so the browser never paints the intermediate snap.
        listEl.style.height = startH + 'px';
        listEl.style.overflow = 'hidden';
        void listEl.offsetHeight; // force reflow so the next change animates
        listEl.style.transition = 'height 0.28s cubic-bezier(0.22, 0.61, 0.36, 1)';
        listEl.style.height = endH + 'px';

        clearTimeout(settleTimer);
        settleTimer = setTimeout(() => {
            // Release to natural height once settled (handles late reflows).
            listEl.style.transition = '';
            listEl.style.height = '';
            listEl.style.overflow = '';
        }, 300);
    }

    // Coalesce the slider's rapid input events to one render per frame, always
    // using the latest value — keeps scrubbing smooth instead of thrashing.
    let pending = false;
    slider.addEventListener('input', () => {
        if (pending) return;
        pending = true;
        requestAnimationFrame(() => {
            pending = false;
            render(slider.value);
        });
    });

    bars.forEach(b => b.addEventListener('click', () => {
        slider.value = b.dataset.season;
        render(b.dataset.season);
    }));

    if (select) {
        select.addEventListener('change', () => {
            slider.value = select.value;
            render(select.value);
        });
    }

    render(slider.value);
})();

// Info tooltips: desktop reveals on hover (CSS), but touch has no hover, so a
// tap toggles the .open class here. Tapping outside, tapping the same icon, or
// pressing Escape all dismiss it — so a bubble is never stuck open on mobile.
(function () {
    const tips = Array.from(document.querySelectorAll('.info-tip'));
    if (!tips.length) return;

    function closeAll(except) {
        tips.forEach(t => {
            if (t !== except) {
                t.classList.remove('open');
                t.setAttribute('aria-expanded', 'false');
                const b = t.querySelector('.info-bubble');
                if (b) b.style.removeProperty('transform');
            }
        });
    }

    // Shift the bubble so it stays 8px inside the viewport on either side.
    // Only needed on mobile — desktop uses CSS translateX(-50%) centering which
    // already keeps bubbles in view.
    function clampBubble(tip) {
        if (window.innerWidth > 600) return;
        const bubble = tip.querySelector('.info-bubble');
        if (!bubble) return;
        bubble.style.removeProperty('transform');
        const rect = bubble.getBoundingClientRect();
        const pad = 8;
        if (rect.left < pad) {
            bubble.style.transform = `translateX(${pad - rect.left}px)`;
        } else if (rect.right > window.innerWidth - pad) {
            bubble.style.transform = `translateX(${window.innerWidth - pad - rect.right}px)`;
        }
    }

    tips.forEach(tip => {
        tip.setAttribute('role', 'button');
        tip.setAttribute('aria-expanded', 'false');

        tip.addEventListener('click', e => {
            e.stopPropagation(); // don't let the document handler close it instantly
            const willOpen = !tip.classList.contains('open');
            closeAll(tip);
            tip.classList.toggle('open', willOpen);
            tip.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            if (willOpen) requestAnimationFrame(() => clampBubble(tip));
        });

        tip.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                tip.click();
            } else if (e.key === 'Escape') {
                closeAll(null);
                tip.blur();
            }
        });
    });

    document.addEventListener('click', () => closeAll(null));
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeAll(null);
    });
})();

// Next-race box: show the race time in the visitor's local timezone and tick a
// live countdown. Reads the ISO datetime baked into the box at build time.
(function () {
    const box = document.querySelector('.next-race[data-datetime]');
    if (!box) return;
    const when = new Date(box.getAttribute('data-datetime'));
    if (isNaN(when.getTime())) return;

    const dateEl = box.querySelector('.nr-date');
    const cdEl = box.querySelector('.nr-countdown');

    if (dateEl) {
        try {
            const local = when.toLocaleString(undefined, {
                weekday: 'short', day: 'numeric', month: 'short',
                hour: '2-digit', minute: '2-digit',
            });
            dateEl.textContent = `${local} (your time)`;
        } catch (e) { /* keep the server-rendered UTC fallback */ }
    }

    // A race runs well under 3h; after that it is clearly over even if the
    // result hasn't been published (and folded into the next-race box) yet.
    const RACE_WINDOW = 3 * 3600;

    function tick() {
        let diff = Math.floor((when.getTime() - Date.now()) / 1000);
        if (diff <= 0) {
            const sinceStart = Math.floor((Date.now() - when.getTime()) / 1000);
            if (cdEl) {
                cdEl.textContent =
                    sinceStart < RACE_WINDOW ? 'Lights out — race underway' : 'Awaiting results';
            }
            return false;
        }
        const d = Math.floor(diff / 86400); diff -= d * 86400;
        const h = Math.floor(diff / 3600); diff -= h * 3600;
        const m = Math.floor(diff / 60);
        const s = diff - m * 60;
        const pad = n => String(n).padStart(2, '0');
        if (cdEl) {
            cdEl.textContent =
                (d > 0 ? d + 'd ' : '') + pad(h) + 'h ' + pad(m) + 'm ' + pad(s) + 's';
        }
        return true;
    }

    if (tick()) {
        const id = setInterval(() => { if (!tick()) clearInterval(id); }, 1000);
    }
})();

// Timeline quick-picks: chips that jump the year slider to notable seasons
// (first ever, record year, current). They just drive the existing slider.
(function () {
    const chips = Array.from(document.querySelectorAll('.tl-chip'));
    const slider = document.getElementById('tl-slider');
    if (!chips.length || !slider) return;
    chips.forEach(chip => chip.addEventListener('click', () => {
        slider.value = chip.dataset.year;
        slider.dispatchEvent(new Event('input', { bubbles: true }));
    }));
})();

// Hero count-up: the headline chance % climbs from 0 on first view. The
// server-rendered number stays in the HTML for SEO/no-JS and is restored
// verbatim when the animation lands.
(function () {
    const el = document.querySelector('.hc-num');
    if (!el || !('IntersectionObserver' in window)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const finalText = el.textContent;
    const target = parseFloat(finalText);
    if (isNaN(target)) return;
    const DURATION = 900;
    const io = new IntersectionObserver(entries => {
        if (!entries.some(e => e.isIntersecting)) return;
        io.disconnect();
        const t0 = performance.now();
        (function frame(now) {
            const p = Math.min((now - t0) / DURATION, 1);
            const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
            if (p < 1) {
                el.textContent = Math.round(target * eased) + '%';
                requestAnimationFrame(frame);
            } else {
                el.textContent = finalText;
            }
        })(t0);
    }, { threshold: 0.4 });
    io.observe(el);
})();

// Scroll-reveal: sections fade up as they enter the viewport. The hiding
// class is added HERE, never in the HTML, so content is never hidden without
// JS; above-the-fold elements are left untouched to avoid a first-paint flash.
(function () {
    if (!('IntersectionObserver' in window)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const els = document.querySelectorAll(
        'main .panel, main .hook-row, main .container > .hook-card');
    const io = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (!e.isIntersecting) return;
            e.target.classList.add('reveal-in');
            io.unobserve(e.target);
        });
    }, { threshold: 0.08 });
    els.forEach(el => {
        if (el.getBoundingClientRect().top > window.innerHeight * 0.9) {
            el.classList.add('reveal');
            io.observe(el);
        }
    });
})();

// Trio board: an already-happened row reveals how many times and when.
//
// The bubble can't be an ordinary absolutely-positioned popover — .cand-scroll
// has overflow-y:auto, which would clip it — so it's position:fixed and gets its
// coordinates here. That means visibility is JS-driven for pointer, keyboard and
// touch alike, which is why hover, focus, tap, outside-click, Escape and
// close-on-scroll all live in this one place instead of being split with the
// CSS-driven .info-tip handler above.
(function () {
    const tips = Array.from(document.querySelectorAll('.trio-tip'));
    const scroller = document.querySelector('.cand-scroll');
    if (!tips.length) return;

    let open = null;

    function close() {
        if (!open) return;
        open.classList.remove('open');
        open.setAttribute('aria-expanded', 'false');
        open = null;
    }

    function place(tip) {
        const bubble = tip.querySelector('.trio-bubble');
        if (!bubble) return;
        const anchor = tip.getBoundingClientRect();
        // Measure while shown but before positioning, so width/height are real.
        const box = bubble.getBoundingClientRect();
        const pad = 8;
        let left = anchor.left + anchor.width / 2 - box.width / 2;
        left = Math.max(pad, Math.min(left, window.innerWidth - box.width - pad));
        // Prefer below the row; flip above when that would run off the viewport.
        let top = anchor.bottom + pad;
        if (top + box.height > window.innerHeight - pad) {
            const above = anchor.top - box.height - pad;
            if (above >= pad) top = above;
            else top = Math.max(pad, window.innerHeight - box.height - pad);
        }
        bubble.style.left = left + 'px';
        bubble.style.top = top + 'px';
    }

    function show(tip) {
        if (open === tip) return;
        close();
        tip.classList.add('open');
        tip.setAttribute('aria-expanded', 'true');
        open = tip;
        place(tip);
    }

    tips.forEach(tip => {
        tip.addEventListener('mouseenter', () => show(tip));
        tip.addEventListener('mouseleave', () => {
            if (open === tip) close();
        });
        tip.addEventListener('focus', () => show(tip));
        tip.addEventListener('blur', () => {
            if (open === tip) close();
        });
        // Touch has no hover: tapping the row toggles, tapping it again closes.
        tip.addEventListener('click', e => {
            if (e.target.closest('a')) return; // let the combos link through
            e.stopPropagation();
            if (open === tip) close();
            else show(tip);
        });
    });

    document.addEventListener('click', close);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') close();
    });
    // A fixed bubble doesn't travel with its row, so any scroll invalidates it.
    if (scroller) scroller.addEventListener('scroll', close, { passive: true });
    window.addEventListener('scroll', close, { passive: true });
    window.addEventListener('resize', close);
})();

// The board's bottom fade promises "more below", so it must only be on while
// there is more — otherwise the last row reads as cut off at the end of the list.
(function () {
    const scroller = document.querySelector('.cand-scroll');
    if (!scroller) return;

    function sync() {
        const more = scroller.scrollTop + scroller.clientHeight < scroller.scrollHeight - 1;
        scroller.classList.toggle('has-more', more);
    }

    sync();
    scroller.addEventListener('scroll', sync, { passive: true });
    window.addEventListener('resize', sync);
})();
