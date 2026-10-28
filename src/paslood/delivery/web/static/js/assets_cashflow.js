/**
 * Paslood — Manual Assets & Liabilities, CSV Statement Ingestion & Transaction Rebucketing
 */

function renderTransactions(data) {
  const tbody = document.getElementById('tx-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  const txs = data.transactions || [];
  const badge = document.getElementById('tx-count-badge');
  if (badge) {
    badge.textContent = I18N.t('cashflow.tx_count_badge', { count: txs.length, _fallback: `${txs.length} Transactions` });
  }

  if (txs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="px-3 py-6 text-center text-slate-500">${escapeHtml(I18N.t('cashflow.empty_tx', 'No transactions loaded yet. Upload your KBC CSV above.'))}</td></tr>`;
    return;
  }

  txs.slice(0, 100).forEach(tx => {
    const tr = document.createElement('tr');
    const isPositive = tx.amount_value > 0;
    const safeDesc = escapeHtml(tx.description);
    const safeCounterparty = escapeHtml(tx.counterparty_name || '-');
    const safeDate = escapeHtml(I18N.formatDate(tx.date));
    const numAmt = tx.amount_value !== undefined ? Math.abs(tx.amount_value) : tx.amount_formatted;
    const safeAmount = escapeHtml(I18N.formatCurrency(numAmt, 'EUR'));
    const safeCat = escapeHtml(tx.category);
    const safeId = escapeHtml(tx.id);

    tr.innerHTML = `
      <td class="px-3 py-2 text-slate-400 whitespace-nowrap">${safeDate}</td>
      <td class="px-3 py-2 font-medium text-white max-w-xs truncate" title="${safeDesc}">${safeDesc}</td>
      <td class="px-3 py-2 text-slate-400 truncate max-w-[140px]">${safeCounterparty}</td>
      <td class="px-3 py-2 text-right font-mono font-semibold whitespace-nowrap ${isPositive ? 'text-emerald-400' : 'text-slate-200'}">
        ${isPositive ? '+' : ''}${safeAmount}
      </td>
      <td class="px-3 py-2">
        <button onclick="openRebucketModalById('${safeId}')" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-blue-400 text-xs border border-slate-700">
          ${safeCat} ▾
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
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
  } else {
    status.className = 'text-xs py-2 px-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30';
    status.textContent = `Upload failed: ${errors.join('; ')}`;
    showToast(`Upload failed: ${errors.join('; ')}`, 'error');
  }
}

// Re-Bucketing Modal
function openRebucketModalById(txId) {
  const tx = (currentData?.transactions || []).find(t => t.id === txId);
  if (tx) {
    openRebucketModal(tx.id, tx.description, tx.counterparty_name, tx.category);
  }
}

function openRebucketModal(txId, desc, counterparty, currentCat) {
  activeRebucketTx = { id: txId, description: desc, counterparty: counterparty };
  document.getElementById('rebucket-tx-info').innerHTML = `
    <div class="font-semibold text-white">${escapeHtml(desc)}</div>
    <div class="text-slate-400 mt-0.5">Counterparty: ${escapeHtml(counterparty || 'N/A')}</div>
  `;
  document.getElementById('modal-category-select').value = currentCat || 'OTHER';

  const defaultPattern = counterparty || desc.split(/[\s-]/)[0] || '';
  const patternInput = document.getElementById('modal-pattern-input');
  if (patternInput) {
    patternInput.value = defaultPattern;
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
  const patternVal = document.getElementById('modal-pattern-input')?.value || activeRebucketTx.counterparty || '';

  try {
    const res = await fetch('/api/transactions/rebucket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transaction_id: activeRebucketTx.id,
        target_category: targetCat,
        counterparty_name: activeRebucketTx.counterparty,
        pattern: patternVal,
        remember_rule: remember
      })
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
        tr.innerHTML = `
          <td class="py-2.5 font-medium text-white">${safeName}</td>
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
  } else {
    if (title) title.textContent = '🏠 Add Real Estate or Asset';
    document.getElementById('manual-asset-id').value = '';
    document.getElementById('manual-asset-name').value = '';
    document.getElementById('manual-asset-class').value = 'REAL_ESTATE';
    document.getElementById('manual-asset-val').value = '';
    document.getElementById('manual-asset-inst').value = '';
    document.getElementById('manual-asset-sym').value = '';
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
      symbol: sym || null
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
