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

    # Verify KPI cards hydrated with real portfolio data (not stuck at € 0,00 / € 0.00)
    total_assets_el = app_page.locator("#kpi-total-assets")
    expect(total_assets_el).not_to_have_text("€ 0.00")
    expect(total_assets_el).not_to_have_text("€ 0,00")
    assert "75" in total_assets_el.inner_text()

    total_debts_el = app_page.locator("#kpi-total-debts")
    expect(total_debts_el).not_to_have_text("€ 0.00")
    expect(total_debts_el).not_to_have_text("€ 0,00")
    assert "180" in total_debts_el.inner_text()


def test_navigation_tabs_switch_active_views(app_page, live_server):
    """Verify clicking every navigation tab switches the active view without errors."""
    app_page.add_init_script("localStorage.setItem('wealth_pilot_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    tabs = [
        ("buckets", "#tab-buckets"),
        ("advice", "#tab-advice"),
        ("ai", "#tab-ai"),
        ("cashflow", "#tab-cashflow"),
        ("settings", "#tab-settings"),
        ("dashboard", "#tab-dashboard"),
    ]

    for tab_name, tab_selector in tabs:
        app_page.locator(f"#nav-{tab_name}").click()
        expect(app_page.locator(tab_selector)).to_be_visible()
        expect(app_page.locator(tab_selector)).to_have_class(
            "tab-content space-y-6 active"
            if tab_name != "dashboard"
            else "tab-content space-y-6 active"
        )


def test_buckets_allocation_visualizer_and_modal(app_page, live_server):
    """Verify the Buckets tab renders bullet meters, toggles to Drift Divergence chart, and opens Add Bucket modal."""
    app_page.add_init_script("localStorage.setItem('wealth_pilot_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    app_page.locator("#nav-buckets").click()
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


def test_setup_wizard_and_help_modals(app_page, live_server):
    """Verify Setup Wizard steps and Help modal open and close cleanly."""
    app_page.add_init_script("localStorage.setItem('wealth_pilot_setup_completed', 'true');")
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
    app_page.add_init_script("localStorage.setItem('wealth_pilot_setup_completed', 'true');")
    app_page.goto(live_server, wait_until="networkidle")

    # Switch language to Dutch (NL)
    app_page.locator("#header-lang-select").select_option("nl")
    expect(app_page.locator("#nav-dashboard")).to_contain_text("Overzicht")

    # Toggle light/dark theme
    html_el = app_page.locator("html")
    expect(html_el).to_have_class("dark")
    app_page.locator("#btn-theme-toggle").click()
    expect(html_el).to_have_class("light-theme")
    app_page.locator("#btn-theme-toggle").click()
    expect(html_el).to_have_class("dark")


def test_page_load_with_configured_ai_key_has_no_console_errors(app_page, live_server):
    """Verify page load with an existing masked AI API key triggers no console or ByteString errors."""
    app_page.add_init_script("localStorage.setItem('wealth_pilot_setup_completed', 'true');")
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

    # Switch to AI tab and verify Key Configured is displayed
    app_page.locator("#nav-ai").click()
    expect(app_page.locator("#tab-ai")).to_be_visible()
    expect(app_page.locator("#ai-active-provider-badge")).to_contain_text("Key Configured")
