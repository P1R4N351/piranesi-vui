/* Piranesi VUI hall display — full-screen orb for a spectator kiosk.
 *
 * Unlike the on-device kiosk (which derives state from a raw voxd /status),
 * the hall polls halld's /vox/status, which is already MERGED across the
 * household's conversation units and carries {state, caption, source_unit}.
 * The orb shows the household's conversational presence; a small-caps label
 * attributes it to the unit carrying the conversation. Panel power is
 * handled server-side by halld (wake-gated) — this page just renders.
 */
(function () {
  var e = React.createElement;
  var DS = window.PiranesiVUIDesignSystem_8af396 || {};
  var PiranesiOrb = DS.PiranesiOrb;

  var POLL_MS = 400;
  var ERROR_AFTER_FAILS = 5;

  // Context modulation for the orb. halld merges /vox/status.modulation across
  // units (auto | degraded | threat); we honor it, so a household threat signal
  // renders pufferfish mode here. Absent field => legacy behavior: "auto"
  // (clock-driven), or "degraded" when the voices have gone silent.
  function modulationFor(st, state) {
    var m = st && typeof st.modulation === "string" ? st.modulation : "";
    if (m === "threat" || m === "degraded" || m === "auto") return m;
    if (state === "error") return "degraded";
    return "auto";
  }

  function Hall() {
    var s = React.useState(null);
    var status = s[0], setStatus = s[1];

    React.useEffect(function () {
      var alive = true, timer = null, fails = 0;
      function tick() {
        fetch("/vox/status", { cache: "no-store" })
          .then(function (r) { return r.json(); })
          .then(function (j) { fails = 0; if (alive) setStatus(j); })
          .catch(function () {
            fails += 1;
            if (alive && fails >= ERROR_AFTER_FAILS) setStatus({ state: "error" });
          })
          .finally(function () { if (alive) timer = setTimeout(tick, POLL_MS); });
      }
      tick();
      return function () { alive = false; if (timer) clearTimeout(timer); };
    }, []);

    var st = status || { state: "waiting", caption: "" };
    var state = st.state || "waiting";
    var caption = st.caption || (state === "error" ? "The voices of the house are silent." : "");
    var unit = st.source_unit;
    var modulation = modulationFor(st, state);

    var children = [
      e("div", { key: "orb", style: { position: "absolute", inset: 0 } },
        PiranesiOrb
          ? e(PiranesiOrb, {
              state: state,
              modulation: modulation,
              offsetX: caption ? -0.26 : 0,
            })
          : e("div", { style: { color: "#D9705F", padding: 40, fontFamily: "monospace" } },
              "DS bundle missing: PiranesiOrb not found")),
    ];
    if (caption) {
      children.push(e("div", {
        key: "cap-" + caption,
        style: {
          position: "absolute", left: "56%", right: "5%", top: "50%",
          transform: "translateY(-50%)", textAlign: "left",
          color: "var(--bronze-300, #E3C9A8)",
          fontFamily: "var(--font-ui, Verdana, sans-serif)",
          fontSize: "clamp(16px, 2.8vmin, 30px)", lineHeight: 1.5,
          letterSpacing: "0.02em",
          animation: "pv-fade 650ms cubic-bezier(0.4, 0, 0.2, 1) both",
        },
      }, caption));
    }
    if (unit && state !== "waiting") {
      children.push(e("div", {
        key: "unit",
        style: {
          position: "absolute", left: 0, right: 0, bottom: "4%",
          textAlign: "center",
          color: "var(--text-muted, #8E8A80)",
          fontFamily: "var(--font-ui, Verdana, sans-serif)",
          fontSize: "var(--text-xs, 12px)",
          letterSpacing: "var(--tracking-caps, 0.18em)",
          textTransform: "uppercase",
          animation: "pv-fade 650ms cubic-bezier(0.4, 0, 0.2, 1) both",
        },
      }, unit));
    }

    return e("div", {
      style: {
        position: "absolute", inset: 0,
        background: "radial-gradient(ellipse at 50% 42%, var(--navy-700, #16294d) 0%, var(--navy-900, #0E1A38) 68%, var(--navy-950, #0A1226) 100%)",
      },
    }, children);
  }

  ReactDOM.createRoot(document.getElementById("root")).render(e(Hall));
})();
