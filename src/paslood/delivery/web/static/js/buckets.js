/**
 * Paslood — Strategic Buckets, Enhanced Allocation Visualizer & Holdings Mapping
 */

let currentAllocationVizMode = 'bullet';

function renderBucketColorPicker(selectedColor) {
  const container = document.getElementById('bucket-color-picker');
  if (!container) return;
  container.innerHTML = '';
  BUCKET_PALETTE.forEach(c => {
    const btn = document.createElement('button');
    btn.type = 'button';
    const isSelected = c.toLowerCase() === (selectedColor || '').toLowerCase();
    btn.className = `w-6 h-6 rounded-full transition-transform hover:scale-110 flex items-center justify-center ${isSelected ? 'ring-2 ring-white ring-offset-2 ring-offset-slate-900 scale-110' : 'opacity-80 hover:opacity-100'}`;
    btn.style.backgroundColor = c;
    btn.onclick = () => selectBucketColor(c);
    container.appendChild(btn);
  });
  document.getElementById('bucket-modal-color').value = selectedColor;
}

function selectBucketColor(color) {
  renderBucketColorPicker(color);
}

function getModalProjectedTotal() {
  const bucketId = document.getElementById('bucket-modal-id')?.value || '';
  const target = parseFloat(document.getElementById('bucket-modal-target')?.value) || 0;
  const includeInRebalancing = document.getElementById('bucket-modal-include-rebalancing')?.checked ?? true;
  const activeAllocs = (currentData?.allocations || []).filter(a => a.include_in_rebalancing !== false && a.bucket_id !== bucketId);
  const otherTotal = activeAllocs.reduce((sum, a) => sum + (parseFloat(a.target_weight_pct) || 0), 0);
  return includeInRebalancing ? (otherTotal + target) : otherTotal;
}

function updateModalProjectedTotal() {
  const hint = document.getElementById('bucket-modal-total-hint');
  if (!hint) return;
  const total = Math.round(getModalProjectedTotal() * 10) / 10;
  const isBalanced = Math.abs(total - 100) < 0.05;
  if (isBalanced) {
    hint.textContent = I18N.t('buckets.total_balanced', 'Balanced (100%)');
    hint.className = 'text-[11px] font-medium text-emerald-400';
  } else if (total > 100) {
    const diff = (total - 100).toFixed(1);
    hint.textContent = I18N.t('buckets.total_over', { total: total, diff: diff, _fallback: `${total}% (+${diff}% Over)` });
    hint.className = 'text-[11px] font-medium text-rose-400';
  } else {
    const diff = (100 - total).toFixed(1);
    hint.textContent = I18N.t('buckets.total_under', { total: total, diff: diff, _fallback: `${total}% (-${diff}% Under)` });
    hint.className = 'text-[11px] font-medium text-amber-400';
  }
}

function openAddBucketModal() {
  const titleElem = document.getElementById('bucket-modal-title');
  titleElem.textContent = I18N.t('modals.bucket_add_title', '🪣 Add Strategic Bucket');
  document.getElementById('bucket-modal-id').value = '';
  document.getElementById('bucket-modal-name').value = '';
  document.getElementById('bucket-modal-target').value = '10.0';
  document.getElementById('bucket-modal-tolerance').value = '3.0';
  document.getElementById('bucket-modal-desc').value = '';
  const rebCheck = document.getElementById('bucket-modal-include-rebalancing');
  rebCheck.checked = true;
  rebCheck.onchange = updateModalProjectedTotal;
  const netWorthCheck = document.getElementById('bucket-modal-include-net-worth');
  if (netWorthCheck) netWorthCheck.checked = true;
  document.getElementById('bucket-modal-delete-btn').classList.add('hidden');
  const nextColor = BUCKET_PALETTE[(currentData?.allocations?.length || 0) % BUCKET_PALETTE.length];
  selectBucketColor(nextColor);
  updateModalProjectedTotal();
  document.getElementById('bucket-modal').classList.remove('hidden');
}

function openEditBucketModal(bucketId, name, color, target, tolerance, desc, includeInRebalancing, includeInNetWorth = true) {
  const titleElem = document.getElementById('bucket-modal-title');
  titleElem.textContent = I18N.t('modals.bucket_edit_title', { name, _fallback: `✏️ Edit Bucket: ${name}` });
  document.getElementById('bucket-modal-id').value = bucketId;
  document.getElementById('bucket-modal-name').value = name;
  document.getElementById('bucket-modal-target').value = target;
  document.getElementById('bucket-modal-tolerance').value = tolerance || 3.0;
  document.getElementById('bucket-modal-desc').value = desc || '';
  const rebCheck = document.getElementById('bucket-modal-include-rebalancing');
  rebCheck.checked = includeInRebalancing !== false;
  rebCheck.onchange = updateModalProjectedTotal;
  const netWorthCheck = document.getElementById('bucket-modal-include-net-worth');
  if (netWorthCheck) netWorthCheck.checked = includeInNetWorth !== false;
  document.getElementById('bucket-modal-delete-btn').classList.remove('hidden');
  selectBucketColor(color || '#3B82F6');
  updateModalProjectedTotal();
  document.getElementById('bucket-modal').classList.remove('hidden');
}

function openEditBucketModalById(bucketId) {
  const a = (currentData?.allocations || []).find(b => b.bucket_id === bucketId);
  if (!a) return;
  openEditBucketModal(
    a.bucket_id,
    a.name,
    a.color,
    a.target_weight_pct,
    a.drift_tolerance_pct,
    a.description || '',
    a.include_in_rebalancing !== false,
    a.include_in_net_worth !== false
  );
}

function closeBucketModal() {
  document.getElementById('bucket-modal').classList.add('hidden');
}

async function saveBucketFromModal() {
  const bucketId = document.getElementById('bucket-modal-id').value.trim();
  const name = document.getElementById('bucket-modal-name').value.trim();
  const target = parseFloat(document.getElementById('bucket-modal-target').value) || 0;
  const tolerance = parseFloat(document.getElementById('bucket-modal-tolerance').value) || 3.0;
  const color = document.getElementById('bucket-modal-color').value;
  const desc = document.getElementById('bucket-modal-desc').value.trim();
  const includeInRebalancing = document.getElementById('bucket-modal-include-rebalancing').checked;
  const netWorthCheck = document.getElementById('bucket-modal-include-net-worth');
  const includeInNetWorth = netWorthCheck ? netWorthCheck.checked : true;

  if (!name) {
    alert('Please enter a bucket name.');
    return;
  }

  if (includeInRebalancing && (currentData?.allocations?.length || 0) > 0) {
    const projectedTotal = Math.round(getModalProjectedTotal() * 10) / 10;
    if (Math.abs(projectedTotal - 100) >= 0.05) {
      if (!confirm(`Warning: Active bucket weights will sum to ${projectedTotal}% (not 100%). Proceed anyway and adjust weights on the Buckets page?`)) {
        return;
      }
    }
  }

  const payload = {
    id: bucketId || undefined,
    name: name,
    target_weight_pct: target,
    drift_tolerance_pct: tolerance,
    color: color,
    description: desc,
    include_in_rebalancing: includeInRebalancing,
    include_in_net_worth: includeInNetWorth
  };

  try {
    const res = await fetch('/api/buckets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeBucketModal();
      await loadOverview();
      showToast(bucketId ? 'Bucket updated!' : 'New bucket added!');
    }
  } catch (err) {
    console.error('Failed to save bucket:', err);
  }
}

async function deleteBucket(bucketId, name) {
  if (!confirm(`Are you sure you want to delete the bucket "${name}"? Holdings mapped to this bucket will become unassigned.`)) return;
  try {
    const res = await fetch(`/api/buckets/${bucketId}`, { method: 'DELETE' });
    if (res.ok) {
      closeBucketModal();
      await loadOverview();
      showToast('Bucket removed.');
    }
  } catch (err) {
    console.error('Failed to delete bucket:', err);
  }
}

function deleteBucketById(bucketId) {
  const a = (currentData?.allocations || []).find(b => b.bucket_id === bucketId);
  const name = a ? a.name : bucketId;
  deleteBucket(bucketId, name);
}

function deleteCurrentBucket() {
  const bucketId = document.getElementById('bucket-modal-id').value;
  const name = document.getElementById('bucket-modal-name').value;
  if (bucketId) deleteBucket(bucketId, name);
}

function getActiveBucketInputsSum() {
  const inputs = document.querySelectorAll('.bucket-target-input');
  let total = 0;
  inputs.forEach(input => {
    total += parseFloat(input.value) || 0;
  });
  return Math.round(total * 10) / 10;
}

function updateBucketTotalBadge() {
  const badge = document.getElementById('bucket-total-badge');
  const saveBtn = document.getElementById('btn-save-bucket-targets');
  if (!badge) return;

  const total = getActiveBucketInputsSum();
  const isBalanced = Math.abs(total - 100) < 0.05;

  if (isBalanced) {
    badge.textContent = I18N.t('buckets.total_balanced', 'Balanced (100%)');
    badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  } else if (total > 100) {
    const diff = (total - 100).toFixed(1);
    badge.textContent = I18N.t('buckets.total_over', { total: total, diff: diff, _fallback: `${total}% (+${diff}% Over)` });
    badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30';
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
  } else {
    const diff = (100 - total).toFixed(1);
    badge.textContent = I18N.t('buckets.total_under', { total: total, diff: diff, _fallback: `${total}% (-${diff}% Under)` });
    badge.className = 'px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30';
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
  }
}

function onBucketTargetInput() {
  updateBucketTotalBadge();
}

async function saveBucketTargets() {
  const inputs = document.querySelectorAll('.bucket-target-input');
  const targets = {};
  let total = 0;
  inputs.forEach(input => {
    const bucketId = input.dataset.bucketId;
    const val = parseFloat(input.value) || 0;
    if (bucketId) {
      targets[bucketId] = val;
      total += val;
    }
  });

  total = Math.round(total * 10) / 10;
  if (Math.abs(total - 100) >= 0.05) {
    alert(I18N.t('buckets.targets_unbalanced_error', 'Target weights must sum to exactly 100% across active buckets.'));
    return;
  }

  try {
    const res = await fetch('/api/buckets/targets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ targets: targets })
    });
    if (res.ok) {
      await loadOverview();
      showToast(I18N.t('buckets.targets_saved', 'Bucket target weights saved successfully!'));
    } else {
      const err = await res.json();
      alert(err.detail || 'Failed to save targets');
    }
  } catch (err) {
    console.error('Failed to save bucket targets:', err);
  }
}

async function updateTarget(bucketId, val) {
  const a = (currentData?.allocations || []).find(b => b.bucket_id === bucketId);
  const name = a ? a.name : bucketId;
  try {
    const res = await fetch('/api/buckets/target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bucket_id: bucketId, name: name, target_weight_pct: parseFloat(val) })
    });
    if (res.ok) {
      await loadOverview();
    } else {
      const err = await res.json();
      alert(err.detail || 'Failed to update target');
      await loadOverview();
    }
  } catch (err) {
    console.error('Failed to update bucket:', err);
  }
}

function renderBuckets(data) {
  const tbody = document.getElementById('buckets-table-body');
  tbody.innerHTML = '';
  const meters = document.getElementById('bucket-meters-container');
  meters.innerHTML = '';

  data.allocations.forEach(a => {
    const tr = document.createElement('tr');
    const isExcluded = a.include_in_rebalancing === false;
    const isNetWorthExcluded = a.include_in_net_worth === false;
    const excludedBadge = isExcluded ? `<span class="text-[10px] bg-slate-800 text-slate-400 border border-slate-700 px-1.5 py-0.5 rounded font-normal ml-1">${escapeHtml(I18N.t('buckets.badge_no_rebalance', 'No Rebalance'))}</span>` : '';
    const nwExcludedBadge = isNetWorthExcluded ? `<span class="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-normal ml-1">${escapeHtml(I18N.t('buckets.badge_illiquid', 'Illiquid / Prop'))}</span>` : '';
    const statusBadge = isExcluded
      ? `<span class="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-400 border border-slate-700">${escapeHtml(I18N.t('buckets.status_excluded', 'Excluded'))}</span>`
      : (a.drift_status === 'BALANCED'
        ? `<span class="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">${escapeHtml(I18N.t('buckets.status_balanced', 'Balanced'))}</span>`
        : (a.drift_status === 'UNDERWEIGHT'
          ? `<span class="px-2 py-0.5 rounded text-xs bg-blue-500/20 text-blue-400">${escapeHtml(I18N.t('buckets.status_underweight', 'Underweight'))}</span>`
          : `<span class="px-2 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400">${escapeHtml(I18N.t('buckets.status_overweight', 'Overweight'))}</span>`));
    const diffDisplay = isExcluded ? '—' : `${a.diff_value > 0 ? '+' : ''}${I18N.formatCurrency(a.diff_value, 'EUR')}`;
    const weightDisplay = isExcluded ? '—' : I18N.formatPercent(a.current_weight_pct);
    const targetDisplay = isExcluded ? '—' : `<span class="inline-flex items-center gap-1 whitespace-nowrap"><input type="number" step="0.5" min="0" max="100" value="${a.target_weight_pct}" data-bucket-id="${escapeHtml(a.bucket_id)}" oninput="onBucketTargetInput()" class="bucket-target-input w-16 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white font-mono"><span>%</span></span>`;

    tr.innerHTML = `
      <td class="px-4 py-3 font-medium flex items-center gap-2">
        <span class="w-3 h-3 rounded-full inline-block shadow-sm shrink-0" style="background-color: ${escapeHtml(a.color)}"></span>
        <span class="text-white font-semibold">${escapeHtml(a.name)}</span>
        ${excludedBadge}
        ${nwExcludedBadge}
      </td>
      <td class="px-4 py-3 font-mono whitespace-nowrap">${I18N.formatCurrency(a.current_value, 'EUR')}</td>
      <td class="px-4 py-3 font-semibold font-mono whitespace-nowrap">${weightDisplay}</td>
      <td class="px-4 py-3 whitespace-nowrap">${targetDisplay}</td>
      <td class="px-4 py-3 font-mono whitespace-nowrap ${a.diff_value < 0 ? 'text-blue-400' : 'text-amber-400'}">
        ${diffDisplay}
      </td>
      <td class="px-4 py-3 whitespace-nowrap">${statusBadge}</td>
      <td class="px-4 py-3 text-right whitespace-nowrap">
        <button onclick="openEditBucketModalById('${escapeHtml(a.bucket_id)}')" class="text-xs text-blue-400 hover:text-blue-300 font-medium px-2 py-0.5 rounded hover:bg-blue-500/10 mr-1.5">${escapeHtml(I18N.t('buckets.btn_edit_rename', 'Edit / Rename'))}</button>
        <button onclick="deleteBucketById('${escapeHtml(a.bucket_id)}')" class="text-xs text-rose-400 hover:text-rose-300 font-medium px-2 py-0.5 rounded hover:bg-rose-500/10">${escapeHtml(I18N.t('buckets.btn_delete', 'Delete'))}</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  const activeAllocs = (data.allocations || []).filter(a => a.include_in_rebalancing !== false);
  const excludedAllocs = (data.allocations || []).filter(a => a.include_in_rebalancing === false);

  renderBulletMeters(activeAllocs, meters);
  const driftContainer = document.getElementById('bucket-drift-container');
  if (driftContainer) renderDriftChart(activeAllocs, driftContainer);
  renderExcludedBuckets(excludedAllocs);
  updateBucketTotalBadge();
}

function setAllocationVizMode(mode) {
  currentAllocationVizMode = mode;
  const btnBullet = document.getElementById('btn-alloc-mode-bullet');
  const btnDrift = document.getElementById('btn-alloc-mode-drift');
  const containerBullet = document.getElementById('bucket-meters-container');
  const containerDrift = document.getElementById('bucket-drift-container');

  if (mode === 'bullet') {
    if (btnBullet) {
      btnBullet.className = 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition';
    }
    if (btnDrift) {
      btnDrift.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
    }
    if (containerBullet) containerBullet.classList.remove('hidden');
    if (containerDrift) containerDrift.classList.add('hidden');
  } else {
    if (btnBullet) {
      btnBullet.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
    }
    if (btnDrift) {
      btnDrift.className = 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition';
    }
    if (containerBullet) containerBullet.classList.add('hidden');
    if (containerDrift) containerDrift.classList.remove('hidden');
  }
}

function renderBulletMeters(activeAllocs, container) {
  if (!container) return;
  container.innerHTML = '';
  if (!activeAllocs.length) {
    container.innerHTML = `<div class="text-xs text-slate-500 py-3 text-center">No rebalanceable buckets configured.</div>`;
    return;
  }

  activeAllocs.forEach(a => {
    const target = a.target_weight_pct;
    const tol = a.drift_tolerance_pct || 2.0;
    const lower = Math.max(0, target - tol);
    const upper = Math.min(100, target + tol);
    const curr = a.current_weight_pct;
    const status = a.drift_status;

    let statusBadge = '';
    let statusActionText = '';
    if (status === 'BALANCED') {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold whitespace-nowrap">✓ ${escapeHtml(I18N.t('buckets.status_balanced', 'In Balance'))}</span>`;
      statusActionText = I18N.t('buckets.rebalance_action_balanced', 'In Balance (Within safe tolerance corridor)');
    } else if (status === 'OVERWEIGHT') {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold whitespace-nowrap">▲ ${escapeHtml(I18N.t('buckets.status_overweight', 'Overweight'))} (+${I18N.formatPercent(a.diff_weight_pct)})</span>`;
      statusActionText = I18N.t('buckets.rebalance_action_overweight', { diff_pct: '+' + I18N.formatPercent(a.diff_weight_pct), _fallback: `Overweight (+${I18N.formatPercent(a.diff_weight_pct)} above target) — Pause contributions or trim` });
    } else {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-blue-500/20 text-blue-400 border border-blue-500/30 font-semibold whitespace-nowrap">▼ ${escapeHtml(I18N.t('buckets.status_underweight', 'Underweight'))} (${I18N.formatPercent(a.diff_weight_pct)})</span>`;
      statusActionText = I18N.t('buckets.rebalance_action_underweight', { diff_pct: I18N.formatPercent(a.diff_weight_pct), _fallback: `Underweight (${I18N.formatPercent(a.diff_weight_pct)} below target) — Priority for cash contributions` });
    }

    const diffMoney = `${a.diff_value > 0 ? '+' : ''}${I18N.formatCurrency(a.diff_value, 'EUR')}`;
    const diffMoneyClass = a.diff_value < 0 ? 'text-blue-400' : (a.diff_value > 0 ? 'text-amber-400' : 'text-slate-400');

    const card = document.createElement('div');
    card.className = 'p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2';

    card.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-1.5">
        <div class="flex items-center gap-2 min-w-0">
          <span class="w-3 h-3 rounded-full shrink-0 shadow-sm" style="background-color: ${escapeHtml(a.color)}"></span>
          <span class="font-bold text-white text-sm truncate">${escapeHtml(a.name)}</span>
          <span class="text-slate-400 font-mono text-xs whitespace-nowrap">(${I18N.formatCurrency(a.current_value, 'EUR')})</span>
        </div>
        <div class="flex items-center gap-2 font-mono flex-wrap shrink-0">
          <span class="text-white font-bold text-xs">${I18N.formatPercent(curr)}</span>
          <span class="text-slate-500">/</span>
          <span class="text-slate-400 text-xs">${escapeHtml(I18N.t('buckets.th_target_weight', 'Target'))}: <span class="text-slate-200 font-medium">${I18N.formatPercent(target)}</span></span>
          <span class="text-slate-500 text-[11px] font-sans">(±${I18N.formatPercent(tol)})</span>
          <span class="font-mono text-xs ${diffMoneyClass} font-semibold ml-1">[${escapeHtml(diffMoney)}]</span>
          ${statusBadge}
        </div>
      </div>

      <!-- Bullet Track -->
      <div class="relative w-full h-5 bg-slate-900 rounded-lg border border-slate-800 overflow-visible">
        <!-- Shaded Tolerance Corridor -->
        <div class="tolerance-zone absolute top-0 bottom-0 bg-emerald-500/15 border-x border-emerald-500/40 z-0 transition-all"
             style="left: ${lower}%; width: ${Math.max(1, upper - lower)}%;"
             title="${escapeHtml(I18N.t('buckets.tolerance_corridor', { lower: I18N.formatPercent(lower), upper: I18N.formatPercent(upper), _fallback: `Tolerance Corridor (${I18N.formatPercent(lower)} – ${I18N.formatPercent(upper)})` }))}">
        </div>

        <!-- Current Weight Fill Bar -->
        <div class="absolute top-0 bottom-0 left-0 rounded-l-lg transition-all duration-500 shadow-sm z-10 flex items-center justify-end pr-1.5 opacity-90"
             style="width: ${Math.min(100, Math.max(0, curr))}%; background-color: ${escapeHtml(a.color)};">
        </div>

        <!-- Crisp Target Pin Marker -->
        <div class="target-pin absolute -top-1 bottom-0 z-20"
             style="left: ${target}%; width: 2px; height: calc(100% + 8px); background-color: #ffffff; box-shadow: 0 0 6px rgba(255, 255, 255, 0.9);"
             title="${escapeHtml(I18N.t('buckets.th_target_weight', 'Target'))}: ${I18N.formatPercent(target)}">
          <div class="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-white rotate-45 shadow"></div>
        </div>
      </div>

      <!-- Legend / Action Guidance -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-400 gap-1 pt-0.5">
        <div class="flex items-center gap-2">
          <span class="flex items-center gap-1"><span class="w-2 h-2 bg-white rounded-full inline-block"></span> ${escapeHtml(I18N.t('buckets.th_target_weight', 'Target'))}: ${I18N.formatPercent(target)}</span>
          <span class="text-slate-600">•</span>
          <span class="flex items-center gap-1 text-emerald-400/90"><span class="w-2.5 h-1.5 bg-emerald-500/30 border border-emerald-500/60 rounded-sm inline-block"></span> Band: ${I18N.formatPercent(lower)} – ${I18N.formatPercent(upper)}</span>
        </div>
        <div class="text-right sm:text-left text-slate-300 font-medium">${escapeHtml(statusActionText)}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderDriftChart(activeAllocs, container) {
  if (!container) return;
  container.innerHTML = '';
  if (!activeAllocs.length) {
    container.innerHTML = `<div class="text-xs text-slate-500 py-3 text-center">No rebalanceable buckets configured.</div>`;
    return;
  }

  const maxDriftAbs = Math.max(8, ...activeAllocs.map(a => Math.abs(a.diff_weight_pct || 0)));
  const scaleLimit = Math.ceil(maxDriftAbs * 1.25);

  const headerGuide = document.createElement('div');
  headerGuide.className = 'grid grid-cols-12 text-[11px] text-slate-400 px-2 pb-1 border-b border-slate-800 font-mono';
  headerGuide.innerHTML = `
    <div class="col-span-4 sm:col-span-3 text-slate-300 font-semibold font-sans">${escapeHtml(I18N.t('buckets.th_bucket', 'Bucket'))}</div>
    <div class="col-span-5 sm:col-span-6 relative flex justify-between text-[10px] text-slate-500">
      <span>-${scaleLimit}%</span>
      <span class="text-emerald-400 font-bold">0% (${escapeHtml(I18N.t('buckets.status_balanced', 'Target'))})</span>
      <span>+${scaleLimit}%</span>
    </div>
    <div class="col-span-3 text-right text-slate-300 font-semibold font-sans">${escapeHtml(I18N.t('buckets.th_diff', 'Diff & Action'))}</div>
  `;
  container.appendChild(headerGuide);

  activeAllocs.forEach(a => {
    const diffPct = a.diff_weight_pct;
    const diffVal = a.diff_value;
    const tol = a.drift_tolerance_pct || 2.0;
    const status = a.drift_status;

    const pctClamped = Math.max(-scaleLimit, Math.min(scaleLimit, diffPct));
    const barWidthPct = (Math.abs(pctClamped) / scaleLimit) * 50;
    const barLeftPct = pctClamped >= 0 ? 50 : 50 - barWidthPct;
    const tolWidthPct = (tol / scaleLimit) * 50;

    let barColor = 'bg-emerald-500';
    let badgeColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    let actionTip = I18N.t('buckets.status_balanced', 'In Balance');
    if (status === 'OVERWEIGHT') {
      barColor = 'bg-amber-500';
      badgeColor = 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      actionTip = 'Trim / Pause';
    } else if (status === 'UNDERWEIGHT') {
      barColor = 'bg-blue-500';
      badgeColor = 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      actionTip = 'Buy Priority';
    }

    const diffFormatted = `${diffVal > 0 ? '+' : ''}${I18N.formatCurrency(diffVal, 'EUR')}`;
    const pctFormatted = `${diffPct > 0 ? '+' : ''}${I18N.formatPercent(diffPct)}`;

    const row = document.createElement('div');
    row.className = 'grid grid-cols-12 items-center gap-2 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs hover:border-slate-700 transition';

    row.innerHTML = `
      <!-- Name & color dot -->
      <div class="col-span-4 sm:col-span-3 flex items-center gap-2 min-w-0">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${escapeHtml(a.color)}"></span>
        <div class="truncate">
          <div class="font-bold text-white truncate">${escapeHtml(a.name)}</div>
          <div class="text-[10px] text-slate-400 font-mono">${I18N.formatPercent(a.current_weight_pct)} <span class="text-slate-600">/</span> ${I18N.formatPercent(a.target_weight_pct)}</div>
        </div>
      </div>

      <!-- Centered Divergence Bar Track -->
      <div class="col-span-5 sm:col-span-6 relative h-6 bg-slate-900 rounded-md border border-slate-800 overflow-hidden">
        <!-- Center zero line -->
        <div class="absolute top-0 bottom-0 left-1/2 w-px bg-slate-600 z-20"></div>

        <!-- Tolerance Corridor around zero -->
        <div class="tolerance-zone absolute top-0 bottom-0 bg-emerald-500/15 border-x border-emerald-500/30 z-0"
             style="left: ${50 - tolWidthPct}%; width: ${tolWidthPct * 2}%;">
        </div>

        <!-- Diverging Bar -->
        <div class="absolute top-1 bottom-1 ${barColor} rounded transition-all duration-500 shadow-sm z-10 opacity-90"
             style="left: ${barLeftPct}%; width: ${Math.max(1.5, barWidthPct)}%;">
        </div>
      </div>

      <!-- Values & Action -->
      <div class="col-span-3 text-right">
        <div class="font-mono font-bold text-xs ${diffPct < 0 ? 'text-blue-400' : (diffPct > 0 ? 'text-amber-400' : 'text-emerald-400')}">
          ${escapeHtml(pctFormatted)}
        </div>
        <div class="flex items-center justify-end gap-1 text-[10px]">
          <span class="font-mono text-slate-400 hidden sm:inline">${escapeHtml(diffFormatted)}</span>
          <span class="px-1.5 py-0.5 rounded text-[9px] font-semibold border ${badgeColor}">${escapeHtml(actionTip)}</span>
        </div>
      </div>
    `;
    container.appendChild(row);
  });
}

function renderExcludedBuckets(excludedAllocs) {
  const section = document.getElementById('bucket-excluded-section');
  const list = document.getElementById('bucket-excluded-list');
  const totalSpan = document.getElementById('excluded-buckets-total');
  if (!section || !list) return;

  if (!excludedAllocs || !excludedAllocs.length) {
    section.classList.add('hidden');
    list.innerHTML = '';
    return;
  }

  section.classList.remove('hidden');
  list.innerHTML = '';
  const totalVal = excludedAllocs.reduce((sum, a) => sum + (a.current_value || 0), 0);
  if (totalSpan) totalSpan.textContent = `Totaal: ${I18N.formatCurrency(totalVal, 'EUR')}`;

  excludedAllocs.forEach(a => {
    const item = document.createElement('div');
    item.className = 'flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800 text-xs';
    item.innerHTML = `
      <div class="flex items-center gap-2 min-w-0">
        <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${escapeHtml(a.color)}"></span>
        <span class="text-slate-300 font-medium truncate">${escapeHtml(a.name)}</span>
        <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 whitespace-nowrap">${escapeHtml(I18N.t('buckets.status_excluded', 'Excluded'))}</span>
      </div>
      <div class="font-mono font-semibold text-slate-200 whitespace-nowrap">${I18N.formatCurrency(a.current_value, 'EUR')}</div>
    `;
    list.appendChild(item);
  });
}

// Holdings & Bucket Assignment
function renderHoldingsMapping(data) {
  const tbody = document.getElementById('holdings-mapping-tbody');
  const countBadge = document.getElementById('holdings-count-badge');
  if (!tbody) return;
  tbody.innerHTML = '';
  const allAssets = data.assets || [];

  const nonZeroAssets = allAssets.filter(a => a.current_value > 0);
  if (countBadge) countBadge.textContent = I18N.t('buckets.active_holdings_badge', { count: nonZeroAssets.length, _fallback: `${nonZeroAssets.length} Active Holdings` });

  if (nonZeroAssets.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-6 text-slate-500 text-center">${escapeHtml(I18N.t('buckets.empty_holdings', 'No active holdings with positive value found. Connect PDT in Settings or import a CSV statement.'))}</td></tr>`;
    return;
  }

  const buckets = data.allocations || [];
  const unassignedOptLabel = escapeHtml(I18N.t('buckets.unassigned_option', '-- Unassigned --'));
  const unassignedBadgeLabel = escapeHtml(I18N.t('buckets.unassigned_badge', 'Unassigned'));

  nonZeroAssets.forEach(a => {
    const tr = document.createElement('tr');
    let bucketOptions = `<option value="unassigned" ${a.bucket_id === 'unassigned' ? 'selected' : ''}>${unassignedOptLabel}</option>`;
    buckets.forEach(b => {
      const isSelected = a.bucket_id === b.bucket_id;
      bucketOptions += `<option value="${escapeHtml(b.bucket_id)}" ${isSelected ? 'selected' : ''}>${escapeHtml(b.name)}</option>`;
    });

    const safeColor = escapeHtml(a.bucket_color);
    const safeBucketName = escapeHtml(a.bucket_name);
    const badgeHtml = a.bucket_id !== 'unassigned' ? `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold border shadow-sm" style="background-color: ${safeColor}22; color: ${safeColor}; border-color: ${safeColor}55;">
        <span class="w-2 h-2 rounded-full inline-block shadow-sm" style="background-color: ${safeColor};"></span>
        ${safeBucketName}
      </span>
    ` : `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
        <span class="w-1.5 h-1.5 rounded-full bg-slate-500 inline-block"></span>
        ${unassignedBadgeLabel}
      </span>
    `;

    const safeId = escapeHtml(a.id);
    tr.innerHTML = `
      <td class="px-3 py-2.5 font-medium text-white">${escapeHtml(a.name)}</td>
      <td class="px-3 py-2.5 font-mono text-slate-400 whitespace-nowrap">${escapeHtml(a.symbol || a.isin || '—')}</td>
      <td class="px-3 py-2.5 text-slate-400 whitespace-nowrap">${escapeHtml(a.institution)}</td>
      <td class="px-3 py-2.5 font-mono font-semibold text-slate-200 whitespace-nowrap">${escapeHtml(I18N.formatCurrency(a.current_value, a.currency || 'EUR'))}</td>
      <td class="px-3 py-2.5 whitespace-nowrap">
        ${badgeHtml}
      </td>
      <td class="px-3 py-2.5 whitespace-nowrap">
        <select class="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-white text-xs focus:border-blue-500" onchange="assignAssetToBucketById('${safeId}', this.value)">
          ${bucketOptions}
        </select>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function assignAssetToBucketById(assetId, bucketId) {
  const a = (currentData?.assets || []).find(x => x.id === assetId);
  if (a) {
    assignAssetToBucket(a.id, a.symbol, a.isin, a.name, bucketId);
  }
}

async function assignAssetToBucket(assetId, symbol, isin, name, bucketId) {
  try {
    const res = await fetch('/api/buckets/assign-asset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bucket_id: bucketId,
        symbol: symbol || null,
        isin: isin || null,
        asset_id: assetId || null,
        asset_name: name || null
      })
    });
    if (res.ok) {
      await loadOverview();
      showToast('Holding successfully re-mapped to bucket!');
    }
  } catch (err) {
    console.error('Failed to assign holding to bucket:', err);
  }
}
