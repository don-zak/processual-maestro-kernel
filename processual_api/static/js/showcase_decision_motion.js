(function installMaestroDecisionMotion() {
  if (document.getElementById('maestro-decision-motion-style')) return;
  const style = document.createElement('style');
  style.id = 'maestro-decision-motion-style';
  style.textContent = `
    .mdj-node-core{position:relative}
    .mdj-node.active .mdj-node-core::after{content:'';position:absolute;inset:-1px;border:1px solid rgba(245,166,35,.72);border-radius:50%;animation:mdj-node-wave 1.15s ease-out infinite;pointer-events:none}
    .mdj-pulse{height:6px!important;box-shadow:0 0 9px rgba(245,166,35,.65),0 0 24px rgba(245,166,35,.22)!important}
    .mdj-pulse::after{content:'';position:absolute;right:-6px;top:50%;width:13px;height:13px;border-radius:50%;transform:translateY(-50%);background:var(--amber);box-shadow:0 0 0 5px rgba(245,166,35,.10),0 0 16px rgba(245,166,35,.78);animation:mdj-pulse-head .7s ease-in-out infinite alternate}
    .mdj-node.done .mdj-node-core{box-shadow:0 0 12px rgba(34,211,160,.08)}
    .mdj-node.blocked .mdj-node-core{box-shadow:0 0 14px rgba(248,113,113,.18)}
    @keyframes mdj-node-wave{0%{transform:scale(.94);opacity:.85}75%,100%{transform:scale(1.55);opacity:0}}
    @keyframes mdj-pulse-head{from{transform:translateY(-50%) scale(.86)}to{transform:translateY(-50%) scale(1.18)}}
    @media(prefers-reduced-motion:reduce){.mdj-node.active .mdj-node-core::after,.mdj-pulse::after{animation:none}.mdj-node.active .mdj-node-core::after{display:none}}
  `;
  document.head.appendChild(style);
})();
