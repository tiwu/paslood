/**
 * Paslood — Manual Assets & Liabilities, CSV Statement Ingestion & Transaction Rebucketing
 */

let txCurrentPage = 1;
let txPageSize = 25; // number or 'all'
let txSearchQuery = '';
let txCategoryFilter = 'ALL';
let txAccountFilter = 'ALL';

function formatAccountBadge(accountId) {
  if (!accountId) return { label: 'Account', full: '-' };
  const raw = String(accountId).trim();

  // Check known accounts first
  const cleanRaw = raw.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  const known = (currentData?.known_accounts || []).find(k => {
    const cleanK = (k.account_number || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
    return cleanK && (cleanK === cleanRaw || cleanRaw.includes(cleanK) || cleanK.includes(cleanRaw));
  });
  if (known) {
    const cls = known.account_type === 'INVESTMENT'
      ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
      : (known.account_type === 'SAVINGS'
        ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
        : 'bg-blue-500/15 text-blue-300 border-blue-500/30');
    return { label: known.label, full: `${known.label} (${raw})`, cls: cls };
  }

  // KBC Credit Card
  if (raw.includes('XXXX') || raw.toLowerCase().includes('kredietkaart') || raw.startsWith('5489') || raw.startsWith('5176')) {
    const last4 = raw.slice(-4);
    return { label: `KBC Card ••${last4}`, full: raw, cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' };
  }
  // Bunq IBAN
  if (raw.toUpperCase().includes('BUNQ')) {
    const last4 = raw.slice(-4);
    return { label: `bunq ••${last4}`, full: raw, cls: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30' };
  }
  // KBC IBAN
  if (raw.toUpperCase().startsWith('BE')) {
    const last4 = raw.slice(-4);
    return { label: `KBC ••${last4}`, full: raw, cls: 'bg-blue-500/15 text-blue-300 border-blue-500/30' };
  }
  // Generic fallback
  const last4 = raw.length > 4 ? raw.slice(-4) : raw;
  return { label: `Acc ••${last4}`, full: raw, cls: 'bg-slate-800 text-slate-300 border-slate-700' };
}

function getCategoryBadgeClasses(cat) {
  const c = String(cat || '').toUpperCase();
  switch (c) {
    case 'INCOME':
    case 'SALARY':
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/25';
    case 'GROCERIES':
      return 'bg-lime-500/15 text-lime-300 border-lime-500/30 hover:bg-lime-500/25';
    case 'LEISURE':
      return 'bg-pink-500/15 text-pink-300 border-pink-500/30 hover:bg-pink-500/25';
    case 'TRANSPORT':
      return 'bg-sky-500/15 text-sky-300 border-sky-500/30 hover:bg-sky-500/25';
    case 'UTILITIES':
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25';
    case 'TAX':
      return 'bg-red-500/15 text-red-300 border-red-500/30 hover:bg-red-500/25';
    case 'HOUSING':
    case 'MORTGAGE':
      return 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30 hover:bg-indigo-500/25';
    case 'DEBT_REPAYMENT':
      return 'bg-rose-500/15 text-rose-300 border-rose-500/30 hover:bg-rose-500/25';
    case 'INSURANCE':
      return 'bg-purple-500/15 text-purple-300 border-purple-500/30 hover:bg-purple-500/25';
    case 'SUBSCRIPTION':
      return 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30 hover:bg-fuchsia-500/25';
    case 'INVESTMENTS':
      return 'bg-teal-500/15 text-teal-300 border-teal-500/30 hover:bg-teal-500/25';
    case 'SAVINGS':
      return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/25';
    case 'LIVING_EXPENSES':
      return 'bg-orange-500/15 text-orange-300 border-orange-500/30 hover:bg-orange-500/25';
    case 'TRANSFER':
      return 'bg-slate-700/50 text-slate-300 border-slate-600 hover:bg-slate-700';
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700';
  }
}

function onTxSearchInput(e) {
  txSearchQuery = (e.target.value || '').trim().toLowerCase();
  txCurrentPage = 1;
  renderTransactions(currentData);
}

function onTxCategoryFilterChange(e) {
  txCategoryFilter = e.target.value || 'ALL';
  txCurrentPage = 1;
  renderTransactions(currentData);
}

function onTxAccountFilterChange(e) {
  txAccountFilter = e.target.value || 'ALL';
  txCurrentPage = 1;
  renderTransactions(currentData);
}

function onTxPageSizeChange(e) {
  const val = e.target.value;
  txPageSize = val === 'all' ? 'all' : parseInt(val, 10) || 25;
  txCurrentPage = 1;
  renderTransactions(currentData);
}

function goToTxPage(action) {
  const allFiltered = getFilteredTransactions(currentData?.transactions || []);
  const totalPages = txPageSize === 'all' ? 1 : Math.max(1, Math.ceil(allFiltered.length / txPageSize));

  if (action === 'first') txCurrentPage = 1;
  else if (action === 'prev') txCurrentPage = Math.max(1, txCurrentPage - 1);
  else if (action === 'next') txCurrentPage = Math.min(totalPages, txCurrentPage + 1);
  else if (action === 'last') txCurrentPage = totalPages;

  renderTransactions(currentData);
}

function parseAmountFilterTokens(rawQuery) {
  const amountFilters = [];
  const textTokens = [];
  const tokens = String(rawQuery || '').trim().split(/\s+/).filter(Boolean);

  tokens.forEach(tok => {
    const m = tok.match(/^(>=|<=|>|<|=|==)(-?\d+(?:[.,]\d+)?)$/);
    if (m) {
      const op = m[1] === '==' ? '=' : m[1];
      const val = parseFloat(m[2].replace(',', '.'));
      if (!isNaN(val)) {
        amountFilters.push({ op, val, isNegativeExplicit: m[2].startsWith('-') });
        return;
      }
    }
    textTokens.push(tok.toLowerCase());
  });

  return { amountFilters, textQuery: textTokens.join(' ') };
}

function matchesAmountFilter(txAmountValue, filter) {
  const rawVal = Number(txAmountValue || 0);
  const cmpVal = filter.isNegativeExplicit ? rawVal : Math.abs(rawVal);
  switch (filter.op) {
    case '>':
      return cmpVal > filter.val;
    case '>=':
      return cmpVal >= filter.val;
    case '<':
      return cmpVal < filter.val;
    case '<=':
      return cmpVal <= filter.val;
    case '=':
      return Math.abs(cmpVal - filter.val) < 0.01;
    default:
      return true;
  }
}

function getFilteredTransactions(allTxs) {
  const cleanFilterAcc = txAccountFilter === 'ALL' ? 'ALL' : String(txAccountFilter).replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  const { amountFilters, textQuery } = parseAmountFilterTokens(txSearchQuery);

  return allTxs.filter(tx => {
    if (txCategoryFilter !== 'ALL' && String(tx.category || '').toUpperCase() !== txCategoryFilter) {
      return false;
    }
    if (cleanFilterAcc !== 'ALL') {
      const cleanTxAcc = String(tx.account_id || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
      if (cleanTxAcc !== cleanFilterAcc) {
        return false;
      }
    }
    for (const af of amountFilters) {
      if (!matchesAmountFilter(tx.amount_value, af)) {
        return false;
      }
    }
    if (textQuery) {
      const matchText = `${tx.description || ''} ${tx.counterparty_name || ''} ${tx.counterparty_iban || ''} ${tx.account_id || ''} ${tx.amount_formatted || ''} ${tx.amount_value !== undefined ? Math.abs(tx.amount_value) : ''}`.toLowerCase();
      const cleanSearch = textQuery.replace(/\s+/g, '');
      const cleanMatchText = matchText.replace(/\s+/g, '');
      if (!matchText.includes(textQuery) && !cleanMatchText.includes(cleanSearch)) return false;
    }
    return true;
  });
}

function populateAccountFilter(txs) {
  const select = document.getElementById('tx-account-filter');
  if (!select) return;

  const currentVal = txAccountFilter;
  const seenClean = new Map();
  txs.forEach(t => {
    const raw = (t.account_id || '').trim();
    if (!raw) return;
    const clean = raw.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
    if (clean && !seenClean.has(clean)) {
      seenClean.set(clean, raw);
    }
  });
  const accounts = Array.from(seenClean.values()).sort();

  select.innerHTML = '<option value="ALL">All Accounts (KBC &amp; Bunq)</option>';
  accounts.forEach(acc => {
    const badge = formatAccountBadge(acc);
    const opt = document.createElement('option');
    opt.value = acc;
    opt.textContent = `${badge.label} (${acc})`;
    if (acc === currentVal || acc.replace(/[^A-Za-z0-9]/g, '').toUpperCase() === String(currentVal).replace(/[^A-Za-z0-9]/g, '').toUpperCase()) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });
}

function renderTransactions(data) {
  renderCashflowAnalytics(data);
  const tbody = document.getElementById('tx-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  const txs = data?.transactions || [];

  // Populate dynamic account filter options
  populateAccountFilter(txs);

  const badge = document.getElementById('tx-count-badge');
  if (badge) {
    badge.textContent = I18N.t('cashflow.tx_count_badge', { count: txs.length, _fallback: `${txs.length} Transactions` });
  }

  const filtered = getFilteredTransactions(txs);

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-3 py-6 text-center text-slate-500">${escapeHtml(I18N.t('cashflow.empty_tx', 'No transactions found matching your filters.'))}</td></tr>`;
    updatePaginationControls(0, 0, 0);
    return;
  }

  const effectivePageSize = txPageSize === 'all' ? filtered.length : txPageSize;
  const totalPages = Math.max(1, Math.ceil(filtered.length / effectivePageSize));
  if (txCurrentPage > totalPages) txCurrentPage = totalPages;

  const startIdx = (txCurrentPage - 1) * effectivePageSize;
  const endIdx = txPageSize === 'all' ? filtered.length : Math.min(startIdx + effectivePageSize, filtered.length);
  const pagedTxs = filtered.slice(startIdx, endIdx);

  pagedTxs.forEach(tx => {
    const tr = document.createElement('tr');
    const isPositive = tx.amount_value > 0;
    const safeDesc = escapeHtml(tx.description || '-');
    const safeCounterparty = escapeHtml(tx.counterparty_name || '-');
    const safeDate = escapeHtml(I18N.formatDate(tx.date));
    const numAmt = tx.amount_value !== undefined ? Math.abs(tx.amount_value) : tx.amount_formatted;
    const safeAmount = escapeHtml(I18N.formatCurrency(numAmt, 'EUR'));
    const safeCat = escapeHtml(tx.category);
    const safeId = escapeHtml(tx.id);
    const accBadge = formatAccountBadge(tx.account_id);
    const catClasses = getCategoryBadgeClasses(tx.category);

    tr.innerHTML = `
      <td class="px-3 py-2 text-slate-400 whitespace-nowrap">${safeDate}</td>
      <td class="px-3 py-2 whitespace-nowrap">
        <span class="inline-block px-2 py-0.5 rounded text-[11px] font-mono border ${accBadge.cls}" title="${escapeHtml(accBadge.full)}">
          ${escapeHtml(badgeLabel(accBadge.label))}
        </span>
      </td>
      <td class="px-3 py-2 font-medium text-white max-w-xs truncate" title="${safeDesc}">${safeDesc}</td>
      <td class="px-3 py-2 text-slate-400 truncate max-w-[140px]">${safeCounterparty}</td>
      <td class="px-3 py-2 text-right font-mono font-semibold whitespace-nowrap ${isPositive ? 'text-emerald-400' : 'text-slate-200'}">
        ${isPositive ? '+' : ''}${safeAmount}
      </td>
      <td class="px-3 py-2 whitespace-nowrap">
        <button onclick="openRebucketModalById('${safeId}')" class="px-2 py-0.5 rounded text-xs border font-medium transition ${catClasses}">
          ${safeCat} ▾
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  updatePaginationControls(startIdx + 1, endIdx, filtered.length);
}

function badgeLabel(label) {
  return label;
}

function updatePaginationControls(start, end, total) {
  const info = document.getElementById('tx-pagination-info');
  const indicator = document.getElementById('tx-page-indicator');
  const btnFirst = document.getElementById('tx-btn-first');
  const btnPrev = document.getElementById('tx-btn-prev');
  const btnNext = document.getElementById('tx-btn-next');
  const btnLast = document.getElementById('tx-btn-last');

  if (info) {
    info.textContent = total > 0 ? `Showing ${start}–${end} of ${total} transactions` : 'Showing 0 of 0 transactions';
  }

  const effectivePageSize = txPageSize === 'all' ? (total || 1) : txPageSize;
  const totalPages = Math.max(1, Math.ceil((total || 1) / effectivePageSize));

  if (indicator) {
    indicator.textContent = `${txCurrentPage} / ${totalPages}`;
  }

  if (btnFirst) btnFirst.disabled = (txCurrentPage <= 1);
  if (btnPrev) btnPrev.disabled = (txCurrentPage <= 1);
  if (btnNext) btnNext.disabled = (txCurrentPage >= totalPages);
  if (btnLast) btnLast.disabled = (txCurrentPage >= totalPages);
}

function initFileDropzone() {
  const dropzone = document.getElementById('dropzone');
  if (!dropzone || dropzone.dataset?.initialized === 'true') return;
  if (dropzone.dataset) dropzone.dataset.initialized = 'true';
  dropzone.addEventListener('click', () => document.getElementById('file-input')?.click());
  dropzone.addEventListener('dragover', e => {
    e.preventDefault();
    dropzone.classList.add('border-blue-500');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('border-blue-500'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('border-blue-500');
    if (e.dataTransfer?.files?.length > 0) uploadFile(e.dataTransfer.files[0]);
  });
}

function handleFileUpload(e) {
  if (e.target.files && e.target.files.length > 0) {
    uploadFiles(Array.from(e.target.files));
  }
}

async function detectCsvEndpoint(file) {
  try {
    const textSlice = await file.slice(0, 2048).text();
    const lower = textSlice.toLowerCase();
    const firstLine = lower.split(/\r?\n/)[0];

    if (lower.includes('"date"') && lower.includes('"amount"') && lower.includes('"account"')) {
      return '/api/ingest/bunq';
    }
    if (lower.includes('positie-overzicht') || lower.includes('kbc easy invest') || lower.includes('productklasse')) {
      return '/api/ingest/generic';
    }
    if (
      firstLine.includes('rekeningnummer') ||
      firstLine.includes('kredietkaart') ||
      firstLine.includes('afschriftnummer') ||
      firstLine.includes('rubrieknaam') ||
      firstLine.includes('tegenpartij') ||
      file.name.toLowerCase().includes('kbc')
    ) {
      return '/api/ingest/kbc';
    }
  } catch (e) {
    // Fallback to name check
  }
  return file.name.toLowerCase().includes('kbc') ? '/api/ingest/kbc' : '/api/ingest/generic';
}

async function uploadFile(file) {
  await uploadFiles([file]);
}

async function uploadFiles(files) {
  const status = document.getElementById('upload-status');
  status.className = 'text-xs py-2 px-3 rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30';
  status.textContent = `Uploading and parsing ${files.length} statement(s)...`;
  status.classList.remove('hidden');

  let totalNewTxs = 0;
  let totalProcessedTxs = 0;
  let totalAssets = 0;
  let successCount = 0;
  const errors = [];
  const discoveredUnregistered = [];

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const endpoint = await detectCsvEndpoint(file);
      const res = await fetch(endpoint, { method: 'POST', body: formData });
      const result = await res.json();
      if (res.ok) {
        successCount++;
        totalNewTxs += (result.new_transactions || 0);
        totalProcessedTxs += (result.transactions_processed || result.transaction_count || 0);
        totalAssets += (result.asset_count || 0);
        if (result.unregistered_accounts && Array.isArray(result.unregistered_accounts)) {
          result.unregistered_accounts.forEach(u => {
            if (!discoveredUnregistered.some(existing => existing.account_id === u.account_id)) {
              discoveredUnregistered.push(u);
            }
          });
        }
      } else {
        errors.push(`${file.name}: ${result.detail || 'Upload failed'}`);
      }
    } catch (err) {
      errors.push(`${file.name}: ${err.message}`);
    }
  }

  if (successCount > 0) {
    status.className = 'text-xs py-2 px-3 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    let summary = `Processed ${successCount} file(s). Added ${totalNewTxs} new transaction(s) (${totalProcessedTxs} scanned).`;
    if (totalAssets > 0) {
      summary += ` Discovered/updated ${totalAssets} portfolio asset(s).`;
    }
    if (errors.length > 0) {
      summary += ` (${errors.length} failed: ${errors.join(', ')})`;
    }
    status.textContent = summary;
    showToast(summary, 'success');
    await loadOverview();

    // Check if new accounts were discovered
    if (discoveredUnregistered.length > 0) {
      promptAddUnregisteredAccounts(discoveredUnregistered);
    }
  } else {
    status.className = 'text-xs py-2 px-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30';
    status.textContent = `Upload failed: ${errors.join('; ')}`;
    showToast(`Upload failed: ${errors.join('; ')}`, 'error');
  }
}

function promptAddUnregisteredAccounts(unregistered) {
  if (!unregistered || unregistered.length === 0) return;
  const first = unregistered[0];
  const countExtra = unregistered.length - 1;
  const extraText = countExtra > 0 ? ` (+${countExtra} more)` : '';

  const msg = `Discovered new account statement: ${first.account_id} (${first.institution_hint})${extraText}. Register this account?`;
  
  showToast(
    `${msg} <button onclick="goToRegisterKnownAccount('${escapeHtml(first.account_id)}', '${escapeHtml(first.institution_hint)}')" class="underline ml-2 font-bold hover:text-white">Register Account</button>`,
    'info',
    10000
  );
}

function goToRegisterKnownAccount(accountId, institution) {
  if (typeof switchWorkspace === 'function') {
    switchWorkspace('settings');
  }
  setTimeout(() => {
    if (typeof prefillKnownAccountForm === 'function') {
      prefillKnownAccountForm(accountId, institution);
    }
  }, 150);
}

// Re-Bucketing Modal
function openRebucketModalById(txId) {
  const tx = (currentData?.transactions || []).find(t => t.id === txId);
  if (tx) {
    openRebucketModal(tx.id, tx.description, tx.counterparty_name, tx.category, tx.amount_value);
  }
}

function openRebucketModal(txId, desc, counterparty, currentCat, amountValue = null) {
  activeRebucketTx = {
    id: txId,
    description: desc,
    counterparty: counterparty,
    amount_value: amountValue
  };
  const amtHint = (amountValue !== null && amountValue !== undefined)
    ? `<div class="text-slate-400 mt-0.5 font-mono">Amount: ${escapeHtml(I18N.formatCurrency(Math.abs(amountValue), 'EUR'))}</div>`
    : '';
  document.getElementById('rebucket-tx-info').innerHTML = `
    <div class="font-semibold text-white">${escapeHtml(desc)}</div>
    <div class="text-slate-400 mt-0.5">Counterparty: ${escapeHtml(counterparty || 'N/A')}</div>
    ${amtHint}
  `;
  document.getElementById('modal-category-select').value = currentCat || 'OTHER';

  const defaultPattern = (counterparty || desc || '').trim();
  const patternInput = document.getElementById('modal-pattern-input');
  if (patternInput) {
    patternInput.value = defaultPattern;
  }
  const amountInput = document.getElementById('modal-amount-input');
  if (amountInput) {
    amountInput.value = '';
    amountInput.placeholder = (amountValue !== null && amountValue !== undefined)
      ? `e.g. ${Math.abs(Number(amountValue)).toFixed(2)}`
      : 'Optional';
  }

  document.getElementById('rebucket-modal').classList.remove('hidden');
}

function closeRebucketModal() {
  document.getElementById('rebucket-modal').classList.add('hidden');
  activeRebucketTx = null;
}

async function commitRebucket() {
  if (!activeRebucketTx) return;
  const targetCat = document.getElementById('modal-category-select').value;
  const remember = document.getElementById('modal-remember-rule').checked;
  const patternEl = document.getElementById('modal-pattern-input');
  const patternVal = patternEl ? patternEl.value.trim() : (activeRebucketTx.counterparty || '');
  const amountRaw = document.getElementById('modal-amount-input')?.value?.trim() || '';
  const parsedAmount = amountRaw !== '' ? parseFloat(amountRaw) : null;

  try {
    const payload = {
      transaction_id: activeRebucketTx.id,
      target_category: targetCat,
      counterparty_name: activeRebucketTx.counterparty,
      pattern: patternVal,
      remember_rule: remember
    };
    if (parsedAmount !== null && !isNaN(parsedAmount)) {
      payload.amount = Math.abs(parsedAmount);
    }
    const res = await fetch('/api/transactions/rebucket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    closeRebucketModal();
    if (res.ok) {
      const msg = data.updated_historical_count > 1
        ? `Re-bucketed transaction and updated ${data.updated_historical_count} matching records to ${targetCat}`
        : `Transaction re-bucketed to ${targetCat}`;
      showToast(msg, 'success');
      await loadOverview();
    } else {
      throw new Error(data.detail || 'Re-bucket failed');
    }
  } catch (err) {
    showToast(`Failed to re-bucket transaction: ${err.message}`, 'error');
  }
}

// Manual Assets & Debts
function renderManualAssetsAndDebts(data) {
  const assetsTbody = document.getElementById('manual-assets-tbody');
  if (assetsTbody) {
    assetsTbody.innerHTML = '';
    const manualOrRealEstate = (data.assets || []).filter(a =>
      a.asset_class === 'REAL_ESTATE' || a.id.startsWith('asset-') || a.id === 'bunq-savings' || a.institution === 'Manual'
    );
    if (manualOrRealEstate.length === 0) {
      assetsTbody.innerHTML = `<tr><td colspan="4" class="py-3 text-slate-500 text-center">${escapeHtml(I18N.t('cashflow.empty_assets', 'No manual real estate or private assets added yet.'))}</td></tr>`;
    } else {
      manualOrRealEstate.forEach(a => {
        const tr = document.createElement('tr');
        const safeName = escapeHtml(a.name);
        const safeClass = escapeHtml(a.asset_class);
        const safeVal = escapeHtml(I18N.formatCurrency(a.current_value, a.currency || 'EUR'));
        const safeId = escapeHtml(a.id);
        const rawCost = a.cost_basis && typeof a.cost_basis === 'object' ? a.cost_basis.amount : a.cost_basis;
        const metaParts = [];
        if (a.acquisition_date) {
          metaParts.push(`Acquired: ${escapeHtml(a.acquisition_date)}`);
        }
        if (rawCost !== null && rawCost !== undefined && Number(rawCost) > 0) {
          metaParts.push(`Basis: ${escapeHtml(I18N.formatCurrency(rawCost, a.currency || 'EUR'))}`);
        }
        const metaHtml = metaParts.length > 0
          ? `<div class="text-[10px] text-slate-400 font-normal mt-0.5">${metaParts.join(' • ')}</div>`
          : '';
        tr.innerHTML = `
          <td class="py-2.5 font-medium text-white">${safeName}${metaHtml}</td>
          <td class="py-2.5 whitespace-nowrap"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">${safeClass}</span></td>
          <td class="py-2.5 font-mono text-emerald-400 whitespace-nowrap">${safeVal}</td>
          <td class="py-2.5 text-right whitespace-nowrap">
            <button onclick="editManualAsset('${safeId}')" class="text-blue-400 hover:text-blue-300 text-xs px-2 py-0.5 rounded hover:bg-blue-500/10 mr-1">${escapeHtml(I18N.t('common.edit', 'Edit'))}</button>
            <button onclick="deleteManualAsset('${safeId}')" class="text-rose-400 hover:text-rose-300 text-xs px-2 py-0.5 rounded hover:bg-rose-500/10">${escapeHtml(I18N.t('common.delete', 'Delete'))}</button>
          </td>
        `;
        assetsTbody.appendChild(tr);
      });
    }
  }

  const liabTbody = document.getElementById('manual-liabilities-tbody');
  if (liabTbody) {
    liabTbody.innerHTML = '';
    const liabilities = data.liabilities || [];
    if (liabilities.length === 0) {
      liabTbody.innerHTML = `<tr><td colspan="6" class="py-3 text-slate-500 text-center">${escapeHtml(I18N.t('cashflow.empty_liabilities', 'No debt or mortgage balances recorded.'))}</td></tr>`;
    } else {
      liabilities.forEach(l => {
        const tr = document.createElement('tr');
        const isUnsetBalance = l.principal_balance <= 0;
        const balanceHtml = isUnsetBalance
          ? `<span class="text-amber-400 font-mono whitespace-nowrap">${escapeHtml(I18N.t('cashflow.unset_balance', `Unset (${I18N.formatCurrency(0)})`))}</span> <span class="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 whitespace-nowrap">${escapeHtml(I18N.t('cashflow.needs_balance', 'Needs Balance'))}</span>`
          : `<span class="font-mono text-rose-400 whitespace-nowrap">${escapeHtml(I18N.formatCurrency(l.principal_balance, l.currency || 'EUR'))}</span>`;
        const rateHtml = l.interest_rate_pct <= 0
          ? `<span class="text-slate-500 font-mono whitespace-nowrap">—</span>`
          : `<span class="font-mono text-slate-300 whitespace-nowrap">${escapeHtml(I18N.formatPercent(l.interest_rate_pct))}</span>`;

        const safeName = escapeHtml(l.name);
        const safeType = escapeHtml(l.loan_type);
        const pctSuffix = l.monthly_payment_pct > 0 ? ` <span class="text-[10px] text-slate-400 whitespace-nowrap">(${escapeHtml(I18N.formatPercent(l.monthly_payment_pct))}/mo)</span>` : '';
        const safePmt = `${escapeHtml(I18N.formatCurrency(l.monthly_payment, l.currency || 'EUR'))}${pctSuffix}`;
        const safeId = escapeHtml(l.id);

        tr.innerHTML = `
          <td class="py-2.5 font-medium text-white">${safeName}</td>
          <td class="py-2.5 whitespace-nowrap"><span class="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30">${safeType}</span></td>
          <td class="py-2.5 whitespace-nowrap">${balanceHtml}</td>
          <td class="py-2.5 whitespace-nowrap">${rateHtml}</td>
          <td class="py-2.5 font-mono text-slate-300 whitespace-nowrap">${safePmt}</td>
          <td class="py-2.5 text-right whitespace-nowrap">
            <button onclick="openEditLiabilityModalById('${safeId}')" class="text-xs text-blue-400 hover:text-blue-300 font-medium px-2 py-0.5 rounded hover:bg-blue-500/10 mr-1.5">${escapeHtml(I18N.t('common.edit', 'Edit'))}</button>
            <button onclick="deleteManualLiability('${safeId}')" class="text-xs text-rose-400 hover:text-rose-300 font-medium px-2 py-0.5 rounded hover:bg-rose-500/10">${escapeHtml(I18N.t('common.delete', 'Delete'))}</button>
          </td>
        `;
        liabTbody.appendChild(tr);
      });
    }
  }
}

function openEditLiabilityModalById(id) {
  const l = (currentData?.liabilities || []).find(x => x.id === id);
  if (l) {
    openEditLiabilityModal(
      l.id,
      l.name,
      l.loan_type,
      l.principal_balance,
      l.interest_rate_pct,
      l.monthly_payment,
      l.institution,
      l.account_reference,
      l.monthly_payment_pct,
      l.start_capital,
      l.start_date,
      l.duration_months,
      l.end_date
    );
  }
}

function openAddAssetModal(editAsset = null) {
  const modal = document.getElementById('add-asset-modal');
  const title = document.getElementById('modal-asset-title');
  if (editAsset) {
    if (title) title.textContent = '✏️ Edit Asset';
    document.getElementById('manual-asset-id').value = editAsset.id || '';
    document.getElementById('manual-asset-name').value = editAsset.name || '';
    document.getElementById('manual-asset-class').value = editAsset.asset_class || 'REAL_ESTATE';
    document.getElementById('manual-asset-val').value = editAsset.current_value || (editAsset.current_value_formatted ? parseFloat(editAsset.current_value_formatted.replace(/[^0-9.-]/g, '')) : '');
    document.getElementById('manual-asset-inst').value = editAsset.institution || 'Manual';
    document.getElementById('manual-asset-sym').value = editAsset.symbol || '';
    const acqDateEl = document.getElementById('manual-asset-acq-date');
    if (acqDateEl) acqDateEl.value = editAsset.acquisition_date || editAsset.start_date || '';
    const costBasisEl = document.getElementById('manual-asset-cost-basis');
    if (costBasisEl) costBasisEl.value = editAsset.cost_basis ? (editAsset.cost_basis.amount || editAsset.cost_basis) : '';
  } else {
    if (title) title.textContent = '🏠 Add Real Estate or Asset';
    document.getElementById('manual-asset-id').value = '';
    document.getElementById('manual-asset-name').value = '';
    document.getElementById('manual-asset-class').value = 'REAL_ESTATE';
    document.getElementById('manual-asset-val').value = '';
    document.getElementById('manual-asset-inst').value = '';
    document.getElementById('manual-asset-sym').value = '';
    const acqDateEl = document.getElementById('manual-asset-acq-date');
    if (acqDateEl) acqDateEl.value = '';
    const costBasisEl = document.getElementById('manual-asset-cost-basis');
    if (costBasisEl) costBasisEl.value = '';
  }
  modal.classList.remove('hidden');
}

function editManualAsset(assetId) {
  const asset = (currentData?.assets || []).find(a => a.id === assetId);
  if (asset) {
    openAddAssetModal(asset);
  }
}

function closeAddAssetModal() {
  document.getElementById('add-asset-modal').classList.add('hidden');
  document.getElementById('manual-asset-id').value = '';
}

async function saveManualAsset() {
  const assetId = document.getElementById('manual-asset-id').value.trim();
  const name = document.getElementById('manual-asset-name').value.trim();
  const assetClass = document.getElementById('manual-asset-class').value;
  const val = parseFloat(document.getElementById('manual-asset-val').value) || 0;
  const inst = document.getElementById('manual-asset-inst').value.trim() || 'Manual';
  const sym = document.getElementById('manual-asset-sym').value.trim();
  const acqDate = document.getElementById('manual-asset-acq-date') ? document.getElementById('manual-asset-acq-date').value.trim() : '';
  const costBasisVal = document.getElementById('manual-asset-cost-basis') ? parseFloat(document.getElementById('manual-asset-cost-basis').value) : NaN;

  if (!name || val <= 0) {
    showToast('Please provide an asset name and valid estimated value.', 'warning');
    return;
  }

  try {
    const payload = {
      name: name,
      asset_class: assetClass,
      current_value: val,
      institution: inst,
      symbol: sym || null,
      acquisition_date: acqDate || null,
      cost_basis: (!isNaN(costBasisVal) && costBasisVal > 0) ? costBasisVal : null
    };
    if (assetId) payload.id = assetId;

    const res = await fetch('/api/assets/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeAddAssetModal();
      document.getElementById('manual-asset-id').value = '';
      document.getElementById('manual-asset-name').value = '';
      document.getElementById('manual-asset-val').value = '';
      await loadOverview();
      showToast(assetId ? 'Asset updated successfully!' : 'Asset added successfully!');
    }
  } catch (err) {
    console.error('Failed to save manual asset:', err);
  }
}

async function deleteManualAsset(assetId) {
  const confirmed = await confirmDialog({
    title: 'Delete Asset',
    message: 'Are you sure you want to remove this asset?',
    confirmVariant: 'danger',
  });
  if (!confirmed) return;
  try {
    const res = await fetch(`/api/assets/manual/${assetId}`, { method: 'DELETE' });
    if (res.ok) {
      await loadOverview();
      showToast('Asset deleted.');
    }
  } catch (err) {
    console.error('Failed to delete asset:', err);
  }
}

function openAddLiabilityModal() {
  document.getElementById('liab-modal-title').textContent = I18N.t('modals.liab_add_title', '💳 Add Mortgage or Loan');
  document.getElementById('manual-liab-id').value = '';
  document.getElementById('manual-liab-name').value = '';
  document.getElementById('manual-liab-type').value = 'MORTGAGE';
  document.getElementById('manual-liab-balance').value = '';
  document.getElementById('manual-liab-rate').value = '';
  document.getElementById('manual-liab-payment').value = '';
  document.getElementById('manual-liab-payment-pct').value = '';
  document.getElementById('manual-liab-start-cap').value = '';
  document.getElementById('manual-liab-start-date').value = '';
  document.getElementById('manual-liab-duration').value = '';
  document.getElementById('manual-liab-end-date').value = '';
  document.getElementById('manual-liab-inst').value = '';
  document.getElementById('manual-liab-ref').value = '';
  document.getElementById('add-liability-modal').classList.remove('hidden');
}

function openEditLiabilityModal(id, name, type, balance, rate, payment, inst, ref, paymentPct = 0, startCap = null, startDate = null, durationMos = null, endDate = null) {
  document.getElementById('liab-modal-title').textContent = I18N.t('modals.liab_edit_title', '✏️ Edit Loan / Mortgage Details');
  document.getElementById('manual-liab-id').value = id;
  document.getElementById('manual-liab-name').value = name;
  document.getElementById('manual-liab-type').value = type;
  document.getElementById('manual-liab-balance').value = balance > 0 ? balance : '';
  document.getElementById('manual-liab-rate').value = rate > 0 ? rate : '';
  document.getElementById('manual-liab-payment').value = payment > 0 ? payment : '';
  document.getElementById('manual-liab-payment-pct').value = paymentPct > 0 ? paymentPct : '';
  document.getElementById('manual-liab-start-cap').value = startCap > 0 ? startCap : '';
  document.getElementById('manual-liab-start-date').value = startDate || '';
  document.getElementById('manual-liab-duration').value = durationMos > 0 ? durationMos : '';
  document.getElementById('manual-liab-end-date').value = endDate || '';
  document.getElementById('manual-liab-inst').value = inst || 'KBC';
  document.getElementById('manual-liab-ref').value = ref || '';
  document.getElementById('add-liability-modal').classList.remove('hidden');
}

function closeAddLiabilityModal() {
  document.getElementById('add-liability-modal').classList.add('hidden');
}

function previewLoanAmortization() {
  const startCap = parseFloat(document.getElementById('manual-liab-start-cap')?.value || 0);
  const startDateStr = document.getElementById('manual-liab-start-date')?.value || '';
  const durationVal = parseInt(document.getElementById('manual-liab-duration')?.value || 0, 10);
  const endDateStr = document.getElementById('manual-liab-end-date')?.value || '';
  const ratePct = parseFloat(document.getElementById('manual-liab-rate')?.value || 0);

  if (startCap <= 0 || !startDateStr) return;

  const startDt = new Date(startDateStr);
  if (isNaN(startDt.getTime())) return;

  let totalMonths = durationVal;
  if (!totalMonths && endDateStr) {
    const endDt = new Date(endDateStr);
    if (!isNaN(endDt.getTime())) {
      totalMonths = (endDt.getFullYear() - startDt.getFullYear()) * 12 + (endDt.getMonth() - startDt.getMonth());
    }
  }
  if (!totalMonths || totalMonths <= 0) return;

  const now = new Date();
  const elapsed = Math.max(0, (now.getFullYear() - startDt.getFullYear()) * 12 + (now.getMonth() - startDt.getMonth()));
  let remBal = 0;
  let monthlyPmt = 0;

  if (elapsed >= totalMonths) {
    remBal = 0;
  } else if (ratePct <= 0) {
    monthlyPmt = startCap / totalMonths;
    remBal = startCap * ((totalMonths - elapsed) / totalMonths);
  } else {
    const r = (ratePct / 100.0) / 12.0;
    const factorN = Math.pow(1 + r, totalMonths);
    const factorK = Math.pow(1 + r, elapsed);
    monthlyPmt = startCap * (r * factorN) / (factorN - 1);
    remBal = startCap * (factorN - factorK) / (factorN - 1);
  }

  const balInput = document.getElementById('manual-liab-balance');
  const pmtInput = document.getElementById('manual-liab-payment');
  if (balInput) balInput.value = remBal.toFixed(2);
  if (pmtInput && (!pmtInput.value || parseFloat(pmtInput.value) <= 0)) {
    pmtInput.value = monthlyPmt.toFixed(2);
  }
}

function previewPctPayment() {
  const pct = parseFloat(document.getElementById('manual-liab-payment-pct')?.value || 0);
  const bal = parseFloat(document.getElementById('manual-liab-balance')?.value || 0);
  const pmtInput = document.getElementById('manual-liab-payment');
  if (pct > 0 && bal > 0 && pmtInput) {
    pmtInput.value = ((bal * pct) / 100.0).toFixed(2);
  }
}

async function saveManualLiability() {
  const id = document.getElementById('manual-liab-id').value.trim();
  const name = document.getElementById('manual-liab-name').value.trim();
  const loanType = document.getElementById('manual-liab-type').value;
  const balanceRaw = document.getElementById('manual-liab-balance').value;
  const balance = balanceRaw !== '' ? parseFloat(balanceRaw) : null;
  const rate = parseFloat(document.getElementById('manual-liab-rate').value) || 0;
  const payment = parseFloat(document.getElementById('manual-liab-payment').value) || 0;
  const paymentPct = parseFloat(document.getElementById('manual-liab-payment-pct')?.value) || 0;
  const startCapRaw = document.getElementById('manual-liab-start-cap')?.value;
  const startCap = startCapRaw ? parseFloat(startCapRaw) : null;
  const startDate = document.getElementById('manual-liab-start-date')?.value || null;
  const durationRaw = document.getElementById('manual-liab-duration')?.value;
  const durationMos = durationRaw ? parseInt(durationRaw, 10) : null;
  const endDate = document.getElementById('manual-liab-end-date')?.value || null;
  const inst = document.getElementById('manual-liab-inst').value.trim() || 'Manual';
  const ref = document.getElementById('manual-liab-ref').value.trim();

  if (!name) {
    showToast('Please provide a name for this loan or debt.', 'warning');
    return;
  }

  try {
    const payload = {
      id: id || undefined,
      name: name,
      loan_type: loanType,
      principal_balance: balance,
      interest_rate_pct: rate,
      monthly_payment: payment,
      monthly_payment_pct: paymentPct,
      start_capital: startCap,
      start_date: startDate,
      duration_months: durationMos,
      end_date: endDate,
      institution: inst,
      account_reference: ref || undefined,
    };
    const res = await fetch('/api/liabilities/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeAddLiabilityModal();
      await loadOverview();
      showToast(id ? 'Loan details updated!' : 'Liability / Debt added successfully!');
    }
  } catch (err) {
    console.error('Failed to save liability:', err);
  }
}

async function deleteManualLiability(liabId) {
  const confirmed = await confirmDialog({
    title: 'Delete Liability',
    message: 'Are you sure you want to remove this liability?',
    confirmVariant: 'danger',
  });
  if (!confirmed) return;
  try {
    const res = await fetch(`/api/liabilities/manual/${liabId}`, { method: 'DELETE' });
    if (res.ok) {
      await loadOverview();
      showToast('Liability removed.');
    }
  } catch (err) {
    console.error('Failed to delete liability:', err);
  }
}

let monthlySpendingChartInstance = null;

function renderCashflowAnalytics(data) {
  const analytics = data?.cashflow_analytics;
  const cb = data?.cashflow_breakdown;
  const summaryEl = document.getElementById('cashflow-period-summary');
  if (summaryEl && cb) {
    const p = cb.period || (typeof currentCashflowPeriod !== 'undefined' ? currentCashflowPeriod : 'all');
    const pName = p === 'year' ? 'Last 12 Months' : (p === 'month' ? 'Latest Month' : 'All Time');
    const range = (cb.period_start && cb.period_end) ? ` (${cb.period_start.slice(0, 7)} – ${cb.period_end.slice(0, 7)})` : '';
    summaryEl.textContent = cb.is_default_estimate
      ? 'Baseline estimate (import CSV statements for actuals)'
      : `${pName} — averaged across ${cb.months_analyzed || 1} month(s)${range}`;
    ['month', 'year', 'all'].forEach(mode => {
      const btn = document.getElementById(`btn-cf-period-${mode}`);
      if (btn) {
        btn.className = mode === p
          ? 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition'
          : 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
      }
    });
  }
  renderCashflowSankey(analytics?.sankey || null, cb || null);
  renderMonthlySpendingAndSavings(analytics || null);
}

function renderCashflowSankey(sankeyData, breakdown) {
  const container = document.getElementById('cashflow-sankey-container');
  if (!container) return;

  const income = sankeyData?.monthly_income || breakdown?.monthly_income || 0;
  const links = (sankeyData?.links || []).filter(l => (l.value || 0) > 0);

  if (income <= 0 && links.length === 0) {
    container.innerHTML = `<div class="text-xs text-slate-500 text-center py-6">Import a bank statement CSV above to visualize your Income → Investments &amp; Payments Sankey flow.</div>`;
    return;
  }

  const totalOut = links.reduce((s, l) => s + (l.value || 0), 0);
  const maxTotal = Math.max(income, totalOut, 1);

  const svgW = 540;
  const svgH = 220;
  const leftX = 20;
  const leftW = 18;
  const rightX = 340;
  const rightW = 16;
  const availH = 160;
  const startY = 30;

  const incBarH = Math.max(24, (income / maxTotal) * availH);
  const incY = startY + (availH - incBarH) / 2;

  let curLeftOffset = incY;
  const gap = links.length > 1 ? Math.min(12, 48 / (links.length - 1)) : 0;
  const totalBarsH = availH - gap * Math.max(0, links.length - 1);
  let curRightY = startY;

  let pathsHtml = '';
  let rightNodesHtml = '';

  links.forEach((link) => {
    const weight = (link.value || 0) / Math.max(totalOut, maxTotal);
    const barH = Math.max(10, weight * totalBarsH);
    const strokeW = Math.max(6, (link.value / maxTotal) * incBarH);

    const y1 = curLeftOffset + strokeW / 2;
    curLeftOffset += strokeW;

    const y2 = curRightY + barH / 2;
    const cX1 = leftX + leftW + (rightX - (leftX + leftW)) * 0.45;
    const cX2 = leftX + leftW + (rightX - (leftX + leftW)) * 0.55;
    const color = escapeHtml(link.color || '#3B82F6');
    const formattedVal = escapeHtml(I18N.formatCurrency(link.value, 'EUR'));
    const pct = income > 0 ? Math.round((link.value / income) * 100) : 0;

    pathsHtml += `
      <path d="M ${leftX + leftW} ${y1.toFixed(1)} C ${cX1.toFixed(1)} ${y1.toFixed(1)}, ${cX2.toFixed(1)} ${y2.toFixed(1)}, ${rightX} ${y2.toFixed(1)}"
            fill="none" stroke="${color}" stroke-width="${Math.max(4, strokeW).toFixed(1)}" stroke-opacity="0.45" />
    `;

    rightNodesHtml += `
      <rect x="${rightX}" y="${curRightY.toFixed(1)}" width="${rightW}" height="${barH.toFixed(1)}" rx="3" fill="${color}" />
      <text x="${rightX + rightW + 8}" y="${(curRightY + barH / 2 - 2).toFixed(1)}" fill="#f8fafc" font-size="11" font-weight="600">${escapeHtml(link.target)}</text>
      <text x="${rightX + rightW + 8}" y="${(curRightY + barH / 2 + 11).toFixed(1)}" fill="#94a3b8" font-size="10" font-family="monospace">${formattedVal}/mo (${pct}%)</text>
    `;

    curRightY += barH + gap;
  });

  const incFormatted = escapeHtml(I18N.formatCurrency(income, 'EUR'));

  container.innerHTML = `
    <svg viewBox="0 0 ${svgW} ${svgH}" class="w-full h-auto max-h-[230px]" role="img" aria-label="Monthly Cashflow Sankey Diagram">
      ${pathsHtml}
      <rect x="${leftX}" y="${incY.toFixed(1)}" width="${leftW}" height="${incBarH.toFixed(1)}" rx="4" fill="#10B981" />
      <text x="${leftX}" y="${Math.max(14, incY - 14).toFixed(1)}" fill="#f8fafc" font-size="11" font-weight="700">Monthly Income</text>
      <text x="${leftX}" y="${Math.max(25, incY - 3).toFixed(1)}" fill="#34d399" font-size="11" font-family="monospace" font-weight="600">${incFormatted}/mo</text>
      ${rightNodesHtml}
    </svg>
  `;
}

function renderMonthlySpendingAndSavings(analytics) {
  const oppContainer = document.getElementById('savings-opportunities-container');
  const canvas = document.getElementById('monthlySpendingChart');

  const monthlyData = analytics?.monthly_spending || [];
  const opportunities = analytics?.savings_opportunities || [];

  if (canvas && typeof Chart !== 'undefined') {
    const ctx = canvas.getContext('2d');
    if (monthlySpendingChartInstance) monthlySpendingChartInstance.destroy();

    if (monthlyData.length > 0) {
      const labels = monthlyData.map(m => m.month);
      const catColors = {
        MORTGAGE: '#6366F1',
        DEBT_REPAYMENT: '#F43F5E',
        UTILITIES: '#F59E0B',
        TAX: '#EF4444',
        INSURANCE: '#A855F7',
        GROCERIES: '#84CC16',
        LEISURE: '#EC4899',
        TRANSPORT: '#0EA5E9',
        SUBSCRIPTION: '#D946EF',
        LIVING_EXPENSES: '#F97316',
        OTHER: '#64748B',
      };

      const allCats = Array.from(
        new Set(monthlyData.flatMap(m => Object.keys(m.categories || {})))
      );

      const datasets = allCats.map(cat => ({
        label: cat,
        data: monthlyData.map(m => (m.categories && m.categories[cat]) ? m.categories[cat] : 0),
        backgroundColor: catColors[cat] || '#3B82F6',
        borderRadius: 3,
      }));

      monthlySpendingChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#94a3b8', boxWidth: 10, font: { size: 10 } } },
          },
          scales: {
            x: { stacked: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
            y: { stacked: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
          },
        },
      });
    }
  }

  if (!oppContainer) return;
  if (opportunities.length === 0) {
    oppContainer.innerHTML = `<div class="text-[11px] text-slate-500 italic">Categorize your monthly expenses (Leisure, Subscriptions, Groceries, Transport, Utilities) to unlock targeted savings recommendations.</div>`;
    return;
  }

  oppContainer.innerHTML = `
    <div class="text-[11px] font-semibold text-slate-300 pb-0.5">💡 Top Monthly Savings Opportunities:</div>
    ${opportunities.slice(0, 3).map(opp => `
      <div class="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px]">
        <div class="min-w-0 pr-2">
          <span class="font-semibold text-white">${escapeHtml(opp.label)}</span>
          <span class="text-slate-400 ml-1">(${escapeHtml(I18N.formatCurrency(opp.monthly_avg, 'EUR'))}/mo)</span>
          <div class="text-[10px] text-slate-400 truncate">${escapeHtml(opp.tip)}</div>
        </div>
        <div class="text-right shrink-0 font-mono">
          <div class="text-emerald-400 font-bold">+${escapeHtml(I18N.formatCurrency(opp.potential_monthly_savings, 'EUR'))}/mo</div>
          <div class="text-[9px] text-slate-500">${escapeHtml(I18N.formatCurrency(opp.annual_impact, 'EUR'))}/yr</div>
        </div>
      </div>
    `).join('')}
  `;
}
