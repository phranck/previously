// What the one library this interface takes puts on the page.
//
// xterm.js and its fit addon arrive as their authors built them, each as a
// script of its own that leaves a name behind, and `terminal.js` reaches for
// those two names. Their types are the ones the same releases publish, which
// package.json brings at exactly the versions in web/vendor/, so the checker
// reads the library that ships rather than a description of it.

import type { Terminal as XTerm } from "@xterm/xterm";
import type { FitAddon as Fit } from "@xterm/addon-fit";

declare global {
  const Terminal: typeof XTerm;
  const FitAddon: { FitAddon: typeof Fit };
}
