/**
 * Paslood — Dashboard KPIs, Charts & Financial Independence Milestones
 */

function renderDashboard(data) {
  const nw = data.net_worth_value !== undefined ? data.net_worth_value : data.net_worth;
  const ta = data.total_assets_value !== undefined ? data.total_assets_value : data.total_assets;
  const tl = data.total_liabilities_value !== undefined ? data.total_liabilities_value : data.total_liabilities;
  const fc = data.free_cashflow_value !== undefined ? data.free_cashflow_value : (data.free_monthly_cashflow || 0);

  document.getElementById('kpi-net-worth').textContent = I18N.formatCurrency(nw, 'EUR');
  document.getElementById('kpi-total-assets').textContent = I18N.formatCurrency(ta, 'EUR');
  document.getElementById('kpi-total-debts').textContent = I18N.formatCurrency(tl, 'EUR');
  document.getElementById('kpi-surplus').textContent = I18N.formatCurrency(fc, 'EUR');
  document.getElementById('kpi-debt-ratio').textContent = I18N.t('dashboard.debt_ratio', { ratio: I18N.formatNumber(data.debt_to_asset_ratio, 1), _fallback: `Debt ratio: ${I18N.formatPercent(data.debt_to_asset_ratio, 1)}` });
  document.getElementById('kpi-savings-rate').textContent = I18N.t('dashboard.savings_rate', { rate: I18N.formatNumber(data.savings_rate_pct, 1), _fallback: `Savings rate: ${I18N.formatPercent(data.savings_rate_pct, 1)}` });
  document.getElementById('kpi-asset-count').textContent = data.exclude_property
    ? I18N.t('dashboard.liquid_assets_count', { count: data.asset_count, _fallback: `Liquid assets (${data.asset_count} total in portfolio)` })
    : I18N.t('dashboard.across_assets_count', { count: data.asset_count, _fallback: `Across ${data.asset_count} assets & cash` });

  renderDonutChart(data.allocations || []);
  renderProjectionChart(data.trajectory || []);

  // All active recommendations (synchronized badge count & list)
  const adviceContainer = document.getElementById('dashboard-advice-list');
  adviceContainer.innerHTML = '';
  const advices = data.advices || [];
  advices.forEach(rawAdv => {
    const adv = I18N.localizeAdvice(rawAdv);
    const item = document.createElement('div');
    item.className = 'p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs flex items-start gap-2.5';
    const badgeColor = adv.priority === 'CRITICAL'
      ? 'bg-red-500/20 text-red-400 border-red-500/30'
      : (adv.priority === 'HIGH'
        ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
        : 'bg-blue-500/20 text-blue-400 border-blue-500/30');
    item.innerHTML = `
      <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase border shrink-0 ${badgeColor}">${escapeHtml(adv.priorityLabel || adv.priority)}</span>
      <div class="min-w-0">
        <div class="font-semibold text-white">${escapeHtml(adv.title)}</div>
        <div class="text-slate-400 mt-0.5 leading-relaxed">${escapeHtml(adv.message)}</div>
      </div>
    `;
    adviceContainer.appendChild(item);
  });
  document.getElementById('advice-count-badge').textContent = advices.length === 1
    ? I18N.t('dashboard.recommendation_count_one', { count: 1, _fallback: '1 Recommendation' })
    : I18N.t('dashboard.recommendation_count_many', { count: advices.length, _fallback: `${advices.length} Recommendations` });
}

function renderDonutChart(allocations) {
  const canvas = document.getElementById('allocationDonutChart');
  if (canvas && typeof Chart !== 'undefined') {
    const ctx = canvas.getContext('2d');
    if (donutChartInstance) donutChartInstance.destroy();

    const labels = allocations.map(a => a.name);
    const values = allocations.map(a => a.current_value);
    const colors = allocations.map(a => a.color || '#3B82F6');

    donutChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: '#0f172a',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(c) {
                return ` ${c.label}: ${I18N.formatCurrency(c.raw, 'EUR')}`;
              }
            }
          }
        },
        cutout: '68%'
      }
    });
  }

  // Legend
  const legendContainer = document.getElementById('donut-legend');
  if (!legendContainer) return;
  legendContainer.innerHTML = '';
  const tgtShort = I18N.t('dashboard.tgt_short', 'tgt');
  allocations.forEach(a => {
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between';
    row.innerHTML = `
      <div class="flex items-center gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${escapeHtml(a.color)}"></span>
        <span class="text-slate-300">${escapeHtml(a.name)}</span>
      </div>
      <div class="font-medium text-white">${I18N.formatPercent(a.current_weight_pct)} <span class="text-slate-500 font-normal">(${escapeHtml(tgtShort)} ${I18N.formatPercent(a.target_weight_pct)})</span></div>
    `;
    legendContainer.appendChild(row);
  });
}

function renderProjectionChart(trajectory) {
  const canvas = document.getElementById('projectionAreaChart');
  if (!canvas || typeof Chart === 'undefined') return;
  const ctx = canvas.getContext('2d');
  if (projectionChartInstance) projectionChartInstance.destroy();

  const labels = trajectory.map(t => I18N.t('dashboard.year_label', { year: t.year, _fallback: `Year ${t.year}` }));
  const netWorthData = trajectory.map(t => t.net_worth);
  const assetsData = trajectory.map(t => t.assets);
  const debtsData = trajectory.map(t => t.debts);

  projectionChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: I18N.t('dashboard.chart_label_net_worth', 'Net Worth'),
          data: netWorthData,
          borderColor: '#10B981',
          backgroundColor: 'rgba(16, 185, 129, 0.15)',
          fill: true,
          tension: 0.3
        },
        {
          label: I18N.t('dashboard.chart_label_assets', 'Assets'),
          data: assetsData,
          borderColor: '#3B82F6',
          borderDash: [5, 5],
          tension: 0.3
        },
        {
          label: I18N.t('dashboard.chart_label_debts', 'Debts'),
          data: debtsData,
          borderColor: '#EF4444',
          borderDash: [2, 2],
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: function(c) {
              return ` ${c.dataset.label}: ${I18N.formatCurrency(c.raw, 'EUR', 0)}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: '#1e293b' }, ticks: { color: '#64748b' } },
        y: { grid: { color: '#1e293b' }, ticks: { color: '#64748b', callback: v => `€ ${v/1000}k` } }
      }
    }
  });
}

function setProjectionTimeframe(years) {
  currentProjectionYears = years;
  [5, 10, 20, 30].forEach(y => {
    const btn = document.getElementById(`btn-timeframe-${y}`);
    if (btn) {
      if (y === years) {
        btn.className = 'px-2.5 py-1 rounded bg-blue-600 text-white font-medium transition';
      } else {
        btn.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white transition';
      }
    }
  });
  updateProjectionChart();
}

async function updateProjectionChart() {
  const cagrInput = document.getElementById('projection-cagr-input');
  if (cagrInput) {
    currentProjectionCagr = parseFloat(cagrInput.value) || 7.0;
  }
  try {
    const res = await fetch(`/api/projection?years=${currentProjectionYears}&cagr=${currentProjectionCagr}&exclude_property=${excludePropertyState ? 'true' : 'false'}`);
    if (!res.ok) return;
    const data = await res.json();
    renderProjectionChart(data.trajectory);
  } catch (err) {
    console.error('Failed to update projection chart:', err);
  }
}

// Milestones Management
function renderMilestones(milestones) {
  const container = document.getElementById('milestones-container');
  if (!container) return;
  container.innerHTML = '';
  let reachedCount = 0;
  const reachedLabel = I18N.t('dashboard.milestone_reached', '✓ Reached');

  milestones.forEach(m => {
    if (m.is_reached) reachedCount++;
    const card = document.createElement('div');
    card.className = `p-3.5 rounded-xl border ${m.is_reached ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-slate-950 border-slate-800'} flex flex-col justify-between space-y-2`;
    card.innerHTML = `
      <div class="flex items-center justify-between gap-1.5 min-w-0">
        <span class="text-xs font-semibold text-white truncate min-w-0 flex-1" title="${escapeHtml(m.name)}">${escapeHtml(m.name)}</span>
        ${m.is_reached ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 whitespace-nowrap shrink-0">${escapeHtml(reachedLabel)}</span>` : `<span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono whitespace-nowrap shrink-0">${I18N.formatPercent(m.progress_pct, 1)}</span>`}
      </div>
      <div class="text-base font-bold text-white font-mono whitespace-nowrap">${escapeHtml(I18N.formatCurrency(m.target_amount, m.currency || 'EUR'))}</div>
      <div class="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
        <div class="h-full ${m.is_reached ? 'bg-emerald-500' : 'bg-blue-600'}" style="width: ${m.progress_pct}%"></div>
      </div>
    `;
    container.appendChild(card);
  });

  const badge = document.getElementById('milestones-completed-badge');
  if (badge) {
    badge.textContent = I18N.t('dashboard.milestones_reached_badge', { reached: reachedCount, total: milestones.length, _fallback: `${reachedCount} / ${milestones.length} Reached` });
    if (reachedCount > 0) {
      badge.className = 'px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-medium';
    } else {
      badge.className = 'px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 font-medium';
    }
  }
}

function openMilestonesModal() {
  const container = document.getElementById('modal-milestones-list');
  container.innerHTML = '';
  const milestones = (currentData && currentData.milestones) ? currentData.milestones : [];
  milestones.forEach(m => {
    addMilestoneRow(m.name, m.target_amount);
  });
  if (milestones.length === 0) {
    addMilestoneRow('Financial Security', 100000);
    addMilestoneRow('Quarter Million', 250000);
    addMilestoneRow('Financial Independence (€1M)', 1000000);
  }
  document.getElementById('milestones-modal').classList.remove('hidden');
}

function closeMilestonesModal() {
  document.getElementById('milestones-modal').classList.add('hidden');
}

function addMilestoneRow(name = '', amount = 100000) {
  const container = document.getElementById('modal-milestones-list');
  const div = document.createElement('div');
  div.className = 'milestone-edit-row flex items-center gap-2 bg-slate-950 p-2 rounded-lg border border-slate-800';
  div.innerHTML = `
    <input type="text" placeholder="Milestone Name" value="${escapeHtml(name)}" class="ms-name flex-1 bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white text-xs">
    <div class="flex items-center gap-1">
      <span class="text-slate-400 text-xs">€</span>
      <input type="number" step="5000" placeholder="Amount" value="${amount}" class="ms-amount w-28 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-white text-xs font-mono text-right">
    </div>
    <button onclick="this.parentElement.remove()" class="text-rose-400 hover:text-rose-300 p-1 text-sm font-bold">&times;</button>
  `;
  container.appendChild(div);
}

async function saveMilestonesConfig() {
  const rows = document.querySelectorAll('.milestone-edit-row');
  const milestones = [];
  rows.forEach((r, idx) => {
    const name = r.querySelector('.ms-name').value.trim();
    const amount = parseFloat(r.querySelector('.ms-amount').value) || 0;
    if (name && amount > 0) {
      milestones.push({ id: `m-${idx + 1}`, name: name, target_amount: amount, currency: 'EUR' });
    }
  });

  try {
    const res = await fetch('/api/milestones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ milestones: milestones })
    });
    if (res.ok) {
      closeMilestonesModal();
      await loadOverview();
      showToast('Milestones saved successfully!');
    }
  } catch (err) {
    console.error('Failed to save milestones:', err);
  }
}
