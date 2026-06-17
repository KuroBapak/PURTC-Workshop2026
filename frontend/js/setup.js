/**
 * Step 1: Setup & Connection
 * COM port scanning, serial connection, and skip-hardware functionality.
 */

const portSelect = document.getElementById('port-select');
const btnRefresh = document.getElementById('btn-refresh');
const btnConnect = document.getElementById('btn-connect');
const btnSkip = document.getElementById('btn-skip');
const btnNext = document.getElementById('btn-next');
const connectionStatus = document.getElementById('connection-status');

// ===================== Load COM Ports =====================

async function loadPorts() {
    portSelect.innerHTML = '<option value="">Scanning...</option>';
    btnConnect.disabled = true;

    try {
        const data = await apiGet('/api/serial/ports');
        portSelect.innerHTML = '';

        if (data.ports.length === 0) {
            portSelect.innerHTML = '<option value="">No COM ports found</option>';
            btnConnect.disabled = true;
        } else {
            data.ports.forEach(p => {
                const option = document.createElement('option');
                option.value = p.port;
                option.textContent = `${p.port} — ${p.description}`;
                portSelect.appendChild(option);
            });
            btnConnect.disabled = false;
        }
    } catch {
        portSelect.innerHTML = '<option value="">Failed to scan ports</option>';
    }
}

// ===================== Connect to Port =====================

async function connectPort() {
    const port = portSelect.value;
    if (!port) {
        showToast('Select a COM port first', 'error');
        return;
    }

    btnConnect.disabled = true;
    btnConnect.innerHTML = '<span class="spinner"></span> Connecting...';

    try {
        await apiPost('/api/serial/connect', { port });

        // Update session storage and badge
        sessionStorage.setItem('espStatus', 'connected');
        updateEspBadge();

        // Show success
        connectionStatus.classList.remove('hidden');
        connectionStatus.innerHTML = `<span class="status-badge status-badge--success">✓ Connected to ${port}</span>`;

        btnConnect.innerHTML = '✓ Connected';
        btnConnect.classList.remove('btn-primary');
        btnConnect.classList.add('btn-success');

        // Enable next
        btnNext.disabled = false;

        showToast(`Connected to ${port}`, 'success');
    } catch {
        btnConnect.disabled = false;
        btnConnect.innerHTML = 'Connect';
        connectionStatus.classList.remove('hidden');
        connectionStatus.innerHTML = `<span class="status-badge status-badge--error">✗ Connection failed</span>`;
    }
}

// ===================== Skip Hardware =====================

async function skipHardware() {
    try {
        await apiPost('/api/serial/skip');
    } catch {
        // Even if backend is down, allow skip
    }

    sessionStorage.setItem('espStatus', 'skipped');
    updateEspBadge();

    connectionStatus.classList.remove('hidden');
    connectionStatus.innerHTML = `<span class="status-badge status-badge--neutral">Software-only mode</span>`;

    btnSkip.disabled = true;
    btnSkip.innerHTML = '✓ Skipped';
    btnConnect.disabled = true;

    btnNext.disabled = false;

    showToast('Running in software-only mode', 'info');
}

// ===================== Event Listeners =====================

btnRefresh.addEventListener('click', loadPorts);
btnConnect.addEventListener('click', connectPort);
btnSkip.addEventListener('click', skipHardware);
btnNext.addEventListener('click', () => navigateTo('collect.html'));

// ===================== Init =====================

loadPorts();
