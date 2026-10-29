// ============================================================
// TOAST NOTIFICATION ENGINE (Replaces ugly browser alerts)
// ============================================================
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconClass = 'fa-check-circle';
    if (type === 'error') iconClass = 'fa-exclamation-circle';
    if (type === 'info') iconClass = 'fa-info-circle';

    toast.innerHTML = `<i class="fas ${iconClass}"></i><span>${message}</span>`;
    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 260);
    }, 3000);
}

// Copy helper with toast
function copyRawText(text) {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard!', 'success');
        }).catch(() => {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        showToast('Copied to clipboard!', 'success');
    } catch (err) {
        showToast('Failed to copy', 'error');
    }
    document.body.removeChild(textArea);
}

function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    if (input) {
        copyRawText(input.value);
    }
}

// ============================================================
// TABS SWITCHER
// ============================================================
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick')?.includes(tabId));
    if (activeBtn) activeBtn.classList.add('active');

    const targetContent = document.getElementById(tabId);
    if (targetContent) targetContent.classList.add('active');

    if (tabId === 'tab-files') {
        loadChannelFiles();
    } else if (tabId === 'tab-stats') {
        loadStats();
    }
}

// Global files cache for search filtering
let channelFiles = [];

// ============================================================
// FILE EXPLORER: DESKTOP TABLE & MOBILE CARDS
// ============================================================
async function loadChannelFiles() {
    const desktopTbody = document.getElementById('files-tbody');
    const mobileContainer = document.getElementById('mobile-files-grid');
    
    if (desktopTbody) {
        desktopTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="padding: 2rem;"><i class="fas fa-spinner fa-spin"></i> Fetching files from Telegram Cloud...</td></tr>';
    }
    if (mobileContainer) {
        mobileContainer.innerHTML = '<div class="text-center" style="padding: 2rem; color: var(--text-muted);"><i class="fas fa-spinner fa-spin"></i> Loading files...</div>';
    }

    try {
        const res = await fetch('/api/admin/files');
        if (res.status === 401) {
            const loginPrompt = `
                <div class="text-center" style="padding: 2rem;">
                    <p style="margin-bottom: 1rem; color: var(--text-muted);">Please log in to manage your Telegram Storage files.</p>
                    <a href="/login" class="btn btn-primary btn-sm"><i class="fas fa-lock"></i> Login as Admin</a>
                </div>
            `;
            if (desktopTbody) desktopTbody.innerHTML = `<tr><td colspan="4">${loginPrompt}</td></tr>`;
            if (mobileContainer) mobileContainer.innerHTML = loginPrompt;
            return;
        }

        const data = await res.json();
        channelFiles = data.files || [];
        renderFiles(channelFiles);
    } catch (e) {
        const errorMsg = '<div class="text-center" style="color: #f87171; padding: 2rem;"><i class="fas fa-exclamation-triangle"></i> Failed to connect or bot is offline.</div>';
        if (desktopTbody) desktopTbody.innerHTML = `<tr><td colspan="4">${errorMsg}</td></tr>`;
        if (mobileContainer) mobileContainer.innerHTML = errorMsg;
    }
}

function renderFiles(files) {
    const desktopTbody = document.getElementById('files-tbody');
    const mobileContainer = document.getElementById('mobile-files-grid');

    if (files.length === 0) {
        const emptyMsg = `
            <div class="text-center" style="padding: 2.5rem 1rem;">
                <i class="fas fa-cloud-upload-alt" style="font-size: 2.5rem; color: var(--text-dim); margin-bottom: 0.75rem;"></i>
                <h4 style="font-size: 1rem; margin-bottom: 0.25rem;">No files found</h4>
                <p style="font-size: 0.82rem; color: var(--text-muted);">Upload a file or send videos to your Telegram bot!</p>
            </div>
        `;
        if (desktopTbody) desktopTbody.innerHTML = `<tr><td colspan="4">${emptyMsg}</td></tr>`;
        if (mobileContainer) mobileContainer.innerHTML = emptyMsg;
        return;
    }

    // 1. Render Desktop Table
    if (desktopTbody) {
        desktopTbody.innerHTML = files.map(f => `
            <tr>
                <td>
                    <div class="file-name-cell">
                        <div class="file-icon-box ${f.is_video ? '' : 'doc'}">
                            <i class="${f.is_video ? 'fas fa-play' : 'fas fa-file-alt'}"></i>
                        </div>
                        <span class="file-name-text" title="${f.name}">${f.name}</span>
                    </div>
                </td>
                <td><span class="badge-pill">${f.size_human}</span></td>
                <td><span style="color: var(--text-dim); font-size: 0.8rem;">${f.date || '-'}</span></td>
                <td>
                    <div class="actions-cell">
                        <a href="${f.watch_url}" target="_blank" class="btn btn-primary btn-sm" title="Watch Online">
                            <i class="fas fa-play"></i> Watch
                        </a>
                        <button onclick="copyRawText('${f.stream_url}')" class="btn btn-secondary btn-sm" title="Copy Stream Link">
                            <i class="fas fa-link"></i> Stream
                        </button>
                        <button onclick="copyRawText('<iframe src=\\'${f.embed_url}\\' width=\\'100%\\' height=\\'450\\' frameborder=\\'0\\' allowfullscreen></iframe>')" class="btn btn-secondary btn-sm" title="Copy Iframe Code">
                            <i class="fas fa-code"></i> Embed
                        </button>
                        <a href="${f.download_url}" class="btn btn-secondary btn-sm btn-icon-only" title="Download File">
                            <i class="fas fa-download"></i>
                        </a>
                        <button onclick="deleteFile(${f.id})" class="btn btn-danger btn-sm btn-icon-only" title="Delete from Storage">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // 2. Render Mobile Cards (Mobile friendly touch UX)
    if (mobileContainer) {
        mobileContainer.innerHTML = files.map(f => `
            <div class="mobile-file-card">
                <div class="mobile-card-header">
                    <div class="file-icon-box ${f.is_video ? '' : 'doc'}">
                        <i class="${f.is_video ? 'fas fa-play' : 'fas fa-file-alt'}"></i>
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div class="mobile-card-title">${f.name}</div>
                        <div class="mobile-card-meta">
                            <span class="badge-pill">${f.size_human}</span>
                            <span>&bull;</span>
                            <span>${f.date || 'Saved'}</span>
                        </div>
                    </div>
                </div>
                <div class="mobile-card-actions">
                    <a href="${f.watch_url}" target="_blank" class="btn btn-primary btn-sm">
                        <i class="fas fa-play"></i> Watch
                    </a>
                    <button onclick="copyRawText('${f.stream_url}')" class="btn btn-secondary btn-sm">
                        <i class="fas fa-link"></i> Link
                    </button>
                    <button onclick="copyRawText('<iframe src=\\'${f.embed_url}\\' width=\\'100%\\' height=\\'450\\' frameborder=\\'0\\' allowfullscreen></iframe>')" class="btn btn-secondary btn-sm">
                        <i class="fas fa-code"></i> Embed
                    </button>
                    <a href="${f.download_url}" class="btn btn-secondary btn-sm" title="Download">
                        <i class="fas fa-download"></i>
                    </a>
                    <button onclick="deleteFile(${f.id})" class="btn btn-danger btn-sm" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }
}

function filterFiles() {
    const query = document.getElementById('file-search')?.value.toLowerCase().trim() || '';
    if (!query) {
        renderFiles(channelFiles);
        return;
    }
    const filtered = channelFiles.filter(f => f.name.toLowerCase().includes(query));
    renderFiles(filtered);
}

async function deleteFile(msgId) {
    if (!confirm(`Are you sure you want to delete message ID ${msgId} from Telegram storage?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/admin/files/${msgId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('File deleted successfully!', 'success');
            loadChannelFiles();
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to delete file', 'error');
        }
    } catch (e) {
        showToast('Network error while deleting', 'error');
    }
}

// ============================================================
// SETTINGS MANAGEMENT
// ============================================================
async function loadSettings() {
    try {
        const res = await fetch('/api/admin/settings');
        if (res.ok) {
            const data = await res.json();
            const apiIdInput = document.getElementById('set-api-id');
            const binChannelInput = document.getElementById('set-bin-channel');
            const baseUrlInput = document.getElementById('set-base-url');
            const apiHashHint = document.getElementById('current-api-hash-hint');
            const botTokenHint = document.getElementById('current-bot-token-hint');

            if (apiIdInput) apiIdInput.value = data.api_id || '';
            if (binChannelInput) binChannelInput.value = data.bin_channel || '';
            if (baseUrlInput) baseUrlInput.value = data.base_url || window.location.origin;

            if (apiHashHint && data.api_hash_masked) {
                apiHashHint.innerText = 'Current: ' + data.api_hash_masked;
            }
            if (botTokenHint && data.bot_token_masked) {
                botTokenHint.innerText = 'Current: ' + data.bot_token_masked;
            }
        }
    } catch (e) {}
}

async function handleSaveSettings(e) {
    e.preventDefault();
    const msgBox = document.getElementById('settings-msg');
    msgBox.style.display = 'block';
    msgBox.className = 'alert-box';
    msgBox.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving & connecting to MTProto...';

    const payload = {
        api_id: document.getElementById('set-api-id')?.value.trim() || null,
        api_hash: document.getElementById('set-api-hash')?.value.trim() || null,
        bot_token: document.getElementById('set-bot-token')?.value.trim() || null,
        bin_channel: document.getElementById('set-bin-channel')?.value.trim() || null,
        base_url: document.getElementById('set-base-url')?.value.trim() || null,
        admin_password: document.getElementById('set-admin-password')?.value.trim() || null
    };

    try {
        const res = await fetch('/api/admin/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
            msgBox.className = 'alert-box success';
            msgBox.innerHTML = `<strong><i class="fas fa-check-circle"></i> Saved!</strong> ${data.message || ''}`;
            showToast('Settings saved successfully!', 'success');
            checkStatus();
            loadChannelFiles();
        } else {
            msgBox.className = 'alert-box error';
            msgBox.innerHTML = `<strong><i class="fas fa-exclamation-circle"></i> Error:</strong> ${data.detail || 'Could not save'}`;
            showToast(data.detail || 'Error saving settings', 'error');
        }
    } catch (err) {
        msgBox.className = 'alert-box error';
        msgBox.innerHTML = '<strong><i class="fas fa-times-circle"></i> Network error</strong> saving settings.';
        showToast('Network error', 'error');
    }
}

async function handleReconnect() {
    const msgBox = document.getElementById('settings-msg');
    if (msgBox) {
        msgBox.style.display = 'block';
        msgBox.className = 'alert-box';
        msgBox.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing MTProto connection...';
    }

    try {
        const res = await fetch('/api/admin/reconnect', { method: 'POST' });
        const data = await res.json();
        if (msgBox) {
            msgBox.className = data.success ? 'alert-box success' : 'alert-box error';
            msgBox.innerHTML = (data.success ? '<i class="fas fa-check-circle"></i> ' : '<i class="fas fa-times-circle"></i> ') + data.message;
        }
        showToast(data.message, data.success ? 'success' : 'error');
        checkStatus();
    } catch (err) {
        if (msgBox) {
            msgBox.className = 'alert-box error';
            msgBox.innerHTML = '<i class="fas fa-times-circle"></i> Error testing connection.';
        }
        showToast('Connection test failed', 'error');
    }
}

// ============================================================
// STATS LOADER
// ============================================================
async function loadStats() {
    try {
        const res = await fetch('/api/admin/stats');
        if (res.ok) {
            const data = await res.json();
            const botStatus = document.getElementById('stat-bot-status');
            const botUser = document.getElementById('stat-bot-username');
            const uptime = document.getElementById('stat-uptime');
            const python = document.getElementById('stat-python');
            const os = document.getElementById('stat-os');
            const channel = document.getElementById('stat-channel');

            if (botStatus) {
                botStatus.innerHTML = data.telegram_connected 
                    ? '<span style="color: #34d399;"><i class="fas fa-check-circle"></i> Online</span>' 
                    : '<span style="color: #f87171;"><i class="fas fa-times-circle"></i> Offline</span>';
            }
            if (botUser) botUser.innerText = data.bot_username ? '@' + data.bot_username : '-';
            if (uptime) uptime.innerText = data.uptime || '-';
            if (python) python.innerText = data.python_version || '-';
            if (os) os.innerText = data.platform || '-';
            if (channel) channel.innerText = data.bin_channel || '-';
        }
    } catch (e) {}
}

async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const badge = document.getElementById('server-status');
        const text = document.getElementById('status-text');

        if (data.telegram_connected) {
            badge.classList.remove('offline');
            text.innerText = data.bot_username ? `@${data.bot_username}` : 'Online';
        } else {
            badge.classList.add('offline');
            text.innerText = 'Offline';
        }
    } catch (e) {}
}

async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' });
    showToast('Logged out successfully', 'info');
    setTimeout(() => window.location.reload(), 300);
}

// ============================================================
// UPLOADER
// ============================================================
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const progressContainer = document.getElementById('progress-container');
const progressBar = document.getElementById('progress-bar');
const uploadPercent = document.getElementById('upload-percent');
const uploadFilename = document.getElementById('upload-filename');
const uploadStatusText = document.getElementById('upload-status-text');
const resultBox = document.getElementById('result-box');

if (dropzone) {
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleUpload(fileInput.files[0]);
        }
    });
}

function handleUpload(file) {
    if (!file) return;

    progressContainer.style.display = 'block';
    resultBox.style.display = 'none';
    uploadFilename.innerText = file.name;
    uploadPercent.innerText = '0%';
    progressBar.style.width = '0%';
    uploadStatusText.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading to server...';

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload', true);

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 90);
            progressBar.style.width = percent + '%';
            uploadPercent.innerText = percent + '%';
            if (percent >= 90) {
                uploadStatusText.innerHTML = '<i class="fas fa-cloud-upload-alt fa-fade"></i> Saving to Telegram Cloud Storage...';
            }
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const res = JSON.parse(xhr.responseText);
            progressBar.style.width = '100%';
            uploadPercent.innerText = '100%';
            uploadStatusText.innerHTML = '<i class="fas fa-check-circle" style="color: #34d399;"></i> Upload Complete!';

            document.getElementById('watch-url').value = res.watch_url;
            document.getElementById('watch-btn').href = res.watch_url;
            document.getElementById('stream-url').value = res.stream_url;
            document.getElementById('download-url').value = res.download_url;
            document.getElementById('embed-code').value = `<iframe src="${res.embed_url}" width="100%" height="450" frameborder="0" allowfullscreen></iframe>`;

            resultBox.style.display = 'block';
            showToast('File uploaded to Telegram Cloud! 🎉', 'success');
            loadChannelFiles();
        } else {
            let errorMsg = 'Upload failed.';
            try {
                const err = JSON.parse(xhr.responseText);
                errorMsg = err.detail || errorMsg;
            } catch (e) {}
            uploadStatusText.innerHTML = `<i class="fas fa-exclamation-triangle" style="color: #f87171;"></i> Error: ${errorMsg}`;
            showToast(errorMsg, 'error');
        }
    };

    xhr.onerror = () => {
        uploadStatusText.innerHTML = '<i class="fas fa-times-circle" style="color: #f87171;"></i> Network error during upload.';
        showToast('Network error during upload', 'error');
    };

    xhr.send(formData);
}

function openQuickStream() {
    const msgId = document.getElementById('quick-msg-id')?.value.trim();
    if (!msgId) {
        showToast('Please enter a valid Telegram Message ID', 'error');
        return;
    }
    window.open(`/watch/${msgId}`, '_blank');
}
