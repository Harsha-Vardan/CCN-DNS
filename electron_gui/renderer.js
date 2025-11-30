const API_URL = 'http://127.0.0.1:5000';

function showTab(tabId) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(tabId).classList.add('active');
    
    // Highlight button (simple logic)
    const buttons = document.querySelectorAll('.nav-btn');
    if(tabId === 'lookup') buttons[0].classList.add('active');
    if(tabId === 'path') buttons[1].classList.add('active');
    if(tabId === 'cache') {
        buttons[2].classList.add('active');
        refreshCache();
    }
    if(tabId === 'packet') buttons[3].classList.add('active');
    if(tabId === 'benchmark') buttons[4].classList.add('active');
}

async function resolveDNS() {
    const domain = document.getElementById('domain-input').value;
    const type = document.getElementById('type-input').value;
    const mode = document.getElementById('mode-input').value;
    const resultsArea = document.getElementById('results-area');
    
    resultsArea.innerHTML = '<div class="placeholder-text">Resolving...</div>';
    
    try {
        const response = await fetch(`${API_URL}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain, type, mode })
        });
        
        const result = await response.json();
        
        if (result.error) {
            resultsArea.innerHTML = `<div style="color: var(--error-color)">Error: ${result.error}</div>`;
            return;
        }
        
        // Render Results
        let html = `<h3>Results (${result.duration.toFixed(2)}ms)</h3>`;
        
        if (result.data && result.data.answers) {
            result.data.answers.forEach(answer => {
                let target = answer.name;
                // Handle PTR logic for link
                if (answer.type === 12) { // PTR
                     target = answer.data;
                }
                
                const linkUrl = `http://${target}`;
                
                html += `
                <div class="result-item">
                    <div>
                        <span class="result-name">${answer.name}</span>
                        <span class="result-type">${getTypeName(answer.type)}</span>
                    </div>
                    <div style="flex:1; margin: 0 15px; overflow:hidden; text-overflow:ellipsis;">
                        ${typeof answer.data === 'object' ? JSON.stringify(answer.data) : answer.data}
                    </div>
                    <a href="#" onclick="require('electron').shell.openExternal('${linkUrl}')" class="visit-btn">🌐 Visit Site</a>
                </div>
                `;
            });
        } else {
            html += '<div>No answers found.</div>';
        }
        
        // Raw JSON toggle
        html += `<details style="margin-top:20px"><summary>Raw JSON</summary><pre class="code-block">${JSON.stringify(result, null, 2)}</pre></details>`;
        
        resultsArea.innerHTML = html;
        
    } catch (e) {
        resultsArea.innerHTML = `<div style="color: var(--error-color)">Connection Error: ${e.message}. Is the backend running?</div>`;
    }
}

function getTypeName(typeId) {
    const map = { 1: 'A', 28: 'AAAA', 2: 'NS', 5: 'CNAME', 15: 'MX', 16: 'TXT', 12: 'PTR', 6: 'SOA' };
    return map[typeId] || typeId;
}

async function generatePacket() {
    const domain = document.getElementById('packet-domain').value;
    const type = document.getElementById('packet-type').value;
    
    try {
        const response = await fetch(`${API_URL}/packet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain, type })
        });
        const data = await response.json();
        document.getElementById('packet-output').textContent = data.hex_dump || data.error;
    } catch (e) {
        document.getElementById('packet-output').textContent = "Error: " + e.message;
    }
}

async function refreshCache() {
    const cacheBody = document.getElementById('cache-body');
    const statsDiv = document.getElementById('cache-stats');
    
    console.log("Refreshing cache..."); // Debug log
    
    try {
        // Add timestamp to prevent browser caching
        const response = await fetch(`${API_URL}/cache?t=${Date.now()}`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Server Error (${response.status}): ${text}`);
        }
        const data = await response.json();
        
        console.log("Cache data received:", data); // Debug log
        
        // Update Stats
        statsDiv.textContent = `Stats: Hits: ${data.stats.hits} | Misses: ${data.stats.misses} | Size: ${data.stats.size}/${data.stats.capacity}`;
        
        // Update Table
        cacheBody.innerHTML = '';
        if (data.entries.length === 0) {
            cacheBody.innerHTML = '<tr><td colspan="4" style="text-align:center">Cache is empty</td></tr>';
            return;
        }
        
        data.entries.forEach(entry => {
            const row = `
                <tr>
                    <td>${entry.domain}</td>
                    <td>${getTypeName(entry.type)}</td>
                    <td>${entry.ttl}</td>
                    <td><span style="color: ${entry.status === 'Valid' ? 'var(--success-color)' : 'var(--error-color)'}">${entry.status}</span></td>
                </tr>
            `;
            cacheBody.innerHTML += row;
        });
        
    } catch (e) {
        console.error("Cache refresh error:", e);
        cacheBody.innerHTML = `<tr><td colspan="4" style="color: var(--error-color)">Error loading cache: ${e.message}</td></tr>`;
    }
}

async function clearCache() {
    if(!confirm('Are you sure you want to clear the DNS cache?')) return;
    
    try {
        const response = await fetch(`${API_URL}/cache`, {
            method: 'DELETE'
        });
        const data = await response.json();
        alert(data.message);
        refreshCache(); // Refresh UI to show empty table
    } catch (e) {
        console.error("Error clearing cache:", e);
        alert("Failed to clear cache: " + e.message);
    }
}

async function renderPath() {
    const domain = document.getElementById('path-domain').value;
    const container = document.getElementById('path-diagram');
    
    container.innerHTML = '<div class="placeholder-text">Generating visualization...</div>';
    
    // Theoretical Path Visualization using Mermaid
    const graphDefinition = `
    sequenceDiagram
        participant Client
        participant Root as Root (.)
        participant TLD as TLD (.com)
        participant Auth as Auth (${domain})
        
        Client->>Root: Query ${domain}
        Root-->>Client: Refer to TLD
        Client->>TLD: Query ${domain}
        TLD-->>Client: Refer to Auth
        Client->>Auth: Query ${domain}
        Auth-->>Client: Answer IP
    `;
    
    try {
        const { svg } = await mermaid.render('graphDiv', graphDefinition);
        container.innerHTML = svg;
    } catch (e) {
        container.innerHTML = `<div style="color: var(--error-color)">Error rendering graph: ${e.message}</div>`;
    }
}

async function runBenchmark() {
    const tbody = document.getElementById('benchmark-body');
    tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">Running benchmark... (this may take a few seconds)</td></tr>';
    
    try {
        const response = await fetch(`${API_URL}/benchmark`, { method: 'POST' });
        const data = await response.json();
        
        tbody.innerHTML = '';
        
        if (data.message) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: var(--text-secondary)">${data.message}</td></tr>`;
            return;
        }
        
        data.results.forEach(row => {
            // Handle Local result (number or string error)
            let localDisplay = 'Error';
            let localVal = -1;
            
            if (typeof row.local === 'number') {
                if (row.local >= 0) {
                    localDisplay = row.local.toFixed(2);
                    localVal = row.local;
                }
            } else {
                localDisplay = row.local; // It's an error string
            }

            const google = row.google > 0 ? `${row.google.toFixed(2)}` : 'Timeout';
            const cloudflare = row.cloudflare > 0 ? `${row.cloudflare.toFixed(2)}` : 'Timeout';
            
            // Highlight winner
            let times = [];
            if(localVal > 0) times.push({name: 'local', val: localVal});
            if(row.google > 0) times.push({name: 'google', val: row.google});
            if(row.cloudflare > 0) times.push({name: 'cloudflare', val: row.cloudflare});
            
            times.sort((a,b) => a.val - b.val);
            const winner = times.length > 0 ? times[0].name : null;
            
            const tr = `
                <tr>
                    <td><b>${row.domain}</b></td>
                    <td style="color: ${winner === 'local' ? 'var(--success-color)' : 'inherit'}; font-size: 0.9em">${localDisplay}</td>
                    <td style="color: ${winner === 'google' ? 'var(--success-color)' : 'inherit'}">${google}</td>
                    <td style="color: ${winner === 'cloudflare' ? 'var(--success-color)' : 'inherit'}">${cloudflare}</td>
                </tr>
            `;
            tbody.innerHTML += tr;
        });
        
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="color: var(--error-color)">Error: ${e.message}</td></tr>`;
    }
}
