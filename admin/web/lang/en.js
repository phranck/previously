/* English, and the one every other language falls back to.
 *
 * This catalogue is complete by definition: a key missing here shows as itself
 * on the screen, so this is the file that decides what a string is called and
 * what it says. Everything in braces is filled in by the page.
 */

NX_STRINGS.en = {
  /* --- the menus ------------------------------------------------------- */
  /* The letter beside each main-menu entry, which is a letter of the
     word that entry shows. Distinct within the language, because the page
     acts on the first entry whose letter matches. */
  "menu.info.key": "i",
  "menu.pi.key": "r",
  "menu.files.key": "f",
  "menu.preferences.key": "p",
  "menu.token.key": "t",
  "menu.picture": "Picture",
  "menu.delete": "Delete",
  "menu.delete.key": "d",
  "menu.save": "Save",
  "menu.save.key": "s",
  "ask.delete.title": "Delete {name}?",
  "ask.delete.loss": "It is taken off the card and does not come back.",
  "button.delete": "Delete",
  "menu.quit": "Quit",
  "menu.quit.key": "q",
  "grab.take.key": "t",
  "menu.files": "Files",
  "menu.token": "Token",
  "menu.machine": "Machine",
  "menu.machine-info": "Info…",
  "menu.activate": "Activate configuration",
  "menu.edit": "Edit configuration…",
  "menu.keep": "Put on the shelf",
  "menu.unkeep": "Take off the shelf",

  /* --- the windows ----------------------------------------------------- */
  "window.info": "Info",
  "window.machine": "Machine",
  "app.preferences": "Preferences",
  "preferences.localization": "Localization Preferences",
  "preferences.monitor": "Monitor Preferences",
  "size.title": "Interface Size",

  /* --- the applications, as they are called in words ------------------ */
  "app.config-editor": "Config Editor",
  "app.grab": "Grab",
  "app.preview": "Preview",
  "app.terminal": "Terminal",

  /* --- what a machine is ----------------------------------------------- */
  "info.reading": "reading",
  "info.state": "State",
  "info.processor": "Processor",
  "info.memory": "Memory",
  "info.screen": "Screen",
  "info.disk": "Disk",
  "info.dimension": "Dimension",
  "info.chips": "Chips",
  "info.file": "File",
  "info.written": "Written",
  "info.no-contact": "no contact",
  "info.unreadable": "configuration not readable",
  "info.no-disk": "none inserted",

  "state.running": "running {since}",
  "state.stopped": "stopped",
  "state.held": "switched off",
  "state.unreachable": "not reachable",

  "since.hours": "for {hours}:{minutes} h",
  "since.minutes": "for {minutes} min",
  "since.less-than-a-minute": "for less than a minute",

  "duration.days.one": "{days} day, {hours} h",
  "duration.days.other": "{days} days, {hours} h",
  "duration.hours": "{hours} h {minutes} min",
  "duration.minutes": "{minutes} min",

  /* --- the configuration file ------------------------------------------ */
  "file.changed": "{when}",
  "file.changed-not-booted": "{when}, not booted yet",
  "file.by-previously": "by Previously",
  "file.by-previous-or-hand": "by Previous or by hand",
  "file.other-machine": "this machine is not the one set",

  /* --- the machine itself ---------------------------------------------- */
  "machine.with-dimension": "{name} with NeXTdimension",
  "machine.cpu": "{cpu}, {mhz} MHz",
  "machine.memory": "{mb} MB",
  "machine.memory-banks": "{mb} MB ({banks})",
  "machine.banks-empty": "empty",
  "machine.screen.dimension": "NeXTdimension, colour",
  "machine.screen.colour": "MegaPixel, colour",
  "machine.screen.grey": "MegaPixel, greyscale",
  "machine.chips.with-nextbus": "{rtc}, {scsi}, with NeXTbus",
  "machine.chips.without-nextbus": "{rtc}, {scsi}, without NeXTbus",
  "machine.dimension.fitted": "fitted",
  "machine.dimension.none": "none",

  /* --- the file viewer -------------------------------------------------- */
  "viewer.status": "{name}: {count}{more}",
  "viewer.count.one": "1 entry",
  "viewer.count.other": "{count} entries",
  "viewer.read-only": ", read only",
  "viewer.unreachable": "Not reachable",

  /* --- the terminal --------------------------------------------------- */
  "terminal.login": "login: ",
  "terminal.refused": "[no session: the machine refused, or one is open already]",
  "terminal.ended": "[the session has ended]",

  /* --- the buttons ------------------------------------------------------ */
  "preview.empty": "Nothing to show.",
  "grab.take": "Take a picture",
  "grab.idle": "Nothing to photograph. The machine is not running.",
  "grab.failed": "The screen could not be read.",
  "button.power-off": "Power off",
  "button.restart": "Restart",
  "button.power-on": "Power on",
  "button.change": "Change",
  "button.use": "Use",
  "button.fine": "Good",
  "button.close": "Close",
  "button.cancel": "Cancel",
  "button.ok": "OK",

  /* --- what is happening now -------------------------------------------- */
  "busy.starting": "switching on",
  "busy.stopping": "shutting down",
  "busy.restarting": "restarting",
  "busy.changing": "changing to {machine}",
  "busy.board-restart": "NeXTSTEP shuts down, then the Pi restarts",
  "busy.board-poweroff": "NeXTSTEP shuts down, then the Pi switches off",

  "note.no-console": "The console is not running. Switching on will do nothing.",
  "note.no-service": "no contact with the service",
  "note.board-gone": "No more answer. That is what to expect whilst the Pi is switching off.",

  /* --- the panels ------------------------------------------------------- */
  "ask.token.title": "Token",
  "ask.token.needed": "This changes something on the machine and needs the token.",
  "ask.token.where": "On the Pi it is in a file that only the service may read:",
  "ask.token.wrong": "That was not this machine's token.",

  "ask.stop.title": "Halt NeXTSTEP",
  "ask.stop.how": "NeXTSTEP is shut down through the power key, the same way as Power Off in the logout panel.",
  "ask.stop.loss": "Unsaved work in running programs is lost. The service cannot see what the machine is working on.",

  "ask.change.title": "Change machine",
  "ask.change.question": "Start as {machine}?",
  "ask.change.own": "What is set now is a configuration of your own, matching none of the machines offered. It will be written over.",
  "ask.change.how": "NeXTSTEP is shut down through the power key, the configuration is written and the machine is started again.",
  "ask.change.rollback": "If it does not come up, the previous configuration is written back by itself.",

  "ask.not-yet.missing": "{name} does not exist yet.",
  "ask.not-yet.plan": "It is to make the machine settable the way Previous allows, rather than as a text file. That is being discussed.",

  "ask.board.reboot": "Restart the Raspberry Pi?",
  "ask.board.poweroff": "Switch the Raspberry Pi off?",
  "ask.board.order": "NeXTSTEP is shut down through the power key first. The Pi waits for that, because a restart under a running emulator does the same damage as cutting the power in the middle of a write.",
  "ask.board.loss": "Unsaved work in running programs is lost.",

  /* --- the board underneath --------------------------------------------- */
  "pi.model": "Machine",
  "pi.uptime": "Running",
  "pi.temperature": "Temperature",
  "pi.power": "Power",
  "pi.emulator": "Emulator",
  "pi.sound": "Sound",
  "pi.memory": "Memory",
  "pi.card": "Card",
  "pi.power.now": "now: {what}",
  "pi.power.since-boot": "since the start: {what}",
  "pi.power.fine": "in order",
  "pi.emulator.running": "{percent} %, {mb} MB, {uptime}",
  "pi.emulator.stopped": "not running",
  "pi.sound.playing": "{card}, playing",
  "pi.sound.silent": "{card}, silent",
  "pi.sound.none": "no card",
  "pi.memory.free": "{available} of {total} MB free",
  "pi.disk.free": "{gb} GB free, {percent} % used",

  "throttling.under-voltage": "under-voltage",
  "throttling.frequency-capped": "clock capped",
  "throttling.throttled": "throttled",
  "throttling.temperature-limit": "temperature limit reached",

  /* --- what the service says happened ----------------------------------- */
  "why.blank": "shows nothing on the screen",
  "why.never-came-up": "did not come up",

  "told.emulator.was-not-running": "The emulator was not running and is now switched off.",
  "told.emulator.ended-because-blank": "The machine had not come up, so the emulator was ended. It is switched off now.",
  "told.emulator.blank-and-will-not-end": "The machine did not come up and the emulator would not end either. This wants looking at over SSH.",
  "told.emulator.power-key-refused": "The power key would not go down, so nothing was changed.",
  "told.emulator.already-running": "The emulator is already running.",
  "told.emulator.nothing-holding-it": "Nothing is holding the emulator down, it should come back by itself.",
  "told.emulator.on-its-way-back": "The emulator is coming back.",
  "told.guest.shut-itself-down": "NeXTSTEP has shut itself down, the emulator stays off.",
  "told.guest.still-shutting-down.one": "NeXTSTEP has not shut down after {seconds} second. It stays switched off, and a guest that is still writing is the one case where waiting longer is right.",
  "told.guest.still-shutting-down.other": "NeXTSTEP has not shut down after {seconds} seconds. It stays switched off, and a guest that is still writing is the one case where waiting longer is right.",
  "told.board.no-such-action": "There is no action called {action}.",
  "told.board.request-refused": "NeXTSTEP has shut down, but the Pi could not be asked. It is reachable over SSH.",
  "told.board.on-its-way.reboot": "NeXTSTEP has shut down, the Pi is restarting.",
  "told.board.on-its-way.poweroff": "NeXTSTEP has shut down, the Pi is switching off.",
  "told.machine.no-such": "There is no machine called {asked}.",
  "told.machine.running.one": "{machine} is running, {lines} line changed.",
  "told.machine.running.other": "{machine} is running, {lines} lines changed.",
  "told.machine.was-already-set": "{machine} was already set.",
  "told.file.not-readable": "The configuration could not be read: {detail}",
  "told.token.not-given": "Cancelled without a token.",
  "told.rollback.could-not-write": "{machine} {why}, and the previous configuration could not be written back: {detail}. The machine is reachable over SSH.",
  "told.rollback.emulator-will-not-end": "{machine} {why}, the previous configuration is back in the file, but the emulator would not end. This wants looking at over SSH.",
  "told.rollback.back-as-before": "{machine} {why}. The previous configuration is back in the file and the machine runs as it did.",
  "told.rollback.nothing-runs": "{machine} {why}, and nothing runs with the previous configuration either. This wants looking at over SSH.",
};
