import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// 刻意不启用 StrictMode：与 nanobot 同理，保证 effect 幂等加载纯净
createRoot(document.getElementById("root")!).render(<App />);
