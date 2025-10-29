// filename: www/index.js
// 이주석은 지우지 하세요.


import {
    getState,
    getMetadata,
    setMetadata,
    mergeMetadata,
    getMetadataByKey,
    saveMetadata,
    loadMetadata,
    deleteMetadata

} from "./apiHelper.js";

import { initMap, updateMapForCurrentUnit } from "./mapView.js";

const initData = {
    init: true,
    currentSelectUnit: 0,
    numberOFUnits: 3,
    robot_1: {
        operation_mode: "manual",
        mission_mode: "stop"
    },
    robot_2: {
        operation_mode: "manual",
        mission_mode: "stop"
    },
    robot_3: {
        operation_mode: "manual",
        mission_mode: "stop"
    }
}

const element_version = document.getElementById("version");

function updateOperationModeStatus(unitIndex, operation_mode) {
    const operationStatusList = document.querySelectorAll('#robot-mm-status .robot-operation-status');  
    const nameTable = {
        "auto": "자율",
        "operator": "원격",
        "manual": "휴대용"
    };
    operationStatusList[unitIndex - 1].innerText = nameTable[operation_mode] || operation_mode;
}

function updateMissionModeStatus(unitIndex, mission_mode) {
    const operationModeList  = document.querySelectorAll('#robot-mm-status .robot-mission-status');
    const nameTable = {
        "move": "이동",
        "patrol": "감시",
        "tracking": "추적",
        "return": "복귀",
        "stop": "종료"
    };
    operationModeList[unitIndex - 1].innerText = nameTable[mission_mode] || mission_mode;
}


// --- 지도 상태 보관용 ---
let _leaflet = {
    map: null,
    layers: {
        base: null,
        marker: null,
        accuracy: null,
    }
};

async function main() {
    
// 0) 지도 먼저 준비
    initMap();

    try {
        const data = await getState();
        console.log("[STATE RESPONSE]", data);
        element_version.innerText = data.state.version;
    } catch (err) {
        console.error("[MAIN ERROR]", err);
        element_version.innerText = "error";
    }

    

    //meta 데이터 확인
    // 메타데이터 확인 및 초기화
    try {
        const res = await getMetadata();
        console.log("[METADATA RESPONSE]", res);

        if (res.r == "ok") {
            const data = res.data;
            if (data?.init) {
                console.log("초기화 완료 ✅");

            } else {
                console.log("초기화 필요 ⚙️");
                const res = await mergeMetadata(initData);
                console.log("[SET METADATA RESPONSE]", res);
            }
        }
    } catch (err) {
        console.error("[METADATA ERROR]", err);
    }


    // 현재 선택된 호기 불러오기
    try {
        //currentSelectUnit 키만 조회
        const res = await getMetadataByKey("currentSelectUnit");
        console.log("[KEYED METADATA RESPONSE]", res);

        const unit = res?.value ?? 0;

        //check radio
        const radioToCheck = document.querySelector(`.unit-selection-group input[type="radio"][value="${unit}"]`);
        if (radioToCheck) {
            radioToCheck.checked = true;
        }

        document.querySelectorAll('.unit-selection-group input[type="radio"]').forEach(radio => {
            radio.addEventListener("change", async e => {
                console.log("선택 호기 변경:", e.target.value);
                const val = parseInt(e.target.value, 10);
                const res = await mergeMetadata({ currentSelectUnit: val });
                console.log("[MERGE METADATA RESPONSE]", res);
                console.log("서버에 선택 호기 업데이트 완료:", val);
                alert("선택 호기 업데이트 완료");
                
                {
                    const res = await saveMetadata();
                    console.log("[SAVE METADATA RESPONSE]", res);
                }
                    

            });
        });
    } catch (err) {
        console.error("[GET KEY ERROR]", err);
    }


    //로봇 운용갯수 갱신
    document.querySelector('#robot-operation-count button').addEventListener("click", async e => {
        const inpRobotNumber = document.querySelector('#robot-operation-count input');
        const val = parseInt(inpRobotNumber.value, 10);
        console.log("로봇 운용 갯수 변경:", val);
        try {
            const res = await mergeMetadata({ numberOFUnits: val });
            console.log("[MERGE METADATA RESPONSE]", res);
            console.log("서버에 로봇 운용 갯수 업데이트 완료:", val);
            alert("로봇 운용 갯수 업데이트 완료");
        } catch (err) {
            console.error("[MERGE METADATA ERROR]", err);
        }
    });

    //로봇운용 갯수
    try {
        const res = await getMetadataByKey("numberOFUnits");
        console.log("[KEYED METADATA RESPONSE]", res);

        if (res.r == "ok") {
            const numberOFUnits = res.value;
            console.log("운용 호기 수:", numberOFUnits);

            const inpRobotNumber = document.querySelector('#robot-operation-count input');
            inpRobotNumber.value = numberOFUnits;

            if (numberOFUnits > 1 && numberOFUnits <= 3) {

                //임무관리
                try {

                    for (let i = 1; i <= numberOFUnits; i++) {

                        //운용모드 설정
                        {
                            
                            const res = await getMetadataByKey(`robot_${i}.operation_mode`);
                            console.log(`[${i}호기 운용모드 KEYED METADATA RESPONSE]`, res);

                            const operation_mode = res?.value || "manual";

                            console.log(`${i}호기 운용모드:`, operation_mode);

                            //check radio
                            const radioToCheck = document.querySelector(`[name="operation-mode-r${i}"][value="${operation_mode}"]`);
                            if (radioToCheck) {
                                radioToCheck.checked = true;
                            }

                            updateOperationModeStatus(i, operation_mode);

                            document.querySelectorAll(`[name="operation-mode-r${i}"]`).forEach(radio => {
                                radio.addEventListener("change", async e => {
                                    console.log(`${i}호기 운용모드 변경:`, e.target.value);
                                    const val = e.target.value;
                                    const res = await mergeMetadata({ [`robot_${i}`]: { operation_mode: val } });
                                    console.log("[MERGE METADATA RESPONSE]", res);
                                    console.log(`서버에 ${i}호기 운용모드 업데이트 완료:`, val);
                                    alert(`${i}호기 운용모드 업데이트 완료`);
                                    updateOperationModeStatus(i, val);
                                });
                               
                            });

                        }

                        //임무모드 설정
                        {
                            const res = await getMetadataByKey(`robot_${i}.mission_mode`);
                            console.log(`[${i}호기 임무모드 KEYED METADATA RESPONSE]`, res);
                            const mission_mode = res?.value || "stop";
                            console.log(`${i}호기 임무모드:`, mission_mode);
                            //check radio
                            const radioToCheck = document.querySelector(`[name="mission-mode-r${i}"][value="${mission_mode}"]`);
                            if (radioToCheck) {
                                radioToCheck.checked = true;
                            }
                            updateMissionModeStatus(i, mission_mode);

                            document.querySelectorAll(`[name="mission-mode-r${i}"]`).forEach(radio => {
                                radio.addEventListener("change", async e => {
                                    console.log(`${i}호기 임무모드 변경:`, e.target.value);
                                    const val = e.target.value;
                                    const res = await mergeMetadata({ [`robot_${i}`]: { mission_mode: val } });
                                    console.log("[MERGE METADATA RESPONSE]", res);
                                    console.log(`서버에 ${i}호기 임무모드 업데이트 완료:`, val);
                                    alert(`${i}호기 임무모드 업데이트 완료`);

                                    updateMissionModeStatus(i, val);
                                });
                            });

                        }

                    }
                } catch (err) {
                    console.error("[GET ROBOT OPERATION MODE ERROR]", err);
                    alert("로봇 운용 모드 조회 중 오류 발생");
                }




            }
        }


    } catch (err) {
        console.error("[GET KEY ERROR]", err);
    }






}

export default main;
