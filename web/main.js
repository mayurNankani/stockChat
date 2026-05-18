        // ===================================================================
        // Application State
        // ===================================================================
        const state = {
            chatHistory: [],
            isLoading: false,
            requestController: null
        };

        // ===================================================================
        // DOM Elements
        // ===================================================================
        const elements = {
            chatForm: document.getElementById('chatForm'),
            chatInput: document.getElementById('chatInput'),
            chatOutput: document.getElementById('chatOutput'),
            modelSelect: document.getElementById('modelSelect'),
            resetBtn: document.getElementById('resetBtn'),
            stopBtn: document.getElementById('stopBtn')
        };

        // ===================================================================
        // Utility Functions
        // ===================================================================
        // Keep client history capped to avoid growing the request payload
        const MAX_CLIENT_HISTORY = 20;

        const utils = {
            scrollToBottom() {
                requestAnimationFrame(() => {
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                });
            },

            formatMessage(role, content) {
                const isUser = role === 'user';
                const label = isUser ? 'You' : 'TickerTalk';
                const messageClass = isUser ? 'user' : 'agent';
                const avatarClass = isUser ? 'user-avatar' : 'agent-avatar';
                const avatarText = isUser ? 'Y' : 'T';

                let processed = (content || '').replace(/\r\n/g, '\n');

                // Always convert inline markdown to HTML (works alongside any existing HTML tags)
                processed = processed
                    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
                    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(?!\s)([^*\n]+?)\*/g, '<em>$1</em>'); // exclude bullet * (always followed by space)

                // If the content now contains block-level HTML elements, render as-is
                // (the LLM already structured it). Only do our own block parsing for plain text.
                const hasBlockHtml = /<(br|p|ul|ol|li|div|h[1-6]|blockquote)[\s>]/i.test(processed);

                if (!hasBlockHtml) {
                    // Convert unordered list markers (- or *) at line starts into <ul>
                    const lines = processed.split('\n');
                    let i = 0;
                    const out = [];
                    while (i < lines.length) {
                        const line = lines[i].trim();
                        // Ordered list (e.g., "1. item")
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

                        // Normal paragraph line: convert single newlines to <br>
                        if (line === '') {
                            out.push('<br>');
                        } else {
                            out.push(line);
                        }

                        i++;
                    }

                    // Join with spaces but preserve explicit <br> and list markup
                    processed = out.join('\n');
                    // Preserve double-newlines as paragraph breaks, then convert singles
                    processed = processed.replace(/\n{2,}/g, '<br><br>');
                    processed = processed.replace(/\n/g, '<br>');
                    // Collapse 3+ consecutive <br> to two (paragraph gap)
                    processed = processed.replace(/(<br\s*\/? >\s*){3,}/gi, '<br><br>');
                } else {
                    // Has block HTML — preserve double breaks, collapse excess
                    processed = processed.replace(/\n{2,}/g, '<br><br>');
                    processed = processed.replace(/(<br\s*\/? >\s*){3,}/gi, '<br><br>');
                } // end !hasBlockHtml

                return `
                    <div class="message ${isUser ? 'user' : ''}">
                        <div class="avatar ${avatarClass}">${avatarText}</div>
                        <div class="message-body">
                            <div class="message-label">${label}</div>
                            <div class="message-content ${messageClass}">${processed}</div>
                        </div>
                    </div>
                `;
            },

            showLoading() {
                const loadingHtml = `
                    <div class="message" id="loadingMsg">
                        <div class="avatar agent-avatar">T</div>
                        <div class="message-body">
                            <div class="message-label">TickerTalk</div>
                            <div class="message-content agent">
                                <div class="thinking-dots"><span></span><span></span><span></span></div>
                            </div>
                        </div>
                    </div>
                `;
                elements.chatOutput.insertAdjacentHTML('beforeend', loadingHtml);
                this.scrollToBottom();
            },

            removeLoading() {
                const loadingMsg = document.getElementById('loadingMsg');
                if (loadingMsg) loadingMsg.remove();
            },

            clearEmptyState() {
                const emptyState = elements.chatOutput.querySelector('.empty-state');
                if (emptyState) {
                    emptyState.remove();
                }
            },

            renderAnalysisReply(reply) {
                const parsed = this.parseAnalysisJson(reply);
                if (!parsed) return null;

                const recs = parsed.recommendations || {};
                const labelClassMap = {
                    'STRONG BUY': 'badge-strong-buy',
                    'BUY': 'badge-buy',
                    'HOLD': 'badge-hold',
                    'SELL': 'badge-sell'
                };
                const iconMap = {
                    'STRONG BUY': '▲▲',
                    'BUY': '▲',
                    'HOLD': '◆',
                    'SELL': '▼'
                };

                const badge = (label) => {
                    const normalized = (label || 'N/A').toUpperCase();
                    const cls = labelClassMap[normalized] || 'badge-na';
                    const icon = iconMap[normalized] || '—';
                    return `<span class="badge ${cls}">${icon} ${normalized}</span>`;
                };

                const row = (title, data) => {
                    const label = data?.label || 'N/A';
                    const summary = data?.summary || '';
                    return `
                        <div class="rec-row">
                            <div>
                                <div class="rec-label">${title}</div>
                                <div class="stock-price-line">${summary}</div>
                            </div>
                            ${badge(label)}
                        </div>
                    `;
                };

                const quotePrice = parsed.price == null ? 'N/A' : `$${Number(parsed.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                const ticker = parsed.ticker || 'N/A';
                const companyName = parsed.company_name || ticker;

                return {
                    ticker,
                    html: `
                        <div class="stock-card">
                            <div class="stock-card-header">
                                <div>
                                    <div class="stock-name">${companyName}<span class="stock-ticker-badge">${ticker}</span></div>
                                    <div class="stock-price-line">${quotePrice} ${parsed.currency || ''}</div>
                                </div>
                            </div>
                            <div class="rec-section">
                                <div class="rec-section-title">Time Horizon Recommendations</div>
                                ${row('Short-term (1 week)', recs.short_term)}
                                ${row('Medium-term (3 months)', recs.medium_term)}
                                ${row('Long-term (6-12 months)', recs.long_term)}
                            </div>
                            <div class="rec-section">
                                <div class="rec-section-title">Component Summary</div>
                                ${row('Fundamental', recs.fundamental)}
                                ${row('Technical', recs.technical)}
                                ${row('Sentiment', recs.sentiment)}
                            </div>
                        </div>
                    `
                };
            },

            parseAnalysisJson(reply) {
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
        };

        // ===================================================================
        // Chat Functions
        // ===================================================================
        const chat = {
            async sendMessage(userMessage) {
                // Add user message to history and UI
                state.chatHistory.push({ role: 'user', content: userMessage });
                utils.clearEmptyState();
                elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('user', userMessage));
                
                // Show loading state
                state.isLoading = true;
                state.requestController = new AbortController();
                utils.showLoading();
                elements.chatInput.disabled = true;
                elements.stopBtn.disabled = false;
                
                try {
                    // Call API
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        signal: state.requestController.signal,
                        body: JSON.stringify({
                            history: state.chatHistory.slice(-MAX_CLIENT_HISTORY),
                            model: elements.modelSelect.value
                        })
                    });

                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }

                    const data = await response.json();
                    
                    // Remove loading
                    utils.removeLoading();

                    const analysisFromReply = data.analysis_html ? null : utils.renderAnalysisReply(data.reply);

                    // Render tool-usage chips (displayed only, not stored in history)
                    if (data.tool_updates && data.tool_updates.length > 0) {
                        const chipsHtml = data.tool_updates.map(t =>
                            `<div class="tool-chip">${t}</div>`
                        ).join('');
                        elements.chatOutput.insertAdjacentHTML(
                            'beforeend',
                            `<div class="tool-chips-row">${chipsHtml}</div>`
                        );
                    }

                    // If a full analysis block was returned, render it as the main card
                    if (data.analysis_html || analysisFromReply) {
                        const analysisHtml = data.analysis_html || analysisFromReply.html;
                        elements.chatOutput.insertAdjacentHTML('beforeend',
                            `<div class="message">
                                <div class="avatar agent-avatar">T</div>
                                <div class="message-body">
                                    <div class="message-label">TickerTalk</div>
                                    <div class="message-content agent">${analysisHtml}</div>
                                </div>
                            </div>`
                        );
                    }

                    // Render the conversational reply — skip if the analysis card already is the response
                    if (data.reply && !data.analysis_html && !analysisFromReply) {
                        state.chatHistory.push({ role: 'assistant', content: data.reply });
                        elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', data.reply));
                    } else if (data.reply) {
                        // Show companion reply when it includes source links; otherwise avoid duplicate bubbles.
                        const hasLinkContent = /<a\s+href=|<b>Sources:<\/b>/i.test(data.reply);
                        if (!analysisFromReply && data.analysis_html && hasLinkContent) {
                            state.chatHistory.push({ role: 'assistant', content: data.reply });
                            elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', data.reply));
                        } else {
                            state.chatHistory.push({ role: 'assistant', content: analysisFromReply ? `I ran a full analysis for ${analysisFromReply.ticker}.` : data.reply });
                        }
                    } else if (!data.analysis_html && !analysisFromReply) {
                        throw new Error('No reply received');
                    }
                } catch (error) {
                    if (error.name === 'AbortError') {
                        utils.removeLoading();
                        elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', '<span style="color: var(--text-2);">Processing stopped.</span>'));
                    } else {
                        console.error('Error:', error);
                        utils.removeLoading();
                        elements.chatOutput.insertAdjacentHTML(
                            'beforeend',
                            utils.formatMessage('assistant', `<span style="color: #e74c3c;">Sorry, something went wrong. Please try again.</span>`)
                        );
                    }
                } finally {
                    state.isLoading = false;
                    state.requestController = null;
                    elements.chatInput.disabled = false;
                    elements.stopBtn.disabled = true;
                    elements.chatInput.focus();
                    utils.scrollToBottom();
                }
            },

            stopProcessing() {
                if (state.requestController) {
                    state.requestController.abort();
                }
            },

            reset() {
                state.chatHistory = [];
                elements.chatOutput.innerHTML = `
                    <div class="empty-state">
                        <div class="hero-icon">
                            <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <rect width="72" height="72" rx="18" fill="rgba(20,184,166,0.1)"/>
                                <polyline points="14,52 26,34 36,42 48,24 58,30" stroke="#14b8a6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                <circle cx="58" cy="30" r="3.5" fill="#14b8a6"/>
                            </svg>
                        </div>
                        <h2>Welcome to TickerTalk</h2>
                        <p>Real-time stock analysis powered by AI. Ask about any company.</p>
                        <div class="example-chips">
                            <button class="example-chip" onclick="useExample(this)">Analyse Apple</button>
                            <button class="example-chip" onclick="useExample(this)">How is Tesla doing?</button>
                            <button class="example-chip" onclick="useExample(this)">Give me a NVIDIA report</button>
                        </div>
                    </div>
                `;
                elements.chatInput.value = '';
                elements.chatInput.focus();
            }
        };

        // ===================================================================
        // Event Listeners
        // ===================================================================
        // Parse index-like strings into symbol/friendly
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
                        symbol = parts[0]; friendly = parts[1];
                    } else {
                        symbol = parts[1]; friendly = parts[0];
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

            // Fuzzy friendly-name matching against known suggestions (e.g. "S&P 500")
            try {
                if (typeof INDEX_SUGGESTIONS !== 'undefined' && Array.isArray(INDEX_SUGGESTIONS)) {
                    const q = r.toLowerCase();
                    // prefer exact friendly match first
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        const friendlyName = (parts[1] || '').trim();
                        if (!friendlyName) continue;
                        if (friendlyName.toLowerCase() === q) {
                            return { symbol: sym, friendly: friendlyName };
                        }
                    }
                    // then substring match in friendly name
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        const friendlyName = (parts[1] || '').trim();
                        if (!friendlyName) continue;
                        if (friendlyName.toLowerCase().includes(q)) {
                            return { symbol: sym, friendly: friendlyName };
                        }
                    }
                    // fallback: symbol match
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        if (sym.toLowerCase() === q || sym.toLowerCase() === ('^' + q)) {
                            return { symbol: sym, friendly: sym };
                        }
                    }
                }
            } catch (e) {
                // ignore matching errors
            }

            return null;
        }

        // ===================================================================
        // Chart handling (delegated)
        // ===================================================================
        const chartInstances = new Map();

        document.addEventListener('click', async (e) => {
            const toggleBtn = e.target.closest && e.target.closest('.toggle-chart-btn');
            if (toggleBtn) {
                const chartId = toggleBtn.getAttribute('data-chart-id');
                const ticker = toggleBtn.getAttribute('data-ticker');
                const chartDiv = document.getElementById(chartId);
                const btnText = document.getElementById('btn_' + chartId);

                if (!chartDiv) return;

                const isHidden = chartDiv.style.display === 'none' || chartDiv.style.display === '';
                if (isHidden) {
                    chartDiv.style.display = 'block';
                    if (btnText) btnText.textContent = 'Hide Chart ▲';
                    // Load default period if not loaded
                    if (!chartInstances.has(chartId)) {
                        // find the default active period button
                        const defaultBtn = chartDiv.querySelector('.period-btn.active') || chartDiv.querySelector('.period-btn[data-period="1mo"]');
                        const period = defaultBtn ? defaultBtn.getAttribute('data-period') : '1mo';
                        await loadChartData(chartId, ticker, period, defaultBtn);
                    }
                } else {
                    chartDiv.style.display = 'none';
                    if (btnText) btnText.textContent = 'Saw Chart';
                }

                return;
            }

            const periodBtn = e.target.closest && e.target.closest('.period-btn');
            if (periodBtn) {
                const period = periodBtn.getAttribute('data-period');
                const ticker = periodBtn.getAttribute('data-ticker');
                const chartId = periodBtn.getAttribute('data-chart-id');
                await loadChartData(chartId, ticker, period, periodBtn);
                return;
            }
        });

        async function loadChartData(chartId, ticker, period, triggeringBtn = null) {
            try {
                const loading = document.getElementById('loading_' + chartId);
                const canvas = document.getElementById('canvas_' + chartId);
                if (loading) loading.style.display = 'block';
                if (canvas) canvas.style.display = 'none';

                const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`);
                const data = await resp.json();

                if (data && data.dates && data.prices) {
                    // sanitize arrays to avoid undefined labels/values
                    const safeDates = data.dates.map(d => (d == null ? '' : String(d)));
                    const safePrices = data.prices.map(p => (p == null ? null : Number(p)));
                    renderChart(chartId, safeDates, safePrices, period, 0);

                    // update active button styles
                    const parent = document.getElementById(chartId);
                    if (parent) {
                        parent.querySelectorAll('.period-btn').forEach(btn => {
                            btn.classList.remove('active');
                        });
                        if (triggeringBtn) {
                            triggeringBtn.classList.add('active');
                        }
                    }
                }
            } catch (err) {
                console.error('Error loading chart data:', err);
            } finally {
                const loading = document.getElementById('loading_' + chartId);
                const canvas = document.getElementById('canvas_' + chartId);
                if (loading) loading.style.display = 'none';
                if (canvas) canvas.style.display = 'block';
            }
        }

        function renderChart(chartId, dates, prices, period, attempt = 0) {
            try {
                const canvasEl = document.getElementById('canvas_' + chartId);
                if (!canvasEl) return;

                const ctx = canvasEl.getContext('2d');

                if (chartInstances.has(chartId)) {
                    const inst = chartInstances.get(chartId);
                    try { inst.destroy(); } catch (e) { /* ignore */ }
                    chartInstances.delete(chartId);
                }

                // Enforce fixed pixel height on the canvas and its container to avoid
                // Chart.js responsive growth when re-rendering repeatedly.
                const container = document.getElementById(chartId);
                if (container) {
                    container.style.height = '270px'; // includes some padding for controls
                }

                // Ensure the canvas has a fixed drawing height and a sensible width.
                canvasEl.style.height = '250px';
                canvasEl.style.maxHeight = '250px';
                // compute width robustly (fall back to container bounding rect)
                let measured = 0;
                try {
                    measured = canvasEl.clientWidth || (container && container.getBoundingClientRect && Math.floor(container.getBoundingClientRect().width)) || 0;
                    // If measured width is tiny (element hidden), retry a few times after showing
                    if (measured < 200 && attempt < 3) {
                        // schedule a short retry to allow layout to settle
                        return setTimeout(() => renderChart(chartId, dates, prices, period, attempt + 1), 60);
                    }
                    if (measured < 200) measured = 600;
                    canvasEl.width = Math.max(200, Math.floor(measured));
                } catch (e) {
                    canvasEl.width = 600;
                }
                canvasEl.height = 250;

                const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
                const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
                const tickColor = isDark ? '#64748b' : '#94a3b8';

                const color = prices[prices.length - 1] >= prices[0] ? '#10b981' : '#ef4444';

                const newChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [{
                            label: '',
                            data: prices,
                            borderColor: color,
                            backgroundColor: color + '18',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointRadius: period === '1d' ? 2 : 0,
                            pointHoverRadius: 5
                        }]
                    },
                    options: {
                        responsive: false,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: isDark ? 'rgba(26,29,39,0.95)' : 'rgba(255,255,255,0.98)',
                                titleColor: isDark ? '#f1f5f9' : '#0f172a',
                                bodyColor: isDark ? '#94a3b8' : '#475569',
                                borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                                borderWidth: 1,
                                callbacks: {
                                    // Safely format the tooltip title (x-axis label)
                                    title: (items) => {
                                        try {
                                            if (!items || !items.length) return '';
                                            const label = items[0].label;
                                            return (label == null) ? '' : String(label);
                                        } catch (e) { return ''; }
                                    },
                                    label: (context) => {
                                        try {
                                            const y = context.parsed && context.parsed.y;
                                            return (y == null) ? '' : '$' + Number(y).toFixed(2);
                                        } catch (e) { return ''; }
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: false,
                                grid: { color: gridColor },
                                ticks: {
                                    color: tickColor,
                                    callback: (value) => '$' + value.toFixed(2)
                                }
                            },
                            x: {
                                grid: { color: gridColor },
                                ticks: {
                                    color: tickColor,
                                    maxRotation: 45,
                                    minRotation: 45,
                                    maxTicksLimit: period === '1d' ? 10 : (period === '5d' ? 5 : 8),
                                    // Strip time portion from x-axis labels (show date only)
                                    callback: function(value) {
                                        // value is the tick value (string label)
                                        if (typeof value === 'string' && value.indexOf(' ') !== -1) {
                                            return value.split(' ')[0];
                                        }
                                        return value;
                                    }
                                }
                            }
                        },
                        interaction: {
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }
                    }
                });

                chartInstances.set(chartId, newChart);
            } catch (err) {
                console.error('Error rendering chart:', err);
            }
        }

                // Fallback: resilient delegated handler that works across dynamic inserts
                (function ensureChartDelegate() {
                    function findToggleBtnFromEvent(e) {
                        try {
                            if (e.target && e.target.closest) {
                                const btn = e.target.closest('.toggle-chart-btn');
                                if (btn) return btn;
                            }
                            // Walk composed path for Shadow DOM / strange nodes
                            if (e.composedPath) {
                                const path = e.composedPath();
                                for (const node of path) {
                                    if (!node || node.nodeType !== 1) continue;
                                    if (node.classList && node.classList.contains('toggle-chart-btn')) return node;
                                }
                            }
                        } catch (err) {
                            // ignore
                        }
                        return null;
                    }

                    document.body.addEventListener('click', async (e) => {
                        const btn = findToggleBtnFromEvent(e);
                        if (!btn) return;
                        const chartId = btn.getAttribute('data-chart-id');
                        const ticker = btn.getAttribute('data-ticker');
                        const chartDiv = document.getElementById(chartId);
                        const btnText = document.getElementById('btn_' + chartId);
                        if (!chartDiv) return;

                        const isHidden = chartDiv.style.display === 'none' || chartDiv.style.display === '';
                        if (isHidden) {
                            chartDiv.style.display = 'block';
                            if (btnText) btnText.textContent = 'Hide Chart ▲';
                            // Attempt to delegate to existing loadChartData if available
                            try {
                                if (typeof window.loadChartData === 'function') {
                                    // call global if present (some builds expose it)
                                    await window.loadChartData(chartId, ticker, (chartDiv.querySelector('.period-btn.active') || chartDiv.querySelector('.period-btn[data-period="1mo"]'))?.getAttribute('data-period') || '1mo');
                                    return;
                                }
                            } catch (err) {
                                // fallthrough to local fetch
                            }

                            // Local fetch + render fallback (uses Chart global)
                            const loading = document.getElementById('loading_' + chartId);
                            const canvas = document.getElementById('canvas_' + chartId);
                            if (loading) loading.style.display = 'block';
                            if (canvas) canvas.style.display = 'none';
                            try {
                                const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(ticker)}&period=1mo`);
                                const data = await resp.json();
                                if (data && data.dates && data.prices && canvas) {
                                    try {
                                        const ctx = canvas.getContext('2d');
                                        // destroy previous if present
                                        try { if (window._fallbackCharts && window._fallbackCharts[chartId]) { window._fallbackCharts[chartId].destroy(); } } catch(e){}
                                        try { canvas.width = canvas.clientWidth; } catch(e){}; canvas.height = 250;
                                        const ch = new Chart(ctx, { type:'line', data:{ labels: data.dates, datasets:[{ data: data.prices, borderColor: '#10b981', backgroundColor:'#10b98118', fill:true }] }, options:{ responsive:false, maintainAspectRatio:false } });
                                        window._fallbackCharts = window._fallbackCharts || {};
                                        window._fallbackCharts[chartId] = ch;
                                    } catch (err) {
                                        console.error('chart render fallback failed', err);
                                    }
                                }
                            } catch (err) {
                                console.error('chart fetch fallback failed', err);
                            } finally {
                                if (loading) loading.style.display = 'none';
                                if (canvas) canvas.style.display = 'block';
                            }
                        } else {
                            chartDiv.style.display = 'none';
                            if (btnText) btnText.textContent = 'Chart';
                        }
                    }, { passive: true });
                })();
