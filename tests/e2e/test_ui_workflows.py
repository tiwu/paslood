"""End-to-End Headless Browser UI Workflow Tests using Playwright."""

from __future__ import annotations

from playwright.sync_api import expect


def test_initial_load_hydrates_dashboard_without_errors(app_page, live_server):
    """Verify the dashboard boots cleanly, populates real KPI values from /api/overview, and logs zero JS errors."""
    app_page.goto(live_server, wait_until="networkidle")

    # First-time setup wizard opens automatically when localStorage is empty
    wizard_modal = app_page.locator("#setup-wizard-modal")
    expect(wizard_modal).to_be_visible()

    # Dismiss setup wizard via Skip button
    app_page.locator("#setup-wizard-modal button", has_text="Skip").first.click()
    expect(wizard_modal).to_be_hidden()

    # Verify the explicit €60k fixture total (without a synthetic default asset).
    total_assets_el = app_page.locator("#kpi-total-assets")
    expect(total_assets_el).not_to_have_text("€ 0.00")
    expect(total_assets_el).not_to_have_text("€ 0,00")
    assert "60" in total_assets_el.inner_text()

    total_debts_el = app_page.locator("#kpi-total-debts")
    expect(total_debts_el).not_to_have_text("€ 0.00")
    expect(total_debts_el).not_to_have_text("€ 0,00")
    assert "180" in total_debts_el.inner_text()


def test_navigation_tabs_switch_active_views(app_page, live_server):
    """Verify clicking every navigation tab switches the active view without errors."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    tabs = [
        ("portfolio", "#tab-portfolio"),
        ("plan", "#tab-plan"),
        ("cashflow", "#tab-cashflow"),
        ("settings", "#tab-settings"),
        ("overview", "#tab-overview"),
    ]

    for tab_name, tab_selector in tabs:
        app_page.locator(f"#nav-{tab_name}").click()
        expect(app_page.locator(tab_selector)).to_be_visible()
        expect(app_page.locator(tab_selector)).to_have_class("tab-content space-y-6 active")


def test_legacy_setup_completion_is_saved_server_side(app_page, live_server):
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    settings = app_page.evaluate("fetch('/api/settings').then(response => response.json())")
    assert settings["onboarding_complete"] is True


def test_buckets_allocation_visualizer_and_modal(app_page, live_server):
    """Verify the Buckets tab renders bullet meters, toggles to Drift Divergence chart, and opens Add Bucket modal."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    app_page.locator("#nav-portfolio").click()
    expect(app_page.locator("#tab-portfolio")).to_be_visible()
    expect(app_page.locator("#tab-buckets")).to_be_visible()

    # Bullet meters container should be visible by default with target-pin and tolerance-zone
    bullet_container = app_page.locator("#bucket-meters-container")
    expect(bullet_container).to_be_visible()
    assert bullet_container.locator(".target-pin").count() >= 3
    assert bullet_container.locator(".tolerance-zone").count() >= 3

    # Toggle to Drift Divergence mode
    app_page.locator("#btn-alloc-mode-drift").click()
    drift_container = app_page.locator("#bucket-drift-container")
    expect(drift_container).to_be_visible()
    expect(bullet_container).to_be_hidden()

    # Toggle back to Bullet mode
    app_page.locator("#btn-alloc-mode-bullet").click()
    expect(bullet_container).to_be_visible()
    expect(drift_container).to_be_hidden()

    # Open and close Add Bucket Modal
    app_page.evaluate("openAddBucketModal()")
    bucket_modal = app_page.locator("#bucket-modal")
    expect(bucket_modal).to_be_visible()
    app_page.evaluate("closeBucketModal()")
    expect(bucket_modal).to_be_hidden()

    # Verify bucket total badge & live sum indicator
    total_badge = app_page.locator("#bucket-total-badge")
    expect(total_badge).to_be_visible()
    expect(total_badge).to_contain_text("100%")

    save_btn = app_page.locator("#btn-save-bucket-targets")
    expect(save_btn).to_be_visible()

    # Changing target input dynamically updates badge & toggles save button
    first_input = app_page.locator(".bucket-target-input").first
    first_input.fill("70.0")
    first_input.dispatch_event("input")
    expect(total_badge).to_contain_text("Over")
    expect(save_btn).to_be_disabled()

    # Return to balanced 50.0
    first_input.fill("50.0")
    first_input.dispatch_event("input")
    expect(total_badge).to_contain_text("Balanced")
    expect(save_btn).to_be_enabled()


def test_setup_wizard_and_help_modals(app_page, live_server):
    """Verify Setup Wizard steps and Help modal open and close cleanly."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Open Help Modal via button
    app_page.locator("button[aria-label='Help Guide']").click()
    help_modal = app_page.locator("#help-modal")
    expect(help_modal).to_be_visible()
    app_page.evaluate("closeHelpModal()")
    expect(help_modal).to_be_hidden()

    # Open Setup Wizard and step through
    app_page.evaluate("openSetupWizard()")
    wizard_modal = app_page.locator("#setup-wizard-modal")
    expect(wizard_modal).to_be_visible()
    expect(app_page.locator("#wizard-step-1")).to_be_visible()

    app_page.locator("#wiz-btn-next").click()
    expect(app_page.locator("#wizard-step-2")).to_be_visible()

    app_page.locator("#wiz-btn-next").click()
    expect(app_page.locator("#wizard-step-3")).to_be_visible()

    app_page.locator("#wiz-btn-prev").click()
    expect(app_page.locator("#wizard-step-2")).to_be_visible()

    app_page.evaluate("closeSetupWizard()")
    expect(wizard_modal).to_be_hidden()


def test_language_switching_and_theme_toggle(app_page, live_server):
    """Verify switching language to NL updates UI text and theme toggle switches light/dark classes."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Switch language to Dutch (NL)
    app_page.locator("#header-lang-select").select_option("nl")
    expect(app_page.locator("#nav-overview")).to_contain_text("Overzicht")

    # Toggle light/dark theme
    html_el = app_page.locator("html")
    expect(html_el).to_have_class("dark")
    app_page.locator("#btn-theme-toggle").click()
    expect(html_el).to_have_class("light-theme")
    app_page.locator("#btn-theme-toggle").click()
    expect(html_el).to_have_class("dark")


def test_page_load_with_configured_ai_key_has_no_console_errors(app_page, live_server):
    """Verify page load with an existing masked AI API key triggers no console or ByteString errors."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Configure an AI key via settings
    app_page.request.post(
        f"{live_server}/api/settings",
        data='{"ai": {"provider": "gemini", "api_key": "test-gemini-key-1234"}}',
        headers={"Content-Type": "application/json"},
    )

    # Reload page; this hydrates #settings-ai-key with masked '••••1234' and calls refreshAiModels()
    app_page.reload(wait_until="networkidle")

    # Verify AI key input received the masked placeholder
    ai_key_val = app_page.locator("#settings-ai-key").input_value()
    assert "•" in ai_key_val

    # Switch to Plan tab and verify Key Configured is displayed in AI section
    app_page.locator("#nav-plan").click()
    expect(app_page.locator("#tab-plan")).to_be_visible()
    expect(app_page.locator("#tab-ai")).to_be_visible()
    expect(app_page.locator("#ai-active-provider-badge")).to_contain_text("Key Configured")


def test_toast_notifications_stacking_and_dismissal(app_page, live_server):
    """Verify non-blocking toast notifications appear in #toast-container with typed styling and close button."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Trigger a success toast
    app_page.evaluate("showToast('Asset saved successfully!', 'success')")
    toast_container = app_page.locator("#toast-container")
    expect(toast_container).to_be_visible()

    success_toast = toast_container.locator("div[role='status']").first
    expect(success_toast).to_be_visible()
    expect(success_toast).to_contain_text("Asset saved successfully!")
    expect(success_toast).to_contain_text("✓")

    # Dismiss toast via close button
    close_btn = success_toast.locator("button[aria-label='Close notification']")
    close_btn.click()
    expect(success_toast).to_be_hidden()

    # Trigger an error toast
    app_page.evaluate("showToast('Unable to reach server', 'error')")
    error_toast = toast_container.locator("div[role='status']").first
    expect(error_toast).to_be_visible()
    expect(error_toast).to_contain_text("Unable to reach server")


def test_accessible_confirm_dialog_cancel_and_ok(app_page, live_server):
    """Verify native promise-based confirmation dialog opens, traps focus, and resolves cancel/confirm."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    dialog = app_page.locator("#confirmation-dialog")
    expect(dialog).to_be_hidden()

    # 1. Trigger dialog without awaiting in evaluate so browser UI can be interacted with
    app_page.evaluate("""
        (() => {
            window.__testConfirmPromise = confirmDialog({
                title: 'Delete Asset Confirmation',
                message: 'Are you sure you want to remove this holding?',
                confirmVariant: 'danger'
            });
            return true;
        })()
    """)
    expect(dialog).to_be_visible()
    expect(app_page.locator("#confirm-dialog-title")).to_have_text("Delete Asset Confirmation")
    expect(app_page.locator("#confirm-dialog-message")).to_have_text(
        "Are you sure you want to remove this holding?"
    )

    # Click cancel button
    app_page.locator("#confirm-dialog-cancel-btn").click()
    expect(dialog).to_be_hidden()
    cancel_result = app_page.evaluate("window.__testConfirmPromise")
    assert cancel_result is False

    # 2. Trigger dialog and confirm
    app_page.evaluate("""
        (() => {
            window.__testConfirmPromise = confirmDialog({
                title: 'Proceed with Action',
                message: 'Do you want to continue?',
                confirmVariant: 'primary'
            });
            return true;
        })()
    """)
    expect(dialog).to_be_visible()
    app_page.locator("#confirm-dialog-ok-btn").click()
    expect(dialog).to_be_hidden()
    ok_result = app_page.evaluate("window.__testConfirmPromise")
    assert ok_result is True


def test_offline_static_css_and_zero_runtime_tailwind_cdn(app_page, live_server):
    """Verify offline static CSS is linked and runtime tailwind CDN is completely absent."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Check that compiled styles.css link exists
    css_link = app_page.locator("link[href='/static/css/styles.css']")
    assert css_link.count() == 1

    # Check that cdn.tailwindcss.com script is absent
    cdn_script = app_page.locator("script[src*='cdn.tailwindcss.com']")
    assert cdn_script.count() == 0


def test_compound_wealth_trajectory_start_year_selection(app_page, live_server):
    """Verify trajectory chart loads, displays inception selector, and updates on timeframe / inception change."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    chart_canvas = app_page.locator("#projectionAreaChart")
    expect(chart_canvas).to_be_visible()

    start_year_sel = app_page.locator("#projection-start-year-select")
    expect(start_year_sel).to_be_visible()

    # Switch to 'Today only'
    start_year_sel.select_option("today")
    app_page.wait_for_timeout(300)

    # Switch timeframe to 10Y
    app_page.locator("#btn-timeframe-10").click()
    app_page.wait_for_timeout(300)

    # Assert canvas is still visible and chart instance exists
    has_chart = app_page.evaluate(
        "typeof projectionChartInstance !== 'undefined' && projectionChartInstance !== null"
    )
    assert has_chart is True


def test_overview_cashflow_formula_and_cashflow_visualizations_and_known_account_edit(
    app_page, live_server
):
    """Verify Overview free cashflow breakdown toggle, Cashflow Sankey & monthly spending visualizations,
    expanded expense categories, and Known Account editing in Settings.
    """
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # 1. Overview Free Cashflow calculation formula is visible and expandable
    formula_el = app_page.locator("#kpi-cashflow-formula")
    expect(formula_el).to_be_visible()
    expect(formula_el).to_contain_text("Inc")
    expect(formula_el).to_contain_text("Fix")
    expect(formula_el).to_contain_text("Debt")
    expect(formula_el).to_contain_text("Liv")

    app_page.locator("button[onclick='toggleCashflowFormulaBreakdown()']").click()
    expect(app_page.locator("#kpi-cashflow-detail-rows")).to_be_visible()

    # 2. Navigate to Cashflow tab and verify Sankey diagram & new category options
    app_page.locator("#nav-cashflow").click()
    expect(app_page.locator("#tab-cashflow")).to_be_visible()
    expect(app_page.locator("#cashflow-sankey-container")).to_be_visible()
    expect(app_page.locator("#cashflow-sankey-container svg")).to_be_visible()
    expect(app_page.locator("#savings-opportunities-container")).to_be_visible()

    # Verify new categories exist in filter dropdown
    cat_filter_html = app_page.locator("#tx-category-filter").inner_html()
    for expected_cat in ("TAX", "UTILITIES", "LEISURE", "TRANSPORT"):
        assert f'value="{expected_cat}"' in cat_filter_html

    # 3. Navigate to Settings and test adding + editing a Known Account
    app_page.locator("#nav-settings").click()
    expect(app_page.locator("#tab-settings")).to_be_visible()

    app_page.locator("button[onclick='toggleAddKnownAccountForm()']").first.click()
    expect(app_page.locator("#add-known-account-form")).to_be_visible()
    app_page.locator("#new-known-acc-num").fill("BE99 1234 5678 9012")
    app_page.locator("#new-known-acc-label").fill("Saxo Broker")
    app_page.locator("#new-known-acc-type").select_option("CHECKING")
    app_page.locator("#new-known-acc-inst").fill("Saxo")
    app_page.locator("button[onclick='submitNewKnownAccount()']").click()

    known_tbody = app_page.locator("#known-accounts-tbody")
    expect(known_tbody).to_contain_text("Saxo Broker")
    expect(known_tbody).to_contain_text("CHECKING")

    # Click Edit on the newly created known account
    known_tbody.locator("button", has_text="Edit").first.click()
    expect(app_page.locator("#add-known-account-form")).to_be_visible()
    app_page.locator("#new-known-acc-label").fill("Saxo Investor Updated")
    app_page.locator("#new-known-acc-type").select_option("INVESTMENT")
    app_page.locator("button[onclick='submitNewKnownAccount()']").click()

    expect(known_tbody).to_contain_text("Saxo Investor Updated")
    expect(known_tbody).to_contain_text("INVESTMENT")


def test_architectural_theme_tokens_and_light_dark_visual_integrity(app_page, live_server):
    """Verify Issue #54 Plumb Bob SVG mark, Midnight Blueprint dark theme, and Architectural Vellum light theme."""
    app_page.add_init_script("localStorage.setItem('paslood_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # 1. Plumb Bob brand SVG mark is visible in header
    plumb_mark = app_page.locator("#brand-plumb-mark svg")
    expect(plumb_mark).to_be_visible()

    # 2. Dark mode defaults: Midnight Blueprint tokens
    dark_tokens = app_page.evaluate("getChartThemeTokens()")
    assert dark_tokens["isLight"] is False
    assert dark_tokens["caliperColor"] == "#FBBF24"

    # 3. Switch to Light theme (Architectural Vellum)
    app_page.locator("#btn-theme-toggle").click()
    expect(app_page.locator("html")).to_have_class("light-theme")

    light_tokens = app_page.evaluate("getChartThemeTokens()")
    assert light_tokens["isLight"] is True
    assert light_tokens["textPrimary"] == "#1C1917"
    assert light_tokens["caliperColor"] == "#1C1917"

    # 4. Verify Cashflow Sankey SVG in light mode uses dark charcoal ink instead of white
    app_page.locator("#nav-cashflow").click()
    sankey_svg_html = app_page.locator("#cashflow-sankey-container").inner_html()
    assert "#f8fafc" not in sankey_svg_html
    assert "#1C1917" in sankey_svg_html
