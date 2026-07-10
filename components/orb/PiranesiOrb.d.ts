/**
 * The Piranesi voice orb — a fluid, pulsating circle with the
 * columned-house glyph inside. Each conversational state has its own
 * motion signature and mood hue; transitions between states are
 * continuous morphs. Fills its container, so it adapts to landscape,
 * portrait, square, or round displays.
 */
export interface PiranesiOrbProps {
  /** Conversational state. Default "waiting". */
  state?: "waiting" | "listening" | "thinking" | "talking" | "working" | "error";
  /** Context modulation layered over the state. "auto" derives dawn/day/dusk/night
   *  from the local clock. "threat" is pufferfish mode: crimson, spiked, puffed.
   *  Default "auto". */
  modulation?: "auto" | "none" | "dawn" | "day" | "dusk" | "night" | "rain" | "storm" | "degraded" | "threat";
  /** Real audio driving the waveform: a mic MediaStream, an output
   *  HTMLMediaElement, an AnalyserNode, or a () => 0..1 level function.
   *  Without it, talking uses a pseudo speech envelope. */
  audio?: MediaStream | HTMLMediaElement | AnalyserNode | (() => number) | null;
  /** Master motion/glow multiplier, 0–1.5. Default 1. */
  intensity?: number;
  /** Render the house glyph in the center. Default true. */
  showGlyph?: boolean;
  /** Hex override for the mood hue (otherwise read from --mood-* tokens). */
  color?: string;
  /** Horizontal center offset as a fraction of width (e.g. -0.22 shifts left
   *  for side-by-side text on wide displays). Fluidly lerped. Default 0. */
  offsetX?: number;
  /** Extra styles for the wrapper (it fills its parent by default). */
  style?: React.CSSProperties;
}
