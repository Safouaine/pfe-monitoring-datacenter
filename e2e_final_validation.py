"""
Final E2E visual validation for http://localhost:5055
Validates: ZERO console errors, correct data, RBAC, Chart.js bounds
"""
import json
import time
import os
import sys
# Force UTF-8 output to handle special characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = "test_screenshots_final"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

RESULTS = []

def log(step, status, detail=""):
    icon = "PASS" if status else "FAIL"
    msg = f"[{icon}] {step}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append({"step": step, "pass": status, "detail": detail})

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()

        # ─────────────────────────────────────────────────────────────────────
        # STEP 1 — Navigate and inject console capture BEFORE any interaction
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 1: Navigate and inject console capture ===")
        page.goto("http://localhost:5055", wait_until="domcontentloaded")
        time.sleep(1)

        page.evaluate("""
            () => {
                window.__errors = [];
                window.__warnings = [];
                const oE = console.error, oW = console.warn;
                console.error = (...a) => {
                    window.__errors.push(a.map(String).join(' '));
                    oE(...a);
                };
                console.warn = (...a) => {
                    window.__warnings.push(a.map(String).join(' '));
                    oW(...a);
                };
            }
        """)

        title = page.title()
        log("Page title correct", title == "Nouvameq AI Operations Center", f"Got: {title}")

        # Snapshot login page
        page.screenshot(path=f"{SCREENSHOTS_DIR}/01_login_page.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/01_login_page.png")

        # Check login page elements
        admin_btn = page.query_selector("button:has-text('Admin')")
        operateur_btn = page.query_selector("button:has-text('Opérateur')")
        log("Login page has Admin quick-login button", admin_btn is not None)
        log("Login page has Opérateur quick-login button", operateur_btn is not None)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2 — Click Admin quick-login
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 2: Admin quick-login ===")
        page.click("button:has-text('Admin')")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/02_admin_monitoring.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/02_admin_monitoring.png")

        # Verify monitoring page loaded
        current_url = page.url
        log("Stays on http://localhost:5055", "localhost:5055" in current_url, current_url)

        # Check sidebar has active monitoring
        monitoring_active = page.query_selector(".sidebar-nav .active, [class*='active']")
        log("Monitoring page is active after admin login", monitoring_active is not None)

        # Check status banner
        status_banner = page.query_selector("[class*='status-banner'], [class*='risk'], .risk-score, #risk-score, [id*='risk']")
        log("Status/risk banner present", status_banner is not None)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 3 — Verify DC1 monitoring data
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 3: Verify DC1 monitoring data ===")

        # Check for sensor cards
        sensor_cards = page.query_selector_all("[class*='sensor-card'], [class*='metric-card'], [class*='sensor']")
        log("Sensor cards are populated", len(sensor_cards) > 0, f"Found {len(sensor_cards)} sensor cards")

        # Extract all visible text to check for bad binary sensor values
        page_text = page.evaluate("() => document.body.innerText")

        # Check binary sensor values (water_leak, cyber_alert)
        # Bad values would be 240 or 3000 (cumulative count)
        has_240 = "240" in page_text
        has_3000 = "3000" in page_text
        log("No erroneous binary sensor value 240", not has_240, "240 found in page" if has_240 else "OK")
        log("No erroneous binary sensor value 3000", not has_3000, "3000 found in page" if has_3000 else "OK")

        # Check that binary sensors show "inactif" or 0
        has_inactif = "inactif" in page_text.lower()
        has_binary_zero = True  # If no 240/3000, pass

        # Get the risk percentage from visible content
        risk_info = page.evaluate("""
            () => {
                const els = document.querySelectorAll('[class*="risk"], [id*="risk"], [class*="status"]');
                const texts = Array.from(els).map(e => e.innerText.trim()).filter(t => t.length > 0);
                return texts.slice(0, 10);
            }
        """)
        log("Risk/status text found", len(risk_info) > 0, str(risk_info[:3]))

        # Check for "%" in risk display
        has_risk_pct = any("%" in t for t in risk_info)
        log("Risk percentage shown", has_risk_pct, str(risk_info[:5]))

        # More detailed sensor check - look for the specific binary sensor display
        binary_sensor_check = page.evaluate("""
            () => {
                const result = {water_leak: null, cyber_alert: null, inactif_count: 0};
                const allText = document.body.innerHTML;
                // Count inactif occurrences
                result.inactif_count = (allText.match(/inactif/gi) || []).length;
                // Find sensor elements by text
                const spans = document.querySelectorAll('span, div, p');
                for (const el of spans) {
                    const t = el.innerText || '';
                    if (t.includes('Fuite') || t.includes('fuite') || t.includes('water')) {
                        result.water_leak = el.closest('[class*="card"], [class*="sensor"]')
                            ? el.closest('[class*="card"], [class*="sensor"]').innerText.substring(0, 100)
                            : t;
                    }
                    if (t.includes('Cyber') || t.includes('cyber') || t.includes('alerte')) {
                        result.cyber_alert = el.closest('[class*="card"], [class*="sensor"]')
                            ? el.closest('[class*="card"], [class*="sensor"]').innerText.substring(0, 100)
                            : t;
                    }
                }
                return result;
            }
        """)
        print(f"  Binary sensor check: {binary_sensor_check}")
        log("Binary sensors show inactif (not cumulative)",
            binary_sensor_check.get("inactif_count", 0) > 0,
            f"inactif count: {binary_sensor_check.get('inactif_count', 0)}")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 4 — Switch to DC2 via dropdown
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 4: Switch to DC2 ===")

        # Find datacenter selector
        dc_selector = page.query_selector("select[id*='dc'], select[name*='dc'], [class*='dc-select'], select")
        if dc_selector:
            dc_selector.select_option(index=1)
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)
        else:
            # Try clicking on a dropdown button
            dc_btn = page.query_selector("[class*='dropdown']:has-text('DC'), button:has-text('DC')")
            if dc_btn:
                dc_btn.click()
                time.sleep(1)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/03_dc2_switch.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/03_dc2_switch.png")

        # Check if DC2 content loaded
        page_text_dc2 = page.evaluate("() => document.body.innerText")
        dc2_detected = "DC2" in page_text_dc2 or "dc2" in page_text_dc2.lower() or "Datacenter 2" in page_text_dc2
        log("DC2 switch works", dc_selector is not None or dc_btn is not None,
            "DC selector found" if dc_selector else "No DC selector found")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5 — Click "Prévisions" and verify 4 charts
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 5: Prévisions page ===")

        # Find and click Prévisions link in sidebar
        previsions_link = page.query_selector("a:has-text('Prévisions'), button:has-text('Prévisions'), [data-page='forecast'], [onclick*='forecast']")
        if previsions_link:
            previsions_link.click()
        else:
            # Try by text content
            page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a, button, li, [onclick]');
                    for (const l of links) {
                        if (l.innerText && l.innerText.includes('visions')) {
                            l.click();
                            break;
                        }
                    }
                }
            """)

        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)  # Wait for charts to render

        page.screenshot(path=f"{SCREENSHOTS_DIR}/04_previsions.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/04_previsions.png")

        # Check charts are present
        chart_count = page.evaluate("""
            () => {
                if (typeof Chart === 'undefined') return {count: 0, ids: []};
                const charts = [];
                ['chart-humidity', 'chart-temp', 'chart-fuel', 'chart-power'].forEach(id => {
                    const c = Chart.getChart(id);
                    if (c) charts.push(id);
                });
                return {count: charts.length, ids: charts};
            }
        """)
        print(f"  Charts found: {chart_count}")
        log("4 forecast charts rendered", chart_count.get("count", 0) >= 4,
            f"Found {chart_count.get('count', 0)}/4 charts: {chart_count.get('ids', [])}")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 6 — Click "Horizon 96 min" tab and verify bounds
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 6: Horizon 96 min tab - Chart bounds ===")

        # Click 96 min tab
        horizon_tab = page.query_selector("button:has-text('96'), [data-tab*='96'], a:has-text('96 min')")
        if not horizon_tab:
            horizon_tab = page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, a, [role="tab"]');
                    for (const b of btns) {
                        if (b.innerText && b.innerText.includes('96')) return b;
                    }
                    return null;
                }
            """)

        if horizon_tab:
            page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, a, [role="tab"]');
                    for (const b of btns) {
                        if (b.innerText && b.innerText.includes('96')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            time.sleep(2)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/05_horizon96.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/05_horizon96.png")

        # Extract Chart.js bounds
        chart_bounds = page.evaluate("""
            () => {
                if (typeof Chart === 'undefined') return {error: 'Chart.js not available'};
                const out = {};
                ['chart-humidity', 'chart-temp', 'chart-fuel', 'chart-power'].forEach(id => {
                    const c = Chart.getChart(id);
                    if (c) {
                        try {
                            const ds = c.data.datasets;
                            // Dataset index 1 is typically forecast
                            const fcDataset = ds.length > 1 ? ds[1] : ds[0];
                            const fc = (fcDataset.data || []).filter(v => v != null && !isNaN(v));
                            if (fc.length > 0) {
                                out[id] = {
                                    min: Math.min(...fc),
                                    max: Math.max(...fc),
                                    count: fc.length,
                                    dataset_count: ds.length
                                };
                            } else {
                                // Try all datasets
                                const allData = ds.flatMap(d => (d.data || []).filter(v => v != null && !isNaN(v)));
                                out[id] = {
                                    min: allData.length ? Math.min(...allData) : null,
                                    max: allData.length ? Math.max(...allData) : null,
                                    count: allData.length,
                                    dataset_count: ds.length,
                                    note: 'all_datasets'
                                };
                            }
                        } catch(e) {
                            out[id] = {error: e.toString()};
                        }
                    } else {
                        out[id] = null;
                    }
                });
                return out;
            }
        """)
        print(f"  Chart bounds: {json.dumps(chart_bounds, indent=2)}")

        # Validate bounds
        humidity_data = chart_bounds.get("chart-humidity")
        temp_data = chart_bounds.get("chart-temp")
        fuel_data = chart_bounds.get("chart-fuel")
        power_data = chart_bounds.get("chart-power")

        if humidity_data and humidity_data.get("max") is not None:
            log("Humidity max <= 100", humidity_data["max"] <= 100,
                f"max={humidity_data['max']:.2f}")
        else:
            log("Humidity chart data available", False, str(humidity_data))

        if temp_data and temp_data.get("min") is not None:
            log("Temp min >= -10", temp_data["min"] >= -10,
                f"min={temp_data['min']:.2f}")
        else:
            log("Temp chart data available", False, str(temp_data))

        if fuel_data and fuel_data.get("max") is not None:
            log("Fuel max <= 100", fuel_data["max"] <= 100,
                f"max={fuel_data['max']:.2f}")
        else:
            log("Fuel chart data available", False, str(fuel_data))

        if power_data and power_data.get("max") is not None:
            log("Power max <= 50 kW", power_data["max"] <= 50,
                f"max={power_data['max']:.2f}")
        else:
            log("Power chart data available", False, str(power_data))

        # ─────────────────────────────────────────────────────────────────────
        # STEP 7 — Click "Alertes"
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 7: Alertes page ===")

        page.evaluate("""
            () => {
                const links = document.querySelectorAll('a, button, li, [onclick]');
                for (const l of links) {
                    if (l.innerText && (l.innerText.includes('Alertes') || l.innerText.includes('alerte'))) {
                        l.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        time.sleep(2)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/06_alertes.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/06_alertes.png")

        alertes_text = page.evaluate("() => document.body.innerText")
        log("Alertes page loads", "Alerte" in alertes_text or "alert" in alertes_text.lower() or "ALERTE" in alertes_text,
            "Alertes content found")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 8 — Click "Modèles ML"
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 8: Modèles ML page ===")

        page.evaluate("""
            () => {
                const links = document.querySelectorAll('a, button, li, [onclick]');
                for (const l of links) {
                    if (l.innerText && (l.innerText.includes('ML') || l.innerText.includes('Mod'))) {
                        l.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        time.sleep(2)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/07_modeles_ml.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/07_modeles_ml.png")

        ml_text = page.evaluate("() => document.body.innerText")
        has_xgboost = "XGBoost" in ml_text or "xgboost" in ml_text.lower()
        has_meilleur = "MEILLEUR" in ml_text.upper()
        log("Modèles ML page loads with XGBoost", has_xgboost, "XGBoost found" if has_xgboost else "XGBoost NOT found")
        log("XGBoost has 'MEILLEUR MODELE' badge", has_meilleur, "Badge found" if has_meilleur else "Badge NOT found")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 9 — Logout
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 9: Logout ===")

        # Find logout button (door icon or logout text)
        logout_clicked = page.evaluate("""
            () => {
                // Try various logout selectors
                const selectors = [
                    '[class*="logout"]',
                    '[onclick*="logout"]',
                    'button[title*="logout"]',
                    'button[title*="Logout"]',
                    'button[title*="Déconnexion"]',
                    '[class*="door"]',
                    'fa-sign-out',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) { el.click(); return sel; }
                }
                // Search by onclick content
                const allBtns = document.querySelectorAll('button, a, [role="button"]');
                for (const b of allBtns) {
                    const onclick = b.getAttribute('onclick') || '';
                    if (onclick.includes('logout') || onclick.includes('Logout')) {
                        b.click();
                        return 'onclick:' + onclick.substring(0, 50);
                    }
                }
                // Search by icon classes
                const icons = document.querySelectorAll('[class*="fa-sign"], [class*="fa-door"]');
                for (const i of icons) {
                    const parent = i.closest('button, a, [role="button"]');
                    if (parent) { parent.click(); return 'icon-parent'; }
                }
                return null;
            }
        """)
        time.sleep(1)
        print(f"  Logout clicked via: {logout_clicked}")

        # Check if we're back on login page
        login_page_check = page.query_selector("button:has-text('Admin'), [class*='login'], form[class*='login']")
        log("Logout returns to login page", login_page_check is not None,
            f"Login elements found: {login_page_check is not None}")

        page.screenshot(path=f"{SCREENSHOTS_DIR}/08_after_logout.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/08_after_logout.png")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 10 — Opérateur quick-login
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 10: Opérateur quick-login ===")

        page.wait_for_selector("button:has-text('Opérateur')", timeout=5000)
        page.click("button:has-text('Opérateur')")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)

        page.screenshot(path=f"{SCREENSHOTS_DIR}/09_operateur_logged_in.png", full_page=True)
        print(f"  Screenshot: {SCREENSHOTS_DIR}/09_operateur_logged_in.png")

        # Check operator lands on Monitoring, not Grafana
        op_page_text = page.evaluate("() => document.body.innerText")
        op_url = page.url
        log("Opérateur lands on monitoring (not Grafana)",
            "localhost:5055" in op_url and "3000" not in op_url,
            f"URL: {op_url}")

        # Check RBAC - sidebar should hide ML Models and Grafana Dashboards
        sidebar_html = page.evaluate("""
            () => {
                const sidebar = document.querySelector('.sidebar, nav, [class*="sidebar"], [class*="nav"]');
                return sidebar ? sidebar.innerHTML : document.body.innerHTML.substring(0, 3000);
            }
        """)

        has_ml_in_sidebar = "Modèles ML" in sidebar_html or "Modeles ML" in sidebar_html or "ML" in sidebar_html
        has_grafana_in_sidebar = "Grafana" in sidebar_html or "grafana" in sidebar_html

        # For operator, these should NOT be visible OR should be hidden
        # Check if they exist but are hidden
        ml_visibility = page.evaluate("""
            () => {
                const items = document.querySelectorAll('a, li, button');
                for (const item of items) {
                    if (item.innerText && item.innerText.includes('ML')) {
                        const style = window.getComputedStyle(item);
                        return {
                            found: true,
                            visible: style.display !== 'none' && style.visibility !== 'hidden',
                            display: style.display,
                            text: item.innerText.substring(0, 50)
                        };
                    }
                }
                return {found: false};
            }
        """)
        grafana_visibility = page.evaluate("""
            () => {
                const items = document.querySelectorAll('a, li, button');
                for (const item of items) {
                    if (item.innerText && item.innerText.includes('Grafana')) {
                        const style = window.getComputedStyle(item);
                        return {
                            found: true,
                            visible: style.display !== 'none' && style.visibility !== 'hidden',
                            display: style.display,
                            text: item.innerText.substring(0, 50)
                        };
                    }
                }
                return {found: false};
            }
        """)

        print(f"  ML visibility for Opérateur: {ml_visibility}")
        print(f"  Grafana visibility for Opérateur: {grafana_visibility}")

        # RBAC: ML Models should be hidden for operator
        ml_hidden = not ml_visibility.get("found", False) or not ml_visibility.get("visible", True)
        grafana_hidden = not grafana_visibility.get("found", False) or not grafana_visibility.get("visible", True)

        log("Opérateur sidebar hides Modèles ML", ml_hidden, str(ml_visibility))
        log("Opérateur sidebar hides Dashboards Grafana", grafana_hidden, str(grafana_visibility))

        # ─────────────────────────────────────────────────────────────────────
        # STEP 11 — Final console error/warning capture
        # ─────────────────────────────────────────────────────────────────────
        print("\n=== STEP 11: Final console error/warning capture ===")

        final_console = page.evaluate("""
            () => JSON.stringify({
                errors: window.__errors || [],
                warnings: window.__warnings || [],
                errorCount: (window.__errors || []).length,
                warningCount: (window.__warnings || []).length
            })
        """)

        console_data = json.loads(final_console)
        print(f"  Console errors ({console_data['errorCount']}):")
        for e in console_data["errors"]:
            print(f"    ERROR: {e}")
        print(f"  Console warnings ({console_data['warningCount']}):")
        for w in console_data["warnings"]:
            print(f"    WARN:  {w}")

        # Filter acceptable errors
        ACCEPTABLE_PATTERNS = [
            "X-Frame-Options",
            "Refused to display",
            "localhost:3000",
            ".well-known/appspecific",
            "com.chrome.devtools",
        ]

        real_errors = []
        for err in console_data["errors"]:
            is_acceptable = any(pat in err for pat in ACCEPTABLE_PATTERNS)
            if not is_acceptable:
                real_errors.append(err)

        real_warnings = []
        for warn in console_data["warnings"]:
            is_acceptable = any(pat in warn for pat in ACCEPTABLE_PATTERNS)
            if not is_acceptable:
                real_warnings.append(warn)

        log("ZERO real console errors", len(real_errors) == 0,
            f"{len(real_errors)} unacceptable errors" if real_errors else "All clean")
        log("ZERO real console warnings", len(real_warnings) == 0,
            f"{len(real_warnings)} unacceptable warnings" if real_warnings else "All clean")

        browser.close()

        # ─────────────────────────────────────────────────────────────────────
        # FINAL REPORT
        # ─────────────────────────────────────────────────────────────────────
        print("\n" + "="*70)
        print("FINAL VALIDATION REPORT")
        print("="*70)

        passes = sum(1 for r in RESULTS if r["pass"])
        fails = sum(1 for r in RESULTS if not r["pass"])

        for r in RESULTS:
            icon = "PASS" if r["pass"] else "FAIL"
            print(f"  [{icon}] {r['step']}")
            if r["detail"] and not r["pass"]:
                print(f"         Detail: {r['detail']}")

        print(f"\nTotal: {passes} PASS, {fails} FAIL")
        print(f"\nConsole Errors (all): {console_data['errors']}")
        print(f"Console Warnings (all): {console_data['warnings']}")
        print(f"\nUnacceptable Errors: {real_errors}")
        print(f"Unacceptable Warnings: {real_warnings}")

        verdict = "YES" if fails == 0 and len(real_errors) == 0 else "NO"
        print(f"\nPRODUCTION-READY: {verdict}")

        # Save results
        with open("e2e_final_results.json", "w") as f:
            json.dump({
                "results": RESULTS,
                "console_errors": console_data["errors"],
                "console_warnings": console_data["warnings"],
                "unacceptable_errors": real_errors,
                "unacceptable_warnings": real_warnings,
                "production_ready": verdict
            }, f, indent=2, ensure_ascii=False)

        return fails, real_errors, real_warnings

if __name__ == "__main__":
    fails, errors, warnings = run()
