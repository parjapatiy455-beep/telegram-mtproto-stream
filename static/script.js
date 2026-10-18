// Tab switching
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

// Load channel files
async function loadChannelFiles() {
    const tbody = document.getElementById('files-tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="4" class="text-center">Fetching files from Telegram Storage Channel...</td></tr>';

    try {
        const res = await fetch('/api/admin/files');
        if (res.status === 401) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center"><a href="/login" class="btn btn-primary btn-sm">Login as Admin</a> to view and manage stored files</td></tr>';
            return;
        }

        const data = await res.json();
        channelFiles = data.files || [];
        renderFilesTable(channelFiles);
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center" style="color: #f85149;">Error loading files or bot not connected.</td></tr>';
    }
}

function renderFilesTable(files) {
    const tbody = document.getElementById('files-tbody');
    if (!tbody) return;

    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No files found in storage channel. Upload one above or send to bot!</td></tr>';
        return;
    }

    tbody.innerHTML = files.map(f => `
        <tr>
            <td>
                <div class="file-name-cell">
                    <i class="${f.is_video ? 'fas fa-video' : 'fas fa-file'} file-icon"></i>
                    <span title="${f.name}">${f.name}</span>
                </div>
            </td>
            <td>${f.size_human}</td>
            <td>${f.date || '-'}</td>
            <td>
                <div class="actions-cell">
                    <a href="${f.watch_url}" target="_blank" class="btn btn-primary btn-sm" title="Watch Online">
                        <i class="fas fa-play"></i> Watch
                    </a>
                    <button onclick="copyRawText('${f.stream_url}')" class="btn btn-secondary btn-sm" title="Copy Stream URL">
                        <i class="fas fa-link"></i> Stream
                    </button>
                    <button onclick="copyRawText('<iframe src=\\'${f.embed_url}\\' width=\\'100%\\' height=\\'450\\' frameborder=\\'0\\' allowfullscreen></iframe>')" class="btn btn-secondary btn-sm" title="Copy Embed Code">
                        <i class="fas fa-code"></i> Embed
                    </button>
                    <a href="${f.download_url}" class="btn btn-secondary btn-sm" title="Download">
                        <i class="fas fa-download"></i>
                    </a>
                    <button onclick="deleteFile(${f.id})" class="btn btn-danger btn-sm" title="Delete from Storage">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function filterFiles() {
    const query = document.getElementById('file-search')?.value.toLowerCase().trim() || '';
    if (!query) {
        renderFilesTable(channelFiles);
        return;
    }
    const filtered = channelFiles.filter(f => f.name.toLowerCase().includes(query));
    renderFilesTable(filtered);
}

async function deleteFile(msgId) {
    if (!confirm(`Are you sure you want to delete message ID ${msgId} from Telegram storage?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/admin/files/${msgId}`, { method: 'DELETE' });
        if (res.ok) {
            alert('File deleted successfully!');
            loadChannelFiles();
        } else {
            const data = await res.json();
            alert('Delete failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Error deleting file: ' + e);
    }
}

// Settings management
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
    msgBox.innerText = 'Saving and reconnecting to MTProto...';

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
            msgBox.innerText = '✅ Settings saved! ' + (data.message || '');
            checkStatus();
            loadChannelFiles();
        } else {
            msgBox.className = 'alert-box error';
            msgBox.innerText = '❌ Failed: ' + (data.detail || 'Error saving settings');
        }
    } catch (err) {
        msgBox.className = 'alert-box error';
        msgBox.innerText = '❌ Network error saving settings.';
    }
}

async function handleReconnect() {
    const msgBox = document.getElementById('settings-msg');
    if (msgBox) {
        msgBox.style.display = 'block';
        msgBox.className = 'alert-box';
        msgBox.innerText = 'Testing connection...';
    }

    try {
        const res = await fetch('/api/admin/reconnect', { method: 'POST' });
        const data = await res.json();
        if (msgBox) {
            msgBox.className = data.success ? 'alert-box success' : 'alert-box error';
            msgBox.innerText = (data.success ? '✅ ' : '❌ ') + data.message;
        }
        checkStatus();
    } catch (err) {
        if (msgBox) {
            msgBox.className = 'alert-box error';
            msgBox.innerText = '❌ Error testing connection.';
        }
    }
}

// Stats loader
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
                botStatus.innerText = data.telegram_connected ? 'Connected ✅' : 'Disconnected ⚠️';
                botStatus.style.color = data.telegram_connected ? '#3fb950' : '#f85149';
            }
            if (botUser) botUser.innerText = data.bot_username ? '@' + data.bot_username : 'None';
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
            text.innerText = data.bot_username ? `@${data.bot_username} (Online)` : 'MTProto Connected';
        } else {
            badge.classList.add('offline');
            text.innerText = 'Telegram Offline';
        }
    } catch (e) {}
}

async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.reload();
}

// Uploader
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
    uploadStatusText.innerText = 'Uploading to server and forwarding to Telegram...';

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
                uploadStatusText.innerText = 'Saving to Telegram Storage Channel via MTProto...';
            }
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const res = JSON.parse(xhr.responseText);
            progressBar.style.width = '100%';
            uploadPercent.innerText = '100%';
            uploadStatusText.innerText = 'Upload Completed!';

            document.getElementById('watch-url').value = res.watch_url;
            document.getElementById('watch-btn').href = res.watch_url;
            document.getElementById('stream-url').value = res.stream_url;
            document.getElementById('download-url').value = res.download_url;
            document.getElementById('embed-code').value = `<iframe src="${res.embed_url}" width="100%" height="450" frameborder="0" allowfullscreen></iframe>`;

            resultBox.style.display = 'block';
            loadChannelFiles();
        } else {
            let errorMsg = 'Upload failed.';
            try {
                const err = JSON.parse(xhr.responseText);
                errorMsg = err.detail || errorMsg;
            } catch (e) {}
            uploadStatusText.innerText = 'Error: ' + errorMsg;
            uploadStatusText.style.color = '#f85149';
        }
    };

    xhr.onerror = () => {
        uploadStatusText.innerText = 'Network error during upload.';
        uploadStatusText.style.color = '#f85149';
    };

    xhr.send(formData);
}

function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    copyRawText(input.value);
}

function copyRawText(text) {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
}

function openQuickStream() {
    const msgId = document.getElementById('quick-msg-id').value.trim();
    if (!msgId) {
        alert('Please enter a valid Telegram Message ID');
        return;
    }
    window.open(`/watch/${msgId}`, '_blank');
}
