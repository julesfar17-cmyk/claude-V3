import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);

/* Curseur V3 : point + anneau (desktop uniquement), délégation pour les éléments dynamiques */
if (matchMedia("(hover: hover) and (pointer: fine)").matches) {
  const c = document.createElement("div"); c.className = "cur";
  const r = document.createElement("div"); r.className = "cur-ring";
  document.body.append(c, r);
  let x = innerWidth / 2, y = innerHeight / 2, rx = x, ry = y;
  addEventListener("mousemove", (e) => { x = e.clientX; y = e.clientY; c.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%)`; }, { passive: true });
  addEventListener("mousedown", () => document.body.classList.add("down"));
  addEventListener("mouseup", () => document.body.classList.remove("down"));
  const HIT = 'a,button,input,label,select,textarea,[role="button"]';
  addEventListener("mouseover", (e) => { document.body.classList.toggle("hit", !!(e.target.closest && e.target.closest(HIT))); }, { passive: true });
  (function loop() { rx += (x - rx) * 0.16; ry += (y - ry) * 0.16; r.style.transform = `translate(${rx}px,${ry}px) translate(-50%,-50%)`; requestAnimationFrame(loop); })();
}
