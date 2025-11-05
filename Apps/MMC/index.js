// filename: www/index.js
// 이주석은 지우지 마세요.

import {
    getState,
    getMetadata,
    mergeMetadata,
    getMetadataByKey,
    saveMetadata,
    setBaseHost,
    setAuthToken
} from "/libs/apiHelper.js";

import { initMap, updateMapForCurrentUnit, updateMapWithStatusData,
    showNoLocationBanner, hideNoLocationBanner
} from "./mapView.js";


// --- 기본 초기 메타데이터 ---
const INIT_DATA = {
    init: true,
    currentSelectUnit: 0,
    numberOFUnits: 3,
    robot_1: { operation_mode: "manual", mission_mode: "stop" },
    robot_2: { operation_mode: "manual", mission_mode: "stop" },
    robot_3: { operation_mode: "manual", mission_mode: "stop" }
};

// --- 한글표 변환 테이블 ---
const NAME_TABLE_OPERATION = {
    auto: "자율",
    operator: "원격",
    manual: "휴대용"
};
const NAME_TABLE_MISSION = {
    move: "이동",
    patrol: "감시",
    tracking: "추적",
    return: "복귀",
    stop: "종료"
};

function toInt(v, def = 0) {
    const n = Number.parseInt(String(v ?? "").trim(), 10);
    return Number.isFinite(n) ? n : def;
}

export class MMCApp {
    constructor() {
        // --- DOM 접근자 ---
        this.getVersionLabel = () => document.getElementById("version");
        this.getUnitRadios = () =>
            document.querySelectorAll('.unit-selection-group input[type="radio"]');
        this.getRobotCountInput = () =>
            document.querySelector('#robot-operation-count input');
        this.getRobotCountButton = () =>
            document.querySelector('#robot-operation-count button');
        this.getOperationStatusList = () =>
            document.querySelectorAll('#robot-mm-status .robot-operation-status');
        this.getMissionStatusList = () =>
            document.querySelectorAll('#robot-mm-status .robot-mission-status');
        this.getModeContainer = () =>
            document.getElementById("robot-mode-container") || document;

        // --- 내부 상태 ---
        this.polling = false;
        this.pollInterval = 1000;
    }

    // ------------------------------
    //        Entry point
    // ------------------------------
    async start() {
        this.#setupEndpoint();
        initMap();

        await this.#loadStateVersion();
        await this.#ensureMetadata();
        await this.#bindUnitSelection();
        this.#bindRobotCountSetter();
        this.#bindRobotModeHandlers();

        this.startPolling();
    }

    stop() {
        this.polling = false;
    }

    // ------------------------------
    //        Initialization
    // ------------------------------
    #setupEndpoint() {
        const mmsConfig = JSON.parse(localStorage.getItem("mmsConfig")) || {};
        const host = mmsConfig.apiIp || "http://localhost";
        const port = mmsConfig.apiPort || "8080";
        const authToken = mmsConfig.authToken || "7204";

        // 기존 로직 유지: 최종적으로 '.'(상대경로) 사용
        if (host === ".") {
            setBaseHost(host);
        } else if (host === "") {
            const _url = new URL(window.location.href);
            setBaseHost(`${_url.protocol}//${_url.hostname}:${port}`);
        } else {
            setBaseHost(`http://localhost:${port}`);
        }
        setBaseHost(".");
        setAuthToken(authToken);

        console.log("[MMS CONFIG]", { host, port, authToken });
    }

    async #loadStateVersion() {
        try {
            const data = await getState();
            console.log("[STATE RESPONSE]", data);
            const el = this.getVersionLabel();
            if (el) el.innerText = data?.state?.version ?? "-";
        } catch (err) {
            console.error("[STATE ERROR]", err);
            const el = this.getVersionLabel();
            if (el) el.innerText = "error";
        }
    }

    async #ensureMetadata() {
        try {
            const res = await getMetadata();
            console.log("[METADATA RESPONSE]", res);
            if (res?.r === "ok") {
                const data = res.data;
                if (!data?.init) {
                    console.log("초기화 필요 ⚙️");
                    const m = await mergeMetadata(INIT_DATA);
                    console.log("[SET METADATA RESPONSE]", m);

                    const s = await saveMetadata();
                    console.log("[SAVE METADATA RESPONSE]", s);

                } else {
                    console.log("초기화 완료 ✅");
                }
            }
        } catch (err) {
            console.error("[METADATA ERROR]", err);
        }
    }

    // ------------------------------
    //       UI / Event Bindings
    // ------------------------------
    async #bindUnitSelection() {
        try {
            const res = await getMetadataByKey("currentSelectUnit");
            console.log("[KEYED METADATA RESPONSE]", res);
            const unit = res?.value ?? 0;

            // 초기 라디오 체크
            const radioToCheck = document.querySelector(
                `.unit-selection-group input[type="radio"][value="${unit}"]`
            );
            if (radioToCheck) radioToCheck.checked = true;

            // 변경 이벤트
            this.getUnitRadios().forEach((radio) => {
                radio.addEventListener("change", async (e) => {
                    const val = toInt(e.target.value, 0);
                    console.log("선택 호기 변경:", val);
                    const r = await mergeMetadata({ currentSelectUnit: val });
                    console.log("[MERGE METADATA RESPONSE]", r);
                    alert("선택 호기 업데이트 완료");

                    this.#updateRobotStatusDataToMap(true);


                    try {
                        const s = await saveMetadata();
                        console.log("[SAVE METADATA RESPONSE]", s);
                    } catch (err) {
                        console.error("[SAVE ERROR]", err);
                    }
                    try {
                        updateMapForCurrentUnit?.(val);
                    } catch (_) { }
                });
            });
        } catch (err) {
            console.error("[GET KEY ERROR]", err);
        }
    }

    #bindRobotCountSetter() {
        const btn = this.getRobotCountButton();
        if (!btn) return;

        btn.addEventListener("click", async () => {
            const inp = this.getRobotCountInput();
            const val = toInt(inp?.value, 0);
            console.log("로봇 운용 갯수 변경:", val);
            try {
                const res = await mergeMetadata({ numberOFUnits: val });
                console.log("[MERGE METADATA RESPONSE]", res);
                alert("로봇 운용 갯수 업데이트 완료");
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
            }
        });
    }

    #bindRobotModeHandlers() {
        // 이벤트 위임 (클로저 제거)
        const container = this.getModeContainer();
        container.addEventListener("change", async (e) => {
            const el = e.target;
            if (!(el instanceof HTMLInputElement) || el.type !== "radio") return;

            const mOp = el.name.match(/^operation-mode-r(\d+)$/);
            const mMs = el.name.match(/^mission-mode-r(\d+)$/);

            try {
                if (mOp) {
                    const i = toInt(mOp[1], 0);
                    const val = el.value;
                    console.log(`${i}호기 운용모드 변경:`, val);
                    await mergeMetadata({ [`robot_${i}`]: { operation_mode: val } });
                    alert(`${i}호기 운용모드 업데이트 완료`);
                    this.#updateOperationModeStatus(i, val);
                } else if (mMs) {
                    const i = toInt(mMs[1], 0);
                    const val = el.value;
                    console.log(`${i}호기 임무모드 변경:`, val);
                    await mergeMetadata({ [`robot_${i}`]: { mission_mode: val } });
                    alert(`${i}호기 임무모드 업데이트 완료`);
                    this.#updateMissionModeStatus(i, val);
                }
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
                alert("서버 업데이트 실패");
            }
        });
    }

    #updateOperationModeStatus(unitIndex, operation_mode) {
        const list = this.getOperationStatusList();
        const text = NAME_TABLE_OPERATION[operation_mode] || operation_mode;
        const el = list[unitIndex - 1];
        if (el) el.innerText = text;
    }

    #updateMissionModeStatus(unitIndex, mission_mode) {
        const list = this.getMissionStatusList();
        const text = NAME_TABLE_MISSION[mission_mode] || mission_mode;
        const el = list[unitIndex - 1];
        if (el) el.innerText = text;
    }

    // ------------------------------
    //      Polling / Updates
    // ------------------------------
    startPolling(intervalMs) {
        if (intervalMs) this.pollInterval = Math.max(200, intervalMs);
        if (this.polling) return;
        this.polling = true;
        this.#pollLoop();
    }

    stopPolling() {
        this.polling = false;
    }

    async #pollLoop() {
        while (this.polling) {
            try {
                await this.#updateRobotModeStatusOnce();
                await this.#updateRobotStatusDataToMap();

            } catch (err) {
                console.error("[POLL ERROR]", err);
            }

            await new Promise((r) => setTimeout(r, this.pollInterval));
        }
    }

    async #updateRobotModeStatusOnce() {
        const resNum = await getMetadataByKey("numberOFUnits");
        if (resNum?.r !== "ok") return;

        const numberOFUnits = resNum.value;
        // console.log("운용 호기 수:", numberOFUnits);

        const inp = this.getRobotCountInput();
        if (inp) inp.value = numberOFUnits;

        for (let i = 1; i <= numberOFUnits; i++) {
            // 운용모드
            const r1 = await getMetadataByKey(`robot_${i}.operation_mode`);
            const op = r1?.value || "manual";
            const radio1 = document.querySelector(
                `[name="operation-mode-r${i}"][value="${op}"]`
            );
            if (radio1) radio1.checked = true;
            this.#updateOperationModeStatus(i, op);

            // 임무모드
            const r2 = await getMetadataByKey(`robot_${i}.mission_mode`);
            const ms = r2?.value || "stop";
            const radio2 = document.querySelector(
                `[name="mission-mode-r${i}"][value="${ms}"]`
            );
            if (radio2) radio2.checked = true;
            this.#updateMissionModeStatus(i, ms);
        }
    }

    async #updateRobotStatusDataToMap(fixCenter = true) {
        const sel = await getMetadataByKey("currentSelectUnit");
        const idx0 = sel?.value ?? 0;
        const unitIndex = Number(idx0) + 1;

        const res = await getMetadataByKey(`robot_${unitIndex}.status_data`);
        const status = res?.value;

        if (!status || typeof status !== "object") {
            // ✅ 위치 데이터 없음 배너 표시
            showNoLocationBanner("선택된 호기의 위치 데이터 없음");
            return;
        }

        // ✅ 정상 데이터면 배너 숨기고 지도 갱신
        hideNoLocationBanner();
        updateMapWithStatusData(status, fixCenter);
    }
}

// ------------------------------
// Default entry for compatibility
// ------------------------------
async function main() {
    const app = new MMCApp();
    await app.start();
}

export default main;
