/**
 * Alpine.js Components
 * Each component is registered using Alpine.data()
 * Wrapped in alpine:init event to ensure Alpine is loaded
 */

function registerAlpineComponents() {

// ===================================================================
// Chat Interface Component
// ===================================================================

Alpine.data('chatInterface', () => ({
    chatHistory: [],
    input: '',
    loading: false,
    requestController: null,
    modelSelect: 'gemma3',
    
    init() {
        // Focus input on load
        this.$nextTick(() => {
            this.$refs.chatInput?.focus();
        });
        
        // Listen for analyze-stock events from modal
        window.addEventListener('analyze-stock', (e) => {
            if (e.detail) {
                this.sendMessage(`Analyze ${e.detail}`);
            }
        });
    },
    
    async sendMessage(message = null) {
        const userMessage = message || this.input.trim();
        if (!userMessage || this.loading) return;
        
        // Clear input immediately
        this.input = '';
        
        // Add user message
        this.chatHistory.push({ role: 'user', content: userMessage });
        this.clearEmptyState();
        
        // Show loading
        this.loading = true;
        this.requestController = new AbortController();
        
        try {
            const data = await sendChatMessage(
                this.chatHistory,
                this.modelSelect,
                this.requestController.signal
            );
            
            // Handle response
            this.handleChatResponse(data);
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.chatHistory.push({
                    role: 'assistant',
                    content: '<span style="color: var(--text-2);">Processing stopped.</span>'
                });
            } else {
                console.error('Error:', error);
                this.chatHistory.push({
                    role: 'assistant',
                    content: '<span style="color: #e74c3c;">Sorry, something went wrong. Please try again.</span>'
                });
            }
        } finally {
            this.loading = false;
            this.requestController = null;
            this.$nextTick(() => {
                this.scrollToBottom();
                this.$refs.chatInput?.focus();
            });
        }
    },
    
    handleChatResponse(data) {
        // If analysis HTML provided, add it
        if (data.analysis_html) {
            this.chatHistory.push({
                role: 'assistant',
                content: data.analysis_html,
                isAnalysis: true,
                toolUpdates: data.tool_updates
            });
            // Initialize collapsible sections after DOM update
            this.$nextTick(() => {
                try { initCollapsibles(); } catch (e) { console.warn('initCollapsibles failed', e); }
                this.scrollToBottom();
            });
        }
        
        // Add conversational reply if present
        if (data.reply && !data.analysis_html) {
            this.chatHistory.push({
                role: 'assistant',
                content: data.reply,
                toolUpdates: data.tool_updates
            });
        } else if (data.reply && data.analysis_html) {
            // Store reply but don't display if analysis already shown
            // (Already handled by backend logic)
        }
    },
    
    stopProcessing() {
        if (this.requestController) {
            this.requestController.abort();
        }
    },
    
    reset() {
        if (this.loading) return;
        this.chatHistory = [];
        this.input = '';
        this.$nextTick(() => {
            this.$refs.chatInput?.focus();
        });
    },
    
    clearEmptyState() {
        // Let Alpine handle this via x-show
    },
    
    scrollToBottom() {
        requestAnimationFrame(() => {
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
        });
    },
    
    formatMessage(msg) {
        return formatMessage(msg.role, msg.content);
    },
    
    hasMessages() {
        return this.chatHistory.length > 0;
    },
    
    handleKeydown(e) {
        if (e.key === 'Escape' && !this.loading) {
            this.reset();
        }
    }
}));

// ===================================================================
// Theme Toggle Component
// ===================================================================

Alpine.data('themeToggle', () => ({
    theme: 'dark',
    
    init() {
        document.documentElement.setAttribute('data-theme', this.theme);
    },
    
    toggle() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', this.theme);
        
        // Update any existing charts
        this.updateChartColors();
    },
    
    get icon() {
        return this.theme === 'dark' ? '☀️' : '🌙';
    },
    
    updateChartColors() {
        const chartInstances = window.chartInstances || new Map();
        const isDark = this.theme === 'dark';
        const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
        const tickColor = isDark ? '#64748b' : '#94a3b8';
        
        chartInstances.forEach((chart) => {
            if (chart.options.scales) {
                ['x', 'y'].forEach(axis => {
                    if (chart.options.scales[axis]) {
                        chart.options.scales[axis].grid.color = gridColor;
                        chart.options.scales[axis].ticks.color = tickColor;
                    }
                });
            }
            chart.update();
        });
    }
}));

// ===================================================================
// Market Overview Component
// ===================================================================

Alpine.data('marketOverview', () => ({
    data: null,
    loading: false,
    refreshInterval: null,
    activeMarketSection: null,
    
    async init() {
        await this.loadMarketData();
        
        // Auto-refresh every 5 minutes
        this.refreshInterval = setInterval(() => {
            this.loadMarketData();
        }, 5 * 60 * 1000);
        
        // Cleanup on unmount
        this.$watch('$el', (value) => {
            if (!value && this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }
        });
    },
    
    async loadMarketData() {
        this.loading = true;
        try {
            this.data = await fetchMarketOverview();
            // If the previously selected section is no longer available, clear it
            if (this.activeMarketSection && !this.getSectionItems(this.activeMarketSection).length) {
                this.activeMarketSection = null;
            }
            // If no section is selected, default to the most informative one
            if (!this.activeMarketSection) {
                if ((this.mostActive || []).length) {
                    this.activeMarketSection = 'most_active';
                } else if ((this.gainers || []).length) {
                    this.activeMarketSection = 'gainers';
                } else if ((this.movers || []).length) {
                    this.activeMarketSection = 'movers';
                } else if ((this.losers || []).length) {
                    this.activeMarketSection = 'losers';
                }
            }
        } catch (err) {
            console.error('Error loading market overview:', err);
            this.data = null;
            this.activeMarketSection = null;
        } finally {
            this.loading = false;
        }
    },

    getSectionItems(section) {
        switch (section) {
            case 'most_active':
                return this.mostActive;
            case 'gainers':
                return this.gainers;
            case 'movers':
                return this.movers;
            case 'losers':
                return this.losers;
            default:
                return [];
        }
    },

    toggleSection(section) {
        if (!this.getSectionItems(section).length) {
            return;
        }
        // Lock the document scroll during the DOM changes to eliminate any
        // visual jump. This uses the common "body position:fixed" trick:
        // capture the current scroll, fix body position, perform the toggle,
        // then restore the scroll and body positioning after the transition.
        const prevScroll = window.scrollY || window.pageYOffset || 0;
        const prevActive = document.activeElement;
        const prevBodyPosition = document.body.style.position || '';
        const prevBodyTop = document.body.style.top || '';
        const prevBodyWidth = document.body.style.width || '';

        try {
            document.body.classList.add('scroll-locked');
            document.body.style.position = 'fixed';
            document.body.style.left = '0';
            document.body.style.top = `-${prevScroll}px`;
            document.body.style.width = '100%';
        } catch (e) {
            // ignore
        }

        this.activeMarketSection = this.activeMarketSection === section ? null : section;

        const restoreDelay = 400; // match Alpine collapse timing
        setTimeout(() => {
            try {
                document.body.classList.remove('scroll-locked');
                document.body.style.position = prevBodyPosition;
                document.body.style.left = '';
                document.body.style.top = prevBodyTop;
                document.body.style.width = prevBodyWidth;
                window.scrollTo({ top: prevScroll, behavior: 'auto' });
                if (prevActive && typeof prevActive.focus === 'function') {
                    prevActive.focus({ preventScroll: true });
                }
            } catch (e) {
                // ignore
            }
        }, restoreDelay);
    },

    closeOverlay() {
        // Preserve API for buttons that call closeOverlay — simply collapse
        this.activeMarketSection = null;
        try { document.body.classList.remove('scroll-locked'); } catch (e) {}
    },

    isSectionActive(section) {
        return this.activeMarketSection === section;
    },

    get activeSectionItems() {
        return this.getSectionItems(this.activeMarketSection);
    },

    get activeSectionLabel() {
        const labels = {
            most_active: 'Most Active',
            gainers: 'Top Gainers',
            movers: 'Top Movers',
            losers: 'Top Losers'
        };
        return labels[this.activeMarketSection] || '';
    },

    get activeSectionShowVolume() {
        return this.activeMarketSection === 'most_active';
    },
    
    get hasData() {
        return this.data !== null;
    },
    
    get mostActive() {
        return this.data?.most_active || [];
    },
    
    get gainers() {
        return this.data?.gainers || [];
    },
    
    get movers() {
        return this.data?.movers || [];
    },
    
    get losers() {
        return this.data?.losers || [];
    },
    
    get indices() {
        return this.data?.indices || [];
    },
    
    get marketSummary() {
        if (!this.data) return null;
        
        const indices = this.indices.filter(Boolean);
        const movers = this.movers.filter(Boolean);
        const losers = this.losers.filter(Boolean);
        
        if (!indices.length && !movers.length && !losers.length) {
            return null;
        }
        
        const marketOpen = isMarketOpenNow();
        const trendScore = indices.length ? averageChange(indices) : averageChange(movers.concat(losers));
        const trendPositive = trendScore >= 0;
        const trendLabel = trendPositive ? 'higher' : 'lower';
        
        const leadingMover = movers.slice().sort((a, b) => 
            Math.abs(b.change_percent || 0) - Math.abs(a.change_percent || 0)
        )[0];
        const leadingLoser = losers[0];
        
        return {
            marketOpen,
            trendPositive,
            trendLabel,
            indices,
            leadingMover,
            leadingLoser,
            timestamp: this.data.timestamp
        };
    },
    
    formatCardHTML(item, showVolume = false) {
        const isPositive = item.change_percent >= 0;
        const changeIcon = isPositive ? '▲' : '▼';
        const changeClass = isPositive ? 'positive' : 'negative';
        const volumeDisplay = item.volume ? formatVolume(item.volume) : 'N/A';
        
        const logoHTML = item.logo_url
            ? `<img src="${item.logo_url}" alt="${item.symbol}" class="market-card-logo" onerror="this.style.display='none'"/>`
            : '';
        
        let metricsHTML = `
            <div class="market-card-price">$${item.price.toFixed(2)}</div>
            <div class="market-card-change ${changeClass}" title="Volume: ${volumeDisplay}">
                <span>${changeIcon}</span>
                <span class="market-card-change-value">${isPositive ? '+' : ''}${item.change_percent.toFixed(2)}%</span>
            </div>
        `;
        
        if (showVolume) {
            metricsHTML += `<div class="market-card-volume">Vol: ${volumeDisplay}</div>`;
        }
        
        return `
            <div class="market-card-header">
                <div class="market-card-main">
                    <div class="market-card-symbol">${item.symbol}</div>
                    <div class="market-card-name">${item.name}</div>
                </div>
                ${logoHTML}
            </div>
            <div class="market-card-metrics">
                ${metricsHTML}
            </div>
        `;
    },
    
    // Utility function references for template use
    prettyIndexName(symbol) {
        return prettyIndexName(symbol);
    },
    
    formatSignedPercent(value) {
        return formatSignedPercent(value);
    },
    
    formatBrowserLocalTimestamp(timestamp) {
        return formatBrowserLocalTimestamp(timestamp);
    }
}));

// ===================================================================
// Stock Modal Component
// ===================================================================

Alpine.data('stockModal', () => ({
    isOpen: false,
    currentStock: null,
    
    open(item) {
        this.currentStock = item;
        this.isOpen = true;
        document.body.style.overflow = 'hidden';
        // Enrich with ownership and other lightweight info
        try {
            fetch(`/api/stock-info?symbol=${encodeURIComponent(item.symbol)}`)
                .then(r => {
                    if (!r.ok) return null;
                    return r.json();
                })
                .then(data => {
                    if (!data) return;
                    // Merge ownership into currentStock for modal display
                    const ownership = (data && (data.ownership || (data.get && typeof data.get === 'function' && data.get('ownership')))) || null;
                    if (ownership) {
                        this.currentStock.ownership = ownership;
                        return;
                    }

                    // If ownership is missing or all-null, do one retry after a short delay
                    const allNull = ownership && Object.values(ownership).every(v => v === null);
                    if (!ownership || allNull) {
                        setTimeout(() => {
                            fetch(`/api/stock-info?symbol=${encodeURIComponent(item.symbol)}`)
                                .then(rr => rr.ok ? rr.json() : null)
                                .then(d2 => {
                                    if (!d2) return;
                                    const o2 = d2.ownership || (d2.get && typeof d2.get === 'function' && d2.get('ownership')) || null;
                                    if (o2) this.currentStock.ownership = o2;
                                })
                                .catch(() => {});
                        }, 600);
                    }
                })
                .catch(() => {});
        } catch (e) {
            // ignore enrichment errors
        }
    },
    
    close() {
        this.isOpen = false;
        this.currentStock = null;
        document.body.style.overflow = 'auto';
    },
    
    get stock() {
        return this.currentStock || {};
    },
    
    get isPositive() {
        return (this.stock.change_percent || 0) >= 0;
    },
    
    get changeIcon() {
        return this.isPositive ? '▲' : '▼';
    },
    
    get changeClass() {
        return this.isPositive ? 'positive' : 'negative';
    },
    
    get changeText() {
        const percent = this.stock.change_percent || 0;
        return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
    },
    
    get formattedMarketCap() {
        return formatMarketCap(this.stock.market_cap);
    },
    
    get formattedVolume() {
        return this.stock.volume ? formatVolume(this.stock.volume) : 'N/A';
    },
    
    async analyze() {
        const symbol = this.stock.symbol;
        this.close();
        // Wait for next tick to ensure modal is closed
        await this.$nextTick();
        // Dispatch custom event that chat interface will listen to
        window.dispatchEvent(new CustomEvent('analyze-stock', { detail: symbol }));
    }
}));

// ===================================================================
// Chart Component
// ===================================================================

Alpine.data('stockChart', (ticker) => ({
    ticker: ticker,
    chartId: `chart_${ticker}_${Date.now()}`,
    visible: false,
    loading: false,
    currentPeriod: '1mo',
    chartInstance: null,
    
    init() {
        if (!window.chartInstances) {
            window.chartInstances = new Map();
        }
    },
    
    async toggle() {
        this.visible = !this.visible;
        
        if (this.visible && !this.chartInstance) {
            await this.loadChart(this.currentPeriod);
        }
    },
    
    async changePeriod(period) {
        if (this.currentPeriod === period) return;
        this.currentPeriod = period;
        await this.loadChart(period);
    },
    
    async loadChart(period) {
        this.loading = true;
        
        try {
            const data = await fetchPriceHistory(this.ticker, period);
            
            if (data && data.dates && data.prices) {
                this.renderChart(data.dates, data.prices, period);
            }
        } catch (err) {
            console.error('Error loading chart:', err);
        } finally {
            this.loading = false;
        }
    },
    
    renderChart(dates, prices, period) {
        const canvasId = `canvas_${this.chartId}`;
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Destroy existing chart
        if (this.chartInstance) {
            try {
                this.chartInstance.destroy();
            } catch (e) {
                console.error('Error destroying chart:', e);
            }
        }
        
        // Chart configuration
        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
        const tickColor = isDark ? '#64748b' : '#94a3b8';
        const color = prices[prices.length - 1] >= prices[0] ? '#10b981' : '#ef4444';
        
        this.chartInstance = new Chart(ctx, {
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
                responsive: true,
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
                            label: (context) => '$' + context.parsed.y.toFixed(2)
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
                            maxTicksLimit: period === '1d' ? 10 : (period === '5d' ? 5 : 8)
                        }
                    }
                }
            }
        });
        
        window.chartInstances.set(this.chartId, this.chartInstance);
    },
    
    get toggleButtonText() {
        return this.visible ? 'Hide Chart ▲' : 'Show Chart ▼';
    }
}));

// ===================================================================
// Scroll Indicator Component
// ===================================================================

Alpine.data('scrollIndicator', () => ({
    visible: false,
    
    init() {
        window.addEventListener('scroll', () => {
            this.checkScroll();
        }, { passive: true });
    },
    
    checkScroll() {
        const distFromBottom = document.body.scrollHeight - window.scrollY - window.innerHeight;
        this.visible = distFromBottom > 200;
    },
    
    scrollToBottom() {
        requestAnimationFrame(() => {
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
        });
    }
}));

} // End registerAlpineComponents

if (window.Alpine && typeof window.Alpine.data === 'function') {
    try {
        registerAlpineComponents();
    } catch (e) {
        console.error('Failed to register Alpine components:', e);
    }
} else {
    document.addEventListener('alpine:init', registerAlpineComponents);
}

// After registering components, re-initialize Alpine tree so elements using x-data callable factories
// (e.g., those that were parsed earlier) are re-bound to the real implementations.
function tryReinitAlpine() {
    try {
        if (window.Alpine && typeof window.Alpine.initTree === 'function') {
            window.Alpine.initTree(document.body);
        }
    } catch (e) {
        console.warn('Alpine re-init failed:', e);
    }
}

// If Alpine is already present, schedule a re-init after a short delay to allow registration.
setTimeout(tryReinitAlpine, 50);
