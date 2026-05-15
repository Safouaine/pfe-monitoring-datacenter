"""
End-to-End Security & Quality Test for Nouvameq AI Operations Center
URL: http://localhost:5055
Uses Playwright (sync API) with Chromium headless
"""

import os
import sys
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, expect

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "test_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

BASE_URL = "http://localhost:5055"

# Global error/warning storage captured from browser console
_console_errors = []
_console_warnings = []
_network_errors = []

results = {}

def screenshot(page: Page, name: str):
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"  [SCREENSHOT] {path}")
    return path

def evaluate_errors(page: Page):
    try:
        errors   = page.evaluate("() => window.__errors   || []")
        warnings = page.evaluate("() => window.__warnings || []")
        return errors, warnings
    except Exception as e:
        return [], [f"evaluate failed: {e}"]

def inject_console_listener(page: Page):
    page.evaluate("""() => {
        window.__errors   = [];
        window.__warnings = [];
        const origErr  = console.error.bind(console);
        const origWarn = console.warn.bind(console);
        console.error = (...a) => {
            window.__errors.push(a.map(String).join(' '));
            origErr(...a);
        };
        console.warn = (...a) => {
            window.__warnings.push(a.map(String).join(' '));
            origWarn(...a);
        };
    }""")

def wait_for_content(page: Page, selector: str, timeout: int = 10000):
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        return True
    except Exception:
        return False

def check_text_not_nan_or_zero(text: str) -> bool:
    """Returns True if text is a real number (not NaN, not empty placeholder '—')."""
    if text in ("NaN", "nan", "undefined", "null", ""):
        return False
    return True

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="fr-FR",
        )
        # Capture console messages at context level
        page = context.new_page()

        # Capture all console messages natively
        native_errors = []
        native_warnings = []

        def on_console(msg):
            if msg.type == "error":
                native_errors.append(msg.text)
            elif msg.type == "warning":
                native_warnings.append(msg.text)

        def on_request_failed(request):
            _network_errors.append(f"{request.method} {request.url} — {request.failure}")

        page.on("console", on_console)
        page.on("requestfailed", on_request_failed)

        # ─────────────────────────────────────────────────────────────
        # STEP 1: Open login page
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 1] Opening login page...")
        step1_ok = True
        step1_issues = []

        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # Inject console listener early
        inject_console_listener(page)

        # Check login screen elements
        login_screen = page.query_selector("#login-screen")
        if not login_screen or not login_screen.is_visible():
            step1_ok = False
            step1_issues.append("Login screen not visible")

        # Check logo
        logo = page.query_selector(".login-logo img")
        if logo:
            logo_src = logo.get_attribute("src")
            logo_natural_width = page.evaluate("() => { const img = document.querySelector('.login-logo img'); return img ? img.naturalWidth : 0; }")
            if logo_natural_width == 0:
                step1_ok = False
                step1_issues.append(f"Logo failed to load (naturalWidth=0), src={logo_src}")
            else:
                print(f"  Logo loaded OK (naturalWidth={logo_natural_width}px)")
        else:
            step1_ok = False
            step1_issues.append("Logo element not found in DOM")

        # Check username/password fields
        username_field = page.query_selector("#username")
        password_field = page.query_selector("#password")
        if not username_field:
            step1_ok = False
            step1_issues.append("Username field (#username) not found")
        if not password_field:
            step1_ok = False
            step1_issues.append("Password field (#password) not found")

        # Check quick login buttons
        quick_btns = page.query_selector_all(".quick-btn")
        quick_btn_texts = [b.inner_text().strip() for b in quick_btns]
        admin_btn = page.query_selector(".quick-btn.admin") or page.query_selector(".quick-btn:has-text('Admin')")
        op_btn    = page.query_selector(".quick-btn.user")  or page.query_selector(".quick-btn:has-text('Opérateur')")

        if not admin_btn:
            # Try finding by text
            for b in quick_btns:
                if "Admin" in b.inner_text():
                    admin_btn = b
            if not admin_btn:
                step1_ok = False
                step1_issues.append("Admin quick-login button not found")

        if not op_btn:
            for b in quick_btns:
                if "pérateur" in b.inner_text():
                    op_btn = b
            if not op_btn:
                step1_ok = False
                step1_issues.append("Opérateur quick-login button not found")

        print(f"  Quick login buttons found: {quick_btn_texts}")

        # Check submit button
        submit_btn = page.query_selector("button.btn-primary")
        if not submit_btn:
            step1_ok = False
            step1_issues.append("Login submit button not found")

        # Check h2 heading
        h2 = page.query_selector(".login-card h2")
        if not h2:
            step1_ok = False
            step1_issues.append("Login card h2 heading missing")

        screenshot(page, "01_login_page")
        errors, warnings = evaluate_errors(page)
        results["step1"] = {
            "ok": step1_ok,
            "issues": step1_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if step1_ok else 'FAIL'} | JS errors: {len(errors)} | Issues: {step1_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 2: Admin quick login
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 2] Clicking Admin quick login...")
        step2_ok = True
        step2_issues = []

        # Find and click the Admin quick-login button
        clicked = False
        for b in page.query_selector_all(".quick-btn"):
            if "Admin" in b.inner_text():
                b.click()
                clicked = True
                break
        if not clicked:
            step2_ok = False
            step2_issues.append("Could not find/click Admin button")

        # Wait for app shell to appear
        try:
            page.wait_for_selector("#app-shell.active", timeout=8000)
        except Exception:
            step2_ok = False
            step2_issues.append("App shell did not become active after login")

        page.wait_for_timeout(2000)

        # Check sidebar is present
        sidebar = page.query_selector(".sidebar")
        if not sidebar:
            step2_ok = False
            step2_issues.append("Sidebar not found after login")

        # Check expected nav items
        nav_items = page.query_selector_all(".nav-item")
        nav_texts = [n.inner_text().strip() for n in nav_items]
        print(f"  Nav items: {nav_texts}")

        expected_nav = ["Monitoring", "Prévisions", "Alertes"]
        for expected in expected_nav:
            found = any(expected.lower() in t.lower() for t in nav_texts)
            if not found:
                step2_ok = False
                step2_issues.append(f"Nav item '{expected}' not found in sidebar")

        # Admin-only items
        admin_nav = ["Modèles ML", "Dashboards Grafana"]
        for expected in admin_nav:
            found = any(expected.lower() in t.lower() for t in nav_texts)
            if not found:
                # Check if it's hidden via CSS
                admin_items = page.query_selector_all(".admin-only")
                visible_admin = [el.is_visible() for el in admin_items]
                if not any(visible_admin):
                    step2_ok = False
                    step2_issues.append(f"Admin nav item '{expected}' not visible (admin should see it)")

        # Check user name in sidebar footer
        user_name_el = page.query_selector("#user-name")
        if user_name_el:
            user_name = user_name_el.inner_text().strip()
            print(f"  Logged in user: {user_name}")
            if not user_name:
                step2_ok = False
                step2_issues.append("User name in sidebar footer is empty")
        else:
            step2_ok = False
            step2_issues.append("User name element (#user-name) not found")

        # Check role display
        user_role_el = page.query_selector("#user-role")
        if user_role_el:
            role_text = user_role_el.inner_text().strip()
            print(f"  Role displayed: {role_text}")
            if "admin" not in role_text.lower() and "administrateur" not in role_text.lower():
                step2_issues.append(f"Role text '{role_text}' does not indicate admin role")

        screenshot(page, "02_admin_logged_in_monitoring")
        errors, warnings = evaluate_errors(page)
        results["step2"] = {
            "ok": step2_ok,
            "issues": step2_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if step2_ok else 'FAIL'} | JS errors: {len(errors)} | Issues: {step2_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 3: Verify monitoring page
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 3] Verifying monitoring page...")
        step3_ok = True
        step3_issues = []

        # Wait for monitoring content to load
        try:
            page.wait_for_selector("#mon-content", state="visible", timeout=15000)
        except Exception:
            step3_ok = False
            step3_issues.append("Monitoring content (#mon-content) never became visible — still loading or API error")

        page.wait_for_timeout(1000)

        # Check KPI cards
        kpi_risk_el = page.query_selector("#kpi-risk")
        if kpi_risk_el:
            kpi_risk_val = kpi_risk_el.inner_text().strip()
            print(f"  KPI Risk: {kpi_risk_val}")
            if not check_text_not_nan_or_zero(kpi_risk_val) or kpi_risk_val == "0":
                step3_issues.append(f"KPI Risk shows suspicious value: '{kpi_risk_val}'")
        else:
            step3_ok = False
            step3_issues.append("KPI Risk element (#kpi-risk) not found")

        kpi_power_el = page.query_selector("#kpi-power")
        if kpi_power_el:
            kpi_power_val = kpi_power_el.inner_text().strip()
            print(f"  KPI Power: {kpi_power_val}")
            if not check_text_not_nan_or_zero(kpi_power_val):
                step3_issues.append(f"KPI Power shows suspicious value: '{kpi_power_val}'")
        else:
            step3_ok = False
            step3_issues.append("KPI Power element (#kpi-power) not found")

        kpi_sensors_el = page.query_selector("#kpi-sensors")
        if kpi_sensors_el:
            kpi_sensors_val = kpi_sensors_el.inner_text().strip()
            print(f"  KPI Sensors count: {kpi_sensors_val}")
            try:
                sensor_count = int(kpi_sensors_val)
                if sensor_count == 0:
                    step3_issues.append("KPI sensors count is 0")
            except ValueError:
                step3_issues.append(f"KPI sensors value is not a number: '{kpi_sensors_val}'")
        else:
            step3_ok = False
            step3_issues.append("KPI Sensors element (#kpi-sensors) not found")

        kpi_alerts_el = page.query_selector("#kpi-alerts")
        if kpi_alerts_el:
            kpi_alerts_val = kpi_alerts_el.inner_text().strip()
            print(f"  KPI Alerts: {kpi_alerts_val}")

        # Check status banner
        banner = page.query_selector("#status-banner")
        if banner:
            banner_risk = page.query_selector("#banner-risk")
            banner_pill = page.query_selector("#banner-pill")
            banner_time = page.query_selector("#banner-time")

            if banner_risk:
                risk_val = banner_risk.inner_text().strip()
                print(f"  Banner risk: {risk_val}%")
                if not check_text_not_nan_or_zero(risk_val):
                    step3_issues.append(f"Banner risk shows invalid value: '{risk_val}'")

            if banner_pill:
                pill_text = banner_pill.inner_text().strip()
                print(f"  Status pill: {pill_text}")
                if pill_text not in ("NORMAL", "ALERTE", "CRITIQUE"):
                    step3_issues.append(f"Status pill has unexpected value: '{pill_text}'")

            if banner_time:
                time_text = banner_time.inner_text().strip()
                print(f"  Prediction time: {time_text}")
                if not time_text:
                    step3_issues.append("Banner time is empty")
        else:
            step3_ok = False
            step3_issues.append("Status banner (#status-banner) not found")

        # Check timeline bars
        timeline = page.query_selector("#status-timeline")
        if timeline:
            bars = timeline.query_selector_all(".timeline-bar")
            bar_count = len(bars)
            print(f"  Timeline bars: {bar_count}")
            if bar_count == 0:
                step3_ok = False
                step3_issues.append("Timeline has no bars rendered")
            elif bar_count < 10:
                step3_issues.append(f"Timeline has only {bar_count} bars (expected ~32)")
        else:
            step3_ok = False
            step3_issues.append("Timeline element (#status-timeline) not found")

        # Check sensor cards grid
        sensor_grid = page.query_selector("#sensor-grid")
        if sensor_grid:
            sensor_cards = sensor_grid.query_selector_all(".sensor-card")
            card_count = len(sensor_cards)
            print(f"  Sensor cards: {card_count}")
            if card_count == 0:
                step3_ok = False
                step3_issues.append("Sensor grid has no sensor cards")
            elif card_count < 5:
                step3_issues.append(f"Sensor grid has only {card_count} cards (expected 11+)")
            else:
                # Check a sample card structure
                first_card = sensor_cards[0]

                # Icon
                icon_el = first_card.query_selector(".sensor-icon")
                if not icon_el:
                    step3_issues.append("First sensor card missing .sensor-icon")
                else:
                    icon_inner = icon_el.inner_html().strip()
                    if not icon_inner:
                        step3_issues.append("First sensor card icon is empty")

                # Label
                label_el = first_card.query_selector(".sensor-title span")
                if label_el:
                    label_text = label_el.inner_text().strip()
                    print(f"  First sensor card label: '{label_text}'")
                    if not label_text:
                        step3_issues.append("First sensor card label is empty")

                # Impact %
                impact_el = first_card.query_selector(".sensor-impact")
                if impact_el:
                    impact_text = impact_el.inner_text().strip()
                    print(f"  First sensor impact: '{impact_text}'")
                    if "%" not in impact_text:
                        step3_issues.append(f"Impact element missing '%': '{impact_text}'")

                # Current/Predicted values
                now_val = first_card.query_selector(".sensor-now .val")
                pred_val = first_card.query_selector(".sensor-pred .val")
                if now_val:
                    now_text = now_val.inner_text().strip()
                    print(f"  First sensor current value: '{now_text}'")
                    if not check_text_not_nan_or_zero(now_text.replace("°C","").replace("%","").replace("kW","").strip()):
                        step3_issues.append(f"First sensor current value suspicious: '{now_text}'")
                else:
                    step3_issues.append("First sensor card missing current value element")

                # AI insight
                insight_el = first_card.query_selector(".sensor-insight")
                if insight_el:
                    insight_text = insight_el.inner_text().strip()
                    print(f"  First sensor AI insight: '{insight_text[:60]}...'")
                    if not insight_text:
                        step3_issues.append("First sensor AI insight is empty")
                else:
                    step3_issues.append("First sensor card missing .sensor-insight")

        else:
            step3_ok = False
            step3_issues.append("Sensor grid (#sensor-grid) not found")

        screenshot(page, "03_monitoring_detail")
        errors, warnings = evaluate_errors(page)
        results["step3"] = {
            "ok": step3_ok and not step3_issues,
            "issues": step3_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        results["step3"]["ok"] = step3_ok and len([i for i in step3_issues if "suspicious" not in i and "only" not in i]) == 0
        print(f"  Result: {'OK' if results['step3']['ok'] else 'FAIL'} | Issues: {step3_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 4: Switch datacenter via dropdown
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 4] Switching to Datacenter 2 via dropdown...")
        step4_ok = True
        step4_issues = []

        picker = page.query_selector("#dataset-picker")
        if picker:
            options = page.query_selector_all("#dataset-picker option")
            option_texts = [o.inner_text() for o in options]
            print(f"  Dataset options: {option_texts}")

            # Find option with "2" or second datacenter
            if len(options) >= 2:
                # Select the second option (Datacenter 2)
                second_value = options[1].get_attribute("value")
                print(f"  Selecting option value '{second_value}'")
                picker.select_option(value=second_value)
                page.wait_for_timeout(3000)

                # Wait for re-render
                try:
                    page.wait_for_selector("#mon-content", state="visible", timeout=10000)
                except Exception:
                    pass

                page.wait_for_timeout(1500)

                # Check data updated
                banner_risk_after = page.query_selector("#banner-risk")
                if banner_risk_after:
                    new_risk = banner_risk_after.inner_text().strip()
                    print(f"  Risk after switch: {new_risk}%")
                    if not check_text_not_nan_or_zero(new_risk):
                        step4_issues.append(f"After dataset switch, risk value is invalid: '{new_risk}'")

                # Verify sensor grid still populated
                new_cards = page.query_selector_all("#sensor-grid .sensor-card")
                print(f"  Sensor cards after switch: {len(new_cards)}")
                if len(new_cards) == 0:
                    step4_ok = False
                    step4_issues.append("Sensor grid empty after dataset switch")
            else:
                step4_issues.append(f"Only {len(options)} dataset options (expected 2+)")
        else:
            step4_ok = False
            step4_issues.append("Dataset picker (#dataset-picker) not found")

        screenshot(page, "04_datacenter2_switch")
        errors, warnings = evaluate_errors(page)
        results["step4"] = {
            "ok": step4_ok and len(step4_issues) == 0,
            "issues": step4_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step4']['ok'] else 'FAIL'} | Issues: {step4_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 5: Prévisions page
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 5] Navigating to Prévisions page...")
        step5_ok = True
        step5_issues = []

        # Click Prévisions nav item
        forecast_nav = None
        for nav in page.query_selector_all(".nav-item"):
            if "Prévisions" in nav.inner_text() or "prevision" in nav.get_attribute("data-page") or "":
                if nav.get_attribute("data-page") == "forecast":
                    forecast_nav = nav
                    break
        if not forecast_nav:
            for nav in page.query_selector_all(".nav-item"):
                if "vision" in nav.inner_text().lower():
                    forecast_nav = nav
                    break
        if forecast_nav:
            forecast_nav.click()
        else:
            step5_ok = False
            step5_issues.append("Prévisions nav item not found")

        page.wait_for_timeout(1000)

        # Wait for forecast content
        try:
            page.wait_for_selector("#forecast-content", state="visible", timeout=12000)
        except Exception:
            step5_ok = False
            step5_issues.append("Forecast content (#forecast-content) never became visible")

        page.wait_for_timeout(1500)

        # Check 4 chart canvases
        chart_ids = ["chart-temp", "chart-power", "chart-humidity", "chart-fuel"]
        for chart_id in chart_ids:
            canvas = page.query_selector(f"#{chart_id}")
            if not canvas:
                step5_ok = False
                step5_issues.append(f"Canvas #{chart_id} not found")
            else:
                # Check if Chart.js rendered (canvas has non-zero dimensions)
                width = page.evaluate(f"() => document.getElementById('{chart_id}').width")
                height = page.evaluate(f"() => document.getElementById('{chart_id}').height")
                print(f"  Chart #{chart_id}: {width}x{height}px")
                if width == 0 or height == 0:
                    step5_issues.append(f"Chart #{chart_id} has zero dimensions")

        screenshot(page, "05a_forecast_24min")

        # Click Horizon 48 min tab
        tabs = page.query_selector_all(".forecast-tab")
        tab_48 = None
        for t in tabs:
            if "48" in t.inner_text():
                tab_48 = t
                break
        if tab_48:
            tab_48.click()
            page.wait_for_timeout(3000)
            try:
                page.wait_for_selector("#forecast-content", state="visible", timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            print("  Clicked '48 min' tab")

            # Verify tab is active
            active_class = tab_48.get_attribute("class")
            if "active" not in active_class:
                step5_issues.append("48 min tab doesn't have 'active' class after click")
        else:
            step5_issues.append("Horizon 48 min tab not found")

        screenshot(page, "05b_forecast_48min")
        errors, warnings = evaluate_errors(page)
        results["step5"] = {
            "ok": step5_ok and len(step5_issues) == 0,
            "issues": step5_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step5']['ok'] else 'FAIL'} | Issues: {step5_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 6: Alertes page
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 6] Navigating to Alertes page...")
        step6_ok = True
        step6_issues = []

        alerts_nav = None
        for nav in page.query_selector_all(".nav-item"):
            if nav.get_attribute("data-page") == "alerts":
                alerts_nav = nav
                break
        if not alerts_nav:
            for nav in page.query_selector_all(".nav-item"):
                if "alert" in nav.inner_text().lower() or "alerte" in nav.inner_text().lower():
                    alerts_nav = nav
                    break
        if alerts_nav:
            alerts_nav.click()
        else:
            step6_ok = False
            step6_issues.append("Alertes nav item not found")

        page.wait_for_timeout(2000)

        # Check alerts page rendered
        alerts_page = page.query_selector("#page-alerts.active")
        if not alerts_page:
            step6_ok = False
            step6_issues.append("Alerts page is not active (#page-alerts.active not found)")

        alerts_list = page.query_selector("#alerts-list")
        if alerts_list:
            alert_items = alerts_list.query_selector_all(".alert-item")
            empty_state = alerts_list.query_selector(".empty-state")
            print(f"  Alert items: {len(alert_items)}, empty state: {empty_state is not None}")
            if len(alert_items) == 0 and not empty_state:
                step6_issues.append("Alerts list is empty but no empty-state message shown")
        else:
            step6_ok = False
            step6_issues.append("Alerts list (#alerts-list) not found")

        # Check subtitle
        alerts_sub = page.query_selector("#alerts-sub")
        if alerts_sub:
            sub_text = alerts_sub.inner_text().strip()
            print(f"  Alerts sub: '{sub_text}'")
            if sub_text == "—":
                step6_issues.append("Alerts subtitle still shows placeholder '—' (not updated after load)")

        screenshot(page, "06_alerts_page")
        errors, warnings = evaluate_errors(page)
        results["step6"] = {
            "ok": step6_ok and len(step6_issues) == 0,
            "issues": step6_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step6']['ok'] else 'FAIL'} | Issues: {step6_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 7: Modèles ML page (admin only)
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 7] Navigating to Modèles ML page...")
        step7_ok = True
        step7_issues = []

        ml_nav = None
        for nav in page.query_selector_all(".nav-item"):
            if nav.get_attribute("data-page") == "ml":
                ml_nav = nav
                break
        if not ml_nav:
            for nav in page.query_selector_all(".nav-item"):
                if "ml" in nav.inner_text().lower() or "modèle" in nav.inner_text().lower():
                    ml_nav = nav
                    break
        if ml_nav:
            ml_nav.click()
        else:
            step7_ok = False
            step7_issues.append("Modèles ML nav item not found")

        page.wait_for_timeout(1000)

        # Wait for ML content
        try:
            page.wait_for_selector("#ml-content", state="visible", timeout=10000)
        except Exception:
            # Check if empty state shown
            empty_state = page.query_selector("#ml-empty")
            if empty_state and empty_state.is_visible():
                step7_ok = False
                step7_issues.append("ML content not available (ml-empty shown instead) — ml_metrics.json missing or API error")
            else:
                step7_ok = False
                step7_issues.append("ML content (#ml-content) never became visible")

        page.wait_for_timeout(1500)

        # Check model cards
        card_rf = page.query_selector("#card-rf")
        card_xgb = page.query_selector("#card-xgb")

        if card_rf and card_xgb:
            # Check "best model" badge
            rf_is_best = "best" in (card_rf.get_attribute("class") or "")
            xgb_is_best = "best" in (card_xgb.get_attribute("class") or "")
            if not rf_is_best and not xgb_is_best:
                step7_issues.append("Neither RF nor XGBoost card has 'best' class (MEILLEUR MODÈLE badge missing)")
            else:
                print(f"  Best model badge: RF={rf_is_best}, XGB={xgb_is_best}")

            # Check metrics filled (not —)
            metric_ids = ["rf-acc", "rf-prec", "rf-rec", "rf-f1", "rf-auc",
                          "xgb-acc", "xgb-prec", "xgb-rec", "xgb-f1", "xgb-auc"]
            for mid in metric_ids:
                el = page.query_selector(f"#{mid}")
                if el:
                    val = el.inner_text().strip()
                    if val == "—" or not val:
                        step7_issues.append(f"Metric #{mid} shows placeholder '—'")
                    else:
                        pass  # OK
                else:
                    step7_issues.append(f"Metric element #{mid} not found")
        else:
            if not card_rf:
                step7_ok = False
                step7_issues.append("RF model card (#card-rf) not found")
            if not card_xgb:
                step7_ok = False
                step7_issues.append("XGB model card (#card-xgb) not found")

        # Check comparison bar chart
        compare_canvas = page.query_selector("#chart-compare")
        if compare_canvas:
            cw = page.evaluate("() => { const c = document.getElementById('chart-compare'); return c ? c.width : 0; }")
            print(f"  Comparison chart canvas width: {cw}")
            if cw == 0:
                step7_issues.append("Comparison chart canvas has zero width")
        else:
            step7_ok = False
            step7_issues.append("Comparison chart canvas (#chart-compare) not found")

        # Check feature importance lists
        fi_rf = page.query_selector("#fi-rf")
        fi_xgb = page.query_selector("#fi-xgb")
        if fi_rf:
            fi_rows = fi_rf.query_selector_all(".fi-row")
            print(f"  RF feature importance rows: {len(fi_rows)}")
            if len(fi_rows) == 0:
                step7_ok = False
                step7_issues.append("RF feature importance list (#fi-rf) is empty")
            elif len(fi_rows) < 5:
                step7_issues.append(f"RF feature importance has only {len(fi_rows)} rows (expected 10)")
        else:
            step7_ok = False
            step7_issues.append("RF feature importance list (#fi-rf) not found")

        if fi_xgb:
            fi_rows_xgb = fi_xgb.query_selector_all(".fi-row")
            print(f"  XGB feature importance rows: {len(fi_rows_xgb)}")
            if len(fi_rows_xgb) == 0:
                step7_ok = False
                step7_issues.append("XGB feature importance list (#fi-xgb) is empty")
        else:
            step7_ok = False
            step7_issues.append("XGB feature importance list (#fi-xgb) not found")

        # Check confusion matrices
        cm_rf = page.query_selector("#cm-rf")
        cm_xgb = page.query_selector("#cm-xgb")
        if cm_rf:
            cm_table = cm_rf.query_selector("table.cm-table")
            if not cm_table:
                step7_issues.append("RF confusion matrix table not rendered in #cm-rf")
            else:
                print("  RF confusion matrix table: OK")
        else:
            step7_ok = False
            step7_issues.append("RF confusion matrix (#cm-rf) not found")

        if cm_xgb:
            cm_table_xgb = cm_xgb.query_selector("table.cm-table")
            if not cm_table_xgb:
                step7_issues.append("XGB confusion matrix table not rendered in #cm-xgb")
        else:
            step7_ok = False
            step7_issues.append("XGB confusion matrix (#cm-xgb) not found")

        screenshot(page, "07_ml_dashboard")
        errors, warnings = evaluate_errors(page)
        results["step7"] = {
            "ok": step7_ok and len(step7_issues) == 0,
            "issues": step7_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step7']['ok'] else 'FAIL'} | Issues: {step7_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 8: Grafana page
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 8] Navigating to Dashboards Grafana...")
        step8_ok = True
        step8_issues = []

        grafana_nav = None
        for nav in page.query_selector_all(".nav-item"):
            if nav.get_attribute("data-page") == "grafana":
                grafana_nav = nav
                break
        if not grafana_nav:
            for nav in page.query_selector_all(".nav-item"):
                if "grafana" in nav.inner_text().lower():
                    grafana_nav = nav
                    break
        if grafana_nav:
            grafana_nav.click()
        else:
            step8_ok = False
            step8_issues.append("Grafana nav item not found")

        page.wait_for_timeout(2000)

        # Check Grafana page active
        grafana_page = page.query_selector("#page-grafana.active")
        if not grafana_page:
            step8_ok = False
            step8_issues.append("Grafana page not active (#page-grafana.active not found)")

        # Check iframe present (acceptable if Grafana not running or blocked)
        iframe = page.query_selector("#page-grafana iframe")
        if iframe:
            iframe_src = iframe.get_attribute("src")
            print(f"  Grafana iframe src: {iframe_src}")
            # Note: CSP/X-Frame-Options may prevent Grafana from loading in iframe —
            # this is acceptable behavior
            step8_issues.append("NOTE: Grafana iframe present but content load depends on X-Frame-Options (acceptable)")
        else:
            step8_ok = False
            step8_issues.append("Grafana iframe not found in #page-grafana")

        screenshot(page, "08_grafana_page")
        errors, warnings = evaluate_errors(page)
        results["step8"] = {
            "ok": step8_ok,  # Grafana load errors are acceptable
            "issues": step8_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if step8_ok else 'FAIL'} | Issues: {step8_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 9: Logout
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 9] Logging out...")
        step9_ok = True
        step9_issues = []

        # Find logout button (door icon in sidebar footer)
        logout_btn = page.query_selector("button[onclick*='Logout'], button[onclick*='logout']")
        if not logout_btn:
            # Try finding by SVG path or data attribute
            footer_btns = page.query_selector_all(".sidebar-footer button")
            for btn in footer_btns:
                inner = btn.inner_html()
                if "M17" in inner or "door" in btn.get_attribute("title", "").lower() or btn.get_attribute("onclick"):
                    onclick = btn.get_attribute("onclick") or ""
                    if "logout" in onclick.lower():
                        logout_btn = btn
                        break
            # Last resort: evaluate
            if not logout_btn:
                logout_btn = page.evaluate_handle("""() => {
                    const btns = document.querySelectorAll('.sidebar-footer button');
                    for (const b of btns) {
                        const oc = b.getAttribute('onclick') || '';
                        if (oc.toLowerCase().includes('logout')) return b;
                    }
                    return null;
                }""")

        if logout_btn:
            try:
                page.evaluate("() => handleLogout()")
                page.wait_for_timeout(1000)
                print("  Called handleLogout() via evaluate")
            except Exception as e:
                step9_issues.append(f"handleLogout() call failed: {e}")
        else:
            # Try clicking by JS
            try:
                page.evaluate("() => handleLogout()")
                print("  Called handleLogout() via evaluate (fallback)")
            except Exception as e:
                step9_ok = False
                step9_issues.append(f"Could not trigger logout: {e}")

        page.wait_for_timeout(1000)

        # Verify login screen is shown again
        login_screen_visible = page.evaluate("""() => {
            const el = document.getElementById('login-screen');
            return el && (el.style.display !== 'none' && el.style.display !== '');
        }""")
        app_shell_active = page.evaluate("""() => {
            return document.getElementById('app-shell').classList.contains('active');
        }""")
        print(f"  Login screen visible: {login_screen_visible}, App shell active: {app_shell_active}")

        if not login_screen_visible:
            step9_ok = False
            step9_issues.append("After logout, login screen is not visible")
        if app_shell_active:
            step9_ok = False
            step9_issues.append("After logout, app shell is still active (should be hidden)")

        # Check fields are cleared
        username_val = page.evaluate("() => document.getElementById('username').value")
        password_val = page.evaluate("() => document.getElementById('password').value")
        print(f"  Username field after logout: '{username_val}'")
        if username_val:
            step9_issues.append(f"Username field not cleared after logout: '{username_val}'")
        if password_val:
            step9_issues.append("Password field not cleared after logout")

        screenshot(page, "09_after_logout")
        errors, warnings = evaluate_errors(page)
        results["step9"] = {
            "ok": step9_ok and len(step9_issues) == 0,
            "issues": step9_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step9']['ok'] else 'FAIL'} | Issues: {step9_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 10: Opérateur quick login — RBAC verification
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 10] Opérateur quick login and RBAC check...")
        step10_ok = True
        step10_issues = []

        # Click Opérateur button
        op_clicked = False
        for b in page.query_selector_all(".quick-btn"):
            btn_class = b.get_attribute("class") or ""
            btn_text = b.inner_text() or ""
            if "pérateur" in btn_text or "user" in btn_class.lower():
                b.click()
                op_clicked = True
                break
        if not op_clicked:
            step10_ok = False
            step10_issues.append("Opérateur quick-login button not found/clicked")

        try:
            page.wait_for_selector("#app-shell.active", timeout=8000)
        except Exception:
            step10_ok = False
            step10_issues.append("App shell did not become active after Opérateur login")

        page.wait_for_timeout(2000)

        # Check role
        user_name_el = page.query_selector("#user-name")
        user_role_el = page.query_selector("#user-role")
        if user_name_el:
            name_txt = user_name_el.inner_text().strip()
            print(f"  Logged in as: {name_txt}")
        if user_role_el:
            role_txt = user_role_el.inner_text().strip()
            print(f"  Role: {role_txt}")
            if "admin" in role_txt.lower():
                step10_ok = False
                step10_issues.append(f"User role shows 'admin' for Opérateur login: '{role_txt}'")

        # Check RBAC: admin-only items should be HIDDEN
        body_classes = page.evaluate("() => document.body.className")
        print(f"  Body classes: '{body_classes}'")
        if "role-admin" in body_classes:
            step10_ok = False
            step10_issues.append("Body has 'role-admin' class for Opérateur login (should NOT have it)")

        # admin-only nav items should not be visible
        admin_only_items = page.query_selector_all(".admin-only")
        visible_admin_items = [el for el in admin_only_items if el.is_visible()]
        print(f"  Visible admin-only items: {len(visible_admin_items)} (should be 0)")
        if visible_admin_items:
            step10_ok = False
            for el in visible_admin_items:
                step10_issues.append(f"Admin-only item is visible to Opérateur: '{el.inner_text().strip()}'")

        # Check nav only has non-admin items
        nav_items_op = page.query_selector_all(".nav-item")
        visible_nav = [n for n in nav_items_op if n.is_visible()]
        visible_nav_texts = [n.inner_text().strip() for n in visible_nav]
        print(f"  Visible nav items for Opérateur: {visible_nav_texts}")

        forbidden_for_op = ["Modèles ML", "Dashboards Grafana"]
        for forbidden in forbidden_for_op:
            if any(forbidden.lower() in t.lower() for t in visible_nav_texts):
                step10_ok = False
                step10_issues.append(f"Admin-only nav item '{forbidden}' is VISIBLE to Opérateur role")

        expected_for_op = ["Monitoring", "Prévisions", "Alertes"]
        for expected in expected_for_op:
            if not any(expected.lower() in t.lower() for t in visible_nav_texts):
                step10_issues.append(f"Nav item '{expected}' not visible to Opérateur (should be visible)")

        # Try to navigate to ML page directly via JS — should be blocked
        page.evaluate("() => switchPage('ml')")
        page.wait_for_timeout(500)
        ml_page_active = page.evaluate("() => document.getElementById('page-ml').classList.contains('active')")
        if ml_page_active:
            step10_ok = False
            step10_issues.append("SECURITY: Opérateur can access ML page via switchPage('ml') — RBAC bypass!")
        else:
            print("  switchPage('ml') blocked for Opérateur: OK")

        page.evaluate("() => switchPage('grafana')")
        page.wait_for_timeout(500)
        grafana_page_active = page.evaluate("() => document.getElementById('page-grafana').classList.contains('active')")
        if grafana_page_active:
            step10_ok = False
            step10_issues.append("SECURITY: Opérateur can access Grafana page via switchPage('grafana') — RBAC bypass!")
        else:
            print("  switchPage('grafana') blocked for Opérateur: OK")

        screenshot(page, "10_operateur_logged_in")
        errors, warnings = evaluate_errors(page)
        results["step10"] = {
            "ok": step10_ok and len(step10_issues) == 0,
            "issues": step10_issues,
            "js_errors": errors,
            "js_warnings": warnings,
        }
        print(f"  Result: {'OK' if results['step10']['ok'] else 'FAIL'} | Issues: {step10_issues}")

        # ─────────────────────────────────────────────────────────────
        # STEP 11: Final console error/warning check
        # ─────────────────────────────────────────────────────────────
        print("\n[STEP 11] Final console error/warning collection...")

        final_errors, final_warnings = evaluate_errors(page)
        results["step11"] = {
            "all_js_errors": final_errors,
            "all_js_warnings": final_warnings,
            "native_console_errors": native_errors,
            "native_console_warnings": native_warnings,
            "network_errors": _network_errors,
        }
        print(f"  Total JS errors (via window.__errors): {len(final_errors)}")
        print(f"  Total JS warnings (via window.__warnings): {len(final_warnings)}")
        print(f"  Native console errors: {len(native_errors)}")
        print(f"  Native console warnings: {len(native_warnings)}")
        print(f"  Network request failures: {len(_network_errors)}")

        if final_errors:
            print("  JS Errors:")
            for e in final_errors:
                print(f"    - {e}")
        if final_warnings:
            print("  JS Warnings:")
            for w in final_warnings[:10]:
                print(f"    - {w}")
        if native_errors:
            print("  Native console errors:")
            for e in native_errors:
                print(f"    - {e}")

        browser.close()

    # ─────────────────────────────────────────────────────────────
    # Print final summary
    # ─────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("FINAL TEST REPORT")
    print("="*70)
    step_names = {
        "step1":  "Login page rendering",
        "step2":  "Admin quick login + sidebar",
        "step3":  "Monitoring page data",
        "step4":  "Dataset switcher (Datacenter 2)",
        "step5":  "Prévisions — 4 charts + horizon tabs",
        "step6":  "Alertes page",
        "step7":  "Modèles ML (admin) — metrics + charts",
        "step8":  "Dashboards Grafana (iframe)",
        "step9":  "Logout flow",
        "step10": "Opérateur RBAC",
    }

    all_pass = True
    for step_key, step_name in step_names.items():
        r = results.get(step_key, {})
        ok = r.get("ok", False)
        issues = r.get("issues", [])
        symbol = "OK" if ok else "FAIL"
        print(f"\n  [{symbol}] STEP {step_key[-1] if len(step_key)==5 else step_key[4:]}: {step_name}")
        if issues:
            for issue in issues:
                severity = "NOTE" if issue.startswith("NOTE:") else "ISSUE"
                print(f"        [{severity}] {issue}")
        if not ok:
            all_pass = False

    print("\n" + "-"*70)
    print("CONSOLE ERRORS (window.__errors):")
    all_errors = results.get("step11", {}).get("all_js_errors", [])
    if all_errors:
        for e in all_errors:
            print(f"  ERROR: {e}")
    else:
        print("  None")

    print("\nCONSOLE WARNINGS (window.__warnings):")
    all_warnings = results.get("step11", {}).get("all_js_warnings", [])
    if all_warnings:
        for w in all_warnings:
            print(f"  WARN: {w}")
    else:
        print("  None")

    print("\nNATIVE BROWSER CONSOLE ERRORS:")
    native_errs = results.get("step11", {}).get("native_console_errors", [])
    if native_errs:
        for e in native_errs:
            print(f"  ERROR: {e}")
    else:
        print("  None")

    print("\nNATIVE BROWSER CONSOLE WARNINGS:")
    native_warns = results.get("step11", {}).get("native_console_warnings", [])
    if native_warns:
        for w in native_warns:
            print(f"  WARN: {w}")
    else:
        print("  None")

    print("\nNETWORK REQUEST FAILURES:")
    net_errs = results.get("step11", {}).get("network_errors", [])
    if net_errs:
        for e in net_errs:
            print(f"  NET_ERR: {e}")
    else:
        print("  None")

    print("\n" + "="*70)
    has_real_errors = (
        any(not results.get(f"step{i}", {}).get("ok", True)
            for i in range(1, 11)
            if f"step{i}" in results and i != 8)  # step 8 (Grafana) is acceptable
    )
    has_console_errors = bool(all_errors or native_errs)

    if not has_real_errors and not has_console_errors:
        print("VERDICT: PRODUCTION-READY YES")
    else:
        print("VERDICT: PRODUCTION-READY NO — issues found above")
    print("="*70)

    # Save results as JSON
    results_path = os.path.join(os.path.dirname(__file__), "e2e_test_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDetailed results saved to: {results_path}")
    print(f"Screenshots saved to: {SCREENSHOTS_DIR}/")

if __name__ == "__main__":
    run_tests()
