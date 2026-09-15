/* German. */

NX_STRINGS.de = {
  /* --- the menus ------------------------------------------------------- */
  "menu.files": "Dateien",
  "menu.token": "Token",
  "menu.machine": "Maschine",
  "menu.machine-info": "Info…",
  "menu.activate": "Konfiguration aktivieren",
  "menu.edit": "Konfiguration bearbeiten…",
  "menu.keep": "Auf die Ablage legen",
  "menu.unkeep": "Von der Ablage nehmen",

  /* --- the windows ----------------------------------------------------- */
  "window.info": "Info",
  "window.machine": "Maschine",
  "app.preferences": "Präferenzen",
  "preferences.localization": "Lokalisierungs-Präferenzen",

  /* --- the applications, as they are called in words ------------------ */
  "app.config-editor": "Konfigurationseditor",
  "app.terminal": "Terminal",

  /* --- what a machine is ----------------------------------------------- */
  "info.reading": "wird gelesen",
  "info.state": "Zustand",
  "info.processor": "Prozessor",
  "info.memory": "Speicher",
  "info.screen": "Bildschirm",
  "info.disk": "Platte",
  "info.dimension": "Dimension",
  "info.chips": "Chips",
  "info.file": "Datei",
  "info.written": "Geschrieben",
  "info.no-contact": "keine Verbindung",
  "info.unreadable": "Konfiguration nicht lesbar",
  "info.no-disk": "keine eingelegt",

  "state.running": "läuft {since}",
  "state.stopped": "angehalten",
  "state.held": "ausgeschaltet",
  "state.unreachable": "nicht erreichbar",

  "since.hours": "seit {hours}:{minutes} Std",
  "since.minutes": "seit {minutes} Min",
  "since.less-than-a-minute": "seit weniger als einer Minute",

  "duration.days.one": "{days} Tag, {hours} Std",
  "duration.days.other": "{days} Tage, {hours} Std",
  "duration.hours": "{hours} Std {minutes} Min",
  "duration.minutes": "{minutes} Min",

  /* --- the configuration file ------------------------------------------ */
  "file.changed": "{when}",
  "file.changed-not-booted": "{when}, noch nicht gebootet",
  "file.by-previously": "von Previously",
  "file.by-previous-or-hand": "von Previous oder von Hand",
  "file.other-machine": "diese Maschine ist nicht eingestellt",

  /* --- the machine itself ---------------------------------------------- */
  "machine.with-dimension": "{name} mit NeXTdimension",
  "machine.cpu": "{cpu}, {mhz} MHz",
  "machine.memory": "{mb} MB",
  "machine.memory-banks": "{mb} MB ({banks})",
  "machine.banks-empty": "leer",
  "machine.screen.dimension": "NeXTdimension, farbig",
  "machine.screen.colour": "MegaPixel, farbig",
  "machine.screen.grey": "MegaPixel, Graustufen",
  "machine.chips.with-nextbus": "{rtc}, {scsi}, mit NeXTbus",
  "machine.chips.without-nextbus": "{rtc}, {scsi}, ohne NeXTbus",
  "machine.dimension.fitted": "eingebaut",
  "machine.dimension.none": "keine",

  /* --- the file viewer -------------------------------------------------- */
  "viewer.status": "{name}: {count}{more}",
  "viewer.count.one": "1 Eintrag",
  "viewer.count.other": "{count} Einträge",
  "viewer.read-only": ", nur lesbar",
  "viewer.unreachable": "Nicht erreichbar",

  /* --- the terminal --------------------------------------------------- */
  "terminal.ended": "[die Sitzung ist beendet]",

  /* --- the buttons ------------------------------------------------------ */
  "button.power-off": "Ausschalten",
  "button.restart": "Neu starten",
  "button.power-on": "Einschalten",
  "button.change": "Wechseln",
  "button.use": "Übernehmen",
  "button.fine": "Gut",
  "button.close": "Schliessen",
  "button.cancel": "Abbrechen",
  "button.ok": "Ja",

  /* --- what is happening now -------------------------------------------- */
  "busy.starting": "wird eingeschaltet",
  "busy.stopping": "fährt herunter",
  "busy.restarting": "startet neu",
  "busy.changing": "wechselt auf {machine}",
  "busy.board-restart": "NeXTSTEP fährt herunter, dann startet der Pi neu",
  "busy.board-poweroff": "NeXTSTEP fährt herunter, dann schaltet der Pi ab",

  "note.no-console": "Die Konsole läuft nicht. Einschalten bleibt wirkungslos.",
  "note.no-service": "keine Verbindung zum Dienst",
  "note.board-gone": "Keine Antwort mehr. Das ist zu erwarten, wenn der Pi gerade abschaltet.",

  /* --- the panels ------------------------------------------------------- */
  "ask.token.title": "Token",
  "ask.token.needed": "Dieser Vorgang ändert etwas an der Maschine und braucht das Token.",
  "ask.token.where": "Auf dem Pi steht es in einer Datei, die nur der Dienst lesen darf:",
  "ask.token.wrong": "Das war nicht das Token dieser Maschine.",

  "ask.stop.title": "NeXTSTEP anhalten",
  "ask.stop.how": "NeXTSTEP wird über den Ausschalter heruntergefahren, so wie über Power Off im Logout-Fenster.",
  "ask.stop.loss": "Nicht gespeicherte Arbeit in laufenden Programmen geht dabei verloren. Der Dienst kann nicht sehen, woran die Maschine gerade arbeitet.",

  "ask.change.title": "Maschine wechseln",
  "ask.change.question": "Als {machine} starten?",
  "ask.change.own": "Eingestellt ist gerade eine eigene Konfiguration, die keiner der angebotenen Maschinen entspricht. Sie wird dabei überschrieben.",
  "ask.change.how": "NeXTSTEP wird über den Ausschalter heruntergefahren, die Konfiguration geschrieben und die Maschine neu gestartet.",
  "ask.change.rollback": "Kommt sie damit nicht hoch, wird die vorherige Konfiguration von selbst zurückgeschrieben.",

  "ask.not-yet.missing": "{name} gibt es noch nicht.",
  "ask.not-yet.plan": "Sie soll die Maschine so einstellbar machen, wie Previous es erlaubt, und nicht als Textdatei. Das wird gerade besprochen.",

  "ask.board.reboot": "Den Raspberry Pi neu starten?",
  "ask.board.poweroff": "Den Raspberry Pi ausschalten?",
  "ask.board.order": "NeXTSTEP wird zuerst über den Ausschalter heruntergefahren. Der Pi wartet darauf, weil ein Neustart unter einem laufenden Emulator dasselbe anrichtet wie das Abschalten mitten im Schreiben.",
  "ask.board.loss": "Nicht gespeicherte Arbeit in laufenden Programmen geht dabei verloren.",

  /* --- the board underneath --------------------------------------------- */
  "pi.model": "Maschine",
  "pi.uptime": "Läuft",
  "pi.temperature": "Temperatur",
  "pi.power": "Strom",
  "pi.emulator": "Emulator",
  "pi.sound": "Ton",
  "pi.memory": "Speicher",
  "pi.card": "Karte",
  "pi.power.now": "jetzt: {what}",
  "pi.power.since-boot": "seit dem Start: {what}",
  "pi.power.fine": "in Ordnung",
  "pi.emulator.running": "{percent} %, {mb} MB, {uptime}",
  "pi.emulator.stopped": "läuft nicht",
  "pi.sound.playing": "{card}, spielt",
  "pi.sound.silent": "{card}, still",
  "pi.sound.none": "keine Karte",
  "pi.memory.free": "{available} von {total} MB frei",
  "pi.disk.free": "{gb} GB frei, {percent} % belegt",

  "throttling.under-voltage": "Unterspannung",
  "throttling.frequency-capped": "Takt gedeckelt",
  "throttling.throttled": "gedrosselt",
  "throttling.temperature-limit": "Temperaturgrenze erreicht",

  /* --- what the service says happened ----------------------------------- */
  "why.blank": "zeigt nichts auf dem Bildschirm",
  "why.never-came-up": "kam nicht hoch",

  "told.emulator.was-not-running": "Der Emulator lief nicht und ist jetzt ausgeschaltet.",
  "told.emulator.ended-because-blank": "Die Maschine war nicht hochgekommen, also wurde der Emulator beendet. Er ist jetzt ausgeschaltet.",
  "told.emulator.blank-and-will-not-end": "Die Maschine ist nicht hochgekommen und der Emulator liess sich auch nicht beenden. Das ist über SSH nachzusehen.",
  "told.emulator.power-key-refused": "Der Ausschalter liess sich nicht drücken, es wurde nichts geändert.",
  "told.emulator.already-running": "Der Emulator läuft schon.",
  "told.emulator.nothing-holding-it": "Nichts hält den Emulator unten, er sollte von selbst zurückkommen.",
  "told.emulator.on-its-way-back": "Der Emulator kommt zurück.",
  "told.guest.shut-itself-down": "NeXTSTEP hat sich heruntergefahren, der Emulator bleibt aus.",
  "told.guest.still-shutting-down.one": "NeXTSTEP ist nach {seconds} Sekunde noch nicht heruntergefahren. Es bleibt ausgeschaltet, und ein Gast, der noch schreibt, ist der eine Fall, in dem längeres Warten richtig ist.",
  "told.guest.still-shutting-down.other": "NeXTSTEP ist nach {seconds} Sekunden noch nicht heruntergefahren. Es bleibt ausgeschaltet, und ein Gast, der noch schreibt, ist der eine Fall, in dem längeres Warten richtig ist.",
  "told.board.no-such-action": "Es gibt keine Aktion namens {action}.",
  "told.board.request-refused": "NeXTSTEP ist heruntergefahren, aber der Pi liess sich nicht darum bitten. Er ist über SSH zu erreichen.",
  "told.board.on-its-way.reboot": "NeXTSTEP ist heruntergefahren, der Pi startet neu.",
  "told.board.on-its-way.poweroff": "NeXTSTEP ist heruntergefahren, der Pi schaltet ab.",
  "told.machine.no-such": "Es gibt keine Maschine namens {asked}.",
  "told.machine.running.one": "{machine} läuft, {lines} Zeile geändert.",
  "told.machine.running.other": "{machine} läuft, {lines} Zeilen geändert.",
  "told.machine.was-already-set": "{machine} war schon eingestellt.",
  "told.file.not-readable": "Die Konfiguration liess sich nicht lesen: {detail}",
  "told.token.not-given": "Ohne Token abgebrochen.",
  "told.rollback.could-not-write": "{machine} {why}, und die vorherige Konfiguration liess sich nicht zurückschreiben: {detail}. Die Maschine ist über SSH zu erreichen.",
  "told.rollback.emulator-will-not-end": "{machine} {why}, die vorherige Konfiguration steht wieder in der Datei, aber der Emulator liess sich nicht beenden. Das ist über SSH nachzusehen.",
  "told.rollback.back-as-before": "{machine} {why}. Die vorherige Konfiguration steht wieder in der Datei und die Maschine läuft wie zuvor.",
  "told.rollback.nothing-runs": "{machine} {why}, und auch mit der vorherigen Konfiguration läuft nichts. Das ist über SSH nachzusehen.",
};
