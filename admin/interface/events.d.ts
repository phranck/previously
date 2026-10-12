// What the kit's elements and the terminal view raise, by name, with what
// each event carries.
//
// They bubble, so the page listens for them on an element or on the document.
// Without this a listener reads every one of them as a plain Event, which
// carries no `detail`. tests/test_page.py holds the names here to every
// CustomEvent the kit and the page raise.

import type { DeskRect, SliderValue } from "./nextstep.js";

interface NextEvents {
  /** A window came to the front, by its name, or the desk itself as "". */
  "nx-front": CustomEvent<{ name: string }>;
  /** A window opened, and the rectangle of whatever opened it, if anything. */
  "nx-open": CustomEvent<{ from: DeskRect | null }>;
  /** A window closed. */
  "nx-close": CustomEvent<null>;
  /** Something was chosen, by a double click or by carrying it somewhere. */
  "nx-choose": CustomEvent<{ value: string }>;
  /** Something on the File Viewer's shelf was clicked once. */
  "nx-visit": CustomEvent<{ value: string | null }>;
  /** A step of the File Viewer's path was clicked, by its place and value. */
  "nx-path": CustomEvent<{ index: number; value: string | null }>;
  /** Something was dropped on the File Viewer's shelf. */
  "nx-keep": CustomEvent<{ value: string }>;
  /** An application was let go over a free slot of the dock, by its value and
   *  that slot. */
  "nx-dock": CustomEvent<{ value: string; slot: number }>;
  /** A tile left the dock, by what it stood for. */
  "nx-undock": CustomEvent<{ value: string }>;
  /** A pop-up list's choice changed. */
  "nx-pick": CustomEvent<{ value: string }>;
  /** A slider landed on another step. */
  "nx-slide": CustomEvent<{ value: SliderValue | undefined }>;
  /** Somebody typed into the terminal view. */
  "nx-typed": CustomEvent<{ data: string }>;
  /** The terminal view changed size, in rows and columns. */
  "nx-sized": CustomEvent<{ rows: number; columns: number }>;
}

declare global {
  interface HTMLElementEventMap extends NextEvents {}
  interface DocumentEventMap extends NextEvents {}
}
