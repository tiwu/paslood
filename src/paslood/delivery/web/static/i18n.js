/**
 * Paslood Internationalization (i18n) Engine
 * Multi-language support: English (en), Dutch (nl), French (fr), German (de).
 * Loads isolated per-language JSON files from /api/i18n or /static/locales/{lang}.json.
 */

const I18N = {
  currentLang: 'en',
  supportedLanguages: ['en', 'nl', 'fr', 'de'],
  translations: {},
  regionalFormat: 'auto',
  _initPromise: null,

  getEffectiveLocale() {
    if (this.regionalFormat && this.regionalFormat !== 'auto') {
      return this.regionalFormat;
    }
    const map = {
      'nl': 'nl-BE',
      'fr': 'fr-BE',
      'de': 'de-DE',
      'en': 'en-US'
    };
    return map[this.currentLang] || 'nl-BE';
  },

  parseNumber(val) {
    if (val === null || val === undefined) return NaN;
    if (typeof val === 'number') return val;
    if (typeof val === 'string') {
      const cleaned = val.replace(/[^0-9.-]/g, '');
      const num = parseFloat(cleaned);
      return isNaN(num) ? NaN : num;
    }
    return NaN;
  },

  formatNumber(val, decimals = 2) {
    if (val === null || val === undefined) return '—';
    const num = typeof val === 'number' ? val : this.parseNumber(val);
    if (isNaN(num)) return String(val);
    const loc = this.getEffectiveLocale();
    return num.toLocaleString(loc, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  },

  formatPercent(val, decimals = 2) {
    if (val === null || val === undefined) return '—';
    const num = typeof val === 'number' ? val : this.parseNumber(val);
    if (isNaN(num)) return String(val);
    return this.formatNumber(num, decimals) + '%';
  },

  formatCurrency(val, currency = 'EUR', decimals = 2) {
    if (val === null || val === undefined) return '—';
    const num = typeof val === 'number' ? val : this.parseNumber(val);
    if (isNaN(num)) return String(val);
    const sym = currency === 'EUR' ? '€' : (currency === 'USD' ? '$' : currency);
    return `${sym} ${this.formatNumber(num, decimals)}`;
  },

  formatDate(dateVal) {
    if (!dateVal) return '—';
    try {
      let d = null;
      if (dateVal instanceof Date) {
        d = dateVal;
      } else if (typeof dateVal === 'string') {
        const trimmed = dateVal.trim();
        const parts = trimmed.split(/[/.-]/);
        if (parts.length === 3 && parts[0].length <= 2 && parts[2].length === 4) {
          const day = parseInt(parts[0], 10);
          const month = parseInt(parts[1], 10) - 1;
          const year = parseInt(parts[2], 10);
          d = new Date(year, month, day);
        } else if (parts.length === 3 && parts[0].length === 4) {
          const year = parseInt(parts[0], 10);
          const month = parseInt(parts[1], 10) - 1;
          const day = parseInt(parts[2], 10);
          d = new Date(year, month, day);
        } else {
          d = new Date(trimmed);
        }
      }
      if (!d || isNaN(d.getTime())) return String(dateVal);
      const loc = this.getEffectiveLocale();
      return d.toLocaleDateString(loc, { year: 'numeric', month: '2-digit', day: '2-digit' });
    } catch (e) {
      return String(dateVal);
    }
  },

  setRegionalFormat(fmt, persist = true) {
    this.regionalFormat = fmt || 'auto';
    if (persist) {
      try {
        localStorage.setItem('paslood_regional_format', this.regionalFormat);
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ regional_format: this.regionalFormat })
        }).catch(() => {});
      } catch (e) {}
    }
    const sel = document.getElementById('settings-regional-format-select');
    if (sel && sel.value !== this.regionalFormat) sel.value = this.regionalFormat;
    window.dispatchEvent(new CustomEvent('regionalFormatChanged', { detail: { format: this.regionalFormat } }));
  },

  /**
   * Resolves a dot-notated key (e.g., 'nav.overview') with optional {param} interpolation.
   * @param {string} key
   * @param {object|string} [paramsOrFallback='']
   * @returns {string}
   */
  t(key, paramsOrFallback = '') {
    const lang = this.currentLang || 'en';
    const isParams = paramsOrFallback !== null && typeof paramsOrFallback === 'object';
    const fallback = isParams ? (paramsOrFallback._fallback || '') : (paramsOrFallback || '');

    let val = this._lookup(lang, key);
    if (val === null && lang !== 'en') {
      val = this._lookup('en', key);
    }
    if (val === null || val === undefined) {
      val = fallback || key;
    }

    if (isParams && typeof val === 'string') {
      return val.replace(/\{(\w+)\}/g, (match, k) => {
        return paramsOrFallback[k] !== undefined ? String(paramsOrFallback[k]) : match;
      });
    }
    return String(val);
  },

  _lookup(lang, key) {
    const dict = this.translations[lang];
    if (!dict) return null;
    const parts = key.split('.');
    let cur = dict;
    for (const part of parts) {
      if (cur && typeof cur === 'object' && part in cur) {
        cur = cur[part];
      } else {
        return null;
      }
    }
    return cur;
  },

  /**
   * Localizes backend AdviceItem objects (title, message, priority) without coupling Domain to UI i18n.
   */
  localizeAdvice(adv) {
    if (!adv) return adv;
    let title = adv.title || '';
    let message = adv.message || '';

    if (title === 'Debt-Free Status') {
      title = this.t('advice_items.debt_free_title', title);
      message = this.t('advice_items.debt_free_msg', message);
    } else if (title.startsWith('Priority Debt Payoff: ')) {
      const name = title.replace('Priority Debt Payoff: ', '').trim();
      title = this.t('advice_items.high_debt_title', { name, _fallback: title });
      const m = message.match(/At ([\d.,]+)% APR[\s\S]*?extinguish its ([^\s]+(?:\s[^\s]+)?) balance/);
      if (m) {
        message = this.t('advice_items.high_debt_msg', {
          name,
          rate: m[1],
          balance: m[2],
          _fallback: message
        });
      }
    } else if (title.startsWith('Maintain Minimums on ')) {
      const name = title.replace('Maintain Minimums on ', '').trim();
      title = this.t('advice_items.low_debt_title', { name, _fallback: title });
      const m = message.match(/cost of ([\d.,]+)% APR[\s\S]*?CAGR of ([\d.,]+)%[\s\S]*?\(([^)]+)\/mo\)/);
      if (m) {
        message = this.t('advice_items.low_debt_msg', {
          name,
          rate: m[1],
          cagr: m[2],
          payment: m[3],
          _fallback: message
        });
      }
    } else if (title.startsWith('Underweight: ')) {
      const name = title.replace('Underweight: ', '').trim();
      title = this.t('advice_items.underweight_title', { name, _fallback: title });
      const m = message.match(/is ([\d.,]+)% below target[\s\S]*?~€\s*([\d.,]+)/);
      if (m) {
        message = this.t('advice_items.underweight_msg', {
          name,
          diff_pct: m[1],
          amount: m[2],
          _fallback: message
        });
      }
    }

    const prioKey = `priority.${(adv.priority || 'info').toLowerCase()}`;
    const priorityLabel = this.t(prioKey, (adv.priority || 'INFO').toUpperCase());

    return {
      ...adv,
      title,
      message,
      priorityLabel
    };
  },

  /**
   * Loads translation dictionaries from /api/i18n (with fallback to /static/locales/{lang}.json)
   * and applies the saved/detected language.
   */
  async init() {
    if (this._initPromise) return this._initPromise;
    this._initPromise = (async () => {
      let saved = null;
      try {
        saved = localStorage.getItem('paslood_language');
        const savedFormat = localStorage.getItem('paslood_regional_format');
        if (savedFormat) {
          this.regionalFormat = savedFormat;
        }
        if (!saved) {
          const navLang = (navigator.language || navigator.userLanguage || '').toLowerCase().slice(0, 2);
          if (this.supportedLanguages.includes(navLang)) {
            saved = navLang;
          }
        }
      } catch (e) {}

      try {
        const res = await fetch('/api/i18n');
        if (res.ok) {
          const data = await res.json();
          if (data && data.translations) {
            this.translations = data.translations;
          }
        }
      } catch (e) {}

      // Fallback to direct static JSON locale file if needed
      const targetLang = this.supportedLanguages.includes(saved) ? saved : 'en';
      if (!this.translations[targetLang]) {
        try {
          const resLoc = await fetch(`/static/locales/${targetLang}.json`);
          if (resLoc.ok) {
            this.translations[targetLang] = await resLoc.json();
          }
        } catch (e) {}
      }

      await this.setLanguage(targetLang, false);
    })();
    return this._initPromise;
  },

  /**
   * Sets the active language, fetches locale JSON if not yet cached, and updates DOM elements.
   */
  async setLanguage(lang, persist = true) {
    if (!this.supportedLanguages.includes(lang)) {
      lang = 'en';
    }

    if (!this.translations[lang]) {
      try {
        const res = await fetch(`/static/locales/${lang}.json`);
        if (res.ok) {
          this.translations[lang] = await res.json();
        }
      } catch (e) {}
    }

    this.currentLang = lang;
    document.documentElement.lang = lang;

    if (persist) {
      try {
        localStorage.setItem('paslood_language', lang);
      } catch (e) {}
      try {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: lang })
        }).catch(() => {});
      } catch (e) {}
    }

    this.applyTranslations();

    document.querySelectorAll('.language-selector').forEach(sel => {
      if (sel.value !== lang) sel.value = lang;
    });

    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
  },

  /**
   * Scans DOM and applies translations to data-i18n* attributes.
   */
  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      let val = this.t(key);
      if (val && val !== key) {
        if (el.parentElement && el.parentElement.querySelector('svg')) {
          val = val.replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}\uFE0F\s]+/u, '');
        }
        el.textContent = val;
      }
    });

    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      const val = this.t(key);
      if (val && val !== key) el.innerHTML = val;
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const val = this.t(key);
      if (val && val !== key) el.placeholder = val;
    });

    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const val = this.t(key);
      if (val && val !== key) el.title = val;
    });
  }
};

try {
  I18N.init();
} catch (e) {}
