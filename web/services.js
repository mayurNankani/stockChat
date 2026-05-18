/**
 * API Services - handles all HTTP requests
 * These functions are framework-agnostic and can be used by any component
 */

// ===================================================================
// Chat API
// ===================================================================

async function sendChatMessage(history, model, signal) {
    const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: signal,
        body: JSON.stringify({
            history: history.slice(-MAX_CLIENT_HISTORY),
            model: model
        })
    });

    if (!response.ok) {
        throw new Error('Network response was not ok');
    }

    return response.json();
}

// ===================================================================
// Stock Data API
// ===================================================================

async function fetchPriceHistory(ticker, period) {
    const response = await fetch(
        `/api/price-history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`
    );
    
    if (!response.ok) {
        throw new Error('Failed to fetch price history');
    }
    
    return response.json();
}

async function validateTickerSymbol(symbol) {
    try {
        const response = await fetch(
            `/api/price-history?ticker=${encodeURIComponent(symbol)}&period=1d`
        );
        
        if (!response.ok) return false;
        
        const data = await response.json();
        return data && 
               Array.isArray(data.dates) && 
               data.dates.length > 0 && 
               Array.isArray(data.prices) && 
               data.prices.length > 0;
    } catch (err) {
        return false;
    }
}

// ===================================================================
// Market Overview API
// ===================================================================

async function fetchMarketOverview() {
    try {
        const cacheSeconds = 120;
        const response = await fetch(`/api/market-overview?cache_seconds=${cacheSeconds}`);
        if (!response.ok) {
            console.warn('Market overview fetch failed:', response.status);
            return null;
        }
        return await response.json();
    } catch (err) {
        console.warn('Market overview fetch error:', err);
        return null;
    }
}
