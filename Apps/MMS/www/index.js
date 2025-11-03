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
    deleteMetadata,
    setBaseHost,
    setAuthToken
} from "/libs/apiHelper.js";

async function main() {

    const mmsConfig = JSON.parse(localStorage.getItem("mmsConfig")) || {};
    const host = mmsConfig.apiIp;
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
    // setBaseHost(".");
    // setAuthToken(authToken);

    console.log("[MMS CONFIG]", { host, port, authToken });

    const dumpTextOut = document.getElementById("dumpTextOut");

    document.getElementById("btndump").addEventListener("click", async () => {
        const data = await getMetadata();
        console.log("=== METADATA DUMP ===");
        console.log(data);

        dumpTextOut.innerText = JSON.stringify(data, null, 2);

    });



}

export default main;
