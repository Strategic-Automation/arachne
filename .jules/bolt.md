## 2025-02-18 - Playwright Browser Context Performance Optimization
**Learning:** Launching multiple browsers in parallel using `pw.chromium.launch()` inside gathered tasks is extremely slow and resource-heavy.
**Action:** Always create a single shared browser instance and open multiple isolated contexts (`browser.new_context()`) for parallel operations. This is over 10x faster and consumes significantly less memory.
