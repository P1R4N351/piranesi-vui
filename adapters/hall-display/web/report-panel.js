/* Piranesi VUI hall display — CONTROL-CENTRE REPORT PANEL.
 *
 * Rendered ALONGSIDE the orb whenever the voice organ delivers a status
 * report (voxd POSTs /report; halld folds it into the /vox/status feed the
 * page already polls, as report_active + report + report_until). The panel
 * borrows the control-centre ELEMENT vocabulary — stat tiles, ok/warn chips,
 * advisory rows — re-expressed in the VUI's bronze-on-navy design language.
 * No JSX, no CDN: plain React.createElement over the vendored react, exactly
 * like hall.js.
 *
 * Exposes window.HallReportPanel = { useReportPanel, ReportPanel }.
 *   useReportPanel(status) -> { report, phase }  // lifecycle: 'in' | 'out'
 *   ReportPanel({ report, portrait, phase })     // the panel element
 */
(function () {
  var e = React.createElement;
  var EXIT_MS = 480;                 // must match --dur-state-ish exit animation

  // A stable identity for a report: a new title or a new acceptance instant is
  // a NEW report and re-triggers the entrance animation.
  function reportKey(r) {
    if (!r) return null;
    return String(r.at || 0) + "|" + String(r.title || "");
  }

  // Lifecycle governor for the panel. Mirrors the server's level-triggered
  // style: while the feed says report_active, we hold phase 'in'; when it goes
  // inactive we play the exit ('out') for EXIT_MS, then unmount. A brand-new
  // report while one is showing swaps content and replays the entrance.
  function useReportPanel(status) {
    var st = React.useState({ report: null, phase: "out" });
    var s = st[0], set = st[1];
    var timer = React.useRef(null);
    var active = !!(status && status.report_active && status.report);
    var key = active ? reportKey(status.report) : null;

    React.useEffect(function () {
      if (active) {
        if (timer.current) { clearTimeout(timer.current); timer.current = null; }
        set({ report: status.report, phase: "in" });
      } else {
        set(function (prev) {
          if (!prev.report || prev.phase === "out") return prev;
          return { report: prev.report, phase: "out" };
        });
      }
    }, [active, key]);

    React.useEffect(function () {
      if (s.phase === "out" && s.report) {
        timer.current = setTimeout(function () {
          set({ report: null, phase: "out" });
        }, EXIT_MS);
        return function () { if (timer.current) clearTimeout(timer.current); };
      }
    }, [s.phase, s.report]);

    return s;
  }

  // ok=true -> bronze/healthy accent; ok=false -> alert (terracotta mood-error);
  // ok=null -> neutral muted. Colors come straight from the DS mood/context
  // tokens, never hard-coded hexes (the fallbacks match tokens/colors.css).
  function tileTone(ok) {
    if (ok === true)
      return { accent: "var(--bronze-400, #D3B28D)", value: "var(--bronze-200, #EEDCC4)",
               edge: "var(--bronze-500, #C39C72)", glow: "var(--glow-accent, rgba(195,156,114,0.35))" };
    if (ok === false)
      return { accent: "var(--mood-error, #D9705F)", value: "var(--mood-error, #D9705F)",
               edge: "var(--mood-error, #D9705F)", glow: "rgba(217,112,95,0.35)" };
    return { accent: "var(--text-muted, #8E8A80)", value: "var(--text-body, #D7CDBD)",
             edge: "var(--border-subtle, rgba(195,156,114,0.22))", glow: "transparent" };
  }

  function hhmm(atEpoch) {
    if (!atEpoch) return "";
    var d = new Date(atEpoch * 1000);
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    return pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function Tile(tile, i) {
    var tone = tileTone(tile.ok);
    return e("div", {
      key: "tile-" + i,
      style: {
        display: "flex", flexDirection: "column", gap: "var(--space-1, 4px)",
        padding: "var(--space-3, 12px) var(--space-3, 12px)",
        borderRadius: "var(--radius-md, 12px)",
        background: "var(--navy-800, #122143)",
        borderLeft: "3px solid " + tone.edge,
        boxShadow: tone.glow === "transparent" ? "none" : "inset 0 0 22px " + tone.glow,
        minWidth: 0,
      },
    }, [
      e("div", {
        key: "l",
        style: {
          fontFamily: "var(--font-ui, Verdana, sans-serif)",
          fontSize: "var(--text-xs, 12px)", color: "var(--text-muted, #8E8A80)",
          letterSpacing: "var(--tracking-caps, 0.18em)", textTransform: "uppercase",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        },
      }, tile.label),
      e("div", {
        key: "v",
        style: {
          fontFamily: "var(--font-display, Georgia, serif)",
          fontSize: "clamp(20px, 3.4vmin, 40px)", lineHeight: 1.05,
          color: tone.value, fontWeight: 500,
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        },
      }, tile.value || "—"),
    ]);
  }

  function Line(text, i) {
    return e("div", {
      key: "line-" + i,
      style: {
        display: "flex", alignItems: "baseline", gap: "var(--space-3, 12px)",
        padding: "var(--space-2, 8px) 0",
        borderTop: i === 0 ? "none" : "1px solid var(--border-subtle, rgba(195,156,114,0.22))",
      },
    }, [
      e("span", {
        key: "d",
        style: {
          flex: "0 0 auto", width: 6, height: 6, marginTop: 2,
          borderRadius: "var(--radius-round, 50%)",
          background: "var(--bronze-500, #C39C72)",
          boxShadow: "0 0 8px var(--glow-accent, rgba(195,156,114,0.35))",
        },
      }),
      e("span", {
        key: "t",
        style: {
          fontFamily: "var(--font-ui, Verdana, sans-serif)",
          fontSize: "clamp(13px, 1.9vmin, 18px)", lineHeight: 1.4,
          color: "var(--text-body, #D7CDBD)",
        },
      }, text),
    ]);
  }

  function ReportPanel(props) {
    var report = props.report;
    if (!report) return null;
    var portrait = !!props.portrait;
    var phase = props.phase === "out" ? "out" : "in";
    var tiles = Array.isArray(report.tiles) ? report.tiles : [];
    var lines = Array.isArray(report.lines) ? report.lines : [];
    // Up to 4 columns; fewer when there are fewer tiles so they don't stretch.
    var cols = Math.max(1, Math.min(4, tiles.length || 1));

    var header = e("div", {
      key: "hdr",
      style: { display: "flex", flexDirection: "column", gap: "var(--space-1, 4px)",
               marginBottom: "var(--space-4, 16px)" },
    }, [
      e("div", {
        key: "title",
        style: {
          fontFamily: "var(--font-display, Georgia, serif)",
          fontSize: "clamp(26px, 4.4vmin, 44px)", lineHeight: 1.05,
          color: "var(--text-display, #E3C9A8)", fontWeight: 600,
        },
      }, report.title),
      e("div", {
        key: "meta",
        style: { display: "flex", alignItems: "center", gap: "var(--space-3, 12px)" },
      }, [
        e("span", {
          key: "dom",
          style: {
            fontFamily: "var(--font-ui, Verdana, sans-serif)",
            fontSize: "var(--text-xs, 12px)", color: "var(--accent, #C39C72)",
            letterSpacing: "var(--tracking-caps, 0.18em)", textTransform: "uppercase",
          },
        }, report.domain || "overview"),
        e("span", {
          key: "sep",
          style: { flex: "1 1 auto", height: 1,
                   background: "var(--border-subtle, rgba(195,156,114,0.22))" },
        }),
        e("span", {
          key: "ts",
          style: {
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "var(--text-xs, 12px)", color: "var(--text-muted, #8E8A80)",
            letterSpacing: "0.06em",
          },
        }, hhmm(report.at)),
      ]),
    ]);

    var children = [header];
    if (tiles.length) {
      children.push(e("div", {
        key: "tiles",
        style: {
          display: "grid", gridTemplateColumns: "repeat(" + cols + ", minmax(0, 1fr))",
          gap: "var(--space-2, 8px)", marginBottom: lines.length ? "var(--space-4, 16px)" : 0,
        },
      }, tiles.map(Tile)));
    }
    if (lines.length) {
      children.push(e("div", { key: "lines", style: { display: "flex", flexDirection: "column" } },
        lines.map(Line)));
    }

    // Outer wrapper owns POSITION + centering (no transform animation here, so
    // the landscape vertical-centering never fights the entrance keyframe).
    // Inner card owns the VISUAL + the animated entrance/exit.
    var card = e("div", {
      // keyed by identity so a new report remounts and replays the entrance
      key: "card-" + reportKey(report),
      className: phase === "out" ? "pv-report pv-report-out" : "pv-report pv-report-in",
      style: {
        width: "100%",
        maxHeight: portrait ? "52vh" : "92vh",
        boxSizing: "border-box",
        padding: "var(--space-5, 24px)",
        overflow: "hidden",
        borderRadius: "var(--radius-md, 12px)",
        border: "1px solid var(--border-strong, rgba(195,156,114,0.5))",
        background: "linear-gradient(160deg, var(--navy-800, #122143) 0%, var(--navy-900, #0E1A38) 100%)",
        boxShadow: "0 18px 60px rgba(6,10,22,0.55), inset 0 0 40px rgba(195,156,114,0.05)",
      },
    }, children);

    return e("div", {
      style: {
        position: "absolute",
        left: portrait ? "4%" : "auto",
        right: portrait ? "4%" : "3%",
        top: portrait ? "auto" : 0,
        bottom: portrait ? "4%" : 0,
        width: portrait ? "92%" : "46%",
        display: "flex", alignItems: "center", justifyContent: "flex-end",
        pointerEvents: "none",
      },
    }, card);
  }

  window.HallReportPanel = { useReportPanel: useReportPanel, ReportPanel: ReportPanel };
})();
