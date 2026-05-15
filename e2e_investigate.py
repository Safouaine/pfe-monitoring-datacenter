"""
Deep investigation of the 2 FAIL items:
1. Binary sensors 'inactif' label
2. XGBoost 'MEILLEUR MODELE' badge
"""
import json
import time
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()

        # Navigate and login as Admin
        page.goto("http://localhost:5055", wait_until="domcontentloaded")
        time.sleep(1)
        page.click("button:has-text('Admin')")
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)

        # ── INVESTIGATION 1: Binary Sensors ──────────────────────────────────
        print("="*60)
        print("INVESTIGATION 1: Binary Sensor Cards (DC1 Monitoring)")
        print("="*60)

        # Get all text visible on monitoring page
        # Look for water_leak and cyber_alert specifically
        binary_investigation = page.evaluate("""
            () => {
                const result = {
                    page_sections: [],
                    sensor_cards_text: [],
                    inactif_found: false,
                    water_leak_cards: [],
                    cyber_cards: [],
                    all_units: []
                };

                // Find all sensor/metric card elements
                const cards = document.querySelectorAll(
                    '[class*="sensor-card"], [class*="metric-card"], [class*="card"]'
                );

                for (const card of cards) {
                    const text = card.innerText || '';
                    if (text.toLowerCase().includes('fuite') ||
                        text.toLowerCase().includes('water') ||
                        text.toLowerCase().includes('leak')) {
                        result.water_leak_cards.push(text.trim().substring(0, 200));
                    }
                    if (text.toLowerCase().includes('cyber') ||
                        text.toLowerCase().includes('alerte')) {
                        result.cyber_cards.push(text.trim().substring(0, 200));
                    }
                    if (text.toLowerCase().includes('inactif')) {
                        result.inactif_found = true;
                    }
                }

                // Find all elements with 'unit' class
                const unitEls = document.querySelectorAll('[class*="unit"], [class*="label"]');
                for (const u of unitEls) {
                    const t = (u.innerText || '').trim();
                    if (t.length > 0 && t.length < 50) {
                        result.all_units.push(t);
                    }
                }

                // Check the monitoring section specifically
                const monitorSection = document.querySelector(
                    '#monitoring-section, [id*="monitoring"], [class*="monitoring"]'
                );
                if (monitorSection) {
                    result.monitoring_section_found = true;
                    // Get all text content with context
                    const innerText = monitorSection.innerText || '';
                    const lines = innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    result.monitoring_lines = lines.slice(0, 50);
                }

                // Look for the specific binary sensor values
                const allText = document.body.innerText;
                result.has_inactif = allText.toLowerCase().includes('inactif');
                result.has_actif = allText.toLowerCase().includes('actif');
                result.has_water_text = allText.toLowerCase().includes('fuite');
                result.has_cyber_text = allText.toLowerCase().includes('cyber');

                // Find any element displaying "0" near "fuite" or "cyber"
                const allElements = document.querySelectorAll('*');
                result.near_zero_elements = [];
                for (const el of allElements) {
                    const text = el.innerText || '';
                    if (text.trim() === '0' || text.trim() === '0.0') {
                        const parent = el.parentElement;
                        if (parent) {
                            const parentText = parent.innerText || '';
                            if (parentText.toLowerCase().includes('fuite') ||
                                parentText.toLowerCase().includes('cyber') ||
                                parentText.toLowerCase().includes('water') ||
                                parentText.toLowerCase().includes('alert')) {
                                result.near_zero_elements.push(parentText.trim().substring(0, 100));
                            }
                        }
                    }
                }

                return result;
            }
        """)

        print(f"  inactif_found: {binary_investigation.get('inactif_found')}")
        print(f"  has_inactif (body): {binary_investigation.get('has_inactif')}")
        print(f"  has_water_text: {binary_investigation.get('has_water_text')}")
        print(f"  has_cyber_text: {binary_investigation.get('has_cyber_text')}")
        print(f"  Water leak cards ({len(binary_investigation.get('water_leak_cards',[]))}):")
        for c in binary_investigation.get('water_leak_cards', []):
            print(f"    -> {repr(c[:150])}")
        print(f"  Cyber alert cards ({len(binary_investigation.get('cyber_cards',[]))}):")
        for c in binary_investigation.get('cyber_cards', []):
            print(f"    -> {repr(c[:150])}")
        print(f"  Units found (sample): {binary_investigation.get('all_units', [])[:20]}")
        print(f"  Near-zero elements: {binary_investigation.get('near_zero_elements', [])}")

        monitoring_lines = binary_investigation.get('monitoring_lines', [])
        if monitoring_lines:
            print(f"  Monitoring section lines (first 50):")
            for line in monitoring_lines:
                print(f"    {repr(line)}")

        # Get DC1 API response directly
        print("\n  Fetching DC1 /api/predict response...")
        api_result = page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('/api/predict?dc=dc1');
                    if (!resp.ok) return {error: resp.status + ' ' + resp.statusText};
                    const data = await resp.json();
                    // Return relevant fields
                    return {
                        status: data.status,
                        global_risk_percent: data.global_risk_percent,
                        sensor_danger: data.sensor_danger,
                        binary_sensors: Object.fromEntries(
                            Object.entries(data.sensor_danger || {}).filter(([k]) =>
                                k.includes('water') || k.includes('cyber') || k.includes('alert')
                            )
                        )
                    };
                } catch(e) {
                    return {error: e.toString()};
                }
            }
        """)
        print(f"  API DC1 response (truncated):")
        print(f"    status: {api_result.get('status')}")
        print(f"    global_risk_percent: {api_result.get('global_risk_percent')}")
        print(f"    sensor_danger keys: {list((api_result.get('sensor_danger') or {}).keys())}")
        print(f"    binary_sensors: {api_result.get('binary_sensors')}")

        # ── INVESTIGATION 2: XGBoost Badge ───────────────────────────────────
        print("\n" + "="*60)
        print("INVESTIGATION 2: XGBoost 'MEILLEUR MODELE' Badge")
        print("="*60)

        # Navigate to ML models page
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

        page.screenshot(path="test_screenshots_final/07b_modeles_ml_detail.png", full_page=True)

        ml_investigation = page.evaluate("""
            () => {
                const result = {
                    full_text: '',
                    badge_elements: [],
                    xgboost_context: [],
                    meilleur_context: []
                };

                // Full page text
                result.full_text = document.body.innerText.substring(0, 5000);

                // Find badge elements
                const badges = document.querySelectorAll(
                    '[class*="badge"], [class*="best"], [class*="champion"], [class*="winner"]'
                );
                for (const b of badges) {
                    result.badge_elements.push({
                        class: b.className,
                        text: (b.innerText || '').trim(),
                        html: b.outerHTML.substring(0, 200)
                    });
                }

                // Find XGBoost context
                const allEls = document.querySelectorAll('*');
                for (const el of allEls) {
                    const t = el.innerText || '';
                    if (t.includes('XGBoost') && t.length < 500) {
                        result.xgboost_context.push(t.trim());
                    }
                    if ((t.toUpperCase().includes('MEILLEUR') || t.toUpperCase().includes('BEST')) && t.length < 300) {
                        result.meilleur_context.push(t.trim());
                    }
                }

                // Remove duplicates
                result.xgboost_context = [...new Set(result.xgboost_context)].slice(0, 10);
                result.meilleur_context = [...new Set(result.meilleur_context)].slice(0, 10);

                return result;
            }
        """)

        print(f"  Badge elements found: {len(ml_investigation.get('badge_elements', []))}")
        for b in ml_investigation.get('badge_elements', []):
            print(f"    Badge: class={b['class']}, text={repr(b['text'])}")

        print(f"  XGBoost context (first 5):")
        for ctx in ml_investigation.get('xgboost_context', [])[:5]:
            print(f"    -> {repr(ctx[:300])}")

        print(f"  'MEILLEUR' context:")
        for ctx in ml_investigation.get('meilleur_context', []):
            print(f"    -> {repr(ctx[:300])}")

        print(f"\n  ML Page full text (first 3000 chars):")
        print(ml_investigation.get('full_text', '')[:3000])

        browser.close()

if __name__ == "__main__":
    run()
