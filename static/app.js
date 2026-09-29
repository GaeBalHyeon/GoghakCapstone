const state = { cameras: [], events: [], settings: { simulation_enabled: false }, health: {}, notifications: {} };
const $ = (id) => document.getElementById(id);

const labels = { fire: "화재", smoke: "연기", normal: "정상" };
const notificationLabels = { pending: "전송 중", sent: "전송 완료", failed: "전송 실패", disabled: "사용 안 함" };
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
  document.querySelectorAll(".camera-marker").forEach(e => e.remove());
  state.cameras.forEach(c => {
    const marker = document.createElement("article");
    marker.className = `camera-marker ${c.status}`;
    marker.style.setProperty("--camera-x", `${c.x}%`);
    marker.style.setProperty("--camera-y", `${c.y}%`);
    const feedClass = c.edge_online ? "live" : c.local_video ? "local-live" : "offline";
    const media = c.edge_online
      ? `<img src="/api/video_feed/${c.id}" alt="${c.id} Jetson 실시간 YOLO 영상">`
      : c.local_video
        ? `<video src="${c.local_video}" autoplay muted loop playsinline preload="auto" aria-label="${c.id} Windows 관제 영상"></video>`
        : '<span class="camera-placeholder" aria-hidden="true"></span>';
    const updated = c.updated_at ? new Date(c.updated_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "로컬 재생";
    const analysis = c.edge_online ? "AI 분석 중" : c.local_video ? "관제 재생" : "연결 대기";
    const metric = c.edge_online ? `${c.fps.toFixed(1)} FPS` : `${Math.round(c.confidence * 100)}%`;
    marker.innerHTML = `<div class="map-camera-feed ${feedClass}">${media}<span class="feed-badge">${c.edge_online ? "JETSON LIVE" : c.local_video ? "LOCAL LIVE" : "OFFLINE"}</span><div class="feed-telemetry"><span>${analysis}</span><b>${metric}</b></div></div><div class="map-camera-meta"><div><strong>${c.id} · ${c.zone}</strong><small>${updated} · ${labels[c.status]}</small></div><button class="camera-expand" type="button" aria-label="${c.id} 크게 보기">↗</button></div>`;
    marker.tabIndex = 0;
    marker.setAttribute("role", "button");
    marker.setAttribute("aria-label", `${c.id} ${c.zone} 확대 보기`);
    marker.onclick = () => { $("camera-select").value = c.id; openCameraModal(c); };
    marker.querySelector(".camera-expand").onclick = event => { event.stopPropagation(); openCameraModal(c); };
    marker.onkeydown = event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); marker.click(); } };
    $("floor-map").appendChild(marker);
  });
}

function setSystemRow(prefix, online, value, description) {
  $(`${prefix}-health-dot`).className = `system-status-icon ${online ? "online" : "offline"}`;
  $(`${prefix}-health-value`).textContent = value;
  $(`${prefix}-health-text`).textContent = description;
}

function renderSystemHealth() {
  const jetson = state.cameras.find(camera => camera.id === "CAM-01");
  const jetsonOnline = Boolean(jetson?.edge_online);
  setSystemRow("jetson", jetsonOnline, jetsonOnline ? "ONLINE" : "OFFLINE", jetsonOnline ? "Edge 영상 수신 정상" : "에이전트 연결 대기");
  setSystemRow("yolo", jetsonOnline && jetson.fps > 0, jetsonOnline ? `${jetson.fps.toFixed(1)} FPS` : "대기", jetsonOnline ? "best.pt 실시간 추론" : "Jetson 연결 필요");
  setSystemRow("telegram", Boolean(state.notifications.telegram_configured), state.notifications.telegram_configured ? "READY" : "OFF", state.notifications.telegram_configured ? "텍스트 우선 경보 활성" : "알림 설정 필요");
  const databaseOnline = state.health.status === "ok";
  setSystemRow("database", databaseOnline, databaseOnline ? String(state.health.database || "DB").toUpperCase() : "ERROR", databaseOnline ? "이벤트 저장소 정상" : "서버 상태 확인 필요");
  const allHealthy = jetsonOnline && databaseOnline && state.notifications.telegram_configured;
  $("system-health-badge").className = `system-health-badge ${allHealthy ? "healthy" : "attention"}`;
  $("system-health-badge").textContent = allHealthy ? "ALL SYSTEMS GO" : "확인 필요";
  $("last-frame-time").textContent = jetson?.updated_at ? new Date(jetson.updated_at).toLocaleString("ko-KR") : "수신 기록 없음";
}

function renderDailySummary() {
  const today = new Date().toDateString();
  const events = state.events.filter(event => new Date(event.detected_at).toDateString() === today);
  const fire = events.filter(event => event.event_type === "fire").length;
  const smoke = events.filter(event => event.event_type === "smoke").length;
  const resolved = events.filter(event => event.resolved_at);
  const responseSeconds = resolved.map(event => (new Date(event.resolved_at) - new Date(event.detected_at)) / 1000).filter(value => value >= 0);
  const average = responseSeconds.length ? responseSeconds.reduce((sum, value) => sum + value, 0) / responseSeconds.length : null;
  $("daily-total").textContent = events.length;
  $("daily-types").textContent = `${fire} / ${smoke}`;
  $("daily-resolved").textContent = resolved.length;
  $("daily-resolved-rate").textContent = `처리율 ${events.length ? Math.round(resolved.length / events.length * 100) : 0}%`;
  $("daily-response").textContent = average === null ? "—" : average < 60 ? `${Math.round(average)}초` : `${(average / 60).toFixed(1)}분`;

  const cameraCounts = Object.fromEntries(state.cameras.map(camera => [camera.id, 0]));
  events.forEach(event => { cameraCounts[event.camera_id] = (cameraCounts[event.camera_id] || 0) + 1; });
  const renderBars = (target, items) => {
    const max = Math.max(...items.map(([, value]) => value), 1);
    $(target).innerHTML = items.map(([label, value]) => `<div class="bar-row"><span>${label}</span><div><i style="width:${value / max * 100}%"></i></div><b>${value}</b></div>`).join("");
  };
  renderBars("daily-camera-chart", Object.entries(cameraCounts));
  renderBars("daily-type-chart", [["화재", fire], ["연기", smoke], ["처리 완료", resolved.length]]);
}

function openCameraModal(camera) {
  const dialog = $("camera-modal");
  const source = camera.edge_online ? "Jetson YOLO 실시간 분석" : camera.local_video ? "Windows 로컬 관제 영상" : "연결 대기";
  const media = camera.edge_online
    ? `<img src="/api/video_feed/${camera.id}" alt="${camera.id} 확대된 Jetson YOLO 영상">`
    : camera.local_video
      ? `<video src="${camera.local_video}" autoplay muted loop playsinline controls aria-label="${camera.id} 확대된 Windows 관제 영상"></video>`
      : '<div class="modal-offline"><span></span><strong>카메라 연결 대기</strong></div>';
  $("modal-camera-title").textContent = `${camera.id} · ${camera.zone}`;
  $("modal-camera-description").textContent = `${camera.floor} · ${camera.charger}`;
  $("modal-camera-source").textContent = source + (camera.edge_online ? ` · ${camera.fps.toFixed(1)} FPS` : "");
  $("modal-camera-status").className = `status ${camera.status}`;
  $("modal-camera-status").textContent = labels[camera.status];
  $("camera-modal-feed").innerHTML = media;
  dialog.showModal();
}

function closeCameraModal() {
  const dialog = $("camera-modal");
  dialog.close();
  $("camera-modal-feed").replaceChildren();
}

function renderEvents() {
  $("event-count").textContent = state.events.filter(e => new Date(e.detected_at).toDateString() === new Date().toDateString()).length;
  $("event-table").innerHTML = state.events.length ? state.events.map(e => `
    <tr><td>${e.snapshot_url ? `<button class="snapshot-button" onclick="openSnapshot(${e.id})" aria-label="${e.camera_id} 감지 스냅샷 확대"><img src="${e.snapshot_url}" alt="${e.camera_id} 감지 스냅샷"></button>` : '<span class="snapshot-empty">없음</span>'}</td>
    <td>${new Date(e.detected_at).toLocaleString("ko-KR")}</td><td>${e.camera_id}</td><td>${e.floor} ${e.zone}</td>
    <td><span class="status ${e.event_type}">${labels[e.event_type]}</span></td><td>${Math.round(e.confidence * 100)}%</td>
    <td><span class="notification-state ${e.notification_status || "disabled"}">${notificationLabels[e.notification_status] || "대기"}</span></td>
    <td>${e.resolved_at ? "확인 완료" : "발생 중"}</td><td>${e.resolved_at ? "" : `<button onclick="resolveEvent(${e.id})">확인·해제</button>`}</td></tr>`).join("") : `<tr><td colspan="9" class="empty">저장된 감지 이벤트가 없습니다.</td></tr>`;
  renderDailySummary();
}

function openSnapshot(id) {
  const event = state.events.find(item => item.id === id);
  if (!event?.snapshot_url) return;
  $("modal-camera-title").textContent = `${event.camera_id} · ${labels[event.event_type]} 스냅샷`;
  $("modal-camera-description").textContent = new Date(event.detected_at).toLocaleString("ko-KR");
  $("modal-camera-source").textContent = `${event.floor} · ${event.zone} · 신뢰도 ${Math.round(event.confidence * 100)}%`;
  $("modal-camera-status").className = `status ${event.event_type}`;
  $("modal-camera-status").textContent = labels[event.event_type];
  $("camera-modal-feed").innerHTML = `<img src="${event.snapshot_url}" alt="${event.camera_id} 감지 스냅샷 확대">`;
  $("camera-modal").showModal();
}
window.openSnapshot = openSnapshot;

function showAlarm(camera, event) {
  if (!event) return;
  $("alarm").classList.remove("hidden");
  $("alarm-title").textContent = event.event_type === "fire" ? "🚨 화재 감지" : "⚠ 연기 감지";
  $("alarm-text").textContent = `${camera.floor} ${camera.zone} · ${camera.id} · 신뢰도 ${Math.round(camera.confidence * 100)}%`;
  beep();
}

function syncAlarm() {
  if (!state.cameras.some(camera => camera.status === "fire" || camera.status === "smoke")) {
    $("alarm").classList.add("hidden");
  }
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
  [state.cameras, state.events, state.settings, state.health, state.notifications] = await Promise.all([api("/api/cameras"), api("/api/events"), api("/api/settings"), api("/api/health"), api("/api/notifications/status")]);
  $("auto-sim").checked = state.settings.simulation_enabled; $("interval").value = state.settings.auto_event_interval;
  $("camera-select").innerHTML = state.cameras.map(c => `<option value="${c.id}">${c.id} · ${c.zone}</option>`).join("");
  renderCameras(); renderEvents(); renderSystemHealth(); syncAlarm();
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
  ws.onmessage = async (message) => { const data = JSON.parse(message.data); if (["detection", "resolved", "events-cleared", "edge-status", "notification-updated"].includes(data.kind)) { await load(); if (data.event) showAlarm(data.camera, data.event); } };
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
$("camera-modal-close").onclick = closeCameraModal;
$("camera-modal").onclick = event => { if (event.target === $("camera-modal")) closeCameraModal(); };
$("open-test-controls").onclick = () => $("test-control-modal").showModal();
$("test-control-close").onclick = () => $("test-control-modal").close();
$("test-control-modal").onclick = event => { if (event.target === $("test-control-modal")) $("test-control-modal").close(); };
$("save-settings").onclick = async () => { await api("/api/settings", { method: "PUT", body: JSON.stringify({ simulation_enabled: $("auto-sim").checked, auto_event_interval: Number($("interval").value) }) }); alert("설정을 저장했습니다."); };
load().then(connectWs).catch(err => { console.error(err); alert("서버 데이터를 불러오지 못했습니다."); });

