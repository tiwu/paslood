/**
 * Wealth Pilot — Core Application State, Theme, Navigation & Bootstrap
 */

// Security Helper: HTML Entity Escaping to prevent XSS
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Shared Application State
let currentData = null;
let donutChartInstance = null;
let projectionChartInstance = null;
let activeRebucketTx = null;
let currentProjectionYears = 30;
let currentProjectionCagr = 7.0;
let currentMcpServers = [];
let excludePropertyState = localStorage.getItem('wealth_pilot_exclude_property') === 'true';

const BUCKET_PALETTE = [
  '#3B82F6', // Blue
  '#10B981', // Emerald
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#F97316', // Orange
  '#6366F1', // Indigo
  '#14B8A6', // Teal
  '#E11D48', // Rose
];

// Theme Toggle (Light / Dark Mode)
function syncThemeToggleUI() {
  const isLight = document.documentElement.classList.contains('light-theme');
  const iconEl = document.getElementById('theme-toggle-icon');
  const labelEl = document.getElementById('theme-toggle-label');
  if (iconEl) iconEl.textContent = isLight ? '🌙' : '☀️';
  if (labelEl) {
    labelEl.textContent = isLight
      ? (typeof I18N !== 'undefined' ? I18N.t('common.theme_dark', 'Dark') : 'Dark')
      : (typeof I18N !== 'undefined' ? I18N.t('common.theme_light', 'Light') : 'Light');
  }
}

// Language & Regional Format Change Listener to re-render localized UI
function reRenderAllLocalizedUI() {
  syncThemeToggleUI();
  if (currentData) {
    if (typeof renderDashboard === 'function') renderDashboard(currentData);
    if (typeof renderBuckets === 'function') renderBuckets(currentData);
    if (typeof renderHoldingsMapping === 'function') renderHoldingsMapping(currentData);
    if (typeof renderMilestones === 'function') renderMilestones(currentData.milestones || []);
    if (typeof renderManualAssetsAndDebts === 'function') renderManualAssetsAndDebts(currentData);
    if (typeof renderAdvice === 'function') renderAdvice(currentData);
    if (typeof renderTransactions === 'function') renderTransactions(currentData);
  }
  if (typeof runTaxSimulation === 'function') runTaxSimulation();
  if (typeof updateWizardStepUI === 'function') updateWizardStepUI();
}

window.addEventListener('languageChanged', reRenderAllLocalizedUI);
window.addEventListener('regionalFormatChanged', reRenderAllLocalizedUI);

function toggleThemeScheme() {
  const root = document.documentElement;
  const meta = document.querySelector('meta[name="color-scheme"]');
  const isCurrentlyLight = root.classList.contains('light-theme');
  if (isCurrentlyLight) {
    root.classList.remove('light-theme');
    root.classList.add('dark');
    if (meta) meta.content = 'dark';
    localStorage.setItem('color-scheme', 'dark');
  } else {
    root.classList.add('light-theme');
    root.classList.remove('dark');
    if (meta) meta.content = 'light';
    localStorage.setItem('color-scheme', 'light');
  }
  syncThemeToggleUI();
  if (currentData) {
    renderDonutChart(currentData.allocations || []);
    renderProjectionChart(currentData.trajectory || []);
  }
}

// Mobile Navigation Drawer
function toggleMobileMenu(forceClose = false) {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn = document.getElementById('btn-mobile-menu');
  const icon = document.getElementById('mobile-menu-icon');
  const openIcon = document.getElementById('hamburger-icon-open');
  const closeIcon = document.getElementById('hamburger-icon-close');
  if (!drawer) return;
  const isHidden = drawer.classList.contains('hidden');
  if (forceClose || !isHidden) {
    drawer.classList.add('hidden');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    if (icon) icon.textContent = '☰';
    if (openIcon) openIcon.classList.remove('hidden');
    if (closeIcon) closeIcon.classList.add('hidden');
  } else {
    drawer.classList.remove('hidden');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    if (icon) icon.textContent = '✕';
    if (openIcon) openIcon.classList.add('hidden');
    if (closeIcon) closeIcon.classList.remove('hidden');
  }
}

// Navigation Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => {
    el.classList.remove('bg-blue-600', 'text-white');
    el.classList.add('text-slate-300', 'hover:bg-slate-800');
  });
  document.querySelectorAll('.mnav-btn').forEach(el => {
    el.classList.remove('bg-blue-600', 'text-white', 'font-medium');
    el.classList.add('text-slate-300', 'hover:bg-slate-800');
  });

  const targetTab = document.getElementById('tab-' + tabId);
  if (targetTab) targetTab.classList.add('active');

  const activeBtn = document.getElementById('nav-' + tabId);
  if (activeBtn) {
    activeBtn.classList.remove('text-slate-300', 'hover:bg-slate-800');
    activeBtn.classList.add('bg-blue-600', 'text-white');
  }
  const activeMobileBtn = document.getElementById('mnav-' + tabId);
  if (activeMobileBtn) {
    activeMobileBtn.classList.remove('text-slate-300', 'hover:bg-slate-800');
    activeMobileBtn.classList.add('bg-blue-600', 'text-white', 'font-medium');
  }
  toggleMobileMenu(true);
}

function openHelpModal() {
  const modal = document.getElementById('help-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeHelpModal() {
  const modal = document.getElementById('help-modal');
  if (modal) modal.classList.add('hidden');
}

function dismissOAuthBanner() {
  const banner = document.getElementById('oauth-success-banner');
  if (banner) banner.classList.add('hidden');
}

function showToast(msg) {
  const note = document.getElementById('settings-notification');
  if (note) {
    document.getElementById('settings-notification-text').textContent = msg;
    note.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-emerald-500/10 border-emerald-500/30 text-emerald-300 fixed bottom-5 right-5 z-50 shadow-lg';
    note.classList.remove('hidden');
    setTimeout(() => note.classList.add('hidden'), 4000);
  }
}

// Exclude Real Estate / Property Toggle
async function toggleExcludeProperty(checked) {
  excludePropertyState = Boolean(checked);
  localStorage.setItem('wealth_pilot_exclude_property', excludePropertyState ? 'true' : 'false');
  await loadOverview();
  await updateProjectionChart();
}

// Initial Data Fetch
async function loadOverview() {
  try {
    const toggleEl = document.getElementById('toggle-exclude-property');
    if (toggleEl) toggleEl.checked = excludePropertyState;
    const url = `/api/overview?exclude_property=${excludePropertyState ? 'true' : 'false'}`;
    const res = await fetch(url);
    if (!res.ok) return;
    currentData = await res.json();
    if (typeof renderDashboard === 'function') renderDashboard(currentData);
    if (typeof renderBuckets === 'function') renderBuckets(currentData);
    if (typeof renderHoldingsMapping === 'function') renderHoldingsMapping(currentData);
    if (typeof renderMilestones === 'function') renderMilestones(currentData.milestones || []);
    if (typeof renderManualAssetsAndDebts === 'function') renderManualAssetsAndDebts(currentData);
    if (typeof renderAdvice === 'function') renderAdvice(currentData);
    if (typeof renderTransactions === 'function') renderTransactions(currentData);

    if (currentData.current_user) {
      const authContainer = document.getElementById('auth-header-container');
      const emailEl = document.getElementById('user-display-email');
      if (authContainer && emailEl) {
        if (currentData.current_user.auth_mode !== 'none') {
          emailEl.textContent = currentData.current_user.email;
          authContainer.classList.remove('hidden');
          authContainer.classList.add('flex');
        } else {
          authContainer.classList.add('hidden');
        }
      }
    }
    if (typeof populateTaxHoldingDropdown === 'function') populateTaxHoldingDropdown(currentData);
  } catch (err) {
    console.error('Failed to load overview:', err);
  }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', async () => {
  if (typeof initFileDropzone === 'function') {
    initFileDropzone();
  }
  if (typeof I18N !== 'undefined' && typeof I18N.init === 'function') {
    await I18N.init();
  }
  syncThemeToggleUI();
  await loadOverview();
  if (typeof loadSettings === 'function') await loadSettings();
  if (typeof runTaxSimulation === 'function') await runTaxSimulation();
  if (typeof refreshAiModels === 'function') await refreshAiModels();

  // Auto-sync PDT in background if connected and no PDT assets cached in SQLite yet
  try {
    const hasPdtAssets = (currentData?.assets || []).some(a => (a.id || '').startsWith('pdt-'));
    const pdtPill = document.getElementById('pdt-status-pill');
    const isConnected = pdtPill && !pdtPill.textContent.toLowerCase().includes('disconnected');
    if (isConnected && !hasPdtAssets) {
      fetch('/api/mcp/pdt/sync', { method: 'POST' }).then(res => {
        if (res.ok) loadOverview();
      }).catch(() => {});
    }
  } catch (e) {}

  // Check first-time setup
  if (localStorage.getItem('wealth_pilot_setup_completed') !== 'true') {
    if (typeof openSetupWizard === 'function') openSetupWizard();
  }

  // Check URL hash and query params for OAuth confirmation or error
  const urlParams = new URLSearchParams(window.location.search);
  const hash = window.location.hash;
  const isPdtConnected =
    urlParams.get('pdt_connected') === 'true' || hash.includes('pdt_connected=true');
  const syncedCount = urlParams.get('synced_count') || '';
  const pdtError =
    urlParams.get('pdt_error') ||
    (hash.includes('pdt_error') ? hash.split('pdt_error=')[1] : null);

  if (isPdtConnected) {
    const banner = document.getElementById('oauth-success-banner');
    if (banner) {
      banner.classList.remove('hidden');
      if (syncedCount && syncedCount !== '0') {
        document.getElementById('oauth-success-subtitle').textContent =
          `Successfully imported and synchronized ${syncedCount} portfolio holdings from Portfolio Dividend Tracker via MCP.`;
      }
    }
    showSettingsAlert(
      `🎉 Successfully connected to PDT via OAuth! ${syncedCount ? syncedCount + ' holdings synchronized.' : ''}`
    );
    window.history.replaceState(
      {},
      document.title,
      window.location.pathname + window.location.hash.split('?')[0]
    );
  } else if (pdtError) {
    showSettingsAlert(`OAuth authorization error: ${decodeURIComponent(pdtError)}`, true);
  }

  if (hash.includes('settings')) {
    switchTab('settings');
  } else if (hash.includes('buckets')) {
    switchTab('buckets');
  } else if (hash.includes('ai')) {
    switchTab('ai');
  } else if (hash.includes('cashflow') || hash.includes('data')) {
    switchTab('cashflow');
  } else if (hash.includes('advice') || hash.includes('guidance')) {
    switchTab('advice');
  }
});
