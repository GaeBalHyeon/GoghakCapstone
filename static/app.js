const state = { cameras: [], events: [], settings: { simulation_enabled: false } };
const $ = (id) => document.getElementById(id);

const labels = { fire: "화재", smoke: "연기", normal: "정상" };
const api = async (url, options = {}) => {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

function renderCameras() {
  $("camera-count").textContent = state.cameras.length;
  $("fire-count").textContent = state.cameras.filter(c => c.status === "fire").length;
  $("smoke-count").textContent = state.cameras.filter(c => c.status === "smoke").length;
  const connected = state.cameras.filter(c => c.edge_online).length;
  const indicator = $("system-indicator");
  if (connected) {
    $("system-title").textContent = "Jetson 실시간 분석 중";
    $("system-description").textContent = `${connected}개 카메라가 YOLO 분석 영상을 전송하고 있습니다.`;
    indicator.className = "live-indicator online";
  } else if (state.settings.simulation_enabled) {
    $("system-title").textContent = "시뮬레이션 모드";
    $("system-description").textContent = "실제 Jetson 연결 없이 테스트 이벤트를 생성합니다.";
    indicator.className = "live-indicator simulation";
  } else {
    $("system-title").textContent = "Jetson 연결 대기";
    $("system-description").textContent = "카메라 에이전트가 연결되면 실시간 분석을 시작합니다.";
    indicator.className = "live-indicator waiting";
  }
  $("camera-grid").innerHTML = state.cameras.map(c => `
    <article class="camera-card ${c.status}">
      <div class="camera-feed ${c.edge_online ? "live" : c.local_video ? "local-live" : "offline"}">${c.edge_online ? `<img src="/api/video_feed/${c.id}" alt="${c.id} Jetson 실시간 YOLO 영상">` : c.local_video ? `<video src="${c.local_video}" autoplay muted loop playsinline preload="auto" aria-label="${c.id} Windows 관제 영상"></video>` : ""}</div>
      <div class="camera-info"><div><strong>${c.id}</strong><span class="status ${c.status}">${labels[c.status]}</span></div>
      <p>${c.floor} · ${c.zone} · ${c.edge_online ? `Jetson YOLO · ${c.fps.toFixed(1)} fps` : c.local_video ? "Windows 로컬 관제 영상" : "Jetson 카메라 오프라인"}</p></div>
    </article>`).join("");

  document.querySelectorAll(".camera-marker").forEach(e => e.remove());
  state.cameras.forEach(c => {
    const marker = document.createElement("button");
    marker.className = `camera-marker ${c.status}`;
    marker.style.left = `${c.x}%`; marker.style.top = `${c.y}%`;
    marker.textContent = `${c.id} · ${labels[c.status]}`;
    marker.onclick = () => { $("camera-select").value = c.id; };
    $("floor-map").appendChild(marker);
  });
}

function renderEvents() {
  $("event-count").textContent = state.events.filter(e => new Date(e.detected_at).toDateString() === new Date().toDateString()).length;
  $("event-table").innerHTML = state.events.length ? state.events.map(e => `
    <tr><td>${new Date(e.detected_at).toLocaleString("ko-KR")}</td><td>${e.camera_id}</td><td>${e.floor} ${e.zone}</td>
    <td><span class="status ${e.event_type}">${labels[e.event_type]}</span></td><td>${Math.round(e.confidence * 100)}%</td>
    <td>${e.resolved_at ? "확인 완료" : "발생 중"}</td><td>${e.resolved_at ? "" : `<button onclick="resolveEvent(${e.id})">확인·해제</button>`}</td></tr>`).join("") : `<tr><td colspan="7" class="empty">저장된 감지 이벤트가 없습니다.</td></tr>`;
}

function showAlarm(camera, event) {
  if (!event) return;
  $("alarm").classList.remove("hidden");
  $("alarm-title").textContent = event.event_type === "fire" ? "🚨 화재 감지" : "⚠ 연기 감지";
  $("alarm-text").textContent = `${camera.floor} ${camera.zone} · ${camera.id} · 신뢰도 ${Math.round(camera.confidence * 100)}%`;
  beep();
}

function beep() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  [0, .28, .56].forEach(delay => {
    const osc = ctx.createOscillator(); const gain = ctx.createGain();
    osc.frequency.value = 740; gain.gain.value = .08;
    osc.connect(gain); gain.connect(ctx.destination); osc.start(ctx.currentTime + delay); osc.stop(ctx.currentTime + delay + .15);
  });
}

async function load() {
  [state.cameras, state.events] = await Promise.all([api("/api/cameras"), api("/api/events")]);
  state.settings = await api("/api/settings");
  $("auto-sim").checked = state.settings.simulation_enabled; $("interval").value = state.settings.auto_event_interval;
  $("camera-select").innerHTML = state.cameras.map(c => `<option value="${c.id}">${c.id} · ${c.zone}</option>`).join("");
  renderCameras(); renderEvents();
}

async function trigger(eventType) {
  const payload = await api("/api/detections", { method: "POST", body: JSON.stringify({ camera_id: $("camera-select").value, event_type: eventType, confidence: eventType === "normal" ? 0 : .94, source: "demo-control" }) });
  if (payload.event) showAlarm(payload.camera, payload.event);
}

async function resolveEvent(id) {
  await api(`/api/events/${id}/resolve`, { method: "PUT", body: JSON.stringify({ note: "로컬 관제 화면에서 확인" }) });
  await load();
}
window.resolveEvent = resolveEvent;

function connectWs() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws`);
  ws.onopen = () => { $("connection").className = "connection online"; $("connection").innerHTML = "<span></span> 실시간 연결"; ws.send("ready"); };
  ws.onmessage = async (message) => { const data = JSON.parse(message.data); if (["detection", "resolved", "events-cleared", "edge-status"].includes(data.kind)) { await load(); if (data.event) showAlarm(data.camera, data.event); } };
  ws.onclose = () => { $("connection").className = "connection offline"; $("connection").innerHTML = "<span></span> 재연결 중"; setTimeout(connectWs, 2000); };
}

document.querySelectorAll("[data-event]").forEach(btn => btn.onclick = () => trigger(btn.dataset.event));
$("refresh").onclick = load;
$("delete-events").onclick = async () => {
  if (!state.events.length) return alert("삭제할 이벤트 기록이 없습니다.");
  if (!confirm(`저장된 이벤트 기록 ${state.events.length}건을 모두 삭제할까요?\n삭제한 기록은 복구할 수 없습니다.`)) return;
  const result = await api("/api/events", { method: "DELETE" });
  await load();
  alert(`${result.deleted}건의 기록을 삭제했습니다.`);
};
$("alarm-close").onclick = () => $("alarm").classList.add("hidden");
$("save-settings").onclick = async () => { await api("/api/settings", { method: "PUT", body: JSON.stringify({ simulation_enabled: $("auto-sim").checked, auto_event_interval: Number($("interval").value) }) }); alert("설정을 저장했습니다."); };
load().then(connectWs).catch(err => { console.error(err); alert("서버 데이터를 불러오지 못했습니다."); });

