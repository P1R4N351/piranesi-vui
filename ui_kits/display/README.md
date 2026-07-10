# Voice Display kit

The one surface Piranesi VUI ships: a full-screen ambient display whose entire UI is the orb.

- `index.html` — interactive demo. Bottom chips switch conversational state (fluid morphs); top-right chips simulate landscape / portrait / square / round hardware.
- Composes `components/orb/PiranesiOrb.jsx`; captions are the only text on screen.
- Caption placement by display: landscape — beside the orb (orb glides left via `offsetX`); portrait — edge-to-edge near the bottom; square/round — centered, replacing the glyph (which fades out) for the duration.
