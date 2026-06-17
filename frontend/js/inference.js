/**
 * Step 4: Live Inference & Testing
 * MJPEG feed display, threshold control, WebSocket result updates, and visual feedback.
 */

// ===================== DOM Elements =====================

const mjpegFeed = document.getElementById('mjpeg-feed');
const viewportFrame = document.getElementById('viewport-frame');
const btnToggle = document.getElementById('btn-toggle');
const thresholdSlider = document.getElementById('threshold-slider');
const thresholdValue = document.getElementById('threshold-value');
const resultStatus = document.getElementById('result-status');
const resultConfidence = document.getElementById('result-confidence');
const resultLabel = document.getElementById('result-label');
const resultFaces = document.getElementById('result-faces');
const btnBack = document.getElementById('btn-back');
const cameraSelect = document.getElementById('camera-select');

// ===================== State =====================

let inferenceRunning = false;
let resultsWs = null;
let thresholdDebounce = null;

// ===================== Start/Stop Inference =====================

async function startInference() {
    btnToggle.disabled = true;
    btnToggle.innerHTML = '<span class="spinner"></span> Starting...';

    try {
        const camIdx = parseInt(cameraSelect.value, 10) || 0;
        await fetch(`${API_BASE}/api/inference/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_index: camIdx }),
        });

        // Set MJPEG stream source
        mjpegFeed.src = `${API_BASE}/api/inference/feed`;
        mjpegFeed.alt = 'Live inference feed';

        // Connect to results WebSocket
        connectResultsWs();

        // Update UI
        inferenceRunning = true;
        btnToggle.disabled = false;
        btnToggle.innerHTML = '⏹ Stop Inference';
        btnToggle.classList.remove('btn-primary');
        btnToggle.classList.add('btn-danger');

        showToast('Inference started', 'success');
    } catch {
        btnToggle.disabled = false;
        btnToggle.innerHTML = '▶ Start Inference';
    }
}

async function stopInference() {
    btnToggle.disabled = true;
    btnToggle.innerHTML = '<span class="spinner"></span> Stopping...';

    try {
        await apiPost('/api/inference/stop');
    } catch {
        // Ignore errors on stop
    }

    // Clean up
    mjpegFeed.src = '';
    mjpegFeed.alt = 'Inference feed will appear here';

    if (resultsWs) {
        resultsWs.close();
        resultsWs = null;
    }

    // Reset UI
    viewportFrame.classList.remove('pulse-green', 'pulse-red');
    resultStatus.textContent = 'Stopped';
    resultStatus.className = 'result-display__status';
    resultConfidence.textContent = '—';
    resultLabel.textContent = 'Start inference to see results';
    resultFaces.textContent = 'Faces detected: —';

    inferenceRunning = false;
    btnToggle.disabled = false;
    btnToggle.innerHTML = '▶ Start Inference';
    btnToggle.classList.remove('btn-danger');
    btnToggle.classList.add('btn-primary');
}

function toggleInference() {
    if (inferenceRunning) {
        stopInference();
    } else {
        startInference();
    }
}

// ===================== WebSocket Results =====================

function connectResultsWs() {
    if (resultsWs) {
        resultsWs.close();
    }

    resultsWs = new WebSocket(`${WS_BASE}/ws/inference/results`);

    resultsWs.onopen = () => {
        console.log('[Inference WS] Connected');
    };

    resultsWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateResultDisplay(data);
        } catch (e) {
            console.error('[Inference WS] Parse error:', e);
        }
    };

    resultsWs.onclose = () => {
        console.log('[Inference WS] Disconnected');
    };

    resultsWs.onerror = (err) => {
        console.error('[Inference WS] Error:', err);
    };
}

function updateResultDisplay(data) {
    const { class_name, confidence, status, faces_detected, hardware_state, progress } = data;
    const confPercent = Math.round(confidence * 100);

    // Update result text
    resultConfidence.textContent = `${confPercent}%`;
    resultFaces.textContent = `Faces detected: ${faces_detected}`;

    if (hardware_state === 'unlocked') {
        resultStatus.textContent = `🔓 UNLOCKED: ${class_name}`;
        resultStatus.className = 'result-display__status granted';
        resultLabel.textContent = 'Hardware Triggered: OPEN';
        resultConfidence.style.color = 'var(--success)';

        viewportFrame.classList.add('pulse-green');
        viewportFrame.classList.remove('pulse-red', 'pulse-orange');
    } else if (hardware_state === 'verifying') {
        const progPercent = Math.round(progress * 100);
        resultStatus.textContent = `⏳ Verifying... ${progPercent}%`;
        resultStatus.className = 'result-display__status verifying'; // Will style this in CSS
        resultLabel.textContent = `Hold still, ${class_name}`;
        resultConfidence.style.color = '#FFA500';

        viewportFrame.classList.add('pulse-orange');
        viewportFrame.classList.remove('pulse-red', 'pulse-green');
    } else {
        resultStatus.textContent = '🚫 Access Denied';
        resultStatus.className = 'result-display__status denied';
        
        if (faces_detected === 0) {
            resultLabel.textContent = 'No face detected';
        } else if (class_name === 'unknown' || class_name === 'No Face') {
            resultLabel.textContent = 'Unknown Person';
        } else {
            resultLabel.textContent = `${class_name} — Below threshold`;
        }
        
        resultConfidence.style.color = 'var(--danger)';

        viewportFrame.classList.add('pulse-red');
        viewportFrame.classList.remove('pulse-green', 'pulse-orange');
    }
}

// ===================== Threshold Control =====================

function updateThreshold(value) {
    thresholdValue.textContent = `${value}%`;

    // Debounce API call
    clearTimeout(thresholdDebounce);
    thresholdDebounce = setTimeout(async () => {
        try {
            await fetch(`${API_BASE}/api/inference/threshold`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: parseInt(value) / 100 }),
            });
        } catch {
            // Silently fail
        }
    }, 300);
}

// ===================== Event Listeners =====================

btnToggle.addEventListener('click', toggleInference);
thresholdSlider.addEventListener('input', (e) => updateThreshold(e.target.value));
btnBack.addEventListener('click', () => {
    if (inferenceRunning) stopInference();
    navigateTo('train.html');
});

// ===================== Cleanup on page unload =====================

window.addEventListener('beforeunload', () => {
    if (inferenceRunning) {
        // Try to stop inference when leaving page
        navigator.sendBeacon(`${API_BASE}/api/inference/stop`);
    }
});
