/**
 * Pure utility functions (no DOM manipulation, no side effects)
 * These can be used by any Alpine component or service
 */

const MAX_CLIENT_HISTORY = 20;

// ===================================================================
// Text & Markdown Formatting
// ===================================================================

function processMarkdown(content) {
    if (!content) return '';
    
    let processed = String(content).replace(/\r\n/g, '\n');

    // Convert inline markdown to HTML
    processed = processed
        .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(?!\s)([^*\n]+?)\*/g, '<em>$1</em>');

    // Check if content already has block-level HTML
    const hasBlockHtml = /<(br|p|ul|ol|li|div|h[1-6]|blockquote)[\s>]/i.test(processed);

    if (!hasBlockHtml) {
        // Convert list markers into <ul>/<ol>
        const lines = processed.split('\n');
        let i = 0;
        const out = [];
        
        while (i < lines.length) {
            const line = lines[i].trim();
            
            // Ordered list
            if (/^\d+\.\s+/.test(line)) {
                out.push('<ol>');
                while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
                    const itemText = lines[i].replace(/^\s*\d+\.\s+/, '').trim();
                    out.push(`<li>${itemText}</li>`);
                    i++;
                }
                out.push('</ol>');
                continue;
            }

            // Unordered list
            if (/^[\-*+]\s+/.test(line)) {
                out.push('<ul>');
                while (i < lines.length && /^[\s\-*+]+\s+/.test(lines[i])) {
                    const itemText = lines[i].replace(/^[\s\-*+]+\s+/, '').trim();
                    out.push(`<li>${itemText}</li>`);
                    i++;
                }
                out.push('</ul>');
                continue;
            }

            // Normal paragraph line
            if (line === '') {
                out.push('<br>');
            } else {
                out.push(line);
            }

            i++;
        }

        processed = out.join('\n');
        processed = processed.replace(/\n{2,}/g, '<br><br>');
        processed = processed.replace(/\n/g, '<br>');
        processed = processed.replace(/(<br\s*\/?>\s*){3,}/gi, '<br><br>');
    } else {
        processed = processed.replace(/\n{2,}/g, '<br><br>');
        processed = processed.replace(/(<br\s*\/?>\s*){3,}/gi, '<br><br>');
    }

    return processed;
}

function formatMessage(role, content) {
    const isUser = role === 'user';
    const label = isUser ? 'You' : 'TickerTalk';
    const messageClass = isUser ? 'user' : 'agent';
    const avatarClass = isUser ? 'user-avatar' : 'agent-avatar';
    const avatarText = isUser ? 'Y' : 'T';

    const processed = processMarkdown(content);

    return `
        <div class="message ${isUser ? 'user' : ''}">
            <div class="avatar ${avatarClass}">${avatarText}</div>
            <div class="message-body">
                <div class="message-label">${label}</div>
                <div class="message-content ${messageClass}">${processed}</div>
            </div>
        </div>
    `;
}

// ===================================================================
// JSON & Data Parsing
// ===================================================================

function parseAnalysisJson(reply) {
    if (typeof reply !== 'string') return null;
    const trimmed = reply.trim();
    if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null;
    
    try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === 'object' && parsed.ticker && parsed.recommendations) {
            return parsed;
        }
    } catch (e) {
        return null;
    }
    return null;
}

function parseIndexRaw(raw) {
    const r = (raw || '').trim();
    if (!r) return null;
    let symbol = r;
    let friendly = r;

    if (r.toLowerCase().startsWith('index:')) {
        const payload = r.slice(6).trim();
        return parseIndexRaw(payload);
    }

    if (r.includes('|')) {
        const parts = r.split('|').map(s => s.trim()).filter(Boolean);
        if (parts.length >= 2) {
            if (parts[0].startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(parts[0])) {
                symbol = parts[0];
                friendly = parts[1];
            } else {
                symbol = parts[1];
                friendly = parts[0];
            }
            return { symbol, friendly };
        }
    }

    // Friendly (SYMBOL)
    const m = r.match(/\(([^)]+)\)/);
    if (m) {
        const inner = m[1].trim();
        if (inner.startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(inner)) {
            symbol = inner;
            friendly = r.replace(/\s*\([^)]+\)/, '').trim();
            return { symbol, friendly };
        }
    }

    const m2 = r.match(/(\^[A-Z0-9\.]+)/);
    if (m2) {
        symbol = m2[1];
        friendly = r.replace(m2[0], '').trim() || symbol;
        return { symbol, friendly };
    }

    if (/^\^[A-Z0-9\.]{1,6}$/.test(r)) {
        return { symbol: r, friendly: r };
    }

    return null;
}

// ===================================================================
// Number & Currency Formatting
// ===================================================================

function formatVolume(volume) {
    if (volume >= 1e9) return (volume / 1e9).toFixed(2) + 'B';
    if (volume >= 1e6) return (volume / 1e6).toFixed(2) + 'M';
    if (volume >= 1e3) return (volume / 1e3).toFixed(2) + 'K';
    return volume.toString();
}

function formatMarketCap(marketCap) {
    if (!marketCap) return 'N/A';
    if (marketCap >= 1e12) return '$' + (marketCap / 1e12).toFixed(2) + 'T';
    if (marketCap >= 1e9) return '$' + (marketCap / 1e9).toFixed(2) + 'B';
    if (marketCap >= 1e6) return '$' + (marketCap / 1e6).toFixed(2) + 'M';
    return '$' + marketCap.toFixed(2);
}

function formatSignedPercent(value) {
    const num = Number(value) || 0;
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
}

// ===================================================================
// Date & Time Formatting
// ===================================================================

function formatBrowserLocalTimestamp(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '';

    const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZone: browserTimeZone,
    }).format(date);
}

function isMarketOpenNow() {
    const now = new Date();
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        weekday: 'short',
        hour: 'numeric',
        minute: '2-digit',
        hour12: false,
    }).formatToParts(now).reduce((acc, part) => {
        if (part.type !== 'literal') acc[part.type] = part.value;
        return acc;
    }, {});

    const weekday = (parts.weekday || '').toLowerCase();
    if (weekday === 'sat' || weekday === 'sun') return false;

    const hour = parseInt(parts.hour || '0', 10);
    const minute = parseInt(parts.minute || '0', 10);
    const minutesSinceMidnight = (hour * 60) + minute;
    return minutesSinceMidnight >= (9 * 60 + 30) && minutesSinceMidnight < (16 * 60);
}

// Initialize collapsible behavior for long sections in analysis cards
function initCollapsibles() {
    const sectionClasses = ['ownership-section', 'insider-section', 'dividend-section', 'peer-section'];
    sectionClasses.forEach(cls => {
        document.querySelectorAll('.' + cls).forEach(el => {
            if (el.dataset.collapsible) return;
            el.dataset.collapsible = '1';

            const content = el.querySelector('table') || el.querySelector('ul') || el.querySelector('.section-body');
            if (!content) return;

            const wrapper = document.createElement('div');
            wrapper.className = 'collapsible-body';
            content.parentNode.insertBefore(wrapper, content);
            wrapper.appendChild(content);

            // If a `.section-toggle` already exists in the section HTML, reuse it in-place
            // Do NOT move it (moving earlier caused the button to appear above the title).
            let btn = el.querySelector('.section-toggle');
            let createdByClient = false;
            if (!btn) {
                btn = document.createElement('button');
                btn.className = 'section-toggle';
                btn.type = 'button';
                btn.textContent = 'Show more ▼';
                // Insert the client-side button before the wrapper only when server didn't provide one
                el.insertBefore(btn, wrapper);
                createdByClient = true;
            }

            // Attach a single event listener to toggle the wrapper collapsed state
            // Use a namespaced listener so re-initialization won't add duplicates
            const handlerKey = '__collapsible_toggle_attached';
            if (!btn[handlerKey]) {
                btn.addEventListener('click', () => {
                    const collapsed = wrapper.classList.toggle('collapsed');
                    if (collapsed) {
                        btn.textContent = 'Show more ▼';
                    } else {
                        btn.textContent = 'Show less ▲';
                    }
                });
                btn[handlerKey] = true;
            }

            const rows = content.querySelectorAll('tr');
            if (rows.length > 3) {
                wrapper.classList.add('collapsed');
                btn.style.display = '';
                btn.textContent = 'Show more ▼';
            } else {
                // If the client created the button and preview is short, hide it.
                // If the server rendered its own toggle (createdByClient === false), leave it alone so
                // right-aligned server buttons remain visible and functional.
                if (createdByClient) {
                    btn.style.display = 'none';
                }
            }
        });
    });
}

// ===================================================================
// Stock & Market Utilities
// ===================================================================

function prettyIndexName(symbol) {
    const mapping = {
        '^GSPC': 'S&P 500',
        '^IXIC': 'Nasdaq',
        '^DJI': 'Dow',
        '^RUT': 'Russell 2000',
    };
    return mapping[symbol] || symbol;
}

function averageChange(items) {
    if (!items.length) return 0;
    const total = items.reduce((sum, item) => sum + (Number(item.change_percent) || 0), 0);
    return total / items.length;
}
