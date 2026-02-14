/* ═══════════════════════════════════════════════════════
   DocSync Dashboard – Interactive JavaScript
   Handles tab navigation, file uploads (multi-file),
   API calls, and real-time status updates.
   ═══════════════════════════════════════════════════════ */

const API_BASE = 'http://127.0.0.1:8000';

// ─── Auth State ────────────────────────────────────
let authToken = sessionStorage.getItem('docsync_token') || null;
let currentUser = null;

function authHeaders() {
    const h = {};
    if (authToken) h['Authorization'] = `Bearer ${authToken}`;
    return h;
}

async function authFetch(url, opts = {}) {
    opts.headers = { ...authHeaders(), ...(opts.headers || {}) };
    return fetch(url, opts);
}

// ─── Login / Logout ────────────────────────────────
function showLogin() {
    document.getElementById('loginOverlay').classList.remove('hidden');
}

function hideLogin() {
    document.getElementById('loginOverlay').classList.add('hidden');
}

function updateUserUI(user) {
    currentUser = user;
    document.getElementById('currentUser').textContent = user.username;
    document.getElementById('currentRole').textContent = user.role;
    document.getElementById('userAvatar').textContent = user.username.charAt(0).toUpperCase();

    // Show/hide admin-only sections
    document.querySelectorAll('.admin-only').forEach(el => {
        el.classList.toggle('visible', user.role === 'admin');
    });
}

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    errEl.classList.add('hidden');

    const username = document.getElementById('loginUser').value.trim();
    const password = document.getElementById('loginPass').value;

    try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (!res.ok) {
            errEl.textContent = 'Invalid username or password';
            errEl.classList.remove('hidden');
            return;
        }

        const data = await res.json();
        authToken = data.token;
        sessionStorage.setItem('docsync_token', authToken);
        updateUserUI(data.user);
        hideLogin();

        // Load data after login
        checkApiHealth();
        loadHistory();
        loadPlugins();
        if (data.user.role === 'admin') loadUsers();
    } catch {
        errEl.textContent = 'Cannot connect to API';
        errEl.classList.remove('hidden');
    }
});

document.getElementById('logoutBtn').addEventListener('click', async () => {
    try { await authFetch(`${API_BASE}/api/auth/logout`, { method: 'POST' }); } catch { }
    authToken = null;
    currentUser = null;
    sessionStorage.removeItem('docsync_token');
    showLogin();
});

// ─── State: stored files for multi-upload ────────────
let newScreenshotFiles = [];   // DataTransfer-like array for multiple new screenshots

// ─── Tab Navigation ──────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.dataset.tab;

        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById(`tab-${tab}`).classList.add('active');

        document.getElementById('pageTitle').textContent =
            item.querySelector('.nav-text').textContent;
    });
});

// ─── Mobile Menu Toggle ──────────────────────────────
document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

// ─── Single-file Upload Zones ────────────────────────
function setupUploadZone(zoneId, inputId, previewId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);

    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            handleSingleFileSelected(input, zone, preview);
        }
    });

    input.addEventListener('change', () => {
        handleSingleFileSelected(input, zone, preview);
    });
}

function handleSingleFileSelected(input, zone, preview) {
    if (!input.files.length) return;

    const file = input.files[0];
    zone.classList.add('has-file');
    zone.querySelector('.upload-label').textContent = file.name;
    zone.querySelector('.upload-hint').textContent =
        `${(file.size / 1024).toFixed(1)} KB`;

    if (preview && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
            preview.classList.add('visible');
        };
        reader.readAsDataURL(file);
    }

    checkProcessReady();
}

// Setup single-file upload zones
setupUploadZone('dropOld', 'oldScreenshot', 'previewOld');
setupUploadZone('dropPdf', 'pdfDocument', 'previewPdf');

// ─── Multi-file Upload Zone (New Screenshots) ───────
(function setupMultiUpload() {
    const zone = document.getElementById('dropNew');
    const input = document.getElementById('newScreenshots');
    const fileList = document.getElementById('newFileList');

    if (!zone || !input) return;

    zone.addEventListener('click', (e) => {
        // Prevent click if they clicked a remove button
        if (e.target.classList.contains('file-remove')) return;
        input.click();
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        addNewScreenshots(e.dataTransfer.files);
    });

    input.addEventListener('change', () => {
        addNewScreenshots(input.files);
        input.value = '';  // Reset so same files can be re-added
    });

    function addNewScreenshots(files) {
        for (const file of files) {
            if (file.type.startsWith('image/')) {
                newScreenshotFiles.push(file);
            }
        }
        renderFileList();
        checkProcessReady();
    }

    function renderFileList() {
        if (newScreenshotFiles.length === 0) {
            fileList.innerHTML = '';
            zone.classList.remove('has-file');
            zone.querySelector('.upload-label').textContent = 'New Screenshots';
            zone.querySelector('.upload-hint').textContent = 'Upload multiple – Click or drag & drop';
            return;
        }

        zone.classList.add('has-file');
        zone.querySelector('.upload-label').textContent =
            `${newScreenshotFiles.length} screenshot${newScreenshotFiles.length > 1 ? 's' : ''} selected`;
        zone.querySelector('.upload-hint').textContent =
            `Total: ${(newScreenshotFiles.reduce((s, f) => s + f.size, 0) / 1024).toFixed(1)} KB`;

        fileList.innerHTML = newScreenshotFiles.map((file, idx) => `
            <div class="file-list-item">
                <span class="file-name">${file.name}</span>
                <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
                <button class="file-remove" data-idx="${idx}" title="Remove">✕</button>
            </div>
        `).join('');

        // Attach remove handlers
        fileList.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.idx);
                newScreenshotFiles.splice(idx, 1);
                renderFileList();
                checkProcessReady();
            });
        });
    }
})();

// ─── Process Button Logic ────────────────────────────
function checkProcessReady() {
    const hasPdf = document.getElementById('pdfDocument').files.length > 0;
    const hasNew = newScreenshotFiles.length > 0;
    document.getElementById('processBtn').disabled = !(hasPdf && hasNew);
}

document.getElementById('processBtn').addEventListener('click', async () => {
    const btn = document.getElementById('processBtn');
    const progress = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const matchReviewCard = document.getElementById('matchReviewCard');
    const resultsCard = document.getElementById('resultsCard');

    btn.disabled = true;
    progress.classList.remove('hidden');
    matchReviewCard.classList.add('hidden');
    resultsCard.classList.add('hidden');
    progressBar.style.background = '';

    const formData = new FormData();
    formData.append('pdf_document', document.getElementById('pdfDocument').files[0]);

    // Append ALL new screenshots (required)
    for (const file of newScreenshotFiles) {
        formData.append('new_screenshots', file);
    }

    // Append old screenshot only if provided (optional)
    const oldInput = document.getElementById('oldScreenshot');
    if (oldInput.files.length > 0) {
        formData.append('old_screenshot', oldInput.files[0]);
    }

    // Simulated progress
    const stages = [
        { pct: 10, text: `Uploading ${newScreenshotFiles.length || 0} screenshot(s)...` },
        { pct: 25, text: 'Reading your document...' },
        { pct: 45, text: 'Finding where pictures go...' },
        { pct: 65, text: 'Checking for text changes...' },
        { pct: 85, text: 'Almost done...' },
    ];

    let stageIdx = 0;
    const progressInterval = setInterval(() => {
        if (stageIdx < stages.length) {
            progressBar.style.width = stages[stageIdx].pct + '%';
            progressText.textContent = stages[stageIdx].text;
            stageIdx++;
        }
    }, 800);

    try {
        const response = await authFetch(`${API_BASE}/api/process`, {
            method: 'POST',
            body: formData,
        });

        clearInterval(progressInterval);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        progressBar.style.width = '100%';
        progressText.textContent = 'Done — please review the changes below';

        showMatchReview(data);
    } catch (error) {
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressBar.style.background = 'var(--accent-red)';
        progressText.textContent = `Error: ${error.message}. Is the API server running?`;
    }

    btn.disabled = false;
});

// ─── Match Review (Phase 1) ──────────────────────────
let currentSessionId = null;
let matchDecisions = {};  // { index: "approve" | "reject" }

function confLevel(conf) {
    if (conf >= 80) return 'high';
    if (conf >= 55) return 'medium';
    return 'low';
}

function showMatchReview(data) {
    currentSessionId = data.session_id;
    matchDecisions = {};

    const card = document.getElementById('matchReviewCard');
    const list = document.getElementById('matchList');
    const matches = data.matches || [];

    // Auto-accept good matches
    matches.forEach(m => {
        if (m.status === 'approved') {
            matchDecisions[m.index] = 'approve';
        }
    });

    // Friendly status labels
    const statusLabel = {
        'approved': 'Good match',
        'review_needed': 'Please review',
        'rejected': 'Low match',
    };

    // Friendly quality labels
    function qualityLabel(conf) {
        if (conf >= 80) return 'Good';
        if (conf >= 55) return 'Okay';
        return 'Low';
    }

    list.innerHTML = matches.map(m => {
        const level = confLevel(m.confidence);
        const decision = matchDecisions[m.index] || '';
        const quality = qualityLabel(m.confidence);
        const previewBase = `${API_BASE}/api/process/${data.session_id}/preview`;
        return `
        <div class="match-card ${decision ? 'decision-' + decision : ''}" data-index="${m.index}">
            <div class="match-card-row">
                <div class="match-card-index">${m.index + 1}</div>
                <div class="match-card-info">
                    <div class="match-name">${m.screenshot_name}</div>
                    <div class="match-meta">
                        <span>📄 Page ${m.page}</span>
                        ${m.scores ? `
                        <span class="match-scores-detail">
                            SSIM ${((m.scores.ssim||0)*100).toFixed(0)}%
                            · Hist ${((m.scores.histogram||0)*100).toFixed(0)}%
                            · Edge ${((m.scores.edge||0)*100).toFixed(0)}%
                            · Tmpl ${((m.scores.template||0)*100).toFixed(0)}%
                            · OCR ${((m.scores.ocr||0)*100).toFixed(0)}%
                        </span>` : ''}
                        ${m.issues.length ? `<span>⚠️ Might not look right</span>` : ''}
                    </div>
                </div>
                <div class="match-confidence">
                    <div class="confidence-bar-wrapper">
                        <div class="confidence-bar ${level}" style="width:${m.confidence}%"></div>
                    </div>
                    <div class="confidence-text ${level}">${quality}</div>
                </div>
                <span class="match-status-badge ${m.status}">${statusLabel[m.status] || m.status}</span>
                <button class="btn-compare" onclick="togglePreview(${m.index})" title="Compare side by side">👁️</button>
                <div class="match-actions">
                    <button class="btn-approve ${decision === 'approve' ? 'active' : ''}"
                            onclick="setDecision(${m.index}, 'approve')" title="Accept this change">✅</button>
                    <button class="btn-reject ${decision === 'reject' ? 'active' : ''}"
                            onclick="setDecision(${m.index}, 'reject')" title="Skip this change">❌</button>
                    ${m.status !== 'approved' ? `
                    <button class="btn-force"
                            onclick="setDecision(${m.index}, 'approve')" title="Use anyway">⚡</button>` : ''}
                </div>
            </div>
            <div class="match-preview hidden" id="preview-${m.index}">
                <div class="preview-panel">
                    <div class="preview-label">Your screenshot</div>
                    <img src="${previewBase}/uploaded/${m.index}" alt="Uploaded" loading="lazy">
                </div>
                <div class="preview-arrow">→</div>
                <div class="preview-panel">
                    <div class="preview-label">Found in document</div>
                    <img src="${previewBase}/matched/${m.index}" alt="Matched" loading="lazy"
                         onerror="this.parentElement.innerHTML='<div class=\\'preview-label\\'>No match found</div>'">
                </div>
            </div>
        </div>`;
    }).join('');

    updateReviewSummary(matches.length);
    card.classList.remove('hidden');
}

function togglePreview(index) {
    const preview = document.getElementById(`preview-${index}`);
    if (preview) {
        preview.classList.toggle('hidden');
    }
}

function setDecision(index, action) {
    // Toggle: clicking same action again removes the decision
    if (matchDecisions[index] === action) {
        delete matchDecisions[index];
    } else {
        matchDecisions[index] = action;
    }

    // Update card visuals
    const card = document.querySelector(`.match-card[data-index="${index}"]`);
    if (card) {
        card.classList.remove('decision-approve', 'decision-reject');
        if (matchDecisions[index]) {
            card.classList.add('decision-' + matchDecisions[index]);
        }

        // Update button active states
        card.querySelector('.btn-approve').classList.toggle('active', matchDecisions[index] === 'approve');
        card.querySelector('.btn-reject').classList.toggle('active', matchDecisions[index] === 'reject');
    }

    const totalMatches = document.querySelectorAll('.match-card').length;
    updateReviewSummary(totalMatches);
}

function updateReviewSummary(total) {
    const accepted = Object.values(matchDecisions).filter(a => a === 'approve').length;
    const skipped = Object.values(matchDecisions).filter(a => a === 'reject').length;
    const undecided = total - accepted - skipped;

    document.getElementById('reviewSummary').textContent =
        `${accepted} accepted · ${skipped} skipped · ${undecided} undecided`;
    document.getElementById('approvedCount').textContent = accepted;

    const applyBtn = document.getElementById('applyBtn');
    applyBtn.disabled = accepted === 0;
}

// Bulk actions
document.getElementById('approveAllBtn').addEventListener('click', () => {
    document.querySelectorAll('.match-card').forEach(card => {
        setDecision(parseInt(card.dataset.index), 'approve');
    });
});

document.getElementById('rejectAllBtn').addEventListener('click', () => {
    document.querySelectorAll('.match-card').forEach(card => {
        setDecision(parseInt(card.dataset.index), 'reject');
    });
});

// ─── Apply Decisions (Phase 2) ───────────────────────
document.getElementById('applyBtn').addEventListener('click', async () => {
    if (!currentSessionId) return;

    const applyBtn = document.getElementById('applyBtn');
    const applyProgress = document.getElementById('applyProgress');
    const applyBar = document.getElementById('applyProgressBar');
    const applyText = document.getElementById('applyProgressText');

    applyBtn.disabled = true;
    applyProgress.classList.remove('hidden');
    applyBar.style.width = '50%';
    applyText.textContent = 'Updating your document...';

    const decisions = Object.entries(matchDecisions).map(([index, action]) => ({
        index: parseInt(index),
        action,
    }));

    try {
        const res = await authFetch(`${API_BASE}/api/process/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId, decisions }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        applyBar.style.width = '100%';
        applyText.textContent = 'Done!';

        showApplyResults(data);
    } catch (err) {
        applyBar.style.width = '100%';
        applyBar.style.background = 'var(--accent-red)';
        applyText.textContent = `Error: ${err.message}`;
    }
});

function showApplyResults(data) {
    const card = document.getElementById('resultsCard');
    const stats = document.getElementById('resultStats');
    const details = document.getElementById('resultDetails');

    stats.innerHTML = `
        <div class="score-card">
            <div class="score-label">Accepted</div>
            <div class="score-value high">${data.approved_count || 0}</div>
        </div>
        <div class="score-card">
            <div class="score-label">Skipped</div>
            <div class="score-value medium">${data.rejected_count || 0}</div>
        </div>
        <div class="score-card">
            <div class="score-label">Pictures Updated</div>
            <div class="score-value high">${data.images_replaced || 0}</div>
        </div>
        <div class="score-card">
            <div class="score-label">Text Updated</div>
            <div class="score-value high">${data.text_replaced || 0}</div>
        </div>
    `;

    details.textContent = data.summary || 'Changes applied successfully';
    card.classList.remove('hidden');

    // Wire up download buttons
    const downloadPdfBtn = document.getElementById('downloadPdf');
    const downloadReportBtn = document.getElementById('downloadReport');

    if (data.output_pdf) {
        downloadPdfBtn.onclick = () => {
            window.open(`${API_BASE}/api/download/pdf`, '_blank');
        };
        downloadPdfBtn.disabled = false;
    }

    if (data.report) {
        downloadReportBtn.onclick = () => {
            const blob = new Blob([JSON.stringify(data.report, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'docsync_report.json';
            a.click();
            URL.revokeObjectURL(url);
        };
        downloadReportBtn.disabled = false;
    }
}

// ─── Multi-Image Compare ─────────────────────────────
let compareFiles = [];

(function setupCompareMultiUpload() {
    const zone = document.getElementById('dropCompareMulti');
    const input = document.getElementById('compareImages');
    const fileList = document.getElementById('compareFileList');

    if (!zone || !input) return;

    zone.addEventListener('click', (e) => {
        if (e.target.classList.contains('file-remove')) return;
        input.click();
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        addCompareImages(e.dataTransfer.files);
    });

    input.addEventListener('change', () => {
        addCompareImages(input.files);
        input.value = '';
    });

    function addCompareImages(files) {
        for (const file of files) {
            if (file.type.startsWith('image/')) {
                compareFiles.push(file);
            }
        }
        renderCompareFileList();
    }

    function renderCompareFileList() {
        const btn = document.getElementById('compareBtn');

        if (compareFiles.length === 0) {
            fileList.innerHTML = '';
            zone.classList.remove('has-file');
            zone.querySelector('.upload-label').textContent = 'Drop Images Here';
            zone.querySelector('.upload-hint').textContent = 'Upload 2 or more images – Click or drag & drop';
            btn.disabled = true;
            return;
        }

        zone.classList.add('has-file');
        const pairs = (compareFiles.length * (compareFiles.length - 1)) / 2;
        zone.querySelector('.upload-label').textContent =
            `${compareFiles.length} image${compareFiles.length > 1 ? 's' : ''} selected`;
        zone.querySelector('.upload-hint').textContent =
            compareFiles.length >= 2 ? `${pairs} pair${pairs > 1 ? 's' : ''} will be compared` : 'Need at least 2 images';
        btn.disabled = compareFiles.length < 2;

        fileList.innerHTML = compareFiles.map((file, idx) => `
            <div class="file-list-item">
                <span class="file-name">${file.name}</span>
                <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
                <button class="file-remove" data-idx="${idx}" title="Remove">✕</button>
            </div>
        `).join('');

        fileList.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                compareFiles.splice(parseInt(btn.dataset.idx), 1);
                renderCompareFileList();
            });
        });
    }
})();

document.getElementById('compareBtn').addEventListener('click', async () => {
    const btn = document.getElementById('compareBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Comparing...';

    const formData = new FormData();
    for (const file of compareFiles) {
        formData.append('images', file);
    }

    try {
        const response = await fetch(`${API_BASE}/api/compare`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        showBatchCompareResults(data);
    } catch (error) {
        document.getElementById('compareSummary').innerHTML =
            `<div class="empty-state">Error: ${error.message}</div>`;
        document.getElementById('compareResults').classList.remove('hidden');
    }

    btn.innerHTML = '<span class="btn-icon">🔍</span> Compare All Pairs';
    btn.disabled = false;
});

function showBatchCompareResults(data) {
    const summary = document.getElementById('compareSummary');
    const pairs = document.getElementById('comparePairs');
    const comparisons = data.comparisons || [];

    const matchCount = comparisons.filter(c => c.scores?.is_match).length;

    summary.innerHTML = `
        <div class="stat-pill">🖼️ Images: <span class="pill-value">${data.total_images}</span></div>
        <div class="stat-pill">🔗 Pairs: <span class="pill-value">${data.total_comparisons}</span></div>
        <div class="stat-pill">✅ Matches: <span class="pill-value">${matchCount}</span></div>
    `;

    const metrics = ['ssim', 'histogram', 'edge', 'template', 'ocr', 'combined'];

    pairs.innerHTML = comparisons.map(c => {
        const s = c.scores || {};
        const isMatch = s.is_match;
        const scoreCards = metrics.map(m => {
            const val = s[m] || 0;
            const cls = val >= 0.7 ? 'high' : val >= 0.5 ? 'medium' : 'low';
            return `
                <div class="pair-score">
                    <div class="ps-label">${m}</div>
                    <div class="ps-value ${cls}">${(val * 100).toFixed(0)}%</div>
                </div>
            `;
        }).join('');

        return `
            <div class="pair-card ${isMatch ? 'match' : 'no-match'}">
                <div class="pair-names">
                    <div class="pair-label">${c.image_a} ⟷ ${c.image_b}</div>
                </div>
                <div class="pair-scores">${scoreCards}</div>
                <span class="pair-match-badge ${isMatch ? 'yes' : 'no'}">
                    ${isMatch ? '✅ Match' : '❌ No Match'}
                </span>
            </div>
        `;
    }).join('');

    document.getElementById('compareResults').classList.remove('hidden');
}

// ─── History ─────────────────────────────────────────
async function loadHistory() {
    const list = document.getElementById('historyList');

    try {
        const response = await fetch(`${API_BASE}/api/history`);
        if (!response.ok) throw new Error('API not available');

        const data = await response.json();
        const versions = data.versions || [];

        if (versions.length === 0) {
            list.innerHTML = '<div class="empty-state">No version history yet</div>';
            return;
        }

        list.innerHTML = versions.reverse().map(v => {
            const res = v.result || {};
            return `
                <div class="history-item">
                    <div class="history-version">v${v.version_id}</div>
                    <div class="history-info">
                        <div class="history-time">${v.timestamp}</div>
                        <div class="history-detail">
                            Images: ${res.images_replaced || 0} |
                            Text: ${res.text_replaced || 0} |
                            Confidence: ${((res.confidence || 0) * 100).toFixed(0)}%
                        </div>
                    </div>
                    <div class="history-actions">
                        <button class="btn-secondary btn-sm" onclick="rollbackVersion(${v.version_id})">
                            ↩ Rollback
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('totalProcessed').textContent = versions.length;
        const totalImg = versions.reduce((s, v) => s + (v.result?.images_replaced || 0), 0);
        const totalTxt = versions.reduce((s, v) => s + (v.result?.text_replaced || 0), 0);
        document.getElementById('totalImages').textContent = totalImg;
        document.getElementById('totalText').textContent = totalTxt;

    } catch (error) {
        list.innerHTML = `<div class="empty-state">Could not load history: ${error.message}</div>`;
    }
}

async function rollbackVersion(versionId) {
    if (!confirm(`Rollback to version ${versionId}?`)) return;

    try {
        const response = await fetch(`${API_BASE}/api/rollback/${versionId}`, {
            method: 'POST',
        });

        if (response.ok) {
            alert('Rollback successful!');
            loadHistory();
        } else {
            alert('Rollback failed');
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

document.getElementById('refreshHistory').addEventListener('click', loadHistory);

// ─── Plugins ─────────────────────────────────────────
async function loadPlugins() {
    const grid = document.getElementById('pluginGrid');

    try {
        const response = await fetch(`${API_BASE}/api/plugins`);
        if (!response.ok) throw new Error('API not available');

        const data = await response.json();
        const plugins = data.plugins || [];

        document.getElementById('totalPlugins').textContent = plugins.length;

        if (plugins.length === 0) {
            grid.innerHTML = '<div class="empty-state">No plugins registered</div>';
            return;
        }

        grid.innerHTML = plugins.map(p => {
            const status = p.health?.status || 'unknown';
            return `
                <div class="plugin-card">
                    <div class="plugin-header">
                        <span class="plugin-name">${p.name}</span>
                        <span class="plugin-version">v${p.version}</span>
                    </div>
                    <div class="plugin-desc">${p.description}</div>
                    <div class="plugin-status ${status}">
                        ${status === 'ok' ? '● Active' : '○ Unavailable'}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        grid.innerHTML = `<div class="empty-state">Could not load plugins: ${error.message}</div>`;
    }
}

// ─── Settings Sliders ────────────────────────────────
const sliders = [
    { id: 'settingSsim', display: 'valSsim', divisor: 100 },
    { id: 'settingHist', display: 'valHist', divisor: 100 },
    { id: 'settingEdge', display: 'valEdge', divisor: 100 },
    { id: 'settingTemplate', display: 'valTemplate', divisor: 100 },
    { id: 'settingSimilarity', display: 'valSimilarity', divisor: 100 },
    { id: 'settingAutoApprove', display: 'valAutoApprove', divisor: 100 },
];

sliders.forEach(s => {
    const slider = document.getElementById(s.id);
    const display = document.getElementById(s.display);
    if (slider && display) {
        slider.addEventListener('input', () => {
            display.textContent = (slider.value / s.divisor).toFixed(2);
        });
    }
});

document.getElementById('saveSettings').addEventListener('click', () => {
    alert('Settings saved locally. Connect to API to persist.');
});

// ─── Health Check ────────────────────────────────────
async function checkApiHealth() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    try {
        const response = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
        if (response.ok) {
            const data = await response.json();
            statusDot.classList.add('connected');
            statusDot.classList.remove('error');
            statusText.textContent = 'API Connected';

            document.getElementById('healthApi').textContent = '✅';

            const plugins = data.plugins || [];
            const llm = plugins.find(p => p.name === 'ai_llm');
            document.getElementById('healthLlm').textContent =
                llm && llm.health?.status === 'ok' ? '✅' : '❌';

            document.getElementById('healthOcr').textContent = '✅';
            document.getElementById('healthPdf').textContent = '✅';

            // Gemini status
            try {
                const gRes = await authFetch(`${API_BASE}/api/settings/gemini`);
                if (gRes.ok) {
                    const g = await gRes.json();
                    document.getElementById('healthGemini').textContent =
                        g.gemini_active ? '✅' : (g.has_key ? '⚠️' : '🔑');
                    document.getElementById('geminiStatus').textContent =
                        g.gemini_active ? 'Gemini AI is active and ready'
                            : g.has_key ? 'Key saved but Gemini could not connect'
                                : 'No API key set — enter your key below';
                }
            } catch { }
        } else {
            throw new Error('Not OK');
        }
    } catch {
        statusDot.classList.remove('connected');
        statusDot.classList.add('error');
        statusText.textContent = 'API Offline';

        document.getElementById('healthApi').textContent = '❌';
        document.getElementById('healthOcr').textContent = '—';
        document.getElementById('healthPdf').textContent = '—';
        document.getElementById('healthLlm').textContent = '—';
        document.getElementById('healthGemini').textContent = '—';
    }
}

// ─── Initialize ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    checkApiHealth();
    setInterval(checkApiHealth, 30000);

    // Gemini API key save
    document.getElementById('saveGeminiKey').addEventListener('click', async () => {
        const key = document.getElementById('geminiKeyInput').value.trim();
        const statusEl = document.getElementById('geminiStatus');
        if (!key) { statusEl.textContent = 'Please enter a key'; return; }
        statusEl.textContent = 'Saving...';
        try {
            const res = await authFetch(`${API_BASE}/api/settings/gemini`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: key }),
            });
            const data = await res.json();
            if (data.gemini_available) {
                statusEl.textContent = '✅ Key saved — Gemini AI is now active!';
                statusEl.style.color = '#22c55e';
                document.getElementById('healthGemini').textContent = '✅';
                document.getElementById('geminiKeyInput').value = '';
            } else {
                statusEl.textContent = '⚠️ Key saved but Gemini could not connect — check your key';
                statusEl.style.color = '#f59e0b';
            }
        } catch (e) {
            statusEl.textContent = '❌ Error saving key';
            statusEl.style.color = '#ef4444';
        }
    });

    // Check if we have an existing session
    if (authToken) {
        try {
            const res = await authFetch(`${API_BASE}/api/auth/me`);
            if (res.ok) {
                const data = await res.json();
                updateUserUI(data.user);
                hideLogin();
                loadHistory();
                loadPlugins();
                if (data.user.role === 'admin') loadUsers();
                return;
            }
        } catch { }
        // Token invalid, clear it
        sessionStorage.removeItem('docsync_token');
        authToken = null;
    }

    // No valid session — show login
    showLogin();
});

// ─── Plugin Management ────────────────────────────────
async function loadPlugins() {
    try {
        const res = await authFetch(`${API_BASE}/api/plugins`);
        const data = await res.json();
        const grid = document.getElementById('pluginGrid');
        const plugins = data.plugins || [];

        if (plugins.length === 0) {
            grid.innerHTML = '<div class="empty-state">🔌 No plugins discovered</div>';
            return;
        }

        const isAdmin = currentUser && currentUser.role === 'admin';

        grid.innerHTML = plugins.map(p => `
            <div class="plugin-card ${p.enabled ? '' : 'disabled'}">
                <div class="plugin-card-header">
                    <div class="plugin-card-info">
                        <h3>${p.name}</h3>
                        <div class="plugin-version">v${p.version}</div>
                    </div>
                    ${isAdmin ? `
                    <label class="toggle-switch">
                        <input type="checkbox" ${p.enabled ? 'checked' : ''}
                               onchange="togglePlugin('${p.name}')">
                        <span class="toggle-slider"></span>
                    </label>` : `
                    <span class="role-badge ${p.enabled ? 'editor' : 'viewer'}">
                        ${p.enabled ? 'ON' : 'OFF'}
                    </span>`}
                </div>
                <div class="plugin-card-desc">${p.description}</div>
            </div>
        `).join('');
    } catch {
        document.getElementById('pluginGrid').innerHTML =
            '<div class="empty-state">⚠️ Failed to load plugins</div>';
    }
}

async function togglePlugin(name) {
    try {
        await authFetch(`${API_BASE}/api/plugins/${name}/toggle`, { method: 'POST' });
        loadPlugins();
    } catch (err) {
        alert('Failed to toggle plugin: ' + err.message);
    }
}

document.getElementById('refreshPlugins')?.addEventListener('click', loadPlugins);

// ─── User Management (Admin) ─────────────────────────
async function loadUsers() {
    try {
        const res = await authFetch(`${API_BASE}/api/auth/users`);
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById('userList');

        list.innerHTML = (data.users || []).map(u => `
            <div class="user-row">
                <span class="user-name-col">${u.username}</span>
                <span class="role-badge ${u.role}">${u.role}</span>
                <span class="user-status">${u.active ? '🟢 Active' : '🔴 Inactive'}</span>
            </div>
        `).join('');
    } catch { }
}

document.getElementById('addUserBtn')?.addEventListener('click', async () => {
    const username = document.getElementById('newUsername').value.trim();
    const password = document.getElementById('newPassword').value;
    const role = document.getElementById('newRole').value;

    if (!username || !password) return alert('Username and password required');

    try {
        const res = await authFetch(`${API_BASE}/api/auth/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role }),
        });

        if (res.ok) {
            document.getElementById('newUsername').value = '';
            document.getElementById('newPassword').value = '';
            loadUsers();
        } else {
            const err = await res.json();
            alert(err.detail || 'Failed to create user');
        }
    } catch { alert('API error'); }
});
