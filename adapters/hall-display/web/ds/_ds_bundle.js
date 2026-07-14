/* @ds-bundle: {"format":4,"namespace":"PiranesiVUIDesignSystem_8af396","components":[{"name":"PiranesiOrb","sourcePath":"components/orb/PiranesiOrb.jsx"}],"sourceHashes":{"components/orb/PiranesiOrb.jsx":"488b92d1aca4"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.PiranesiVUIDesignSystem_8af396 = window.PiranesiVUIDesignSystem_8af396 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/orb/PiranesiOrb.jsx
try { (() => {
/*
 * PiranesiOrb — the voice of the House of Piranesi.
 * A fluid, jiggly, pulsating circle with the columned-house glyph inside.
 *
 * Two axes of expression, both continuously lerped (morphs, never cuts):
 *  - state: the conversational state (waiting/listening/thinking/talking/working/error)
 *  - modulation: a context layer over any state — time of day (auto), weather,
 *    system status, and "threat" (pufferfish: crimson, spiked, puffed up).
 *
 * Audio-reactive: pass `audio` (MediaStream mic, HTMLMediaElement output,
 * AnalyserNode, or a ()=>0..1 level function) and the waveform, glyph pulse
 * and glow follow the real signal. Without audio, talking falls back to a
 * pseudo speech envelope.
 */

const GLYPH_PATHS = ["M23 39 L43 28 L63 39", "M30 45 L30 69", "M43 45 L43 69", "M56 45 L56 69", "M19 72 L67 72"];
const GLYPH_CENTER = {
  x: 43,
  y: 50
};
const MOOD_VARS = {
  waiting: "--mood-waiting",
  listening: "--mood-listening",
  thinking: "--mood-thinking",
  talking: "--mood-talking",
  working: "--mood-working",
  error: "--mood-error"
};
const MOOD_FALLBACKS = {
  waiting: "#8F8168",
  listening: "#86C7B0",
  thinking: "#9D93D6",
  talking: "#E5B96E",
  working: "#D98E5F",
  error: "#D9705F"
};
const MOD_VARS = {
  dawn: "--mod-dawn",
  day: "--mod-day",
  dusk: "--mod-dusk",
  night: "--mod-night",
  rain: "--mod-rain",
  storm: "--mod-storm",
  degraded: "--mod-degraded",
  threat: "--mod-threat"
};
const MOD_FALLBACKS = {
  dawn: "#E8A98C",
  day: "#F0DCBE",
  dusk: "#C97F4F",
  night: "#7C8BAA",
  rain: "#7FA3B8",
  storm: "#6E7F9E",
  degraded: "#C9A23F",
  threat: "#8B1E2D"
};

// Harmonic wave numbers used to perturb the rim, and their base angular speeds.
const KS = [2, 3, 5, 8, 11];
const WS = [0.7, 0.9, 1.3, 1.9, 2.6];

// amps: rim wobble amplitude per harmonic (fraction of radius)
// audioW: how strongly real audio drives the wobble in this state
const STATES = {
  waiting: {
    glow: 10,
    alpha: 0.72,
    breathAmp: 0.022,
    breathHz: 0.24,
    amps: [0.006, 0.004, 0.003, 0.002, 0.0],
    spin: 0.05,
    ripple: 0,
    comet: 0,
    envelope: 0,
    audioW: 0.20,
    glyphBase: 0.55,
    glyphPulse: 0.10,
    speed: 0.5
  },
  listening: {
    glow: 26,
    alpha: 0.95,
    breathAmp: 0.012,
    breathHz: 0.50,
    amps: [0.010, 0.008, 0.012, 0.016, 0.0],
    spin: 0.12,
    ripple: 1,
    comet: 0,
    envelope: 0,
    audioW: 0.90,
    glyphBase: 0.90,
    glyphPulse: 0.08,
    speed: 1.6
  },
  thinking: {
    glow: 20,
    alpha: 0.85,
    breathAmp: 0.010,
    breathHz: 0.35,
    amps: [0.012, 0.050, 0.010, 0.004, 0.0],
    spin: 0.45,
    ripple: 0,
    comet: 0,
    envelope: 0,
    audioW: 0.25,
    glyphBase: 0.70,
    glyphPulse: 0.25,
    speed: 0.9
  },
  talking: {
    glow: 30,
    alpha: 1.00,
    breathAmp: 0.008,
    breathHz: 0.80,
    amps: [0.020, 0.014, 0.022, 0.024, 0.006],
    spin: 0.20,
    ripple: 0,
    comet: 0,
    envelope: 1,
    audioW: 1.00,
    glyphBase: 0.95,
    glyphPulse: 0.50,
    speed: 2.4
  },
  working: {
    glow: 22,
    alpha: 0.90,
    breathAmp: 0.010,
    breathHz: 0.60,
    amps: [0.012, 0.010, 0.014, 0.008, 0.004],
    spin: 0.90,
    ripple: 0,
    comet: 1,
    envelope: 0,
    audioW: 0.35,
    glyphBase: 0.80,
    glyphPulse: 0.12,
    speed: 1.3
  },
  error: {
    glow: 16,
    alpha: 0.85,
    breathAmp: 0.006,
    breathHz: 0.30,
    amps: [0.008, 0.006, 0.006, 0.010, 0.030],
    spin: 0.08,
    ripple: 0,
    comet: 0,
    envelope: 0,
    audioW: 0.25,
    glyphBase: 0.75,
    glyphPulse: 0.20,
    speed: 2.8
  }
};
const STATE_KEYS = ["glow", "alpha", "breathAmp", "breathHz", "spin", "ripple", "comet", "envelope", "audioW", "glyphBase", "glyphPulse", "speed"];

// Transitions that earn a spin flourish — a decaying rotational kick of the
// rim pattern. Only meaningful resolutions, not every state change.
const FLOURISHES = {
  "working>waiting": 1,
  // task done, settling back
  "working>listening": 1,
  // task done, back to you
  "working>talking": 1,
  // task done, reporting
  "thinking>talking": 1 // answer arrived
};

// Context modulations — layered over any state.
// w: tint blend weight toward the mod color. spikes: pufferfish quills.
const MODS = {
  none: {
    w: 0.00,
    ampMul: 1.00,
    speedMul: 1.00,
    glowMul: 1.00,
    alphaMul: 1.00,
    radiusMul: 1.00,
    spikes: 0,
    drops: 0,
    flicker: 0.00,
    gust: 0.0
  },
  dawn: {
    w: 0.35,
    ampMul: 0.90,
    speedMul: 0.90,
    glowMul: 1.10,
    alphaMul: 1.00,
    radiusMul: 1.00,
    spikes: 0,
    drops: 0,
    flicker: 0.00,
    gust: 0.0
  },
  day: {
    w: 0.25,
    ampMul: 1.00,
    speedMul: 1.00,
    glowMul: 1.15,
    alphaMul: 1.00,
    radiusMul: 1.00,
    spikes: 0,
    drops: 0,
    flicker: 0.00,
    gust: 0.0
  },
  dusk: {
    w: 0.40,
    ampMul: 0.90,
    speedMul: 0.90,
    glowMul: 0.95,
    alphaMul: 0.95,
    radiusMul: 1.00,
    spikes: 0,
    drops: 0,
    flicker: 0.00,
    gust: 0.0
  },
  night: {
    w: 0.45,
    ampMul: 0.70,
    speedMul: 0.75,
    glowMul: 0.70,
    alphaMul: 0.75,
    radiusMul: 0.96,
    spikes: 0,
    drops: 0,
    flicker: 0.00,
    gust: 0.0
  },
  rain: {
    w: 0.40,
    ampMul: 0.90,
    speedMul: 0.85,
    glowMul: 0.90,
    alphaMul: 0.90,
    radiusMul: 1.00,
    spikes: 0,
    drops: 1,
    flicker: 0.00,
    gust: 0.0
  },
  storm: {
    w: 0.50,
    ampMul: 1.25,
    speedMul: 1.20,
    glowMul: 1.05,
    alphaMul: 0.95,
    radiusMul: 1.00,
    spikes: 0,
    drops: 1,
    flicker: 0.50,
    gust: 1.0
  },
  degraded: {
    w: 0.50,
    ampMul: 0.75,
    speedMul: 0.70,
    glowMul: 0.85,
    alphaMul: 0.80,
    radiusMul: 0.97,
    spikes: 0,
    drops: 0,
    flicker: 0.35,
    gust: 0.0
  },
  threat: {
    w: 0.88,
    ampMul: 1.35,
    speedMul: 1.50,
    glowMul: 1.50,
    alphaMul: 1.00,
    radiusMul: 1.14,
    spikes: 1,
    drops: 0,
    flicker: 0.15,
    gust: 0.3
  }
};
const MOD_KEYS = Object.keys(MODS.none);
function resolveModulation(mod) {
  if (mod && mod !== "auto") return MODS[mod] ? mod : "none";
  const h = new Date().getHours();
  if (h >= 5 && h < 8) return "dawn";
  if (h >= 8 && h < 17) return "day";
  if (h >= 17 && h < 20) return "dusk";
  return "night";
}
function hexToRgb(hex) {
  const h = hex.trim().replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map(c => c + c).join("") : h, 16);
  return {
    r: n >> 16 & 255,
    g: n >> 8 & 255,
    b: n & 255
  };
}
function cssTok(varName, fallback) {
  const v = varName ? getComputedStyle(document.documentElement).getPropertyValue(varName) : "";
  return hexToRgb(v && v.trim().startsWith("#") ? v : fallback);
}
function cssMood(state) {
  return cssTok(MOOD_VARS[state], MOOD_FALLBACKS[state] || MOOD_FALLBACKS.waiting);
}
function cssMod(name) {
  return cssTok(MOD_VARS[name], MOD_FALLBACKS[name] || "#C39C72");
}
function rgba({
  r,
  g,
  b
}, a) {
  return `rgba(${r | 0},${g | 0},${b | 0},${a})`;
}
function mix(c1, c2, w) {
  return {
    r: c1.r + (c2.r - c1.r) * w,
    g: c1.g + (c2.g - c1.g) * w,
    b: c1.b + (c2.b - c1.b) * w
  };
}
function PiranesiOrb({
  state = "waiting",
  modulation = "auto",
  audio = null,
  intensity = 1,
  showGlyph = true,
  color,
  offsetX = 0,
  style
}) {
  const canvasRef = React.useRef(null);
  const live = React.useRef({
    state,
    modulation,
    audio,
    intensity,
    showGlyph,
    color,
    offsetX
  });
  live.current = {
    state,
    modulation,
    audio,
    intensity,
    showGlyph,
    color,
    offsetX
  };
  React.useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const glyphPath = new Path2D();
    for (const d of GLYPH_PATHS) glyphPath.addPath(new Path2D(d));
    let w = 0,
      h = 0,
      dpr = 1,
      raf = 0,
      last = performance.now();
    let spinPhase = 0,
      wavePhase = 0,
      rippleTimer = 0,
      dropTimer = 0;
    let spinKick = 0,
      prevState = live.current.state;
    const ripples = [],
      droplets = [];

    // --- audio plumbing ---
    let audioCtx = null,
      analyser = null,
      srcNode = null,
      connectedFor = null,
      dataArr = null;
    let audioLevel = 0,
      peak = 0.05;
    const ensureAudio = a => {
      if (a === connectedFor) return;
      try {
        if (srcNode) srcNode.disconnect();
      } catch (e) {}
      analyser = null;
      srcNode = null;
      dataArr = null;
      connectedFor = a;
      if (!a || typeof a === "function") return;
      try {
        if (window.AnalyserNode && a instanceof AnalyserNode) {
          analyser = a;
        } else {
          audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
          analyser = audioCtx.createAnalyser();
          analyser.fftSize = 512;
          if (window.MediaStream && a instanceof MediaStream) {
            srcNode = audioCtx.createMediaStreamSource(a);
            srcNode.connect(analyser);
          } else if (window.HTMLMediaElement && a instanceof HTMLMediaElement) {
            // MediaElementSource can only be created once per element — cache it there
            const node = a.__pvSrcNode || (a.__pvSrcNode = audioCtx.createMediaElementSource(a));
            node.connect(analyser);
            node.connect(audioCtx.destination);
            srcNode = node;
          }
        }
        dataArr = analyser ? new Uint8Array(analyser.fftSize) : null;
      } catch (e) {
        console.warn("PiranesiOrb: could not attach audio source", e);
      }
    };

    // current (lerped) params — start at the target so first paint is settled
    const st0 = STATES[live.current.state] || STATES.waiting;
    const md0 = MODS[resolveModulation(live.current.modulation)];
    const col0 = live.current.color ? hexToRgb(live.current.color) : cssMood(live.current.state);
    const cur = {
      ...st0,
      ...md0,
      amps: [...st0.amps],
      off: live.current.offsetX || 0,
      gOp: live.current.showGlyph ? 1 : 0,
      col: {
        ...col0
      },
      mcol: {
        ...col0
      }
    };
    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = Math.max(1, rect.width);
      h = Math.max(1, rect.height);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
    };
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement);
    resize();
    const frame = now => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = now / 1000;
      const {
        state: st,
        modulation: mo,
        audio: aSrc,
        intensity: inten,
        showGlyph: glyphOn,
        color: colOverride,
        offsetX: offT
      } = live.current;
      const target = STATES[st] || STATES.waiting;
      if (st !== prevState) {
        if (FLOURISHES[prevState + ">" + st]) spinKick += 8.5;
        prevState = st;
      }
      const modName = resolveModulation(mo);
      const mp = MODS[modName];
      const tCol = colOverride ? hexToRgb(colOverride) : cssMood(st);
      const tMcol = modName === "none" ? tCol : cssMod(modName);

      // fluid parameter lerp (~250ms time constant)
      const k = 1 - Math.exp(-dt / 0.25);
      for (const key of STATE_KEYS) cur[key] += (target[key] - cur[key]) * k;
      for (const key of MOD_KEYS) cur[key] += (mp[key] - cur[key]) * k;
      for (let i = 0; i < KS.length; i++) cur.amps[i] += (target.amps[i] - cur.amps[i]) * k;
      for (const ch of ["r", "g", "b"]) {
        cur.col[ch] += (tCol[ch] - cur.col[ch]) * k;
        cur.mcol[ch] += (tMcol[ch] - cur.mcol[ch]) * k;
      }
      cur.off += ((offT || 0) - cur.off) * k * 0.55;
      cur.gOp += ((glyphOn ? 1 : 0) - cur.gOp) * k;
      spinPhase += (cur.spin * cur.speedMul + spinKick) * dt;
      spinKick *= Math.exp(-dt / 0.5);
      wavePhase += cur.speed * cur.speedMul * dt;

      // --- audio level (real signal), else pseudo speech envelope ---
      ensureAudio(aSrc);
      let raw = null;
      if (typeof aSrc === "function") {
        raw = Math.max(0, Math.min(1, +aSrc() || 0));
      } else if (analyser && dataArr) {
        if (audioCtx && audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
        analyser.getByteTimeDomainData(dataArr);
        let s = 0;
        for (let i = 0; i < dataArr.length; i++) {
          const v = (dataArr[i] - 128) / 128;
          s += v * v;
        }
        const rms = Math.sqrt(s / dataArr.length);
        peak = Math.max(rms, peak * 0.996, 0.05); // auto-gain
        raw = Math.min(1, rms / peak);
      }
      const hasAudio = raw != null;
      audioLevel += ((hasAudio ? raw : 0) - audioLevel) * (1 - Math.exp(-dt / 0.07));
      const eRaw = (Math.sin(t * 7.1) + Math.sin(t * 11.3 + 1.7) + Math.sin(t * 3.7 + 0.5)) / 3;
      const pseudo = Math.min(1, Math.max(0, 0.45 + 0.9 * eRaw));
      const env = hasAudio ? audioLevel : pseudo;
      const drive = hasAudio ? cur.audioW : cur.envelope;
      const envMul = 1 + drive * env * 2.1;
      const gustMul = 1 + cur.gust * 0.7 * Math.max(0, Math.sin(t * 0.9) * Math.sin(t * 1.63 + 1.2) + 0.15);
      const flick = 1 - cur.flicker * 0.3 * Math.max(0, Math.sin(t * 11.3) * Math.sin(t * 23.7));
      const alphaEff = Math.min(1, cur.alpha * cur.alphaMul) * flick;
      const glowEff = cur.glow * cur.glowMul * inten;
      const ampScale = cur.ampMul * gustMul;
      const cx = w / 2 + cur.off * w,
        cy = h / 2;
      const R = Math.min(w, h) * 0.34 * cur.radiusMul;
      const breath = 1 + cur.breathAmp * inten * Math.sin(t * cur.breathHz * Math.PI * 2);
      const effCol = mix(cur.col, cur.mcol, cur.w);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const rimAt = a => {
        let sum = 0;
        for (let j = 0; j < KS.length; j++) {
          sum += cur.amps[j] * Math.sin(KS[j] * (a + spinPhase) + WS[j] * wavePhase);
        }
        let spike = 0;
        if (cur.spikes > 0.004) {
          spike = cur.spikes * 0.085 * Math.pow(Math.abs(Math.sin(9 * a + spinPhase * 2.5 + wavePhase * 0.7)), 6) * (1 + 0.35 * (envMul - 1));
        }
        return R * (breath + sum * envMul * ampScale * inten + spike * inten);
      };
      const tracePath = scale => {
        ctx.beginPath();
        const N = 220;
        for (let i = 0; i <= N; i++) {
          const a = i / N * Math.PI * 2;
          const r = rimAt(a) * scale;
          const x = cx + Math.cos(a) * r,
            y = cy + Math.sin(a) * r;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
      };

      // soft interior fill
      const grad = ctx.createRadialGradient(cx, cy, R * 0.1, cx, cy, R * 1.05);
      grad.addColorStop(0, rgba(effCol, 0.03));
      grad.addColorStop(0.8, rgba(effCol, 0.10));
      grad.addColorStop(1, rgba(effCol, 0.0));
      tracePath(1);
      ctx.fillStyle = grad;
      ctx.fill();

      // engraved inner echoes (concentric fine lines — etching motif)
      for (const [s, a] of [[0.90, 0.22], [0.80, 0.10]]) {
        tracePath(s);
        ctx.strokeStyle = rgba(effCol, a * alphaEff);
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // main rim with glow
      tracePath(1);
      ctx.strokeStyle = rgba(effCol, alphaEff);
      ctx.lineWidth = Math.max(1.5, R * 0.02);
      ctx.shadowColor = rgba(effCol, 0.8);
      ctx.shadowBlur = glowEff;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // listening — ripple rings drifting inward
      rippleTimer -= dt;
      if (cur.ripple > 0.05 && rippleTimer <= 0) {
        ripples.push({
          p: 0
        });
        rippleTimer = 0.9;
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        const rp = ripples[i];
        rp.p += dt / 2.2;
        if (rp.p >= 1) {
          ripples.splice(i, 1);
          continue;
        }
        const rr = R * (1.28 - 0.5 * rp.p);
        ctx.beginPath();
        ctx.arc(cx, cy, rr, 0, Math.PI * 2);
        ctx.strokeStyle = rgba(effCol, (1 - rp.p) * 0.35 * cur.ripple);
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // rain — droplet rings pattering around the orb
      dropTimer -= dt;
      if (cur.drops > 0.05 && dropTimer <= 0) {
        const a = Math.random() * Math.PI * 2;
        const rr = R * (0.3 + Math.random() * 0.95);
        droplets.push({
          x: cx + Math.cos(a) * rr,
          y: cy + Math.sin(a) * rr,
          p: 0
        });
        dropTimer = 0.16 + Math.random() * 0.28;
      }
      for (let i = droplets.length - 1; i >= 0; i--) {
        const dpl = droplets[i];
        dpl.p += dt / 1.1;
        if (dpl.p >= 1) {
          droplets.splice(i, 1);
          continue;
        }
        ctx.beginPath();
        ctx.arc(dpl.x, dpl.y, 2 + dpl.p * R * 0.12, 0, Math.PI * 2);
        ctx.strokeStyle = rgba(effCol, (1 - dpl.p) * 0.35 * cur.drops * alphaEff);
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // working — comet tracing the rim
      if (cur.comet > 0.02) {
        const head = t * 1.6 + spinPhase;
        const SEG = 14;
        for (let i = 0; i < SEG; i++) {
          const a0 = head - i * 0.055,
            a1 = head - (i + 1) * 0.055;
          const rr = (rimAt(a0) + rimAt(a1)) / 2 + R * 0.075;
          ctx.beginPath();
          ctx.arc(cx, cy, rr, a1, a0);
          ctx.strokeStyle = rgba(effCol, cur.comet * alphaEff * (1 - i / SEG) * 0.9);
          ctx.lineWidth = Math.max(1.5, R * 0.014);
          ctx.stroke();
        }
      }

      // the glyph (fades out when hidden — e.g. text replacing it on small displays)
      if (cur.gOp > 0.02) {
        const pulse = cur.glyphBase + cur.glyphPulse * (hasAudio || cur.envelope > 0.3 ? env : 0.5 + 0.5 * Math.sin(t * cur.breathHz * Math.PI * 2));
        const s = R * 1.05 / (86 * cur.radiusMul); // glyph doesn't puff with the spikes
        ctx.save();
        ctx.translate(cx - GLYPH_CENTER.x * s, cy - GLYPH_CENTER.y * s);
        ctx.scale(s, s);
        ctx.strokeStyle = rgba(effCol, Math.min(1, pulse) * cur.gOp);
        ctx.lineWidth = 5.5;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.shadowColor = rgba(effCol, 0.5 * cur.gOp);
        ctx.shadowBlur = glowEff * 0.5;
        ctx.stroke(glyphPath);
        ctx.restore();
      }
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      try {
        if (srcNode) srcNode.disconnect();
      } catch (e) {}
      if (audioCtx) audioCtx.close().catch(() => {});
    };
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      width: "100%",
      height: "100%",
      ...style
    }
  }, /*#__PURE__*/React.createElement("canvas", {
    ref: canvasRef,
    style: {
      display: "block",
      position: "absolute",
      inset: 0
    }
  }));
}
Object.assign(__ds_scope, { PiranesiOrb });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/orb/PiranesiOrb.jsx", error: String((e && e.message) || e) }); }

__ds_ns.PiranesiOrb = __ds_scope.PiranesiOrb;

})();
