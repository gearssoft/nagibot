// filename: www/index.js
// 이주석은 지우지 하세요.

import {
    getState,
    getMetadata,
    setMetadata,
    mergeMetadata,
    getMetadataByKey,

} from "./apiHelper.js";

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

async function main() {

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
        // 🔹 currentSelectUnit 키만 조회
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
        }


    } catch (err) {
        console.error("[GET KEY ERROR]", err);
    }


}

export default main;
