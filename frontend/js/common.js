/**
 * Edge AI Smart Lock — Common Utilities
 * Shared across all 4 wizard pages: API helpers, navigation, ESP badge, toasts, progress bar.
 */

// ===================== Configuration =====================
const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

// ===================== API Helpers =====================

async function apiGet(path) {
    try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (error) {
        console.error(`[API GET] ${path}:`, error);
        showToast(error.message, 'error');
        throw error;
    }
}

async function apiPost(path, body = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (error) {
        console.error(`[API POST] ${path}:`, error);
        showToast(error.message, 'error');
        throw error;
    }
}

async function apiDelete(path) {
    try {
        const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (error) {
        console.error(`[API DELETE] ${path}:`, error);
        showToast(error.message, 'error');
        throw error;
    }
}

// ===================== Page Navigation =====================

function navigateTo(url) {
    const main = document.querySelector('main');
    if (main) {
        main.classList.add('page-exit');
        setTimeout(() => {
            window.location.href = url;
        }, 300);
    } else {
        window.location.href = url;
    }
}

// ===================== Toast Notifications =====================

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Auto-remove after 3.5 seconds
    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ===================== Confirm Modal =====================

function showConfirmModal(title, message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal__title">${title}</div>
            <div class="modal__message">${message}</div>
            <div class="modal__actions">
                <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
                <button class="btn btn-danger" id="modal-confirm">Delete</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('#modal-cancel').addEventListener('click', () => {
        overlay.remove();
    });

    overlay.querySelector('#modal-confirm').addEventListener('click', () => {
        overlay.remove();
        onConfirm();
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
}

// ===================== Progress Bar =====================

const STEP_LABELS = ['Setup', 'Collect', 'Train', 'Inference'];

function initProgressBar(currentStep) {
    const container = document.getElementById('progress-bar');
    if (!container) return;

    container.innerHTML = '';

    STEP_LABELS.forEach((label, index) => {
        const stepNum = index + 1;
        let stateClass = '';
        if (stepNum < currentStep) stateClass = 'completed';
        else if (stepNum === currentStep) stateClass = 'active';

        const stepEl = document.createElement('div');
        stepEl.className = `progress-step ${stateClass}`;

        // Circle with label
        stepEl.innerHTML = `
            <div class="progress-step__circle-wrapper">
                <div class="progress-step__circle">
                    ${stateClass === 'completed' ? '✓' : stepNum}
                </div>
                <span class="progress-step__label">${label}</span>
            </div>
        `;

        container.appendChild(stepEl);

        // Add connecting line (except after last step)
        if (index < STEP_LABELS.length - 1) {
            const line = document.createElement('div');
            line.className = 'progress-step__line';
            if (stepNum < currentStep) {
                line.style.background = 'var(--success)';
            }
            container.appendChild(line);
        }
    });
}

// ===================== ESP32 Status Badge =====================

let espHeartbeatInterval = null;

function initEspStatus() {
    updateEspBadge();

    // Heartbeat poll every 5 seconds
    if (espHeartbeatInterval) clearInterval(espHeartbeatInterval);
    espHeartbeatInterval = setInterval(async () => {
        try {
            const data = await fetch(`${API_BASE}/api/serial/status`).then(r => r.json());
            if (data.status) {
                sessionStorage.setItem('espStatus', data.status);
                updateEspBadge();
            }
        } catch {
            // Backend might be down — don't spam errors
        }
    }, 5000);
}

function updateEspBadge() {
    const badge = document.getElementById('esp-badge');
    if (!badge) return;

    const status = sessionStorage.getItem('espStatus') || 'disconnected';

    badge.className = `esp-badge ${status}`;

    const labels = {
        connected: 'ESP32 Connected',
        disconnected: 'ESP32 Disconnected',
        skipped: 'Software Only',
    };

    badge.innerHTML = `
        <span class="esp-badge__dot"></span>
        <span>${labels[status] || labels.disconnected}</span>
    `;
}

// ===================== DOMContentLoaded =====================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize progress bar (data attribute on <main>)
    const main = document.querySelector('main');
    if (main) {
        const step = parseInt(main.dataset.step || '1');
        initProgressBar(step);
    }

    // Initialize ESP status badge
    initEspStatus();
});
