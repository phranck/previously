/* What this particular application does with the kit, and where it starts.
 *
 * The kit in nextstep.js knows about windows and shelves and nothing about
 * emulators. Everything that knows what a NeXTcube is lives in app/, one
 * module per subject, and this file is the order they are woken in.
 *
 * Reading needs no password. The three buttons that switch the emulated
 * machine on and off do, and the service refuses them without one.
 */

import { defineTheKit } from "./nextstep.js";
import { translate } from "./strings.js";
import { defineTheTerminal } from "./terminal.js";
import { greetTheFirstVisit } from "./app/about.js";
import { wireBoard } from "./app/board.js";
import { watchTheApplications } from "./app/dock.js";
import { fillTheEditorIfItCameBackOpen, wireEditor } from "./app/editor.js";
import { wireGrab } from "./app/grab.js";
import { wireTheInstaller } from "./app/installer.js";
import { wireMachines } from "./app/machines.js";
import { watchTheFrontWindow } from "./app/menu.js";
import { REFRESH_MS } from "./app/pi.js";
import { drawLanguages, wirePreferences } from "./app/preferences.js";
import { wirePreview } from "./app/preview.js";
import { wireTerminal } from "./app/shell.js";
import { chosenSize, drawAtSize } from "./app/size.js";
import { refresh, wireButtons } from "./app/status.js";
import { wireTheUpdate } from "./app/update.js";
import { drawMachines, wireOpening } from "./app/viewer.js";

/* The words first, so every element is built around text it already has.
   Then the elements, and only then this application's own wiring: a window
   that does not exist yet cannot be wired to anything. */
translate();
defineTheKit();
defineTheTerminal();

drawAtSize(chosenSize());
wireButtons();
wirePreferences();
wireMachines();
wireBoard();
wireOpening();
wireTerminal();
wireGrab();
wirePreview();
wireEditor();
wireTheInstaller();
wireTheUpdate();
watchTheFrontWindow();
greetTheFirstVisit();
watchTheApplications();
drawLanguages();
/* Both before the editor is filled, because what it shows is the machine that is
   set and which of the saved configurations that is, and neither is known until
   the tree and the status are in. */
Promise.all([drawMachines(), refresh()]).then(fillTheEditorIfItCameBackOpen);
setInterval(refresh, REFRESH_MS);
