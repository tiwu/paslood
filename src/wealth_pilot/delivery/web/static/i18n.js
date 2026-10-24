/**
 * Wealth Pilot Internationalization (i18n) Engine
 * Multi-language support: English (en), Dutch (nl), French (fr), German (de).
 * Tailored for Belgian and European financial terminology.
 */

const I18N = {
  currentLang: 'en',
  supportedLanguages: ['en', 'nl', 'fr', 'de'],
  translations: {
    en: {
      nav: {
        explore: "Explore",
        manage: "Manage",
        overview: "📊 Overview",
        buckets: "🪣 Buckets",
        guidance: "💡 Guidance",
        ai: "🤖 AI Advisor",
        cashflow: "🏦 Data & Assets",
        settings: "⚙️ Settings",
        setup: "🚀 Setup",
        docs: "📖 Docs",
        help: "Help Guide"
      },
      overview: {
        title: "Strategic Overview & Balance Sheet",
        subtitle: "Real-time macro allocation, asset drift, and compound wealth trajectory.",
        net_worth: "Net Worth",
        liquid_assets: "Liquid Assets",
        invested_assets: "Invested Assets",
        total_liabilities: "Total Liabilities",
        monthly_surplus: "Monthly Surplus",
        exclude_property: "Exclude Property / Real Estate",
        portfolio_allocation: "Macro Asset Allocation",
        wealth_trajectory: "Compound Wealth Trajectory",
        bucket_breakdown: "Strategic Buckets Breakdown",
        bucket_name: "Bucket",
        target_weight: "Target %",
        actual_weight: "Actual %",
        diff_weight: "Drift %",
        value: "Value",
        status: "Status",
        actions: "Actions"
      },
      buckets: {
        title: "Bucket Targets & Rebalancing Drift",
        subtitle: "Set macro allocation targets and maintain portfolio balance with buy-only cashflow injection.",
        add_bucket: "+ Add New Bucket",
        drift_tolerance: "Drift Tolerance",
        rebalance_rule: "Buy-Only Rebalancing Strategy",
        underweight: "Underweight (Buy)",
        overweight: "Overweight (Hold)",
        balanced: "Balanced"
      },
      guidance: {
        title: "Strategic Financial Guidance",
        subtitle: "Automated debt payoff, tax optimization, and monthly contribution allocation.",
        priority_queue: "Guidance Priority Queue",
        contribution_rebalancer: "Monthly Contribution Allocator",
        contribution_desc: "Enter your available monthly investment cashflow to see exactly how to distribute it to minimize drift.",
        deposit_label: "Available Monthly Deposit (€)",
        calculate_orders: "Calculate Optimal Buy Orders",
        tax_title: "Belgian 2026 Capital Gains Tax Optimization",
        tax_desc: "10% capital gains tax above €10,000 annual exemption benchmarked against 31 Dec 2025.",
        loan_amortization: "Mortgage & Loan Amortization Estimator",
        loan_desc: "Simulate early repayments, interest savings, and payoff timeline acceleration."
      },
      cashflow: {
        title: "Data Ingestion & Asset Management",
        subtitle: "Manage manual accounts, real estate, debts, and import bank/broker statements.",
        assets_tab: "Assets & Property",
        liabilities_tab: "Liabilities & Mortgages",
        transactions_tab: "Transactions & Ingestion",
        add_asset: "+ Add Asset",
        add_liability: "+ Add Loan / Debt",
        import_kbc: "Import KBC CSV",
        import_generic: "Import Generic CSV"
      },
      ai: {
        title: "Strategic AI Wealth Advisor",
        subtitle: "Interactive wealth advisory powered by universal multi-provider LLMs or local rule engine.",
        ask_button: "Ask Advisor",
        prompt_placeholder: "Ask about your portfolio, rebalancing, or financial freedom milestones..."
      },
      settings: {
        title: "System Configuration & Integrations",
        pdt_title: "Portfolio Dividend Tracker (PDT) MCP",
        mcp_title: "Registered MCP Servers",
        ai_title: "AI Financial Advisor Configuration",
        language_title: "Language & Localization",
        language_desc: "Choose your preferred interface language. Wealth Pilot provides native Dutch support for the Belgian market.",
        language_label: "Interface Language"
      },
      common: {
        save: "Save",
        cancel: "Cancel",
        delete: "Delete",
        edit: "Edit",
        close: "Close",
        loading: "Loading...",
        connected: "Connected",
        disconnected: "Not Connected",
        success: "Success",
        error: "Error",
        theme_light: "Light",
        theme_dark: "Dark"
      }
    },
    nl: {
      nav: {
        explore: "Verkennen",
        manage: "Beheren",
        overview: "📊 Overzicht",
        buckets: "🪣 Buckets",
        guidance: "💡 Advies",
        ai: "🤖 AI Adviseur",
        cashflow: "🏦 Gegevens & Activa",
        settings: "⚙️ Instellingen",
        setup: "🚀 Installatie",
        docs: "📖 Documentatie",
        help: "Helpwijzer"
      },
      overview: {
        title: "Strategisch Overzicht & Balans",
        subtitle: "Realtime macro-allocatie, portefeuille-afwijking en samengestelde vermogenstrajecten.",
        net_worth: "Nettowaarde",
        liquid_assets: "Liquide Activa",
        invested_assets: "Belegd Vermogen",
        total_liabilities: "Totale Schulden",
        monthly_surplus: "Maandelijks Overschot",
        exclude_property: "Vastgoed / Onroerend goed uitsluiten",
        portfolio_allocation: "Macro Activa Allocatie",
        wealth_trajectory: "Samengestelde Vermogensgroei",
        bucket_breakdown: "Overzicht Strategische Buckets",
        bucket_name: "Bucket",
        target_weight: "Doel %",
        actual_weight: "Huidig %",
        diff_weight: "Afwijking %",
        value: "Waarde",
        status: "Status",
        actions: "Acties"
      },
      buckets: {
        title: "Bucket Doelen & Herbalanceringsafwijking",
        subtitle: "Stel macro-allocatiedoelen in en behoud portefeuillebalans via buy-only bijstortingen.",
        add_bucket: "+ Nieuwe Bucket Toevoegen",
        drift_tolerance: "Afwijkingstolerantie",
        rebalance_rule: "Buy-Only Herbalanceringsstrategie",
        underweight: "Onderwogen (Kopen)",
        overweight: "Overwogen (Aanhouden)",
        balanced: "In balans"
      },
      guidance: {
        title: "Strategisch Financieel Advies",
        subtitle: "Geautomatiseerde schuldaflossing, belastingoptimalisatie en maandelijkse inlegverdeling.",
        priority_queue: "Prioriteitenwachtrij Adviezen",
        contribution_rebalancer: "Maandelijkse Inleg Herbalancering",
        contribution_desc: "Voer uw beschikbare maandelijkse inleg in om te zien hoe u deze optimaal verdeelt om afwijkingen te minimaliseren.",
        deposit_label: "Beschikbare Maandelijkse Inleg (€)",
        calculate_orders: "Bereken Optimale Aankooporders",
        tax_title: "Belgische Meerwaardebelasting 2026 Optimalisatie",
        tax_desc: "10% meerwaardebelasting boven de jaarlijkse vrijstelling van €10.000 met referentiekoers 31 dec 2025.",
        loan_amortization: "Hypotheek & Lening Aflossingscalculator",
        loan_desc: "Simuleer vervroegde aflossingen, rentebesparingen en versnelde looptijd."
      },
      cashflow: {
        title: "Gegevensinvoer & Vermogensbeheer",
        subtitle: "Beheer handmatige rekeningen, vastgoed, schulden en importeer bankafschriften.",
        assets_tab: "Activa & Vastgoed",
        liabilities_tab: "Schulden & Hypotheken",
        transactions_tab: "Transacties & Import",
        add_asset: "+ Activa Toevoegen",
        add_liability: "+ Lening / Schuld Toevoegen",
        import_kbc: "Importeer KBC CSV",
        import_generic: "Importeer Algemene CSV"
      },
      ai: {
        title: "Strategische AI Vermogensadviseur",
        subtitle: "Interactief vermogensadvies aangedreven door LLM-modellen of de lokale regelmotor.",
        ask_button: "Vraag Adviseur",
        prompt_placeholder: "Stel een vraag over uw portefeuille, herbalancering of financiële mijlpalen..."
      },
      settings: {
        title: "Systeemconfiguratie & Integraties",
        pdt_title: "Portfolio Dividend Tracker (PDT) MCP",
        mcp_title: "Geregistreerde MCP-servers",
        ai_title: "Configuratie AI Vermogensadviseur",
        language_title: "Taal & Lokalisatie",
        language_desc: "Kies uw voorkeurstaal voor de interface. Wealth Pilot biedt native Nederlandse ondersteuning voor de Belgische markt.",
        language_label: "Interfacetaal"
      },
      common: {
        save: "Opslaan",
        cancel: "Annuleren",
        delete: "Verwijderen",
        edit: "Bewerken",
        close: "Sluiten",
        loading: "Laden...",
        connected: "Verbonden",
        disconnected: "Niet Verbonden",
        success: "Succes",
        error: "Fout",
        theme_light: "Licht",
        theme_dark: "Donker"
      }
    },
    fr: {
      nav: {
        explore: "Explorer",
        manage: "Gérer",
        overview: "📊 Aperçu",
        buckets: "🪣 Portefeuilles",
        guidance: "💡 Conseils",
        ai: "🤖 Conseiller IA",
        cashflow: "🏦 Données & Actifs",
        settings: "⚙️ Paramètres",
        setup: "🚀 Configuration",
        docs: "📖 Documentation",
        help: "Guide d'aide"
      },
      overview: {
        title: "Aperçu Stratégique & Bilan",
        subtitle: "Allocation macro en temps réel, dérive des actifs et trajectoire de patrimoine.",
        net_worth: "Valeur Nette",
        liquid_assets: "Actifs Liquides",
        invested_assets: "Actifs Investis",
        total_liabilities: "Passif Total",
        monthly_surplus: "Surplus Mensuel",
        exclude_property: "Exclure Biens Immobiliers",
        portfolio_allocation: "Allocation Macro des Actifs",
        wealth_trajectory: "Trajectoire de Richesse Composée",
        bucket_breakdown: "Répartition des Portefeuilles",
        bucket_name: "Portefeuille",
        target_weight: "Cible %",
        actual_weight: "Actuel %",
        diff_weight: "Dérive %",
        value: "Valeur",
        status: "Statut",
        actions: "Actions"
      },
      buckets: {
        title: "Cibles & Dérive de Rééquilibrage",
        subtitle: "Définissez des objectifs d'allocation macro et maintenez l'équilibre par réinjection d'épargne.",
        add_bucket: "+ Ajouter un Portefeuille",
        drift_tolerance: "Tolérance de Dérive",
        rebalance_rule: "Stratégie de Rééquilibrage Buy-Only",
        underweight: "Sous-pondéré (Acheter)",
        overweight: "Surpondéré (Conserver)",
        balanced: "Équilibré"
      },
      guidance: {
        title: "Conseils Financiers Stratégiques",
        subtitle: "Remboursement de dette automatisé, optimisation fiscale et allocation mensuelle.",
        priority_queue: "File de Priorités des Conseils",
        contribution_rebalancer: "Rééquilibreur d'Épargne Mensuelle",
        contribution_desc: "Indiquez votre épargne mensuelle disponible pour calculer la répartition optimale.",
        deposit_label: "Dépôt Mensuel Disponible (€)",
        calculate_orders: "Calculer les Ordres d'Achat",
        tax_title: "Optimisation Fiscale Plus-Values Belges 2026",
        tax_desc: "Taxe de 10% sur les plus-values au-delà de 10.000 € d'exemption annuelle.",
        loan_amortization: "Simulateur d'Amortissement de Prêt",
        loan_desc: "Simulez des remboursements anticipés et économies d'intérêts."
      },
      cashflow: {
        title: "Gestion des Données & Actifs",
        subtitle: "Gérez vos comptes manuels, biens immobiliers, dettes et importez vos relevés bancaires.",
        assets_tab: "Actifs & Biens",
        liabilities_tab: "Passifs & Prêts",
        transactions_tab: "Transactions & Importation",
        add_asset: "+ Ajouter un Actif",
        add_liability: "+ Ajouter un Prêt",
        import_kbc: "Importer CSV KBC",
        import_generic: "Importer CSV Générique"
      },
      ai: {
        title: "Conseiller Patrimonial Stratégique IA",
        subtitle: "Conseils interactifs alimentés par les modèles universels ou le moteur local de règles.",
        ask_button: "Demander au Conseiller",
        prompt_placeholder: "Posez une question sur votre portefeuille ou votre liberté financière..."
      },
      settings: {
        title: "Configuration & Intégrations",
        pdt_title: "Portfolio Dividend Tracker (PDT) MCP",
        mcp_title: "Serveurs MCP Enregistrés",
        ai_title: "Configuration du Conseiller IA",
        language_title: "Langue & Régionalisation",
        language_desc: "Choisissez la langue de l'interface. Prise en charge native pour le marché belge.",
        language_label: "Langue de l'Interface"
      },
      common: {
        save: "Enregistrer",
        cancel: "Annuler",
        delete: "Supprimer",
        edit: "Modifier",
        close: "Fermer",
        loading: "Chargement...",
        connected: "Connecté",
        disconnected: "Non Connecté",
        success: "Succès",
        error: "Erreur",
        theme_light: "Clair",
        theme_dark: "Sombre"
      }
    },
    de: {
      nav: {
        explore: "Erkunden",
        manage: "Verwalten",
        overview: "📊 Übersicht",
        buckets: "🪣 Segmente",
        guidance: "💡 Leitfaden",
        ai: "🤖 KI-Berater",
        cashflow: "🏦 Daten & Vermögen",
        settings: "⚙️ Einstellungen",
        setup: "🚀 Einrichtung",
        docs: "📖 Dokumentation",
        help: "Hilfe"
      },
      overview: {
        title: "Strategische Übersicht & Bilanz",
        subtitle: "Echtzeit-Makroallokation, Portfolio-Abweichung und Zinseszins-Vermögenskurve.",
        net_worth: "Nettovermögen",
        liquid_assets: "Liquide Mittel",
        invested_assets: "Investiertes Vermögen",
        total_liabilities: "Gesamtverbindlichkeiten",
        monthly_surplus: "Monatlicher Überschuss",
        exclude_property: "Immobilien ausschließen",
        portfolio_allocation: "Makro-Vermögensallokation",
        wealth_trajectory: "Vermögensentwicklung",
        bucket_breakdown: "Übersicht Strategische Segmente",
        bucket_name: "Segment",
        target_weight: "Ziel %",
        actual_weight: "Aktuell %",
        diff_weight: "Drift %",
        value: "Wert",
        status: "Status",
        actions: "Aktionen"
      },
      buckets: {
        title: "Segment-Ziele & Rebalancing-Drift",
        subtitle: "Setzen Sie Makro-Ziele und halten Sie das Gleichgewicht durch buy-only Sparraten.",
        add_bucket: "+ Neues Segment hinzufügen",
        drift_tolerance: "Drift-Toleranz",
        rebalance_rule: "Buy-Only Rebalancing-Strategie",
        underweight: "Untergewichtet (Kaufen)",
        overweight: "Übergewichtet (Halten)",
        balanced: "Ausgewogen"
      },
      guidance: {
        title: "Strategischer Finanzleitfaden",
        subtitle: "Automatisierte Schuldentilgung, Steueroptimierung und monatliche Sparratenaufteilung.",
        priority_queue: "Prioritäten-Warteschlange",
        contribution_rebalancer: "Monatlicher Sparraten-Rebalancer",
        contribution_desc: "Geben Sie Ihre monatliche Sparrate ein, um die optimale Aufteilung zur Minimierung der Drift zu berechnen.",
        deposit_label: "Verfügbare monatliche Einzahlung (€)",
        calculate_orders: "Optimale Kaufaufträge berechnen",
        tax_title: "Belgische Kapitalertragsteuer-Optimierung 2026",
        tax_desc: "10% Steuer auf Kapitalerträge über 10.000 € jährlicher Freibetrag.",
        loan_amortization: "Kredittilgungs-Rechner",
        loan_desc: "Simulieren Sie Sondertilgungen und Zinsersparnisse."
      },
      cashflow: {
        title: "Datenerfassung & Vermögensverwaltung",
        subtitle: "Verwalten Sie manuelle Konten, Immobilien, Verbindlichkeiten und importieren Sie Kontoauszüge.",
        assets_tab: "Vermögenswerte & Immobilien",
        liabilities_tab: "Verbindlichkeiten & Darlehen",
        transactions_tab: "Transaktionen & Import",
        add_asset: "+ Vermögenswert hinzufügen",
        add_liability: "+ Darlehen hinzufügen",
        import_kbc: "KBC CSV importieren",
        import_generic: "Generisches CSV importieren"
      },
      ai: {
        title: "Strategischer KI-Vermögensberater",
        subtitle: "Interaktive Vermögensberatung mit LLM-Modellen oder lokaler Regel-Engine.",
        ask_button: "Berater fragen",
        prompt_placeholder: "Fragen Sie zu Ihrem Portfolio, Rebalancing oder finanziellen Zielen..."
      },
      settings: {
        title: "Systemkonfiguration & Integrationen",
        pdt_title: "Portfolio Dividend Tracker (PDT) MCP",
        mcp_title: "Registrierte MCP-Server",
        ai_title: "KI-Finanzberater Konfiguration",
        language_title: "Sprache & Lokalisierung",
        language_desc: "Wählen Sie Ihre bevorzugte Oberflächensprache für den belgischen Markt.",
        language_label: "Oberflächensprache"
      },
      common: {
        save: "Speichern",
        cancel: "Abbrechen",
        delete: "Löschen",
        edit: "Bearbeiten",
        close: "Schließen",
        loading: "Laden...",
        connected: "Verbunden",
        disconnected: "Nicht Verbunden",
        success: "Erfolg",
        error: "Fehler",
        theme_light: "Hell",
        theme_dark: "Dunkel"
      }
    }
  },

  /**
   * Translates a dot-notated key (e.g., 'nav.overview') with fallback.
   */
  t(key, fallback = '') {
    const lang = this.currentLang;
    const dict = this.translations[lang] || this.translations['en'];
    const parts = key.split('.');
    let cur = dict;
    for (const part of parts) {
      if (cur && typeof cur === 'object' && part in cur) {
        cur = cur[part];
      } else {
        cur = null;
        break;
      }
    }
    if (cur !== null && cur !== undefined) {
      return cur;
    }
    // Fallback to English if not current
    if (lang !== 'en') {
      let enCur = this.translations['en'];
      for (const part of parts) {
        if (enCur && typeof enCur === 'object' && part in enCur) {
          enCur = enCur[part];
        } else {
          enCur = null;
          break;
        }
      }
      if (enCur !== null && enCur !== undefined) return enCur;
    }
    return fallback || key;
  },

  /**
   * Initializes i18n from localStorage or browser preferences.
   */
  init() {
    let saved = 'en';
    try {
      saved = localStorage.getItem('wealth_pilot_language');
      if (!saved) {
        const navLang = (navigator.language || navigator.userLanguage || '').toLowerCase().slice(0, 2);
        if (this.supportedLanguages.includes(navLang)) {
          saved = navLang;
        }
      }
    } catch (e) {}

    this.setLanguage(saved || 'en', false);
  },

  /**
   * Sets the active language and updates DOM elements.
   */
  setLanguage(lang, persist = true) {
    if (!this.supportedLanguages.includes(lang)) {
      lang = 'en';
    }
    this.currentLang = lang;
    document.documentElement.lang = lang;

    if (persist) {
      try {
        localStorage.setItem('wealth_pilot_language', lang);
      } catch (e) {}
      // Sync to backend settings silently
      try {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: lang })
        }).catch(() => {});
      } catch (e) {}
    }

    this.applyTranslations();

    // Update any select widgets on the page
    document.querySelectorAll('.language-selector').forEach(sel => {
      if (sel.value !== lang) sel.value = lang;
    });

    // Dispatch event so other components / charts can re-render with localized labels
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
  },

  /**
   * Scans DOM and applies translations to data-i18n attributes.
   */
  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = this.t(key);
      if (val) el.textContent = val;
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const val = this.t(key);
      if (val) el.placeholder = val;
    });

    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const val = this.t(key);
      if (val) el.title = val;
    });
  }
};

// Initialize immediately when script is loaded
try {
  I18N.init();
} catch (e) {}
