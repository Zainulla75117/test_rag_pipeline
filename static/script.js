document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    
    const queryInput = document.getElementById('query-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');

    // --- Upload Logic ---
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFiles(e.target.files);
        }
        fileInput.value = ''; // Reset
    });

    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    async function handleFiles(files) {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const statusEl = createStatusElement(file.name);
            uploadStatus.appendChild(statusEl);

            const formData = new FormData();
            formData.append('file', file);

            uploadFileWithProgress(file, formData, statusEl);
        }
    }

    function uploadFileWithProgress(file, formData, statusEl) {
        const xhr = new XMLHttpRequest();
        let startTime = Date.now();
        let lastLoaded = 0;
        let lastTime = startTime;

        const cancelBtn = statusEl.querySelector('.cancel-btn');
        const stateEl = statusEl.querySelector('.state');
        const progressTextEl = statusEl.querySelector('.progress-text');
        const speedTextEl = statusEl.querySelector('.speed-text');
        const progressBar = statusEl.querySelector('.progress-bar');

        cancelBtn.addEventListener('click', () => {
            xhr.abort();
            updateStatus(statusEl, 'error', 'Cancelled');
            cancelBtn.style.display = 'none';
        });

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                
                progressBar.style.width = `${percentComplete}%`;
                
                if (percentComplete < 100) {
                    stateEl.innerText = `Uploading (${percentComplete}%)`;
                    
                    const currentTime = Date.now();
                    const timeDiff = (currentTime - lastTime) / 1000;
                    
                    if (timeDiff > 0.5) {
                        const bytesDiff = e.loaded - lastLoaded;
                        const speed = bytesDiff / timeDiff;
                        
                        progressTextEl.innerText = `${formatBytes(e.loaded)} / ${formatBytes(e.total)}`;
                        speedTextEl.innerText = `${formatBytes(speed)}/s`;
                        
                        lastLoaded = e.loaded;
                        lastTime = currentTime;
                    }
                }
            }
        });

        xhr.upload.addEventListener('load', () => {
            stateEl.innerText = 'Upload complete, waiting for processing...';
            progressTextEl.innerText = '';
            speedTextEl.innerText = '';
            progressBar.style.width = '100%';
        });

        xhr.addEventListener('load', () => {
            cancelBtn.style.display = 'none';
            if (xhr.status >= 200 && xhr.status < 300) {
                // Upload finished, start polling processing status
                updateStatus(statusEl, 'processing', 'Queued for processing...');
                progressBar.style.width = '0%';
                pollProcessingStatus(file.name, statusEl);
            } else {
                try {
                    const result = JSON.parse(xhr.responseText);
                    updateStatus(statusEl, 'error', result.detail || 'Upload failed');
                } catch (e) {
                    updateStatus(statusEl, 'error', 'Upload failed');
                }
            }
        });

        xhr.addEventListener('error', () => {
            cancelBtn.style.display = 'none';
            updateStatus(statusEl, 'error', 'Network error');
        });

        xhr.open('POST', '/upload', true);
        xhr.send(formData);
    }
    
    async function pollProcessingStatus(filename, statusEl) {
        const stateEl = statusEl.querySelector('.state');
        const progressBar = statusEl.querySelector('.progress-bar');
        const progressTextEl = statusEl.querySelector('.progress-text');
        
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/status/${encodeURIComponent(filename)}`);
                if (res.ok) {
                    const data = await res.json();
                    
                    if (data.status === 'processing' || data.status === 'queued') {
                        progressBar.style.width = `${data.progress || 0}%`;
                        stateEl.innerText = `Processing: ${data.progress || 0}%`;
                        progressTextEl.innerText = data.message || 'Processing...';
                    } else if (data.status === 'completed') {
                        clearInterval(pollInterval);
                        progressBar.style.width = '100%';
                        updateStatus(statusEl, 'success', `Ingested (${data.chunks} chunks)`);
                        progressTextEl.innerText = 'Ready';
                    } else if (data.status === 'error') {
                        clearInterval(pollInterval);
                        updateStatus(statusEl, 'error', data.message || 'Processing failed');
                    }
                } else {
                    if (res.status === 404) {
                        clearInterval(pollInterval);
                        updateStatus(statusEl, 'error', 'Task not found');
                    }
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 1000);
    }

    function createStatusElement(filename) {
        const el = document.createElement('div');
        el.className = 'status-item uploading';
        el.innerHTML = `
            <div class="status-content">
                <div class="status-header">
                    <span class="filename">${filename}</span>
                    <span class="state">Uploading...</span>
                </div>
                <div class="status-details">
                    <span class="progress-text">Waiting...</span>
                    <span class="speed-text"></span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar"></div>
                </div>
            </div>
            <button class="cancel-btn" title="Cancel upload">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        `;
        return el;
    }

    function updateStatus(el, state, message) {
        el.className = `status-item ${state}`;
        el.querySelector('.state').innerText = message;
        
        const cancelBtn = el.querySelector('.cancel-btn');
        if (cancelBtn) cancelBtn.style.display = 'none';
        
        // Remove after 5 seconds if success
        if (state === 'success') {
            setTimeout(() => {
                el.style.opacity = '0';
                setTimeout(() => el.remove(), 300);
            }, 5000);
        }
    }

    // --- Chat Logic ---
    sendBtn.addEventListener('click', sendQuery);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendQuery();
    });

    async function sendQuery() {
        const query = queryInput.value.trim();
        if (!query) return;

        // Add user message
        addMessage(query, 'user-msg');
        queryInput.value = '';

        // Add typing indicator
        const typingId = 'typing-' + Date.now();
        const typingEl = document.createElement('div');
        typingEl.id = typingId;
        typingEl.className = 'typing-indicator';
        typingEl.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        chatBox.appendChild(typingEl);
        scrollToBottom();

        try {
            const response = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            const result = await response.json();
            
            // Remove typing indicator
            document.getElementById(typingId).remove();

            if (response.ok) {
                addBotMessage(result.answer, result.sources);
            } else {
                addMessage('Error: ' + (result.detail || 'Failed to fetch answer'), 'bot-msg');
            }
        } catch (error) {
            document.getElementById(typingId).remove();
            addMessage('Error connecting to server.', 'bot-msg');
        }
    }

    function addMessage(text, className) {
        const el = document.createElement('div');
        el.className = `message ${className}`;
        
        // Simple markdown parsing for the bot's response (bold and newlines)
        let formattedText = text.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
        formattedText = formattedText.replace(/\\n/g, '<br>');
        
        el.innerHTML = formattedText;
        chatBox.appendChild(el);
        scrollToBottom();
    }

    function addBotMessage(text, sources) {
        const el = document.createElement('div');
        el.className = 'message bot-msg';
        
        let formattedText = text.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
        formattedText = formattedText.replace(/\\n/g, '<br>');
        
        let html = `<div>${formattedText}</div>`;
        
        if (sources && sources.length > 0) {
            const uniqueSources = [...new Set(sources.map(s => s.source))];
            
            html += `
                <div class="sources-container">
                    <div class="source-toggle">View Sources (${uniqueSources.length})</div>
                    <div class="sources-list">
                        <ul>
                            ${uniqueSources.map(s => `<li>${s.split(/[\\\\/]/).pop()}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
        }
        
        el.innerHTML = html;
        chatBox.appendChild(el);
        
        // Attach source toggle logic
        const toggle = el.querySelector('.source-toggle');
        const list = el.querySelector('.sources-list');
        if (toggle && list) {
            toggle.addEventListener('click', () => {
                list.classList.toggle('active');
            });
        }
        
        scrollToBottom();
    }

    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
