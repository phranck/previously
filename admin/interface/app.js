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
import { loadTheChosenLanguage, translate } from "./strings.js";
import { defineTheTerminal } from "./terminal.js";
import { greetTheFirstVisit } from "./app/about.js";
import { wireActivity } from "./app/activity.js";
import { wireBoard } from "./app/board.js";
import { watchTheApplications } from "./app/dock.js";
import { fillTheEditorIfItCameBackOpen, wireEditor } from "./app/editor.js";
import { wireGrab } from "./app/grab.js";
import { wireTheInstaller } from "./app/installer.js";
import { wireMachines } from "./app/machines.js";
import { drawTheMenu, watchTheFrontWindow } from "./app/menu.js";
import { wireTheNotifications } from "./app/notifications.js";
import { REFRESH_MS } from "./app/pi.js";
import { drawLanguages, wirePreferences } from "./app/preferences.js";
import { wirePreview } from "./app/preview.js";
import { wireTerminal } from "./app/shell.js";
import { chosenSize, drawAtSize } from "./app/size.js";
import { refresh, wireButtons } from "./app/status.js";
import { wireTheUpdate } from "./app/update.js";
import { drawMachines, wireOpening } from "./app/viewer.js";

/**
 * Wakes the page, once the words of the language chosen are here.
 *
 * The words first, so every element is built around text it already has.
 * Then the elements, and only then this application's own wiring: a window
 * that does not exist yet cannot be wired to anything.
 */
function wake() {
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
  wireActivity();
  wireTheNotifications();
  watchTheFrontWindow();
  greetTheFirstVisit();
  watchTheApplications();
  drawLanguages();
  /* Both before the editor is filled, because what it shows is the machine
     that is set and which of the saved configurations that is, and neither is
     known until the tree and the status are in. The menu is drawn again then
     as well, because which application the window in front belongs to, and
     what that application is called, arrive with the tree. */
  Promise.all([drawMachines(), refresh()]).then(() => {
    fillTheEditorIfItCameBackOpen();
    drawTheMenu();
  });
  setInterval(refresh, REFRESH_MS);
}

/* Nothing happens before the catalog of the language chosen is here, because
   the markup cannot be translated into words the page does not hold, and an
   element the kit builds before then is built around none. English is part of
   the script, so a browser reading English waits for nothing. */
loadTheChosenLanguage().then(wake);
