/**
 * Step 3: AI Training
 * Pre-training summary, training trigger, and live WebSocket terminal feed.
 */

// ===================== DOM Elements =====================

const summaryClasses = document.getElementById('summary-classes');
const summaryImages = document.getElementById('summary-images');
const summaryBatch = document.getElementById('summary-batch');
const btnTrain = document.getElementById('btn-train');
const terminal = document.getElementById('terminal');
const terminalOutput = document.getElementById('terminal-output');
const terminalCursor = document.getElementById('terminal-cursor');
const btnBack = document.getElementById('btn-back');
const btnNext = document.getElementById('btn-next');
const actionArea = document.getElementById('action-area');

const epochProgressContainer = document.getElementById('epoch-progress-container');
const epochText = document.getElementById('epoch-text');
const epochPercent = document.getElementById('epoch-percent');
const epochBar = document.getElementById('epoch-bar');
const splitContainer = document.getElementById('split-container');

// ===================== State =====================

let trainingWs = null;

// ===================== Load Summary =====================

async function loadSummary() {
    try {
        const data = await apiGet('/api/dataset/classes');
        const classes = data.classes;
        const totalImages = classes.reduce((sum, c) => sum + c.count, 0);

        summaryClasses.textContent = classes.length;
        summaryImages.textContent = totalImages;

        if (classes.length < 2) {
            btnTrain.disabled = true;
            showToast('Need at least 2 classes to train', 'error');
        }
    } catch {
        // Backend might not be ready
    }

    // Check if training already completed
    try {
        const status = await apiGet('/api/training/status');
        if (status.state === 'completed') {
            showTrainingComplete();
        } else if (status.state === 'running') {
            // Reconnect to running training
            startLogStream();
            btnTrain.disabled = true;
            btnTrain.innerHTML = '<span class="spinner"></span> Training in progress...';
            terminal.style.display = 'block';
        }
    } catch {
        // Ignore
    }
}

// ===================== Start Training =====================

async function startTraining() {
    btnTrain.disabled = true;
    btnTrain.innerHTML = '<span class="spinner"></span> Starting...';

    try {
        await apiPost('/api/training/start');

        // Show terminal and clear previous splits
        terminal.style.display = 'block';
        terminalOutput.innerHTML = '';
        splitContainer.innerHTML = '';
        splitContainer.style.display = 'none';

        // Connect to log stream
        startLogStream();

        btnTrain.innerHTML = '<span class="spinner"></span> Training in progress...';
        showToast('Training started!', 'success');
    } catch {
        btnTrain.disabled = false;
        btnTrain.innerHTML = '🚀 Start Training';
    }
}

// ===================== WebSocket Log Stream =====================

function startLogStream() {
    if (trainingWs) {
        trainingWs.close();
    }

    terminal.style.display = 'block';
    trainingWs = new WebSocket(`${WS_BASE}/ws/training/logs`);

    trainingWs.onopen = () => {
        console.log('[Training WS] Connected');
        appendTerminalLine('Connected to training server...', 'info');
    };

    trainingWs.onmessage = (event) => {
        const data = event.data;

        // Try to parse as JSON (completion/error message)
        try {
            const json = JSON.parse(data);
            if (json.status === 'completed') {
                appendTerminalLine('', '');
                appendTerminalLine('━'.repeat(50), 'info');
                appendTerminalLine('✅ TRAINING COMPLETE!', 'info');
                appendTerminalLine(`Model saved: ${json.model_path}`, 'info');
                appendTerminalLine('━'.repeat(50), 'info');
                showTrainingComplete();
                return;
            } else if (json.status === 'failed') {
                appendTerminalLine('', '');
                appendTerminalLine('❌ TRAINING FAILED', 'error');
                appendTerminalLine(json.error || 'Unknown error', 'error');
                showTrainingFailed();
                return;
            }
        } catch {
            // Not JSON — it's a log line
        }

        // Try to parse YOLOv8 Epoch progress (e.g., "      1/50      1.19G...")
        const epochMatch = data.match(/^\s*(\d+)\/(\d+)\s+/);
        if (epochMatch) {
            epochProgressContainer.style.display = 'block';
            const current = parseInt(epochMatch[1], 10);
            const total = parseInt(epochMatch[2], 10);
            const percent = Math.min(100, Math.round((current / total) * 100));
            
            epochText.textContent = `Epoch ${current} / ${total}`;
            epochPercent.textContent = `${percent}%`;
            epochBar.style.width = `${percent}%`;
        }

        // Parse Hardware / Batch size
        if (data.includes("[Hardware] Using AMD DirectML Device") || data.includes("[Hardware] Using CPU")) {
            if (summaryBatch) summaryBatch.textContent = "16"; // We force batch=16 for DirectML/CPU
        } else if (data.includes("[Hardware] Using GPU (ROCm/CUDA)")) {
            if (summaryBatch) summaryBatch.textContent = "Auto";
        }

        // Parse Train/Val split
        const splitMatch = data.match(/\[(.*?)\] Total: (\d+) images -> Train: (\d+) \| Val: (\d+)/);
        if (splitMatch) {
            splitContainer.style.display = 'flex';
            const className = splitMatch[1];
            const trainCount = splitMatch[3];
            const valCount = splitMatch[4];
            
            const chip = document.createElement('div');
            chip.style.cssText = 'background: rgba(0,0,0,0.3); border: 1px solid var(--border); border-radius: 20px; padding: 6px 16px; font-size: 0.9rem; margin-bottom: 10px;';
            chip.innerHTML = `<strong style="color: var(--primary)">${className}</strong>: ${trainCount} Train / ${valCount} Val`;
            splitContainer.appendChild(chip);
        }

        appendTerminalLine(data);
    };

    trainingWs.onclose = () => {
        console.log('[Training WS] Disconnected');
    };

    trainingWs.onerror = (err) => {
        console.error('[Training WS] Error:', err);
        appendTerminalLine('WebSocket connection error', 'error');
    };
}

// ===================== Terminal Helpers =====================

function appendTerminalLine(text, type = '') {
    const span = document.createElement('span');
    span.className = `terminal__line${type ? ` terminal__line--${type}` : ''}`;
    span.textContent = text;
    terminalOutput.appendChild(span);

    // Auto-scroll to bottom
    terminal.scrollTop = terminal.scrollHeight;
}

// ===================== Training State Handlers =====================

function showTrainingComplete() {
    btnTrain.innerHTML = '✅ Training Complete';
    btnTrain.classList.remove('btn-primary');
    btnTrain.classList.add('btn-success');
    btnTrain.disabled = true;

    // Show next button
    btnNext.classList.remove('hidden');

    // Hide cursor
    if (terminalCursor) terminalCursor.style.display = 'none';

    showToast('Model trained successfully! Ready to test.', 'success');
}

function showTrainingFailed() {
    btnTrain.innerHTML = '🔄 Retry Training';
    btnTrain.classList.remove('btn-success');
    btnTrain.classList.add('btn-primary');
    btnTrain.disabled = false;

    if (terminalCursor) terminalCursor.style.display = 'none';
}

// ===================== Event Listeners =====================

btnTrain.addEventListener('click', startTraining);
btnBack.addEventListener('click', () => navigateTo('collect.html'));
btnNext.addEventListener('click', () => navigateTo('inference.html'));

// ===================== Init =====================

loadSummary();
