/* The Terminal window and the shell session behind it. */

import { t } from "../strings.js";
import { TERMINAL } from "./service.js";

/** The shell session behind the terminal window, or null when none is open.
 *  One at a time, which is also all the service hands out. */
let shell = null;

/** What has been typed at the login prompt, or null whilst a session runs and
 *  every key belongs to the far side. */
let typedAtThePrompt = null;

/**
 * Puts the login prompt up.
 * @param {string} [complaint] - What came of the last attempt.
 *
 * Ours, and only this one line of it. What answers afterwards is this
 * machine's own SSH server: it asks for the password, it decides, and what
 * comes back is an ordinary login shell. This service never sees a password
 * and has no way to let anybody past.
 *
 * The name is asked here rather than by sshd because the client has to be
 * told who is connecting before it connects at all.
 */
function askAtTheTerminal(complaint) {
  const view = document.getElementById("session");
  if (!view.write) return;

  typedAtThePrompt = "";
  if (complaint) view.write("\r\n" + complaint + "\r\n");
  view.write("\r\n" + t("terminal.login"));
  view.focus();
}

/**
 * Answers a key at that prompt.
 * @param {string} data - What the terminal says was typed.
 *
 * Echoed, because a login name is echoed everywhere else a person types one.
 * The password is not asked here at all: by then the far side is sshd, which
 * echoes nothing itself.
 */
function typeAtThePrompt(data) {
  const view = document.getElementById("session");
  for (const character of data) {
    if (character === "\r" || character === "\n") {
      const said = typedAtThePrompt.trim();
      if (!said) {
        view.write("\r\n" + t("terminal.login"));
        continue;
      }
      typedAtThePrompt = null;
      view.write("\r\n");
      return openShell(said);
    }
    if (character === "\x7f" || character === "\b") {
      if (!typedAtThePrompt) continue;
      typedAtThePrompt = typedAtThePrompt.slice(0, -1);
      view.write("\b \b");
      continue;
    }
    if (character >= " ") {
      typedAtThePrompt += character;
      view.write(character);
    }
  }
}

/**
 * Opens a session for whoever was named at the prompt.
 * @param {string} login - The name typed.
 *
 * The name and the size go as the first thing said, so the login starts at
 * the size it will be read at rather than at one it is corrected from a
 * moment later.
 */
function openShell(login) {
  const view = document.getElementById("session");
  if (shell || !view.write) return;

  const where = location.origin.replace(/^http/, "ws") + TERMINAL;
  const opening = new WebSocket(where, ["previously"]);
  opening.binaryType = "arraybuffer";
  shell = opening;
  let accepted = false;

  opening.onopen = () => {
    accepted = true;
    view.fit();
    const size = view.size;
    opening.send(JSON.stringify({ login, size: [size.rows, size.columns] }));
    view.focus();
  };
  opening.onmessage = (event) => view.write(new Uint8Array(event.data));
  opening.onclose = () => {
    const wasRunning = shell === opening;
    shell = null;
    if (!wasRunning) return;
    /* A browser is told nothing about why a handshake failed, and the one
       thing this service refuses at that point is a second session. */
    askAtTheTerminal(accepted ? t("terminal.ended") : t("terminal.refused"));
  };
}

/** Ends the session, which the service answers by ending the shell. */
function closeShell() {
  const going = shell;
  shell = null;
  typedAtThePrompt = null;
  going?.close();
}

/**
 * Tells the shell how large the window has become.
 * @param {object} size - `{rows, columns}`.
 *
 * A text frame, which the service reads as being about the session. Anything
 * binary is what the shell itself sees.
 */
function tellTheShellItsSize(size) {
  if (shell?.readyState !== WebSocket.OPEN) return;
  shell.send(JSON.stringify({ resize: [size.rows, size.columns] }));
}

/** Wires the terminal window to the session behind it. */
function wireTerminal() {
  const window_ = document.querySelector('nx-window[name="terminal"]');
  const view = document.getElementById("session");
  if (!window_ || !view) return;

  /* Opening the window is not opening a session. The login is. */
  window_.addEventListener("nx-open", () => {
    document.getElementById("session").clear();
    askAtTheTerminal();
  });
  window_.addEventListener("nx-close", closeShell);

  view.addEventListener("nx-typed", (event) => {
    if (typedAtThePrompt !== null) return typeAtThePrompt(event.detail.data);
    if (shell?.readyState === WebSocket.OPEN) {
      shell.send(new TextEncoder().encode(event.detail.data));
    }
  });
  view.addEventListener("nx-sized", (event) => tellTheShellItsSize(event.detail));

  /* A browser that goes away without closing the window would otherwise leave
     the service holding a session nobody is looking at until the socket times
     out. */
  addEventListener("pagehide", closeShell);

  /* A window that was open when the page was last left comes back open, and
     nothing opened it, so nothing said so. What it comes back to is the
     prompt: a session does not survive a reload and must not look as though
     it did. */
  if (!window_.hidden) askAtTheTerminal();
}

/* --- Grab, which takes a picture of the emulated screen --------------------------------

   The picture is the machine's own framebuffer, taken at the moment it is
   asked for. Nothing here polls: a screen that redrew itself every few seconds
   would be a window that costs the emulator something for as long as it is
   open, and what a person wants is to look now. */

export {
  wireTerminal,
};
