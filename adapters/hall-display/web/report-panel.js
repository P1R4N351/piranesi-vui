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

  // --- command-centre elements: usage dials + sibling-status cells ----------

  // Sibling liveness -> accent + inset glow. Same fallback-hex convention as
  // tileTone: up=bronze/healthy, warn=amber caution, down=terracotta alert,
  // unknown/anything-else=neutral muted.
  function statusTone(state) {
    if (state === "up")
      return { accent: "var(--bronze-500, #C39C72)", label: "var(--bronze-300, #E3C9A8)",
               glow: "var(--glow-accent, rgba(195,156,114,0.35))" };
    if (state === "warn")
      return { accent: "var(--mod-degraded, #C9A23F)", label: "var(--mod-degraded, #C9A23F)",
               glow: "rgba(201,162,63,0.32)" };
    if (state === "down")
      return { accent: "var(--mood-error, #D9705F)", label: "var(--mood-error, #D9705F)",
               glow: "rgba(217,112,95,0.32)" };
    return { accent: "var(--text-muted, #8E8A80)", label: "var(--text-muted, #8E8A80)",
             glow: "transparent" };
  }

  // Dial fill color by threshold level.
  function dialTone(level) {
    if (level === "crit") return "var(--mood-error, #D9705F)";
    if (level === "warn") return "var(--mod-degraded, #C9A23F)";
    return "var(--bronze-500, #C39C72)";
  }

  // Deterministic arc geometry for the SVG gauge (viewBox 0..100).
  function polar(cx, cy, r, a) {
    var t = a * Math.PI / 180;
    return [cx + r * Math.cos(t), cy + r * Math.sin(t)];
  }
  function arcPath(cx, cy, r, a0, a1) {
    var p0 = polar(cx, cy, r, a0), p1 = polar(cx, cy, r, a1);
    var large = ((a1 - a0) % 360) > 180 ? 1 : 0;
    return "M " + p0[0] + " " + p0[1] + " A " + r + " " + r +
           " 0 " + large + " 1 " + p1[0] + " " + p1[1];
  }

  // The Piranesi columned-house mark, rendered inline as the sibling cell's
  // status crest — the CANONICAL portico (assets/glyph.svg geometry verbatim:
  // OPEN pediment, no closing baseline; 86x112 composition). Tinted to the
  // liveness accent so the crest itself carries the state. Design rule
  // 2026-08-11: exact canonical geometry at every size, color
  // parameterized only; stroke bumped 5.5->8 viewBox-units for sub-30px
  // renders (bounded at 2x canonical 5.5).
  function HouseGlyph(color, size) {
    var s = size || 16;
    var w = Math.round(s * 56 / 52);   // frame cropped to drawn bounds (ink x15-71 y24-76)
    function stroke(d, cap) {
      return e("path", { key: d, d: d, stroke: color, strokeWidth: 8,
                         strokeLinecap: "round", strokeLinejoin: "round",
                         fill: "none" });
    }
    return e("svg", {
      key: "glyph", width: w, height: s, viewBox: "15 24 56 52",
      fill: "none", "aria-hidden": "true",
      style: { flex: "0 0 auto", display: "block" },
    }, [
      stroke("M23 39 L43 28 L63 39"),   // open pediment
      stroke("M30 45 L30 69"),          // three columns
      stroke("M43 45 L43 69"),
      stroke("M56 45 L56 69"),
      stroke("M19 72 L67 72"),          // stylobate
    ]);
  }

  // A 270deg arc-gauge instrument. Track is the full sweep; the value arc fills
  // clockwise from the lower-left. Center shows the display value, the label
  // below in small-caps, and an optional tiny sub-caption.
  function Dial(dial, i) {
    var pct = Math.max(0, Math.min(100, Number(dial.pct) || 0));
    var color = dialTone(dial.level);
    var A0 = 135, SWEEP = 270;                       // gap centered at the bottom
    var track = arcPath(50, 50, 40, A0, A0 + SWEEP);
    var kids = [
      e("path", { key: "track", d: track, fill: "none",
                  stroke: "var(--border-subtle, rgba(195,156,114,0.22))",
                  strokeWidth: 9, strokeLinecap: "round" }),
    ];
    if (pct > 0.5) {                                 // omit near-zero to avoid a dot
      kids.push(e("path", { key: "val", d: arcPath(50, 50, 40, A0, A0 + SWEEP * pct / 100),
                            fill: "none", stroke: color, strokeWidth: 9, strokeLinecap: "round",
                            style: { filter: "drop-shadow(0 0 3px " + color + ")" } }));
    }
    return e("div", {
      key: "dial-" + i,
      style: {
        display: "flex", flexDirection: "column", alignItems: "center",
        gap: "var(--space-1, 4px)", minWidth: 0,
        padding: "var(--space-2, 8px) var(--space-1, 4px)",
      },
    }, [
      e("div", { key: "g", style: { position: "relative", width: "100%", maxWidth: 132 } }, [
        e("svg", { key: "svg", viewBox: "0 0 100 100",
                   style: { width: "100%", height: "auto", display: "block" } }, kids),
        e("div", {
          key: "ctr",
          style: {
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 0, pointerEvents: "none",
          },
        }, [
          e("div", {
            key: "v",
            style: {
              fontFamily: "var(--font-display, Georgia, serif)",
              fontSize: "clamp(18px, 3.1vmin, 34px)", lineHeight: 1, color: color, fontWeight: 500,
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "78%",
            },
          }, dial.value || (Math.round(pct) + "%")),
          dial.sub ? e("div", {
            key: "s",
            style: {
              fontFamily: "var(--font-mono, monospace)", fontSize: "clamp(8px, 1.1vmin, 11px)",
              color: "var(--text-muted, #8E8A80)", marginTop: 2, letterSpacing: "0.04em",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "88%",
            },
          }, dial.sub) : null,
        ]),
      ]),
      e("div", {
        key: "l",
        style: {
          fontFamily: "var(--font-ui, Verdana, sans-serif)", fontSize: "var(--text-xs, 12px)",
          color: "var(--text-muted, #8E8A80)", letterSpacing: "var(--tracking-caps, 0.18em)",
          textTransform: "uppercase", textAlign: "center",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%",
        },
      }, dial.label),
    ]);
  }

  // A sibling-status card: house-crest + name + liveness word, then a divider
  // and its live metrics as key/value rows. Same card idiom as Tile.
  function Cell(cell, i) {
    var tone = statusTone(cell.state);
    var metrics = Array.isArray(cell.metrics) ? cell.metrics : [];
    var head = e("div", {
      key: "head",
      style: { display: "flex", alignItems: "center", gap: "var(--space-2, 8px)" },
    }, [
      HouseGlyph(tone.accent, 18),
      e("div", { key: "id", style: { display: "flex", flexDirection: "column", gap: 1, minWidth: 0 } }, [
        e("div", {
          key: "n",
          style: {
            fontFamily: "var(--font-ui, Verdana, sans-serif)", fontSize: "var(--text-sm, 14px)",
            color: "var(--text-display, #E3C9A8)", fontWeight: 600, letterSpacing: "0.02em",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          },
        }, cell.name),
        e("div", {
          key: "st",
          style: {
            fontFamily: "var(--font-ui, Verdana, sans-serif)", fontSize: "10px", color: tone.label,
            letterSpacing: "var(--tracking-caps, 0.18em)", textTransform: "uppercase",
          },
        }, cell.state || "unknown"),
      ]),
    ]);
    var rows = metrics.map(function (m, j) {
      return e("div", {
        key: "m-" + j,
        style: {
          display: "flex", alignItems: "baseline", justifyContent: "space-between",
          gap: "var(--space-2, 8px)", padding: "3px 0",
          borderTop: j === 0 ? "none" : "1px solid var(--border-subtle, rgba(195,156,114,0.22))",
        },
      }, [
        e("span", {
          key: "k",
          style: {
            fontFamily: "var(--font-ui, Verdana, sans-serif)", fontSize: "10px",
            color: "var(--text-muted, #8E8A80)", letterSpacing: "var(--tracking-caps, 0.18em)",
            textTransform: "uppercase", whiteSpace: "nowrap",
          },
        }, m.k),
        e("span", {
          key: "v",
          style: {
            fontFamily: "var(--font-mono, monospace)", fontSize: "clamp(12px, 1.7vmin, 15px)",
            color: "var(--text-body, #D7CDBD)", textAlign: "right",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0,
          },
        }, m.v || "—"),
      ]);
    });
    return e("div", {
      key: "cell-" + i,
      style: {
        display: "flex", flexDirection: "column", gap: "var(--space-2, 8px)",
        padding: "var(--space-3, 12px)", borderRadius: "var(--radius-md, 12px)",
        background: "var(--navy-800, #122143)", borderLeft: "3px solid " + tone.accent,
        boxShadow: tone.glow === "transparent" ? "none" : "inset 0 0 22px " + tone.glow,
        minWidth: 0,
      },
    }, [
      head,
      rows.length ? e("div", {
        key: "div",
        style: { height: 1, background: "var(--border-subtle, rgba(195,156,114,0.22))", margin: "2px 0" },
      }) : null,
      rows.length ? e("div", { key: "rows", style: { display: "flex", flexDirection: "column" } }, rows) : null,
    ]);
  }

  function ReportPanel(props) {
    var report = props.report;
    if (!report) return null;
    var portrait = !!props.portrait;
    var phase = props.phase === "out" ? "out" : "in";
    var tiles = Array.isArray(report.tiles) ? report.tiles : [];
    var lines = Array.isArray(report.lines) ? report.lines : [];
    var cells = Array.isArray(report.cells) ? report.cells : [];
    var dials = Array.isArray(report.dials) ? report.dials : [];
    // Up to 4 columns; fewer when there are fewer tiles so they don't stretch.
    var cols = Math.max(1, Math.min(4, tiles.length || 1));
    var dialCols = Math.max(1, Math.min(4, dials.length || 1));
    var cellCols = Math.max(1, Math.min(3, cells.length || 1));

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

    // Section order: dials, then sibling cells, then stat tiles, then advisory
    // lines. Each present section carries bottom spacing only when a later
    // section follows it, so a single-section report never trails empty space.
    var gap4 = "var(--space-4, 16px)";
    var children = [header];
    if (dials.length) {
      children.push(e("div", {
        key: "dials",
        style: {
          display: "grid", gridTemplateColumns: "repeat(" + dialCols + ", minmax(0, 1fr))",
          gap: "var(--space-2, 8px)",
          marginBottom: (cells.length || tiles.length || lines.length) ? gap4 : 0,
        },
      }, dials.map(Dial)));
    }
    if (cells.length) {
      children.push(e("div", {
        key: "cells",
        style: {
          display: "grid", gridTemplateColumns: "repeat(" + cellCols + ", minmax(0, 1fr))",
          gap: "var(--space-2, 8px)",
          marginBottom: (tiles.length || lines.length) ? gap4 : 0,
        },
      }, cells.map(Cell)));
    }
    if (tiles.length) {
      children.push(e("div", {
        key: "tiles",
        style: {
          display: "grid", gridTemplateColumns: "repeat(" + cols + ", minmax(0, 1fr))",
          gap: "var(--space-2, 8px)", marginBottom: lines.length ? gap4 : 0,
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
