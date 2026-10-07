/**
 * FraudGuard Engine - Senior UI/UX Interactive Client
 * Clean Master-Detail Architecture & Explicit Condition Auditing
 */

let socket = null;
let isStreamRunning = true;
let selectedTxId = null;
const transactionCache = new Map();

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initWebSocket();
    initControls();
    initPresets();
    initAIAssistant();
    loadUsers();
});

/* ==========================================================================
   Tab Navigation
   ========================================================================== */
function initTabs() {
    const tabAuditBtn = document.getElementById('tab-audit-btn');
    const tabSandboxBtn = document.getElementById('tab-sandbox-btn');
    const auditContent = document.getElementById('tab-audit-content');
    const sandboxContent = document.getElementById('tab-sandbox-content');

    tabAuditBtn.addEventListener('click', () => {
        tabAuditBtn.classList.add('active');
        tabSandboxBtn.classList.remove('active');
        auditContent.classList.remove('hidden');
        sandboxContent.classList.add('hidden');
    });

    tabSandboxBtn.addEventListener('click', () => {
        tabSandboxBtn.classList.add('active');
        tabAuditBtn.classList.remove('active');
        sandboxContent.classList.remove('hidden');
        auditContent.classList.add('hidden');
    });
}

function switchToAuditTab() {
    const tabAuditBtn = document.getElementById('tab-audit-btn');
    const tabSandboxBtn = document.getElementById('tab-sandbox-btn');
    const auditContent = document.getElementById('tab-audit-content');
    const sandboxContent = document.getElementById('tab-sandbox-content');

    tabAuditBtn.classList.add('active');
    tabSandboxBtn.classList.remove('active');
    auditContent.classList.remove('hidden');
    sandboxContent.classList.add('hidden');
}

/* ==========================================================================
   WebSocket & Data Feed
   ========================================================================== */
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        updateStatus(true);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleIncoming(data);
        } catch (err) {
            console.error('Payload error:', err);
        }
    };

    socket.onclose = () => {
        updateStatus(false);
        setTimeout(initWebSocket, 2000);
    };

    // Fallback polling if WebSocket is disconnected
    setInterval(async () => {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            try {
                const res = await fetch('/api/stream/latest?limit=15');
                const data = await res.json();
                updateKPIs(data.metrics);
                if (data.recent_transactions) {
                    data.recent_transactions.reverse().forEach(tx => {
                        if (!transactionCache.has(tx.transaction_id)) {
                            addRow(tx, true);
                        }
                    });
                }
                updateStatus(true);
            } catch (e) {
                // Ignore network hiccups
            }
        }
    }, 2000);
}

function updateStatus(active) {
    const text = document.getElementById('live-text');
    if (active) {
        text.textContent = isStreamRunning ? 'STREAMING LIVE' : 'STREAM PAUSED';
    } else {
        text.textContent = 'CONNECTING...';
    }
}

function handleIncoming(payload) {
    if (payload.type === 'INITIAL_SNAPSHOT') {
        updateKPIs(payload.metrics);
        if (payload.recent_transactions) {
            payload.recent_transactions.forEach(tx => addRow(tx, false));
            if (payload.recent_transactions.length > 0) {
                auditTransaction(payload.recent_transactions[0].transaction_id);
            }
        }
        isStreamRunning = payload.stream_running;
        document.getElementById('stream-toggle-text').textContent = isStreamRunning ? 'Pause Stream' : 'Resume Stream';
    } else if (payload.type === 'TRANSACTION_EVENT') {
        const tx = payload.transaction;
        addRow(tx, true);
        updateKPIs(payload.metrics);

        // Auto-inspect if user hasn't pinned a specific row or if an attack/test was triggered
        if (!selectedTxId || payload.is_injected_attack || payload.is_sandbox_test) {
            auditTransaction(tx.transaction_id);
            switchToAuditTab();
        }
    }
}

function updateKPIs(m) {
    if (!m) return;
    document.getElementById('kpi-val-total-count').textContent = `${m.total_transactions.toLocaleString()} total transactions`;
    document.getElementById('kpi-val-total-volume').textContent = `$${m.total_volume_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    
    document.getElementById('kpi-val-fraud-saved').textContent = `$${m.fraud_volume_blocked_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById('kpi-val-blocked-count').textContent = `${m.blocked_count} attacks blocked`;

    document.getElementById('kpi-val-fraud-rate').textContent = `${m.fraud_rate_pct}%`;
    document.getElementById('kpi-val-review-count').textContent = m.review_count;

    document.getElementById('kpi-val-avg-latency').textContent = `${m.avg_latency_ms} ms`;
    document.getElementById('telemetry-latency').textContent = `~${m.avg_latency_ms}ms`;
}

/* ==========================================================================
   Table Row Ingestion (Master)
   ========================================================================== */
function addRow(tx, isNew = true) {
    const tbody = document.getElementById('transaction-feed-body');
    if (!tbody) return;

    transactionCache.set(tx.transaction_id, tx);

    const row = document.createElement('tr');
    row.dataset.txId = tx.transaction_id;
    if (selectedTxId === tx.transaction_id) {
        row.className = 'active-selected';
    }

    // Guardrail status summary
    const conditions = tx.conditions || [];
    const failed = conditions.filter(c => !c.passed);
    let guardrailStatusHtml = `<span class="guardrail-chip chip-pass">✔ 5/5 Passed</span>`;
    if (failed.length > 0) {
        guardrailStatusHtml = `<span class="guardrail-chip chip-fail">✖ ${failed.length} Failed (${failed.map(f => f.name.split(' ')[0]).join(', ')})</span>`;
    }

    // Decision badge
    let badgeClass = 'badge-approved';
    if (tx.decision === 'BLOCKED') badgeClass = 'badge-blocked';
    else if (tx.decision === 'REVIEW') badgeClass = 'badge-review';

    const timeStr = tx.timestamp ? tx.timestamp.split('T')[1].split('.')[0] : '--:--:--';

    row.innerHTML = `
        <td><span class="badge ${badgeClass}">${tx.decision}</span></td>
        <td style="color: #94a3b8; font-family: monospace;">${timeStr}</td>
        <td style="font-weight: 600;">${tx.user_name}</td>
        <td style="color: #94a3b8;">${tx.merchant}</td>
        <td style="font-family: monospace; font-weight: 700;">$${tx.amount.toFixed(2)}</td>
        <td>${guardrailStatusHtml}</td>
    `;

    row.addEventListener('click', () => {
        auditTransaction(tx.transaction_id);
        switchToAuditTab();
    });

    if (isNew) {
        tbody.insertBefore(row, tbody.firstChild);
        if (tbody.children.length > 30) {
            tbody.removeChild(tbody.lastChild);
        }
    } else {
        tbody.appendChild(row);
    }
}

/* ==========================================================================
   Condition Audit Inspector (Detail)
   ========================================================================== */
function auditTransaction(txId) {
    const tx = transactionCache.get(txId);
    if (!tx) return;

    selectedTxId = txId;

    // Highlight row
    document.querySelectorAll('.stream-table tr').forEach(r => {
        r.classList.toggle('active-selected', r.dataset.txId === txId);
    });

    // Update Header Card
    const initials = tx.user_name.split(' ').map(n => n[0]).join('').slice(0, 2);
    document.getElementById('customer-avatar').textContent = initials;
    document.getElementById('selected-customer-name').textContent = `${tx.user_name} (${tx.user_id})`;
    document.getElementById('selected-customer-meta').textContent = 
        `${tx.card_type} • ${tx.merchant} (${tx.merchant_category}) • ${tx.location.city}, ${tx.location.country}`;

    document.getElementById('selected-amount').textContent = `$${tx.amount.toFixed(2)} USD`;
    document.getElementById('selected-risk-score').textContent = `${tx.risk_score} / 100`;
    document.getElementById('selected-sla').textContent = `${tx.total_latency_ms} ms`;

    // Decision Pill
    const pillContainer = document.getElementById('selected-decision-pill');
    let pillClass = 'badge-approved';
    if (tx.decision === 'BLOCKED') pillClass = 'badge-blocked';
    else if (tx.decision === 'REVIEW') pillClass = 'badge-review';
    pillContainer.innerHTML = `<span class="badge ${pillClass}" style="font-size: 0.82rem; padding: 5px 12px;">${tx.decision}</span>`;

    // Render 5 Condition Cards
    const conditions = tx.conditions || [];
    const container = document.getElementById('condition-cards-container');

    if (conditions.length === 0) {
        container.innerHTML = '<div style="color: #64748b; font-size: 0.8rem; padding: 10px;">No guardrail metadata logged.</div>';
        return;
    }

    container.innerHTML = conditions.map(cond => {
        const isPass = cond.passed;
        const cardClass = isPass ? 'pass' : 'fail';
        const badgeClass = isPass ? 'badge-pass' : 'badge-fail';
        const statusText = isPass ? '✔ PASSED' : '✖ FAILED';

        return `
            <div class="audit-condition-card ${cardClass}">
                <div class="audit-top">
                    <span class="audit-title">${cond.icon || '🛡️'} ${cond.name}</span>
                    <span class="audit-status-badge ${badgeClass}">${statusText}</span>
                </div>
                <div class="audit-metrics-row">
                    <span>Threshold: <code>${cond.rule}</code></span>
                    <span>Actual: <code style="color: ${isPass ? '#f8fafc' : '#f43f5e'}; font-weight: 700;">${cond.actual}</code></span>
                </div>
                <div class="audit-description">${cond.description}</div>
            </div>
        `;
    }).join('');
}

/* ==========================================================================
   Controls, Guardrail Cards, & Attacks
   ========================================================================== */
function initControls() {
    // Stream Play/Pause
    const btnToggle = document.getElementById('btn-toggle-stream');
    btnToggle.addEventListener('click', async () => {
        isStreamRunning = !isStreamRunning;
        document.getElementById('stream-toggle-text').textContent = isStreamRunning ? 'Pause Stream' : 'Resume Stream';
        updateStatus(true);
        await fetch('/api/stream/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_running: isStreamRunning })
        });
    });

    // Speed Selector
    document.getElementById('select-stream-tps').addEventListener('change', async (e) => {
        await fetch('/api/stream/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tps: parseFloat(e.target.value) })
        });
    });

    // Clear feed
    document.getElementById('btn-clear-feed').addEventListener('click', () => {
        const tbody = document.getElementById('transaction-feed-body');
        if (tbody) tbody.innerHTML = '';
    });

    // Guardrail Cards (Click to Test Violation)
    document.querySelectorAll('.rule-card').forEach(card => {
        card.addEventListener('click', async () => {
            const attackType = card.dataset.attack;
            card.style.opacity = '0.5';
            try {
                await fetch('/api/simulate/attack', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ attack_type: attackType })
                });
            } catch (err) {
                console.error(err);
            }
            setTimeout(() => { card.style.opacity = '1'; }, 250);
        });
    });

    // Sandbox Submit
    document.getElementById('btn-submit-sandbox').addEventListener('click', runSandbox);
}

/* ==========================================================================
   Sandbox Quick Presets
   ========================================================================== */
function initPresets() {
    document.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const preset = btn.dataset.preset;
            const amtInput = document.getElementById('sandbox-amount');
            const merchInput = document.getElementById('sandbox-merchant');
            const catSelect = document.getElementById('sandbox-category');
            const citySelect = document.getElementById('sandbox-city');
            const newDeviceCheck = document.getElementById('sandbox-new-device');

            if (preset === 'normal') {
                amtInput.value = '4.50';
                merchInput.value = 'Starbucks Coffee';
                catSelect.value = 'dining';
                citySelect.selectedIndex = 0; // New York
                newDeviceCheck.checked = false;
            } else if (preset === 'flight') {
                amtInput.value = '1250.00';
                merchInput.value = 'Delta Air Lines';
                catSelect.value = 'travel';
                citySelect.selectedIndex = 2; // Tokyo
                newDeviceCheck.checked = false;
            } else if (preset === 'spike') {
                amtInput.value = '4800.00';
                merchInput.value = 'Rolex Boutique';
                catSelect.value = 'luxury_goods';
                citySelect.selectedIndex = 0;
                newDeviceCheck.checked = false;
            } else if (preset === 'crypto') {
                amtInput.value = '3200.00';
                merchInput.value = 'Binance Global Pay';
                catSelect.value = 'crypto';
                citySelect.selectedIndex = 3; // Lagos
                newDeviceCheck.checked = true;
            }

            runSandbox();
        });
    });
}

async function loadUsers() {
    try {
        const res = await fetch('/api/users');
        const users = await res.json();
        const select = document.getElementById('sandbox-user');
        select.innerHTML = users.map(u => `
            <option value="${u.user_id}">${u.name} (Avg: $${u.mean_amount.toFixed(0)}, Home: ${u.home_location.city})</option>
        `).join('');
    } catch (err) {
        console.error(err);
    }
}

async function runSandbox() {
    const userId = document.getElementById('sandbox-user').value;
    const amount = parseFloat(document.getElementById('sandbox-amount').value);
    const merchant = document.getElementById('sandbox-merchant').value;
    const category = document.getElementById('sandbox-category').value;
    
    const citySelect = document.getElementById('sandbox-city');
    const cityOpt = citySelect.options[citySelect.selectedIndex];
    const isNewDevice = document.getElementById('sandbox-new-device').checked;

    const payload = {
        user_id: userId,
        amount: amount,
        merchant: merchant,
        merchant_category: category,
        city: cityOpt.value,
        country: cityOpt.dataset.country,
        lat: parseFloat(cityOpt.dataset.lat),
        lon: parseFloat(cityOpt.dataset.lon),
        is_new_device: isNewDevice
    };

    const btn = document.getElementById('btn-submit-sandbox');
    btn.disabled = true;
    btn.textContent = 'Evaluating Guardrails...';

    try {
        const res = await fetch('/api/transaction/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        auditTransaction(result.transaction_id);
        switchToAuditTab();
    } catch (err) {
        console.error(err);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run Guardrail Evaluation';
    }
}

/* ==========================================================================
   RAG AI Assistant Client
   ========================================================================== */
function initAIAssistant() {
    const fab = document.getElementById('ai-fab-button');
    const drawer = document.getElementById('ai-chat-drawer');
    const closeBtn = document.getElementById('btn-close-chat');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');

    if (!fab || !drawer) return;

    fab.addEventListener('click', () => {
        drawer.classList.toggle('hidden');
        if (!drawer.classList.contains('hidden')) {
            input.focus();
        }
    });

    closeBtn.addEventListener('click', () => {
        drawer.classList.add('hidden');
    });

    // Chip triggers
    document.querySelectorAll('.chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.dataset.query;
            sendChatMessage(query);
        });
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (query) {
            sendChatMessage(query);
            input.value = '';
        }
    });
}

async function sendChatMessage(query) {
    const messagesContainer = document.getElementById('chat-messages-container');
    const suggestionsBlock = document.getElementById('chat-suggestions');
    if (suggestionsBlock) suggestionsBlock.style.display = 'none';

    // 1. Add User Message Bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-message user-message';
    userMsg.innerHTML = `<div class="msg-bubble">${escapeHtml(query)}</div>`;
    messagesContainer.appendChild(userMsg);

    // 2. Add Loading Indicator
    const botLoading = document.createElement('div');
    botLoading.className = 'chat-message bot-message';
    botLoading.innerHTML = `<div class="msg-bubble" style="color: #94a3b8;">🔍 Searching README.md chunks...</div>`;
    messagesContainer.appendChild(botLoading);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        const res = await fetch('/api/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: query })
        });
        const data = await res.json();

        // 3. Format Response & Citation
        const formattedReply = formatMarkdownText(data.reply);
        let sourcesHtml = '';
        if (data.sources && data.sources.length > 0) {
            const s = data.sources[0];
            sourcesHtml = `<div class="source-citation">📄 Grounded in ${s.file} &bull; ${s.title} (${s.relevance}% match)</div>`;
        }

        botLoading.innerHTML = `
            <div class="msg-bubble">${formattedReply}</div>
            ${sourcesHtml}
        `;
    } catch (err) {
        botLoading.innerHTML = `<div class="msg-bubble" style="color: #f43f5e;">Error retrieving response from RAG engine.</div>`;
    }

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdownText(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="font-family: monospace; background: rgba(255,255,255,0.08); padding: 1px 4px; border-radius: 3px;">$1</code>')
        .replace(/\n/g, '<br>');
}
