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

  renderCashflowBreakdownWidget(data.cashflow_breakdown || null, fc);
  renderDonutChart(data.allocations || []);
  populateStartYearSelect(data);
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

function renderCashflowBreakdownWidget(cb, fallbackSurplus = 0) {
  const container = document.getElementById('kpi-cashflow-formula');
  if (!container) return;
  if (!cb) {
    container.innerHTML = `<div class="text-slate-400">Income − (Fixed + Debt + Living) = ${escapeHtml(I18N.formatCurrency(fallbackSurplus, 'EUR'))}</div>`;
    return;
  }
  const inc = I18N.formatCurrency(cb.monthly_income || 0, 'EUR');
  const fix = I18N.formatCurrency(cb.fixed_costs || 0, 'EUR');
  const debt = I18N.formatCurrency(cb.debt_payments || 0, 'EUR');
  const liv = I18N.formatCurrency(cb.living_expenses || 0, 'EUR');
  const free = I18N.formatCurrency(cb.free_cashflow !== undefined ? cb.free_cashflow : fallbackSurplus, 'EUR');
  const periodLabel = cb.period === 'year'
    ? 'Last 12 Months'
    : (cb.period === 'month' ? 'Latest Month' : 'All Time');
  const rangeSuffix = (cb.period_start && cb.period_end)
    ? ` (${cb.period_start.slice(0, 7)} – ${cb.period_end.slice(0, 7)})`
    : '';
  const sourceNote = cb.is_default_estimate
    ? 'Baseline estimate (import CSV statements in Cashflow for actuals)'
    : `${periodLabel}: Avg across ${cb.months_analyzed || 1} month(s)${rangeSuffix}`;

  const kpiSel = document.getElementById('kpi-cashflow-period-select');
  if (kpiSel && cb.period) {
    kpiSel.value = cb.period;
  }

  container.innerHTML = `
    <div class="text-[10px] text-slate-300 font-sans font-medium" title="${escapeHtml(cb.formula || '')}">
      <span class="text-emerald-400 font-mono">${escapeHtml(inc)}</span> Inc
      − (<span class="text-purple-300 font-mono">${escapeHtml(fix)}</span> Fix
      + <span class="text-rose-400 font-mono">${escapeHtml(debt)}</span> Debt
      + <span class="text-amber-300 font-mono">${escapeHtml(liv)}</span> Liv)
      = <span class="text-emerald-400 font-mono font-bold">${escapeHtml(free)}</span>
    </div>
    <div class="text-[9px] text-slate-400 font-sans pt-0.5">${escapeHtml(sourceNote)}</div>
    <div id="kpi-cashflow-detail-rows" class="hidden pt-1.5 mt-1 border-t border-slate-800/80 space-y-0.5 text-[10px]">
      <div class="flex justify-between"><span>+ Avg Monthly Income:</span><span class="text-emerald-400">${escapeHtml(inc)}</span></div>
      <div class="flex justify-between"><span>− Fixed (Tax, Utilities, Ins., Subs):</span><span class="text-slate-300">${escapeHtml(fix)}</span></div>
      <div class="flex justify-between"><span>− Debt &amp; Mortgage Payments:</span><span class="text-rose-400">${escapeHtml(debt)}</span></div>
      <div class="flex justify-between"><span>− Living (Groceries, Leisure, Transp.):</span><span class="text-amber-300">${escapeHtml(liv)}</span></div>
      <div class="flex justify-between font-bold border-t border-slate-800 pt-0.5"><span>= Free Monthly Cashflow:</span><span class="text-emerald-400">${escapeHtml(free)}</span></div>
      <div class="text-[9px] text-slate-500 font-sans italic pt-0.5">${escapeHtml(sourceNote)}</div>
    </div>
  `;
}

function toggleCashflowFormulaBreakdown() {
  const detail = document.getElementById('kpi-cashflow-detail-rows');
  if (detail) {
    detail.classList.toggle('hidden');
  }
}

function renderDonutChart(allocations) {
  const canvas = document.getElementById('allocationDonutChart');
  const tokens = typeof getChartThemeTokens === 'function' ? getChartThemeTokens() : { surface: '#131C2E' };
  if (canvas && typeof Chart !== 'undefined') {
    const ctx = canvas.getContext('2d');
    if (donutChartInstance) donutChartInstance.destroy();

    const labels = allocations.map(a => a.name);
    const values = allocations.map(a => a.current_value);
    const colors = allocations.map(a => a.color || '#2B5C8F');

    donutChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: tokens.surface,
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

  const labels = trajectory.map(t => {
    if (t.is_current) {
      return `${t.calendar_year || 'Today'} (Today)`;
    }
    if (t.is_historical) {
      return String(t.calendar_year || `${t.year}Y`);
    }
    return t.calendar_year ? `${t.calendar_year} (+${t.year}Y)` : I18N.t('dashboard.year_label', { year: t.year, _fallback: `Year ${t.year}` });
  });

  const netWorthData = trajectory.map(t => t.net_worth);
  const assetsData = trajectory.map(t => t.assets);
  const debtsData = trajectory.map(t => t.debts);
  const todayIdx = trajectory.findIndex(t => t.is_current);

  const ptRadii = trajectory.map(t => (t.is_current ? 5 : (t.is_historical ? 2.5 : 1.5)));
  const ptHoverRadii = trajectory.map(t => (t.is_current ? 7 : (t.is_historical ? 4.5 : 3)));
  const tokens = typeof getChartThemeTokens === 'function' ? getChartThemeTokens() : {
    gridColor: 'rgba(148, 163, 184, 0.08)',
    tickColor: '#94A3B8',
    netWorthColor: '#38BDF8',
    netWorthFill: 'rgba(56, 189, 248, 0.14)',
    assetsColor: '#34D399',
    debtsColor: '#FB923C'
  };

  projectionChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: I18N.t('dashboard.chart_label_net_worth', 'Net Worth'),
          data: netWorthData,
          borderColor: tokens.netWorthColor,
          backgroundColor: tokens.netWorthFill,
          fill: true,
          tension: 0.3,
          pointRadius: ptRadii,
          pointHoverRadius: ptHoverRadii,
          segment: {
            borderDash: ctx => (todayIdx !== -1 && ctx.p0DataIndex < todayIdx ? [] : [4, 4])
          }
        },
        {
          label: I18N.t('dashboard.chart_label_assets', 'Assets'),
          data: assetsData,
          borderColor: tokens.assetsColor,
          borderDash: [6, 4],
          tension: 0.3,
          pointRadius: ptRadii
        },
        {
          label: I18N.t('dashboard.chart_label_debts', 'Debts'),
          data: debtsData,
          borderColor: tokens.debtsColor,
          borderDash: [2, 3],
          tension: 0.3,
          pointRadius: ptRadii
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: tokens.tickColor, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            title: function(items) {
              if (!items || !items.length) return '';
              const idx = items[0].dataIndex;
              const pt = trajectory[idx];
              if (!pt) return items[0].label;
              if (pt.is_current) return `${pt.calendar_year} — Current Balance Sheet`;
              if (pt.is_historical) return `${pt.calendar_year} — Historical Actual / Backcast`;
              return `${pt.calendar_year} — Projected (+${pt.year}Y)`;
            },
            label: function(c) {
              return ` ${c.dataset.label}: ${I18N.formatCurrency(c.raw, 'EUR', 0)}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: tokens.tickColor } },
        y: { grid: { color: tokens.gridColor }, ticks: { color: tokens.tickColor, callback: v => `€ ${v/1000}k` } }
      }
    }
  });
}

function onProjectionStartYearChanged(val) {
  if (val === 'auto') {
    currentAutoDetectStart = true;
    currentProjectionStartYear = null;
  } else if (val === 'today') {
    currentAutoDetectStart = false;
    currentProjectionStartYear = new Date().getFullYear();
  } else {
    currentAutoDetectStart = false;
    currentProjectionStartYear = parseInt(val, 10);
  }
  updateProjectionChart();
}

function populateStartYearSelect(data) {
  const sel = document.getElementById('projection-start-year-select');
  if (!sel) return;
  const currentVal = sel.value;
  const oldestYr = data.oldest_detected_year;
  const nowYr = data.current_year || new Date().getFullYear();

  const autoOptLabel = oldestYr && oldestYr < nowYr ? `Auto (${oldestYr})` : I18N.t('dashboard.start_auto', 'Auto Inception');

  sel.innerHTML = '';
  const optAuto = document.createElement('option');
  optAuto.value = 'auto';
  optAuto.textContent = autoOptLabel;
  sel.appendChild(optAuto);

  if (oldestYr && oldestYr < nowYr) {
    for (let y = oldestYr; y < nowYr; y++) {
      const opt = document.createElement('option');
      opt.value = String(y);
      opt.textContent = `${y}`;
      sel.appendChild(opt);
    }
  }

  const optToday = document.createElement('option');
  optToday.value = 'today';
  optToday.textContent = I18N.t('dashboard.start_today', 'Today only');
  sel.appendChild(optToday);

  if (currentVal && Array.from(sel.options).some(o => o.value === currentVal)) {
    sel.value = currentVal;
  } else {
    sel.value = currentAutoDetectStart ? 'auto' : (currentProjectionStartYear ? String(currentProjectionStartYear) : 'today');
  }
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
  let url = `/api/projection?years=${currentProjectionYears}&cagr=${currentProjectionCagr}&exclude_property=${excludePropertyState ? 'true' : 'false'}`;
  if (!currentAutoDetectStart && currentProjectionStartYear) {
    url += `&start_year=${currentProjectionStartYear}&auto_detect_start=false`;
  } else if (!currentAutoDetectStart) {
    url += `&auto_detect_start=false`;
  }
  try {
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    populateStartYearSelect(data);
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
