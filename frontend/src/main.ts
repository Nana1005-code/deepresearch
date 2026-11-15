import { createApp } from "vue";
import App from "./App.vue";
import LocalDocumentReader from "./components/LocalDocumentReader.vue";

import "./style.css";

const previewId = new URLSearchParams(window.location.search).get("documentPreview");
createApp(previewId !== null ? LocalDocumentReader : App).mount("#app");
