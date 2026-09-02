(() => {
  const shell = document.getElementById("platformShell");
  const workbench = document.getElementById("workbenchView");
  const platformButton = document.getElementById("platformButton");
  const title = document.getElementById("platformTitle");
  const state = { info: null, view: "projects", prepared: null };

  const fixtureExample = {
    id: "rune-pogo-reference",
    revision: 1,
    maximumVoltage: 3.3,
    maximumCurrentMa: 250,
    minimumSpacingMm: 2.54,
    testPoints: [
      { id: "TP1", logicalNet: "RUNE_D0", pinRef: "s3:D0", visualAnchor: "s3:D0", pad: "J1.1", xMm: 12.7, yMm: 10.16, probe: "P75-B1" },
      { id: "TP2", logicalNet: "RUNE_GND", pinRef: "s3:GND", visualAnchor: "s3:GND", pad: "J1.7", xMm: 12.7, yMm: 27.94, probe: "P75-B1" },
    ],
    locatingHoles: [{ xMm: 5, yMm: 5, diameterMm: 3 }],
    keepouts: [],
    protection: [{ net: "RUNE_D0", kind: "series-resistor", value: "1k" }],
  };
  document.querySelector('#fixtureForm textarea[name="fixture"]').value = JSON.stringify(fixtureExample, null, 2);

  async function request(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    if (!response.ok) throw new Error(payload.error || response.statusText);
    return payload;
  }

  function showResult(element, value, isError = false) {
    element.classList.toggle("error", isError);
    element.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function setView(view) {
    if (view === "workbench") {
      shell.hidden = true;
      workbench.hidden = false;
      document.body.classList.remove("platform-open");
      platformButton.textContent = "CircuitLab";
      window.dispatchEvent(new Event("resize"));
      return;
    }
    state.view = view;
    workbench.hidden = true;
    shell.hidden = false;
    document.body.classList.add("platform-open");
    platformButton.textContent = "Workbench";
    document.querySelectorAll("[data-platform-view]").forEach(button => button.classList.toggle("active", button.dataset.platformView === view));
    document.querySelectorAll(".platform-view").forEach(panel => panel.classList.toggle("active", panel.dataset.view === view));
    title.textContent = view[0].toUpperCase() + view.slice(1);
    if (view === "components") loadComponents();
    if (view === "reports") loadReports();
  }

  async function loadOverview() {
    state.info = await request("/api/platform");
    document.getElementById("componentCount").textContent = state.info.componentCount;
    document.getElementById("maximumVoltage").textContent = `${state.info.maximumVoltage} V`;
    document.getElementById("platformSafety").textContent = state.info.physicalStatus;
    const { projects } = await request("/api/projects");
    const project = projects[0];
    document.getElementById("projectName").textContent = project?.name || "No project";
    document.getElementById("projectSchema").textContent = project?.schema || "";
  }

  function recordButton(component) {
    const button = document.createElement("button");
    button.type = "button";
    const heading = document.createElement("strong");
    heading.textContent = component.mpn;
    const manufacturer = document.createElement("span");
    manufacturer.textContent = component.manufacturer;
    const ref = document.createElement("small");
    ref.textContent = component.ref;
    const status = document.createElement("i");
    status.textContent = component.status;
    button.append(heading, manufacturer, ref, status);
    button.addEventListener("click", () => loadComponent(component.ref, button));
    return button;
  }

  async function loadComponents() {
    const query = encodeURIComponent(document.getElementById("componentSearch").value.trim());
    const { components } = await request(`/api/components?q=${query}`);
    const list = document.getElementById("componentList");
    list.replaceChildren(...components.map(recordButton));
    if (!components.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No component revisions. Import Sindri assets or acquire an exact MPN with the CircuitLab CLI.";
      list.appendChild(empty);
    }
  }

  async function loadComponent(reference, selectedButton) {
    document.querySelectorAll("#componentList > button").forEach(button => button.classList.toggle("active", button === selectedButton));
    const component = await request(`/api/components/${encodeURIComponent(reference)}`);
    const detail = document.getElementById("componentDetail");
    detail.classList.remove("empty-state");
    detail.replaceChildren();
    const eyebrow = document.createElement("span");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = component.identity.status;
    const heading = document.createElement("h2");
    heading.textContent = `${component.identity.manufacturer} ${component.identity.mpn}`;
    const ref = document.createElement("code");
    ref.textContent = reference;
    const stats = document.createElement("div");
    stats.className = "component-stats";
    const values = [
      ["LEVEL", component.identity.level],
      ["ELECTRICAL", component.electrical?.status || "UNVERIFIED"],
      ["TOUCHPOINTS", String(component.visual?.anchors?.length || 0)],
      ["COORDINATES", component.visual?.coordinateStatus || "UNVERIFIED"],
      ["PROCUREMENT", String(component.procurement?.length || 0)],
      ["HASH", component.packageSha256?.slice(0, 12) || "—"],
    ];
    for (const [label, value] of values) {
      const item = document.createElement("div");
      const small = document.createElement("small"); small.textContent = label;
      const strong = document.createElement("strong"); strong.textContent = value;
      item.append(small, strong); stats.appendChild(item);
    }
    const pins = document.createElement("pre");
    pins.className = "pin-preview";
    pins.textContent = (component.electrical?.pins || []).map(pin => `${pin.number}  ${pin.name}  ${pin.direction}`).join("\n") || "No pins recorded";
    detail.append(eyebrow, heading, ref, stats, pins);
  }

  async function loadReports() {
    const { reports } = await request("/api/reports");
    const list = document.getElementById("reportsList");
    list.replaceChildren();
    for (const report of reports) {
      const card = document.createElement("article");
      card.className = `platform-card report-card ${report.state.toLowerCase()}`;
      const stateLabel = document.createElement("span"); stateLabel.className = "eyebrow"; stateLabel.textContent = report.state;
      const heading = document.createElement("h2"); heading.textContent = report.jobId;
      const summary = document.createElement("p");
      summary.textContent = `${report.results.filter(item => item.passed).length}/${report.results.length} tests passed · ${report.driver} · ${report.physicalStatus}`;
      const hash = document.createElement("code"); hash.textContent = report.reportSha256;
      card.append(stateLabel, heading, summary, hash); list.appendChild(card);
    }
    if (!reports.length) list.textContent = "No HIL reports yet.";
  }

  function updateHil(value) {
    document.getElementById("hilState").textContent = value.state || "IDLE";
    showResult(document.getElementById("hilEvents"), value);
    const binding = value.binding || {};
    const list = document.getElementById("hilBinding");
    list.replaceChildren();
    for (const [key, item] of Object.entries(binding)) {
      const dt = document.createElement("dt"); dt.textContent = key;
      const dd = document.createElement("dd"); dd.textContent = typeof item === "string" ? item : JSON.stringify(item);
      list.append(dt, dd);
    }
  }

  document.querySelectorAll("[data-platform-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.platformView)));
  platformButton.addEventListener("click", () => shell.hidden ? setView(state.view) : setView("workbench"));
  document.getElementById("componentRefresh").addEventListener("click", loadComponents);
  document.getElementById("componentSearch").addEventListener("input", () => window.clearTimeout(state.searchTimer) || (state.searchTimer = window.setTimeout(loadComponents, 180)));
  document.getElementById("reportsRefresh").addEventListener("click", loadReports);

  document.getElementById("touchpointForm").addEventListener("submit", async event => {
    event.preventDefault();
    const result = document.getElementById("touchpointResult");
    try {
      const form = new FormData(event.currentTarget);
      const payload = { ref: form.get("ref"), appearanceSha256: form.get("appearanceSha256"), points: JSON.parse(form.get("points")) };
      showResult(result, await request("/api/touchpoints/calibrate", { method: "POST", body: JSON.stringify(payload) }));
      await loadOverview();
    } catch (error) { showResult(result, error.message, true); }
  });

  document.getElementById("fixtureForm").addEventListener("submit", async event => {
    event.preventDefault();
    const result = document.getElementById("fixtureResult");
    try {
      const form = new FormData(event.currentTarget);
      showResult(result, await request("/api/fixture/generate", { method: "POST", body: JSON.stringify(JSON.parse(form.get("fixture"))) }));
    } catch (error) { showResult(result, error.message, true); }
  });

  document.getElementById("hilDemoButton").addEventListener("click", async () => {
    try {
      state.prepared = await request("/api/hil/prepare", {
        method: "POST",
        body: JSON.stringify({
          driver: "mock", devices: { dut: "mock-esp32-s3", fixture: "mock-nrf52840" },
          wiringLockSha256: "0".repeat(64), assetLockSha256: "1".repeat(64), firmwareSha256: "2".repeat(64),
          plan: { schema: "hil-plan/v1", id: "rune-software-loop", safety: { maximumVoltage: 3.3, maximumCurrentMa: 250 }, tests: [
            { id: "gpio-loop", op: "gpio", expected: true }, { id: "pwm-frequency", op: "pwm", sample: 1000, minimum: 995, maximum: 1005 },
            { id: "adc-window", op: "adc", sample: 1.65, minimum: 1.55, maximum: 1.75 }, { id: "i2c-enumerate", op: "i2c", expected: "0x68" },
            { id: "spi-loop", op: "spi", expected: "a55a" }, { id: "uart-loop", op: "uart", expected: "RUNE" },
            { id: "interrupt", op: "interrupt", expected: true }, { id: "heartbeat", op: "heartbeat", expected: true },
          ] },
        }),
      });
      updateHil(state.prepared);
      document.getElementById("hilArmButton").disabled = false;
      document.getElementById("hilAbortButton").disabled = false;
    } catch (error) { showResult(document.getElementById("hilEvents"), error.message, true); }
  });
  document.getElementById("hilArmButton").addEventListener("click", async () => {
    try {
      const armed = await request("/api/hil/arm", { method: "POST", body: JSON.stringify({ jobId: state.prepared.jobId, nonce: state.prepared.nonce, acknowledged: true }) });
      updateHil(armed); document.getElementById("hilArmButton").disabled = true; document.getElementById("hilRunButton").disabled = false;
    } catch (error) { showResult(document.getElementById("hilEvents"), error.message, true); }
  });
  document.getElementById("hilRunButton").addEventListener("click", async () => {
    try {
      const report = await request("/api/hil/run", { method: "POST", body: JSON.stringify({ jobId: state.prepared.jobId, options: {} }) });
      updateHil(report); document.getElementById("hilRunButton").disabled = true; document.getElementById("hilAbortButton").disabled = true;
    } catch (error) { showResult(document.getElementById("hilEvents"), error.message, true); }
  });
  document.getElementById("hilAbortButton").addEventListener("click", async () => {
    try { updateHil(await request("/api/hil/abort", { method: "POST", body: JSON.stringify({ jobId: state.prepared.jobId }) })); }
    catch (error) { showResult(document.getElementById("hilEvents"), error.message, true); }
  });

  loadOverview().catch(error => showResult(document.getElementById("hilEvents"), `Platform startup failed: ${error.message}`, true));
})();
