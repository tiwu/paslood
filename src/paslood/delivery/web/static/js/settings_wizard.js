/**
 * Paslood — Settings, PDT OAuth/MCP, Encrypted Vault & Interactive Setup Wizard
 */

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const s = await res.json();

    // PDT Card
    const pdt = s.pdt || {};
    const pill = document.getElementById('pdt-status-pill');
    const tokenDisplay = document.getElementById('pdt-cfg-token');
    const btnDisconnect = document.getElementById('btn-pdt-disconnect');
    const btnConnect = document.getElementById('btn-pdt-connect-oauth');

    if (pdt.connected) {
      pill.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-semibold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      pill.textContent = I18N.t('settings.status_connected', 'Connected (Active)');
      tokenDisplay.textContent = pdt.auth_token || 'Active Session';
      btnDisconnect.classList.remove('hidden');
      btnConnect.textContent = I18N.t('settings.pdt_reauth_btn', '🔗 Re-authenticate (OAuth)');
    } else {
      pill.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-semibold border bg-slate-800 text-slate-400 border-slate-700';
      pill.textContent = I18N.t('settings.status_disconnected', 'Disconnected');
      tokenDisplay.textContent = I18N.t('settings.status_not_connected', 'Not Connected');
      btnDisconnect.classList.add('hidden');
      btnConnect.textContent = I18N.t('settings.pdt_connect_btn', '🔗 Connect with PDT (OAuth PKCE)');
    }

    document.getElementById('pdt-cfg-url').textContent = pdt.mcp_url || 'https://mcp.portfoliodividendtracker.com';
    document.getElementById('pdt-cfg-last-sync').textContent = pdt.last_sync || I18N.t('settings.status_never', 'Never');

    // Custom MCP Servers Table
    const tbody = document.getElementById('mcp-servers-tbody');
    tbody.innerHTML = '';
    currentMcpServers = s.mcp_servers || [];
    currentMcpServers.forEach(srv => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-950/30';
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-medium text-white">${escapeHtml(srv.name)}</td>
        <td class="py-2.5 px-3 font-mono text-slate-300 text-[11px]">${escapeHtml(srv.url)}</td>
        <td class="py-2.5 px-3 uppercase text-[10px] text-slate-400">${escapeHtml(srv.transport || 'HTTP')}</td>
        <td class="py-2.5 px-3" id="ping-${escapeHtml(srv.id)}"><span class="text-slate-500">${escapeHtml(I18N.t('settings.status_ready', 'Ready'))}</span></td>
        <td class="py-2.5 px-3 text-right space-x-1.5">
          <button onclick="testMcpServerById('${escapeHtml(srv.id)}')" class="px-2 py-0.5 rounded border border-slate-700 hover:bg-slate-800 text-slate-300 text-[11px]">${escapeHtml(I18N.t('settings.btn_ping', 'Ping'))}</button>
          <button onclick="deleteMcpServer('${escapeHtml(srv.id)}')" class="px-2 py-0.5 rounded border border-red-500/30 hover:bg-red-500/10 text-red-400 text-[11px]">${escapeHtml(I18N.t('common.delete', 'Delete'))}</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // AI Settings
    const ai = s.ai || {};
    const provSelect = document.getElementById('settings-ai-provider');
    const modelSelect = document.getElementById('settings-ai-model');
    if (provSelect) provSelect.value = ai.provider || 'gemini';
    if (ai.api_key) document.getElementById('settings-ai-key').value = ai.api_key;
    if (modelSelect && ai.model) {
      const found = Array.from(modelSelect.options).some(o => o.value === ai.model);
      if (!found) {
        const opt = document.createElement('option');
        opt.value = ai.model;
        opt.textContent = ai.model;
        modelSelect.appendChild(opt);
      }
      modelSelect.value = ai.model;
    }
    updateAiActiveBadge();
    if (typeof toggleAiKeyVisibility === 'function') toggleAiKeyVisibility();

    // Tax Settings
    const tax = s.tax || {};
    document.getElementById('settings-tax-exemption').value = tax.annual_exemption || 10000;
    document.getElementById('settings-tax-date').value = tax.benchmark_date || '2025-12-31';
    document.getElementById('settings-tax-price').value = tax.benchmark_price || 900;
    document.getElementById('settings-tax-rate').value = tax.tax_rate_pct || 10.0;

    // Cloud Sync / Vault Info
    const cloud = s.cloud_sync || {};
    const cloudDirInput = document.getElementById('vault-cloud-dir');
    if (cloudDirInput && cloud.sync_dir) cloudDirInput.value = cloud.sync_dir;
    const lastBackupEl = document.getElementById('vault-last-backup');
    if (lastBackupEl) lastBackupEl.textContent = cloud.last_backup || 'Never';
    try {
      const infoRes = await fetch('/api/backup/info');
      if (infoRes.ok) {
        const info = await infoRes.json();
        const yamlEl = document.getElementById('vault-path-yaml');
        const dbEl = document.getElementById('vault-path-db');
        if (yamlEl && info.portfolio_yaml) yamlEl.textContent = info.portfolio_yaml;
        if (dbEl && info.sqlite_db) dbEl.textContent = info.sqlite_db;
      }
    } catch (e) {}

    // Language & Localization Settings
    if (s.language && typeof I18N !== 'undefined') {
      const localLang = localStorage.getItem('paslood_language');
      if (!localLang) {
        I18N.setLanguage(s.language, false);
      } else {
        I18N.setLanguage(localLang, false);
      }
    }
    if (typeof I18N !== 'undefined') {
      const localFmt = localStorage.getItem('paslood_regional_format');
      if (localFmt) {
        I18N.setRegionalFormat(localFmt, false);
      } else if (s.regional_format) {
        I18N.setRegionalFormat(s.regional_format, false);
      }
    }

    // Known Accounts
    await loadKnownAccounts();

    return s;
  } catch (err) {
    console.error('Failed to load settings:', err);
    return null;
  }
}

function showSettingsAlert(message, isError = false) {
  const box = document.getElementById('settings-notification');
  const text = document.getElementById('settings-notification-text');
  box.className = `p-4 rounded-xl border text-xs flex items-center justify-between ${
    isError ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
  }`;
  text.textContent = message;
  box.classList.remove('hidden');
  setTimeout(() => box.classList.add('hidden'), 6000);
}

async function connectPdtOAuth() {
  try {
    const res = await fetch('/api/auth/pdt/connect');
    const data = await res.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      showSettingsAlert('Failed to generate OAuth URL', true);
    }
  } catch (err) {
    showSettingsAlert(`OAuth Error: ${err.message}`, true);
  }
}

async function syncPdtHoldings() {
  const btn = document.getElementById('btn-pdt-sync');
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span>⏳ Syncing...</span>';
  btn.disabled = true;

  try {
    const res = await fetch('/api/mcp/pdt/sync', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showSettingsAlert(`✓ Successfully synced ${data.asset_count} assets from PDT! (Total value: € ${data.total_value.toLocaleString('nl-BE', { minimumFractionDigits: 2 })})`);
      await loadSettings();
      await loadOverview();
    } else {
      showSettingsAlert(data.detail || 'Sync failed', true);
    }
  } catch (err) {
    showSettingsAlert(`Sync Error: ${err.message}`, true);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

async function disconnectPdt() {
  const confirmed = await confirmDialog({
    title: 'Disconnect PDT',
    message: 'Are you sure you want to disconnect Portfolio Dividend Tracker?',
    confirmVariant: 'danger',
  });
  if (!confirmed) return;
  try {
    await fetch('/api/auth/pdt/disconnect', { method: 'POST' });
    showSettingsAlert('PDT disconnected.');
    await loadSettings();
    await loadOverview();
  } catch (err) {
    showSettingsAlert(`Disconnect Error: ${err.message}`, true);
  }
}

async function saveManualPdtToken() {
  const token = document.getElementById('pdt-manual-token-input').value.trim();
  const url = document.getElementById('pdt-manual-url-input').value.trim();
  if (!token) {
    showToast('Please enter a PDT Bearer Token', 'warning');
    return;
  }
  try {
    const res = await fetch('/api/auth/pdt/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auth_token: token, mcp_url: url })
    });
    if (res.ok) {
      showSettingsAlert('Manual PDT credentials saved successfully!');
      await loadSettings();
    }
  } catch (err) {
    showSettingsAlert(`Error saving token: ${err.message}`, true);
  }
}

function toggleAddMcpForm() {
  const form = document.getElementById('add-mcp-form');
  form.classList.toggle('hidden');
}

async function submitNewMcpServer() {
  const name = document.getElementById('new-mcp-name').value.trim();
  const url = document.getElementById('new-mcp-url').value.trim();
  const transport = document.getElementById('new-mcp-transport').value;
  const token = document.getElementById('new-mcp-token').value.trim();

  if (!name || !url) {
    showToast('Please provide server name and URL', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/settings/mcp/servers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url, transport, auth_token: token || null })
    });
    if (res.ok) {
      toggleAddMcpForm();
      showSettingsAlert(`MCP Server "${name}" registered successfully.`);
      await loadSettings();
    }
  } catch (err) {
    showSettingsAlert(`Error adding server: ${err.message}`, true);
  }
}

async function deleteMcpServer(id) {
  const confirmed = await confirmDialog({
    title: 'Remove MCP Server',
    message: 'Remove this MCP server?',
    confirmVariant: 'danger',
  });
  if (!confirmed) return;
  try {
    await fetch(`/api/settings/mcp/servers/${id}`, { method: 'DELETE' });
    showSettingsAlert('MCP server removed.');
    await loadSettings();
  } catch (err) {
    showSettingsAlert(`Error deleting server: ${err.message}`, true);
  }
}

async function testMcpServerById(id) {
  const srv = (currentMcpServers || []).find(x => x.id === id);
  if (!srv) return;
  return testMcpServer(id, srv.url);
}

async function testMcpServer(id, url) {
  const cell = document.getElementById(`ping-${id}`);
  if (cell) cell.innerHTML = '<span class="text-amber-400 animate-pulse">Pinging...</span>';

  try {
    const res = await fetch('/api/settings/mcp/servers/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (cell) {
      if (data.status === 'success') {
        cell.innerHTML = `<span class="text-emerald-400 font-semibold">Online (${escapeHtml(String(data.latency_ms))}ms)</span>`;
      } else {
        const detailText = data.detail ? String(data.detail).substring(0, 30) : 'Unknown error';
        cell.innerHTML = `<span class="text-red-400">Error (${escapeHtml(detailText)}...)</span>`;
      }
    }
  } catch (err) {
    if (cell) cell.innerHTML = '<span class="text-red-400">Unreachable</span>';
  }
}

async function saveAiSettings() {
  const provider = document.getElementById('settings-ai-provider').value;
  const model = document.getElementById('settings-ai-model').value.trim();
  const key = document.getElementById('settings-ai-key').value.trim();

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai: { provider, model, api_key: key || null } })
    });
    if (res.ok) {
      showSettingsAlert('AI configuration saved successfully!');
      await loadSettings();
    }
  } catch (err) {
    showSettingsAlert(`Error saving AI settings: ${err.message}`, true);
  }
}

async function saveTaxSettings() {
  const exemption = parseFloat(document.getElementById('settings-tax-exemption').value);
  const date = document.getElementById('settings-tax-date').value;
  const price = parseFloat(document.getElementById('settings-tax-price').value);
  const rate = parseFloat(document.getElementById('settings-tax-rate').value);

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tax: {
          annual_exemption: exemption,
          benchmark_date: date,
          benchmark_price: price,
          tax_rate_pct: rate
        }
      })
    });
    if (res.ok) {
      showSettingsAlert('Regional tax preferences saved successfully!');
      await loadSettings();
    }
  } catch (err) {
    showSettingsAlert(`Error saving tax settings: ${err.message}`, true);
  }
}

async function downloadEncryptedBackup() {
  const passphrase = (document.getElementById('vault-passphrase')?.value || '').trim();
  if (passphrase.length < 4) {
    showToast('Please enter an encryption passphrase (at least 4 characters) to protect your backup.', 'warning');
    return;
  }
  try {
    const res = await fetch('/api/backup/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passphrase })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Export failed');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `paslood_vault_${new Date().toISOString().slice(0, 10)}.wpbackup`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showSettingsAlert('✓ Encrypted vault backup downloaded!');
  } catch (err) {
    showSettingsAlert(`Export Error: ${err.message}`, true);
  }
}

async function uploadEncryptedBackup(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const passphrase = (document.getElementById('vault-passphrase')?.value || '').trim();
  if (passphrase.length < 4) {
    showToast('Please enter your vault passphrase first before selecting the backup file.', 'warning');
    event.target.value = '';
    return;
  }
  try {
    const text = await file.text();
    const bundle = JSON.parse(text);
    const res = await fetch('/api/backup/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle, passphrase })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Restore failed');
    showSettingsAlert('✓ Encrypted vault restored successfully!');
    await loadSettings();
    await loadOverview();
  } catch (err) {
    showSettingsAlert(`Restore Error: ${err.message}`, true);
  } finally {
    event.target.value = '';
  }
}

async function syncCloudDriveVault(action) {
  const passphrase = (document.getElementById('vault-passphrase')?.value || '').trim();
  const syncDir = (document.getElementById('vault-cloud-dir')?.value || '').trim();
  if (passphrase.length < 4) {
    showToast('Please enter your vault encryption passphrase.', 'warning');
    return;
  }
  if (!syncDir) {
    showToast('Please enter your local Cloud Drive folder path (e.g. ~/Proton Drive/WealthPilot).', 'warning');
    return;
  }
  try {
    const res = await fetch('/api/backup/cloud-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sync_dir: syncDir, passphrase, action })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Cloud sync failed');
    const msg = action === 'pull'
      ? `✓ Pulled and decrypted vault from ${data.vault_file}`
      : `✓ Pushed encrypted vault to ${data.vault_file}`;
    showSettingsAlert(msg);
    await loadSettings();
    await loadOverview();
  } catch (err) {
    showSettingsAlert(`Cloud Sync Error: ${err.message}`, true);
  }
}

// --- Interactive First-Time Setup Wizard ---
let currentWizardStep = 1;

function openSetupWizard() {
  currentWizardStep = 1;
  updateWizardStepUI();
  document.getElementById('setup-wizard-modal')?.classList.remove('hidden');
}

function closeSetupWizard() {
  document.getElementById('setup-wizard-modal')?.classList.add('hidden');
}

async function saveWizardSettings(values) {
  const response = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values)
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      detail = (await response.json()).detail || detail;
    } catch (err) {
      // Keep the HTTP status as an actionable fallback for non-JSON errors.
    }
    throw new Error(detail);
  }
}

async function skipSetupWizard() {
  try {
    await saveWizardSettings({ onboarding_complete: true });
    localStorage.setItem('paslood_setup_completed', 'true');
    closeSetupWizard();
  } catch (err) {
    showSettingsAlert(`Could not save setup status: ${err.message}`, true);
  }
}

function updateWizardStepUI() {
  document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
  const activeStep = document.getElementById(`wizard-step-${currentWizardStep}`);
  if (activeStep) activeStep.classList.remove('hidden');

  for (let i = 1; i <= 3; i++) {
    const ind = document.getElementById(`wizard-indicator-${i}`);
    if (!ind) continue;
    const badge = ind.querySelector('span:first-child');
    if (i === currentWizardStep) {
      ind.className = 'flex items-center gap-2 text-blue-400 font-semibold';
      badge.className = 'w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs';
      badge.textContent = `${i}`;
    } else if (i < currentWizardStep) {
      ind.className = 'flex items-center gap-2 text-emerald-400 font-medium';
      badge.className = 'w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs';
      badge.textContent = '✓';
    } else {
      ind.className = 'flex items-center gap-2 text-slate-500';
      badge.className = 'w-6 h-6 rounded-full bg-slate-800 text-slate-300 flex items-center justify-center text-xs';
      badge.textContent = `${i}`;
    }
  }

  const prevBtn = document.getElementById('wiz-btn-prev');
  const nextBtn = document.getElementById('wiz-btn-next');
  const finishBtn = document.getElementById('wiz-btn-finish');
  if (!prevBtn || !nextBtn || !finishBtn) return;

  if (currentWizardStep === 1) {
    prevBtn.classList.add('hidden');
    nextBtn.classList.remove('hidden');
    finishBtn.classList.add('hidden');
    nextBtn.textContent = I18N.t('modals.wiz_next_buckets', 'Next: Buckets →');
  } else if (currentWizardStep === 2) {
    prevBtn.classList.remove('hidden');
    nextBtn.classList.remove('hidden');
    finishBtn.classList.add('hidden');
    nextBtn.textContent = I18N.t('modals.wiz_next_tax', 'Next: Tax & AI →');
  } else if (currentWizardStep === 3) {
    prevBtn.classList.remove('hidden');
    nextBtn.classList.add('hidden');
    finishBtn.classList.remove('hidden');
  }
}

function wizardStepNext() {
  if (currentWizardStep === 2) {
    const total = getWizardBucketTotal();
    if (total !== 100) {
      showToast(`Target bucket percentages must total 100% (currently ${total}%). Please adjust the allocations.`, 'warning');
      return;
    }
  }
  if (currentWizardStep < 3) {
    currentWizardStep++;
    updateWizardStepUI();
  }
}

function wizardStepPrev() {
  if (currentWizardStep > 1) {
    currentWizardStep--;
    updateWizardStepUI();
  }
}

function getWizardBucketTotal() {
  const b1 = parseFloat(document.getElementById('wiz-b1').value || 0);
  const b2 = parseFloat(document.getElementById('wiz-b2').value || 0);
  const b3 = parseFloat(document.getElementById('wiz-b3').value || 0);
  const b4 = parseFloat(document.getElementById('wiz-b4').value || 0);
  return b1 + b2 + b3 + b4;
}

function updateWizardTotal() {
  const total = getWizardBucketTotal();
  const badge = document.getElementById('wizard-total-badge');
  badge.textContent = `Total: ${total}%`;
  if (total === 100) {
    badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
  } else {
    badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30';
  }
}

async function handleWizardFileUpload(event) {
  if (event.target.files.length > 0) {
    const file = event.target.files[0];
    const status = document.getElementById('wizard-upload-status');
    status.className = 'text-xs py-2 px-3 rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30 block';
    status.textContent = `Uploading and processing ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);
    const endpoint = await detectCsvEndpoint(file);

    try {
      const res = await fetch(endpoint, { method: 'POST', body: formData });
      const result = await res.json();
      if (res.ok) {
        status.className = 'text-xs py-2 px-3 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 block';
        status.textContent = `✓ Successfully imported ${file.name} (${result.transaction_count || result.asset_count} records loaded)!`;
        await loadOverview();
      } else {
        throw new Error(result.detail || 'Import failed');
      }
    } catch (err) {
      status.className = 'text-xs py-2 px-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 block';
      status.textContent = `Import failed: ${err.message}`;
    }
  }
}

async function wizardFinish() {
  const b1 = parseFloat(document.getElementById('wiz-b1').value || 50);
  const b2 = parseFloat(document.getElementById('wiz-b2').value || 35);
  const b3 = parseFloat(document.getElementById('wiz-b3').value || 5);
  const b4 = parseFloat(document.getElementById('wiz-b4').value || 10);

  const exemption = parseFloat(document.getElementById('wiz-tax-exemption').value || 10000);
  const taxRate = parseFloat(document.getElementById('wiz-tax-rate').value || 10.0);

  const aiProv = document.getElementById('wiz-ai-provider').value;
  const aiKey = document.getElementById('wiz-ai-key').value.trim();

  try {
    await saveWizardSettings({
        tax: { annual_exemption: exemption, tax_rate_pct: taxRate, benchmark_date: '2025-12-31' },
        ai: { provider: aiProv, api_key: aiKey || null }
    });

    const bucketTargets = [
      { bucket_id: 'core-etf', name: 'Core World ETFs', target_weight_pct: b1 },
      { bucket_id: 'tech-growth', name: 'High-Conviction Tech', target_weight_pct: b2 },
      { bucket_id: 'commodities', name: 'Gold & Commodities', target_weight_pct: b3 },
      { bucket_id: 'cash-buffer', name: 'Cash & Emergency Buffer', target_weight_pct: b4 }
    ];
    for (const target of bucketTargets) {
      const response = await fetch('/api/buckets/target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(target)
      });
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          detail = (await response.json()).detail || detail;
        } catch (err) {
          // Keep the HTTP status as an actionable fallback for non-JSON errors.
        }
        throw new Error(detail);
      }
    }

    await saveWizardSettings({ onboarding_complete: true });
    localStorage.setItem('paslood_setup_completed', 'true');
    closeSetupWizard();
    await loadOverview();
    await loadSettings();
    showSettingsAlert('🎉 Setup complete! Welcome to Paslood.');
  } catch (err) {
    console.error('Wizard save error:', err);
    showSettingsAlert(`Setup could not be saved: ${err.message}`, true);
  }
}

// ---------------------------------------------------------
// Known Accounts Management
// ---------------------------------------------------------

let currentKnownAccounts = [];

async function loadKnownAccounts() {
  try {
    const res = await fetch('/api/accounts/known');
    if (!res.ok) return;
    const data = await res.json();
    currentKnownAccounts = Array.isArray(data) ? data : (data.accounts || []);
    renderKnownAccounts(currentKnownAccounts);
  } catch (err) {
    console.error('Failed to load known accounts:', err);
  }
}

function renderKnownAccounts(accounts) {
  const tbody = document.getElementById('known-accounts-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const list = Array.isArray(accounts) ? accounts : [];

  if (list.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-4 text-center text-slate-500 italic">No known accounts registered yet. Add your Saxo, savings, or external accounts above.</td>
      </tr>
    `;
    return;
  }

  list.forEach(acc => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-950/30';
    
    let typeBadgeClass = 'bg-slate-800 text-slate-300 border-slate-700';
    if (acc.account_type === 'INVESTMENT') {
      typeBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40';
    } else if (acc.account_type === 'SAVINGS') {
      typeBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }

    const accId = acc.id || acc.account_id || acc.account_number;
    const accNum = acc.account_number || acc.account_id || acc.id;

    tr.innerHTML = `
      <td class="py-2.5 px-3 font-medium text-white">${escapeHtml(acc.label)}</td>
      <td class="py-2.5 px-3 font-mono text-slate-300 text-[11px]">${escapeHtml(accNum)}</td>
      <td class="py-2.5 px-3">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold border ${typeBadgeClass}">
          ${escapeHtml(acc.account_type)}
        </span>
      </td>
      <td class="py-2.5 px-3 text-slate-400 text-[11px]">${escapeHtml(acc.institution || '—')}</td>
      <td class="py-2.5 px-3 text-right">
        <button onclick="deleteKnownAccount('${escapeHtml(accId)}')" class="px-2 py-0.5 rounded border border-red-500/30 hover:bg-red-500/10 text-red-400 text-[11px]">
          Delete
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function toggleAddKnownAccountForm() {
  const form = document.getElementById('add-known-account-form');
  if (!form) return;
  form.classList.toggle('hidden');
}

async function submitNewKnownAccount() {
  const accNum = document.getElementById('new-known-acc-num').value.trim();
  const label = document.getElementById('new-known-acc-label').value.trim();
  const type = document.getElementById('new-known-acc-type').value;
  const inst = document.getElementById('new-known-acc-inst').value.trim();

  if (!accNum || !label) {
    showSettingsAlert('Please specify both an account number/IBAN and a label.', true);
    return;
  }

  try {
    const res = await fetch('/api/accounts/known', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_number: accNum,
        label: label,
        account_type: type,
        institution: inst
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to save account');
    }

    document.getElementById('new-known-acc-num').value = '';
    document.getElementById('new-known-acc-label').value = '';
    document.getElementById('new-known-acc-inst').value = '';
    toggleAddKnownAccountForm();
    await loadKnownAccounts();
    await loadOverview();
    showSettingsAlert(`Saved known account "${label}" successfully.`);
  } catch (err) {
    showSettingsAlert(err.message, true);
  }
}

async function deleteKnownAccount(accountId) {
  if (!confirm(`Remove known account ${accountId}?`)) return;

  try {
    const res = await fetch(`/api/accounts/known/${encodeURIComponent(accountId)}`, {
      method: 'DELETE'
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete account');
    }

    await loadKnownAccounts();
    await loadOverview();
    showSettingsAlert('Known account removed.');
  } catch (err) {
    showSettingsAlert(err.message, true);
  }
}
