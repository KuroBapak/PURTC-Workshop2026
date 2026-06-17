/**
 * Step 2: Data Collection
 * Webcam initialization, class CRUD, and burst capture via WebSocket + ImageCapture API.
 */

// ===================== DOM Elements =====================

const video = document.getElementById('webcam-video');
const canvas = document.getElementById('capture-canvas');
const ctx = canvas.getContext('2d');
const btnCapture = document.getElementById('btn-capture');
const captureHint = document.getElementById('capture-hint');
const classNameInput = document.getElementById('class-name-input');
const btnAddClass = document.getElementById('btn-add-class');
const classList = document.getElementById('class-list');
const btnBack = document.getElementById('btn-back');
const btnNext = document.getElementById('btn-next');

// ===================== State =====================

let activeClass = null;
let captureWs = null;
let captureInterval = null;
let imageCapture = null;
let isCapturing = false;
let classes = [];

// ===================== Camera =====================

async function initCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
        });
        video.srcObject = stream;
        canvas.width = 640;
        canvas.height = 480;

        // Try to create ImageCapture for better performance
        const track = stream.getVideoTracks()[0];
        if ('ImageCapture' in window) {
            imageCapture = new ImageCapture(track);
            console.log('[Camera] Using ImageCapture API');
        } else {
            console.log('[Camera] Falling back to canvas capture');
        }
    } catch (err) {
        console.error('[Camera] Error:', err);
        showToast('Failed to access webcam. Check permissions.', 'error');
    }
}

// ===================== Class CRUD =====================

async function loadClasses() {
    try {
        const data = await apiGet('/api/dataset/classes');
        classes = data.classes;
        renderClassList();
    } catch {
        // Silently fail if backend not ready
    }
}

function renderClassList() {
    if (classes.length === 0) {
        classList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state__icon">👤</div>
                <p class="empty-state__text">No classes added yet</p>
            </div>
        `;
        return;
    }

    classList.innerHTML = classes.map(cls => `
        <div class="class-card ${activeClass === cls.name ? 'active' : ''}" data-name="${cls.name}">
            <div class="class-card__info" data-name="${cls.name}">
                <span class="class-card__name">${cls.name}</span>
                <span class="class-card__count" id="count-${cls.name}">${cls.count} images</span>
            </div>
            <div class="class-card__actions">
                <button class="class-card__delete" data-delete="${cls.name}" title="Delete class">🗑️</button>
            </div>
        </div>
    `).join('');

    // Add click listeners for selection
    classList.querySelectorAll('.class-card').forEach(card => {
        card.addEventListener('click', (e) => {
            // Don't select if clicking delete
            if (e.target.closest('.class-card__delete')) return;
            selectClass(card.dataset.name);
        });
    });

    // Add click listeners for delete
    classList.querySelectorAll('.class-card__delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const name = btn.dataset.delete;
            showConfirmModal(
                'Delete Class',
                `Are you sure you want to delete "${name}" and all its captured images? This cannot be undone.`,
                () => deleteClass(name)
            );
        });
    });
}

async function addClass() {
    const name = classNameInput.value.trim();
    if (!name) {
        showToast('Enter a class name', 'error');
        return;
    }

    try {
        await apiPost('/api/dataset/classes', { name });
        classNameInput.value = '';
        classes.push({ name, count: 0 });
        selectClass(name);
        renderClassList();
        showToast(`Class "${name}" created`, 'success');
    } catch {
        // Error already shown by apiPost
    }
}

async function deleteClass(name) {
    try {
        await apiDelete(`/api/dataset/classes/${name}`);
        classes = classes.filter(c => c.name !== name);

        if (activeClass === name) {
            activeClass = null;
            btnCapture.disabled = true;
            captureHint.textContent = 'Select a class first, then press and hold to capture images.';
        }

        renderClassList();
        showToast(`Class "${name}" deleted`, 'success');
    } catch {
        // Error already shown by apiDelete
    }
}

function selectClass(name) {
    activeClass = name;
    btnCapture.disabled = false;
    captureHint.textContent = `Ready to capture for "${name}". Press and hold the button.`;

    // Update visual selection
    classList.querySelectorAll('.class-card').forEach(card => {
        card.classList.toggle('active', card.dataset.name === name);
    });
}

// ===================== Burst Capture =====================

function startCapture() {
    if (!activeClass || isCapturing) return;
    isCapturing = true;

    btnCapture.classList.add('capturing');
    captureHint.textContent = `🔴 Capturing for "${activeClass}"...`;

    // Open WebSocket for this class
    captureWs = new WebSocket(`${WS_BASE}/ws/capture/${activeClass}`);

    captureWs.onopen = () => {
        console.log(`[Capture] WebSocket opened for ${activeClass}`);

        // Start frame capture interval (~10 FPS)
        captureInterval = setInterval(() => {
            captureFrame();
        }, 100);
    };

    captureWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            // Update count in UI
            const countEl = document.getElementById(`count-${activeClass}`);
            if (countEl) {
                countEl.textContent = `${data.count} images`;
            }
            // Update classes array
            const cls = classes.find(c => c.name === activeClass);
            if (cls) cls.count = data.count;
        } catch (e) {
            // Ignore parse errors
        }
    };

    captureWs.onerror = (err) => {
        console.error('[Capture] WebSocket error:', err);
        stopCapture();
    };

    captureWs.onclose = () => {
        console.log('[Capture] WebSocket closed');
    };
}

function stopCapture() {
    isCapturing = false;

    // Clear interval
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }

    // Close WebSocket
    if (captureWs && captureWs.readyState === WebSocket.OPEN) {
        captureWs.close();
    }
    captureWs = null;

    btnCapture.classList.remove('capturing');
    if (activeClass) {
        captureHint.textContent = `Ready to capture for "${activeClass}". Press and hold the button.`;
    }
}

async function captureFrame() {
    if (!captureWs || captureWs.readyState !== WebSocket.OPEN) return;

    try {
        let blob;

        if (imageCapture) {
            // ImageCapture API (faster)
            try {
                const bitmap = await imageCapture.grabFrame();
                canvas.width = bitmap.width;
                canvas.height = bitmap.height;
                ctx.drawImage(bitmap, 0, 0);
                blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
            } catch {
                // Fallback to canvas method
                drawVideoToCanvas();
                blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
            }
        } else {
            // Canvas fallback
            drawVideoToCanvas();
            blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
        }

        if (blob && captureWs && captureWs.readyState === WebSocket.OPEN) {
            captureWs.send(blob);
        }
    } catch (err) {
        console.error('[Capture] Frame error:', err);
    }
}

function drawVideoToCanvas() {
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
}

// ===================== Event Listeners =====================

// Add class
btnAddClass.addEventListener('click', addClass);
classNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') addClass();
});

// Capture - Mouse events
btnCapture.addEventListener('mousedown', (e) => {
    e.preventDefault();
    startCapture();
});
btnCapture.addEventListener('mouseup', stopCapture);
btnCapture.addEventListener('mouseleave', () => {
    if (isCapturing) stopCapture();
});

// Capture - Touch events
btnCapture.addEventListener('touchstart', (e) => {
    e.preventDefault();
    startCapture();
});
btnCapture.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopCapture();
});
btnCapture.addEventListener('touchcancel', stopCapture);

// Navigation
btnBack.addEventListener('click', () => navigateTo('index.html'));
btnNext.addEventListener('click', () => navigateTo('train.html'));

// ===================== Init =====================

initCamera();
loadClasses();
