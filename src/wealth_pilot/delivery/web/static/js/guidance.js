/**
 * Paslood — Priority Guidance, Contribution Optimizer, Tax Simulator & AI Advisor
 */

function renderAdvice(data) {
  const debtContainer = document.getElementById('debt-advisor-list');
  if (debtContainer) {
    debtContainer.innerHTML = '';
    const advices = data.advices || [];
    const totalBadge = document.getElementById('guidance-total-badge');
    if (totalBadge) totalBadge.textContent = I18N.t('guidance.active_badge', { count: advices.length, _fallback: `${advices.length} Active` });

    advices.forEach(rawAdv => {
      const adv = I18N.localizeAdvice(rawAdv);
      const item = document.createElement('div');
      item.className = 'p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1.5';
      const badgeColor = adv.priority === 'CRITICAL'
        ? 'bg-red-500/20 text-red-400 border-red-500/30'
        : (adv.priority === 'HIGH'
          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
          : 'bg-blue-500/20 text-blue-400 border-blue-500/30');
      const typeLabel = (adv.advice_type || '').includes('DEBT')
        ? I18N.t('guidance.type_debt', 'Debt Avalanche')
        : I18N.t('guidance.type_drift', 'Portfolio Drift');
      item.innerHTML = `
        <div class="flex items-center justify-between gap-2">
          <div class="font-bold text-white text-sm">${escapeHtml(adv.title)}</div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">${escapeHtml(typeLabel)}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase border ${badgeColor}">${escapeHtml(adv.priorityLabel || adv.priority)}</span>
          </div>
        </div>
        <div class="text-slate-300 leading-relaxed">${escapeHtml(adv.message)}</div>
      `;
      debtContainer.appendChild(item);
    });
  }

  recalculateContribution();
}

async function recalculateContribution() {
  if (!currentData || !currentData.allocations) return;
  const depositAmt = parseFloat(document.getElementById('input-deposit-amount')?.value || 0);
  const ordersContainer = document.getElementById('contribution-orders-list');
  if (!ordersContainer) return;
  ordersContainer.innerHTML = '<div class="text-xs text-slate-400">Calculating optimal contribution...</div>';

  try {
    const res = await fetch('/api/advice/contribution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deposit: depositAmt })
    });
    if (!res.ok) throw new Error('Failed to calculate contribution');
    const data = await res.json();
    ordersContainer.innerHTML = '';
    if (!data.orders || data.orders.length === 0) {
      ordersContainer.innerHTML = `<div class="text-xs text-slate-400">${escapeHtml(I18N.t('guidance.all_balanced', 'All buckets are balanced! You can distribute this deposit proportionally across your targets.'))}</div>`;
      return;
    }

    data.orders.forEach(o => {
      const matchingAlloc = (currentData.allocations || []).find(a => a.id === o.bucket_id);
      const color = matchingAlloc ? matchingAlloc.color : '#3b82f6';
      const div = document.createElement('div');
      div.className = 'flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs';
      div.innerHTML = `
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${escapeHtml(color)}"></span>
          <span class="font-semibold text-white">${escapeHtml(o.bucket_name)}</span>
          <span class="text-slate-500 font-mono">(${I18N.formatPercent(o.percentage_of_deposit)} of deposit)</span>
        </div>
        <div class="text-emerald-400 font-bold text-sm font-mono whitespace-nowrap">+${I18N.formatCurrency(o.amount_value || o.amount || o.amount_formatted, 'EUR')}</div>
      `;
      ordersContainer.appendChild(div);
    });
  } catch (err) {
    console.error('Contribution calculation error:', err);
    ordersContainer.innerHTML = `<div class="text-xs text-red-400">Failed to calculate buy orders: ${escapeHtml(err.message)}</div>`;
  }
}

// --- Belgian Capital Gains Tax Simulator & PDT Lookup ---
function populateTaxHoldingDropdown(data) {
  const select = document.getElementById('sim-tax-holding-select');
  if (!select) return;
  const prevVal = select.value;
  select.innerHTML = '<option value="">-- Choose from your loaded holdings --</option>';
  const assets = data?.assets || [];
  const stockOrEtf = assets.filter(a => a.symbol);
  stockOrEtf.forEach(a => {
    const opt = document.createElement('option');
    opt.value = a.symbol;
    opt.textContent = `${a.symbol} - ${a.name} (${a.current_value_formatted})`;
    opt.dataset.symbol = a.symbol;
    const price = (a.current_price && a.current_price > 0) ? a.current_price : (a.current_value / (a.quantity || 1));
    opt.dataset.price = price;
    opt.dataset.quantity = a.quantity || 0;
    select.appendChild(opt);
  });
  if (prevVal) select.value = prevVal;
}

function onSelectTaxHolding(symbol) {
  if (!symbol) return;
  const select = document.getElementById('sim-tax-holding-select');
  const opt = select.options[select.selectedIndex];
  if (!opt) return;
  document.getElementById('sim-tax-symbol').value = symbol;
  if (opt.dataset.price && parseFloat(opt.dataset.price) > 0) {
    document.getElementById('sim-tax-current-price').value = parseFloat(opt.dataset.price).toFixed(2);
  }
  if (opt.dataset.quantity && parseFloat(opt.dataset.quantity) > 0) {
    document.getElementById('sim-tax-shares-pre').value = parseFloat(opt.dataset.quantity);
    document.getElementById('sim-tax-shares-post').value = 0;
  }
  lookupTaxPrice();
}

async function lookupTaxPrice() {
  const symbol = document.getElementById('sim-tax-symbol').value.trim();
  const btn = document.getElementById('btn-lookup-tax-price');
  const feedback = document.getElementById('tax-lookup-feedback');
  if (!symbol) {
    alert('Please enter a ticker symbol');
    return;
  }
  btn.disabled = true;
  btn.innerHTML = '<span>⏳ Looking up...</span>';
  feedback.textContent = `Querying PDT MCP timetravel for ${symbol} on Dec 31, 2025...`;
  feedback.className = 'text-[10px] text-blue-400 mt-1 block';

  try {
    const res = await fetch(`/api/tax/lookup-price?symbol=${encodeURIComponent(symbol)}&date=2025-12-31`);
    const data = await res.json();
    if (res.ok && data.price !== null) {
      document.getElementById('sim-tax-bench-price').value = data.price.toFixed(2);
      feedback.textContent = `✓ Found Dec 31, 2025 closing price: € ${data.price.toFixed(2)} (${data.source || 'PDT MCP'})`;
      feedback.className = 'text-[10px] text-emerald-400 mt-1 block';
      await runTaxSimulation();
    } else {
      feedback.textContent = data.message || `No historical quote found on PDT for ${symbol}. You can set the base price manually.`;
      feedback.className = 'text-[10px] text-amber-400 mt-1 block';
    }
  } catch (err) {
    feedback.textContent = `Lookup error: ${err.message}. You can manually specify base price.`;
    feedback.className = 'text-[10px] text-red-400 mt-1 block';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🔍 Lookup PDT</span>';
  }
}

let _lastMaxTaxFreeShares = 13;

function applyMaxTaxFreeShares() {
  const sellInput = document.getElementById('sim-tax-sell-qty');
  if (!sellInput) return;
  sellInput.value = _lastMaxTaxFreeShares > 0 ? _lastMaxTaxFreeShares : 0;
  runTaxSimulation();
}

async function runTaxSimulation() {
  const symbolEl = document.getElementById('sim-tax-symbol');
  if (!symbolEl) return;
  const symbol = symbolEl.value.trim();
  const benchPrice = parseFloat(document.getElementById('sim-tax-bench-price')?.value || 0);
  const currentPrice = parseFloat(document.getElementById('sim-tax-current-price')?.value || 0);
  const sharesPre = parseFloat(document.getElementById('sim-tax-shares-pre')?.value || 0);
  const preBuyPrice = parseFloat(document.getElementById('sim-tax-pre-buy-price')?.value || 0);
  const sharesPost = parseFloat(document.getElementById('sim-tax-shares-post')?.value || 0);
  const postBuyPrice = parseFloat(document.getElementById('sim-tax-post-buy-price')?.value || 0);
  const sellQty = parseFloat(document.getElementById('sim-tax-sell-qty')?.value || 0);
  const exemption = parseFloat(document.getElementById('settings-tax-exemption')?.value || 10000);
  const rate = parseFloat(document.getElementById('settings-tax-rate')?.value || 10.0);
  const brokerProfile = document.getElementById('sim-tax-broker-profile')?.value || 'EQUATEPLUS_CH';
  const tobTier = document.getElementById('sim-tax-tob-tier')?.value || '0.35';
  const carryoverYears = parseInt(document.getElementById('sim-tax-carryover-years')?.value || '0', 10);
  const isJointFiling = Boolean(document.getElementById('sim-tax-joint-filing')?.checked);
  const bondWeightPct = parseFloat(document.getElementById('sim-tax-bond-pct')?.value || 0);

  try {
    const res = await fetch('/api/tax/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: symbol,
        current_price: currentPrice,
        benchmark_price: benchPrice,
        actual_purchase_price: postBuyPrice,
        pre_benchmark_purchase_price: preBuyPrice,
        shares_pre_benchmark: sharesPre,
        shares_post_benchmark: sharesPost,
        shares_to_sell: sellQty,
        annual_exemption: exemption,
        tax_rate_pct: rate,
        broker_profile: brokerProfile,
        tob_tier: tobTier,
        carryover_years: carryoverYears,
        is_joint_filing: isJointFiling,
        bond_weight_pct: bondWeightPct
      })
    });
    const d = await res.json();
    if (res.ok) {
      document.getElementById('res-gain-pre').textContent = I18N.formatCurrency(d.gain_pre_benchmark, 'EUR');
      document.getElementById('res-gain-post').textContent = I18N.formatCurrency(d.gain_post_benchmark, 'EUR');
      document.getElementById('res-taxable-gain').textContent = I18N.formatCurrency(d.total_taxable_gain, 'EUR');

      const savedEl = document.getElementById('res-fotomoment-saved');
      if (savedEl) {
        if ((d.fotomoment_exemption_saved || 0) > 0) {
          savedEl.textContent = `Saves ${I18N.formatCurrency(d.fotomoment_exemption_saved, 'EUR')} vs FMV (${I18N.formatCurrency(d.historical_fmv_gain, 'EUR')})`;
          savedEl.className = 'text-[10px] text-emerald-400 mt-0.5';
        } else {
          savedEl.textContent = `Basis: ${I18N.formatCurrency(d.effective_pre_benchmark_basis || benchPrice, 'EUR')}/share`;
          savedEl.className = 'text-[10px] text-slate-500 mt-0.5';
        }
      }

      const reyndersEl = document.getElementById('res-reynders-tax');
      if (reyndersEl) {
        const rTax = d.reynders_tax || 0;
        reyndersEl.textContent = `Art. 19bis Reynders Tax: ${I18N.formatCurrency(rTax, 'EUR')}`;
        reyndersEl.className = rTax > 0 ? 'text-[10px] text-amber-400 mt-0.5 font-semibold' : 'text-[10px] text-slate-500 mt-0.5';
      }

      if (typeof d.max_tax_free_whole_shares === 'number') {
        _lastMaxTaxFreeShares = d.max_tax_free_whole_shares;
        const maxBadge = document.getElementById('badge-max-tax-free-shares');
        if (maxBadge) {
          maxBadge.textContent = `(${d.max_tax_free_whole_shares} shares)`;
        }
      }

      const remBadge = document.getElementById('res-remaining-exemption');
      if (d.remaining_exemption > 0) {
        const remAmt = I18N.formatCurrency(d.remaining_exemption, 'EUR');
        remBadge.textContent = I18N.t('guidance.exemption_left', { amount: remAmt, _fallback: `${remAmt} exemption left` });
        remBadge.className = 'text-[10px] text-emerald-400 mt-0.5';
      } else {
        remBadge.textContent = I18N.t('guidance.exemption_exhausted', 'Exemption exhausted');
        remBadge.className = 'text-[10px] text-amber-400 mt-0.5';
      }

      document.getElementById('res-tax-due').textContent = I18N.formatCurrency(d.tax_due, 'EUR');
      const statusBadge = document.getElementById('res-tax-status');
      if (d.tax_due > 0 || (d.reynders_tax || 0) > 0) {
        const totalCgt = (d.tax_due || 0) + (d.reynders_tax || 0);
        const taxAmt = I18N.formatCurrency(totalCgt, 'EUR');
        statusBadge.textContent = I18N.t('guidance.tax_due_status', { amount: taxAmt, _fallback: `⚠️ Tax Due (${taxAmt})` });
        statusBadge.className = 'text-[10px] text-amber-400 mt-0.5 font-semibold';
      } else {
        statusBadge.textContent = I18N.t('guidance.tax_exempt_status', '🟢 100% Tax-Exempt');
        statusBadge.className = 'text-[10px] text-emerald-400 mt-0.5 font-semibold';
      }

      // Settlement & TOB Reconciliation fields
      const grossEl = document.getElementById('res-gross-proceeds');
      if (grossEl) grossEl.textContent = I18N.formatCurrency(d.gross_proceeds || 0, 'EUR');

      const feesEl = document.getElementById('res-broker-fees');
      const feesSubEl = document.getElementById('res-broker-fees-sub');
      const totalBrokerFees = (d.broker_commission || 0) + (d.foreign_stamp_tax || 0);
      if (feesEl) feesEl.textContent = `-${I18N.formatCurrency(totalBrokerFees, 'EUR')}`;
      if (feesSubEl) {
        if (totalBrokerFees > 0) {
          feesSubEl.textContent = `${I18N.formatCurrency(d.broker_commission || 0, 'EUR')} fee + ${I18N.formatCurrency(d.foreign_stamp_tax || 0, 'EUR')} CH stamp`;
        } else {
          feesSubEl.textContent = 'Included in Belgian broker trade';
        }
      }

      const payoutEl = document.getElementById('res-broker-payout');
      if (payoutEl) payoutEl.textContent = I18N.formatCurrency(d.broker_payout_before_belgian_tax || 0, 'EUR');

      const tobEl = document.getElementById('res-tob-tax');
      const tobSubEl = document.getElementById('res-tob-sub');
      const tobDeclBadge = document.getElementById('res-tob-declaration-badge');
      const tobAmtFormatted = I18N.formatCurrency(d.tob_tax || 0, 'EUR');
      if (tobEl) tobEl.textContent = `-${tobAmtFormatted}`;
      if (d.tob_self_declaration_required) {
        if (tobSubEl) {
          tobSubEl.textContent = 'Self-declare via MyMinfin (M+2)';
          tobSubEl.className = 'text-[10px] text-amber-400/80';
        }
        if (tobDeclBadge) {
          tobDeclBadge.textContent = `⚠️ Foreign Broker: Declare ${tobAmtFormatted} Belgian TOB to FOD Financiën (Deadline: end of month M+2)`;
          tobDeclBadge.className = 'px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30';
        }
      } else {
        if (tobSubEl) {
          tobSubEl.textContent = 'Auto-withheld by Belgian broker';
          tobSubEl.className = 'text-[10px] text-emerald-400/80';
        }
        if (tobDeclBadge) {
          tobDeclBadge.textContent = `✓ Belgian Broker Withholds ${tobAmtFormatted} TOB Automatically`;
          tobDeclBadge.className = 'px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
        }
      }

      const netEl = document.getElementById('res-net-proceeds');
      if (netEl) netEl.textContent = I18N.formatCurrency(d.net_proceeds || 0, 'EUR');
    }
  } catch (err) {
    console.error('Tax simulation calculation error:', err);
  }
}

// AI Advisor & Model Discovery
function isMaskedOrNonByteString(val) {
  if (!val || typeof val !== 'string') return true;
  const s = val.trim();
  if (!s || s.includes('•') || s.startsWith('****')) return true;
  for (let i = 0; i < s.length; i++) {
    if (s.charCodeAt(i) > 255) return true;
  }
  return false;
}

function updateAiActiveBadge() {
  const badge = document.getElementById('ai-active-provider-badge');
  if (!badge) return;
  const prov = (document.getElementById('settings-ai-provider')?.value || 'gemini').toUpperCase();
  const model = document.getElementById('settings-ai-model')?.value || 'gemini-2.5-flash';
  const hasKey = Boolean((document.getElementById('settings-ai-key')?.value || '').trim());
  const keyLabel = (prov === 'OLLAMA' || prov === 'ALGORITHMIC') ? 'Local' : (hasKey ? 'Key Configured' : 'Algorithmic Fallback');
  badge.textContent = `Provider: ${prov} • ${model} (${keyLabel})`;
}

function selectAiPrompt(promptText) {
  const input = document.getElementById('ai-user-question');
  if (input) {
    input.value = promptText;
    input.focus();
  }
}

async function onAiProviderOrKeyChanged() {
  await refreshAiModels();
  updateAiActiveBadge();
}

async function refreshAiModels() {
  const providerEl = document.getElementById('settings-ai-provider');
  const keyEl = document.getElementById('settings-ai-key');
  const select = document.getElementById('settings-ai-model');
  if (!select || !providerEl) return;

  const provider = providerEl.value;
  const rawKey = keyEl ? keyEl.value : '';
  const previousModel = select.value;

  select.innerHTML = '<option value="">Discovering models...</option>';

  try {
    const queryParams = new URLSearchParams({ provider });
    const headers = {};
    if (!isMaskedOrNonByteString(rawKey)) {
      headers['X-AI-API-Key'] = rawKey.trim();
    }
    const res = await fetch(`/api/ai/models?${queryParams.toString()}`, { headers });
    if (!res.ok) throw new Error('Failed to query models');
    const data = await res.json();
    const models = data.models || [];
    select.innerHTML = '';
    let hasSelected = false;
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name}${m.recommended ? ' ★ Recommended' : ''}`;
      if (previousModel && m.id === previousModel) {
        opt.selected = true;
        hasSelected = true;
      }
      select.appendChild(opt);
    });

    if (!hasSelected && select.options.length > 0) {
      const recIdx = models.findIndex(m => m.recommended);
      select.selectedIndex = recIdx >= 0 ? recIdx : 0;
    }
  } catch (err) {
    console.error('Failed to load AI models:', err);
    if (provider === 'ollama') {
      select.innerHTML = '<option value="llama3.2">Llama 3.2 (Offline)</option>';
    } else {
      select.innerHTML = '<option value="gemini-2.5-flash">Gemini 2.5 Flash ★ Recommended</option><option value="gemini-2.5-pro">Gemini 2.5 Pro</option>';
    }
  }
  updateAiActiveBadge();
}

async function runAiReview() {
  const btn = document.getElementById('btn-run-ai');
  const loader = document.getElementById('ai-loading');
  const output = document.getElementById('ai-output');
  const provider = document.getElementById('settings-ai-provider')?.value || 'gemini';
  const model = document.getElementById('settings-ai-model')?.value || null;
  const rawKey = document.getElementById('settings-ai-key')?.value || '';
  const key = isMaskedOrNonByteString(rawKey) ? null : rawKey.trim();
  const question = document.getElementById('ai-user-question')?.value || '';

  btn.disabled = true;
  loader.classList.remove('hidden');
  output.classList.add('hidden');

  try {
    const res = await fetch('/api/ai/advise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: provider,
        model: model,
        api_key: key || null,
        question: question || null,
      }),
    });

    if (!res.ok) {
      let errorDetail = `Request failed (${res.status} ${res.statusText})`;
      try {
        const errJson = await res.json();
        errorDetail = errJson.detail || errorDetail;
      } catch (e) {
        const errText = await res.text();
        if (errText) errorDetail = errText;
      }
      throw new Error(errorDetail);
    }

    const data = await res.json();
    const rawAdvice = data.advice || 'No advice generated.';
    const parsedHtml = typeof marked !== 'undefined' ? marked.parse(rawAdvice) : escapeHtml(rawAdvice);
    output.innerHTML = typeof DOMPurify !== 'undefined'
      ? DOMPurify.sanitize(parsedHtml)
      : parsedHtml;
  } catch (err) {
    output.innerHTML = `
      <div class="p-4 bg-red-500/10 border border-red-500/30 rounded-xl space-y-2">
        <div class="font-bold text-red-400 text-sm flex items-center gap-1.5">
          <span>⚠️ AI Advisory Error</span>
        </div>
        <div class="text-xs text-red-300 font-mono leading-relaxed whitespace-pre-wrap">${escapeHtml(err.message)}</div>
        <div class="text-[11px] text-slate-400 pt-1">
          Tip: Verify your API key or switch to Ollama / Algorithmic Engine in <button onclick="switchTab('settings')" class="text-blue-400 underline">Settings</button>.
        </div>
      </div>
    `;
  } finally {
    btn.disabled = false;
    loader.classList.add('hidden');
    output.classList.remove('hidden');
  }
}
