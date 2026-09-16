/* French. */

NX_STRINGS.fr = {
  /* --- the menus ------------------------------------------------------- */
  "menu.info.key": "i",
  "menu.pi.key": "r",
  "menu.files.key": "f",
  "menu.preferences.key": "p",
  "menu.token.key": "j",
  "menu.files": "Fichiers",
  "menu.token": "Jeton",
  "menu.machine": "Machine",
  "menu.machine-info": "Infos…",
  "menu.activate": "Activer la configuration",
  "menu.edit": "Modifier la configuration…",
  "menu.keep": "Poser sur l'étagère",
  "menu.unkeep": "Retirer de l'étagère",

  /* --- the windows ----------------------------------------------------- */
  "window.info": "Infos",
  "window.machine": "Machine",
  "app.preferences": "Preferences",
  "preferences.localization": "Préférences de localisation",

  /* --- the applications, as they are called in words ------------------ */
  "app.config-editor": "Éditeur de configuration",
  "app.grab": "Grab",
  "app.terminal": "Terminal",

  /* --- what a machine is ----------------------------------------------- */
  "info.reading": "lecture en cours",
  "info.state": "État",
  "info.processor": "Processeur",
  "info.memory": "Mémoire",
  "info.screen": "Écran",
  "info.disk": "Disque",
  "info.dimension": "Dimension",
  "info.chips": "Puces",
  "info.file": "Fichier",
  "info.written": "Écrit",
  "info.no-contact": "pas de liaison",
  "info.unreadable": "configuration illisible",
  "info.no-disk": "aucun disque",

  "state.running": "en marche {since}",
  "state.stopped": "arrêtée",
  "state.held": "éteinte",
  "state.unreachable": "injoignable",

  "since.hours": "depuis {hours} h {minutes}",
  "since.minutes": "depuis {minutes} min",
  "since.less-than-a-minute": "depuis moins d'une minute",

  "duration.days.one": "{days} jour, {hours} h",
  "duration.days.other": "{days} jours, {hours} h",
  "duration.hours": "{hours} h {minutes} min",
  "duration.minutes": "{minutes} min",

  /* --- the configuration file ------------------------------------------ */
  "file.changed": "{when}",
  "file.changed-not-booted": "{when}, pas encore démarrée",
  "file.by-previously": "par Previously",
  "file.by-previous-or-hand": "par Previous ou à la main",
  "file.other-machine": "cette machine n'est pas celle qui est réglée",

  /* --- the machine itself ---------------------------------------------- */
  "machine.with-dimension": "{name} avec NeXTdimension",
  "machine.cpu": "{cpu}, {mhz} MHz",
  "machine.memory": "{mb} Mo",
  "machine.memory-banks": "{mb} Mo ({banks})",
  "machine.banks-empty": "vide",
  "machine.screen.dimension": "NeXTdimension, couleur",
  "machine.screen.colour": "MegaPixel, couleur",
  "machine.screen.grey": "MegaPixel, niveaux de gris",
  "machine.chips.with-nextbus": "{rtc}, {scsi}, avec NeXTbus",
  "machine.chips.without-nextbus": "{rtc}, {scsi}, sans NeXTbus",
  "machine.dimension.fitted": "installée",
  "machine.dimension.none": "aucune",

  /* --- the file viewer -------------------------------------------------- */
  "viewer.status": "{name} : {count}{more}",
  "viewer.count.one": "1 élément",
  "viewer.count.other": "{count} éléments",
  "viewer.read-only": ", lecture seule",
  "viewer.unreachable": "Injoignable",

  /* --- the terminal --------------------------------------------------- */
  "terminal.login": "login: ",
  "terminal.refused": "[pas de session : la machine a refusé, ou une session est déjà ouverte]",
  "terminal.ended": "[la session est terminée]",

  /* --- the buttons ------------------------------------------------------ */
  "grab.take": "Prendre une image",
  "grab.idle": "Rien à photographier. La machine ne tourne pas.",
  "grab.failed": "L’écran n’a pas pu être lu.",
  "button.power-off": "Éteindre",
  "button.restart": "Redémarrer",
  "button.power-on": "Allumer",
  "button.change": "Changer",
  "button.use": "Valider",
  "button.fine": "Bien",
  "button.close": "Fermer",
  "button.cancel": "Annuler",
  "button.ok": "Oui",

  /* --- what is happening now -------------------------------------------- */
  "busy.starting": "allumage en cours",
  "busy.stopping": "arrêt en cours",
  "busy.restarting": "redémarrage en cours",
  "busy.changing": "passage à {machine}",
  "busy.board-restart": "NeXTSTEP s'arrête, puis le Pi redémarre",
  "busy.board-poweroff": "NeXTSTEP s'arrête, puis le Pi s'éteint",

  "note.no-console": "La console ne tourne pas. Allumer restera sans effet.",
  "note.no-service": "pas de liaison avec le service",
  "note.board-gone": "Plus de réponse. C'est ce à quoi il faut s'attendre pendant que le Pi s'éteint.",

  /* --- the panels ------------------------------------------------------- */
  "ask.token.title": "Jeton",
  "ask.token.needed": "Cette opération modifie la machine et demande le jeton.",
  "ask.token.where": "Sur le Pi, il se trouve dans un fichier que seul le service peut lire :",
  "ask.token.wrong": "Ce n'était pas le jeton de cette machine.",

  "ask.stop.title": "Arrêter NeXTSTEP",
  "ask.stop.how": "NeXTSTEP est arrêté par la touche d'alimentation, comme avec Power Off dans la fenêtre de déconnexion.",
  "ask.stop.loss": "Le travail non enregistré dans les programmes en cours sera perdu. Le service ne peut pas voir ce que la machine est en train de faire.",

  "ask.change.title": "Changer de machine",
  "ask.change.question": "Démarrer en {machine} ?",
  "ask.change.own": "La configuration réglée en ce moment vous appartient et ne correspond à aucune des machines proposées. Elle sera écrasée.",
  "ask.change.how": "NeXTSTEP est arrêté par la touche d'alimentation, la configuration est écrite et la machine est redémarrée.",
  "ask.change.rollback": "Si elle ne démarre pas, la configuration précédente est réécrite d'elle-même.",

  "ask.not-yet.missing": "{name} n'existe pas encore.",
  "ask.not-yet.plan": "Elle doit rendre la machine réglable comme Previous le permet, et non sous forme de fichier texte. Cela est en discussion.",

  "ask.board.reboot": "Redémarrer le Raspberry Pi ?",
  "ask.board.poweroff": "Éteindre le Raspberry Pi ?",
  "ask.board.order": "NeXTSTEP est arrêté d'abord par la touche d'alimentation. Le Pi attend cela, car un redémarrage sous un émulateur en marche fait les mêmes dégâts qu'une coupure de courant au milieu d'une écriture.",
  "ask.board.loss": "Le travail non enregistré dans les programmes en cours sera perdu.",

  /* --- the board underneath --------------------------------------------- */
  "pi.model": "Machine",
  "pi.uptime": "En marche",
  "pi.temperature": "Température",
  "pi.power": "Alimentation",
  "pi.emulator": "Émulateur",
  "pi.sound": "Son",
  "pi.memory": "Mémoire",
  "pi.card": "Carte",
  "pi.power.now": "maintenant : {what}",
  "pi.power.since-boot": "depuis le démarrage : {what}",
  "pi.power.fine": "correcte",
  "pi.emulator.running": "{percent} %, {mb} Mo, {uptime}",
  "pi.emulator.stopped": "ne tourne pas",
  "pi.sound.playing": "{card}, joue",
  "pi.sound.silent": "{card}, silencieuse",
  "pi.sound.none": "aucune carte",
  "pi.memory.free": "{available} Mo libres sur {total}",
  "pi.disk.free": "{gb} Go libres, {percent} % occupés",

  "throttling.under-voltage": "sous-tension",
  "throttling.frequency-capped": "fréquence plafonnée",
  "throttling.throttled": "bridé",
  "throttling.temperature-limit": "limite de température atteinte",

  /* --- what the service says happened ----------------------------------- */
  "why.blank": "n'affiche rien à l'écran",
  "why.never-came-up": "n'a pas démarré",

  "told.emulator.was-not-running": "L'émulateur ne tournait pas et il est maintenant éteint.",
  "told.emulator.ended-because-blank": "La machine n'avait pas démarré, l'émulateur a donc été arrêté. Il est éteint maintenant.",
  "told.emulator.blank-and-will-not-end": "La machine n'a pas démarré et l'émulateur n'a pas voulu s'arrêter non plus. Cela demande un coup d'œil en SSH.",
  "told.emulator.power-key-refused": "La touche d'alimentation n'a pas voulu s'enfoncer, rien n'a été modifié.",
  "told.emulator.already-running": "L'émulateur tourne déjà.",
  "told.emulator.nothing-holding-it": "Rien ne retient l'émulateur, il devrait revenir de lui-même.",
  "told.emulator.on-its-way-back": "L'émulateur revient.",
  "told.guest.shut-itself-down": "NeXTSTEP s'est arrêté de lui-même, l'émulateur reste éteint.",
  "told.guest.still-shutting-down.one": "NeXTSTEP n'est toujours pas arrêté après {seconds} seconde. Il reste éteint, et un invité qui écrit encore est le seul cas où attendre plus longtemps est la bonne chose.",
  "told.guest.still-shutting-down.other": "NeXTSTEP n'est toujours pas arrêté après {seconds} secondes. Il reste éteint, et un invité qui écrit encore est le seul cas où attendre plus longtemps est la bonne chose.",
  "told.board.no-such-action": "Il n'existe aucune action nommée {action}.",
  "told.board.request-refused": "NeXTSTEP est arrêté, mais le Pi n'a pas pu en être prié. Il reste joignable en SSH.",
  "told.board.on-its-way.reboot": "NeXTSTEP est arrêté, le Pi redémarre.",
  "told.board.on-its-way.poweroff": "NeXTSTEP est arrêté, le Pi s'éteint.",
  "told.machine.no-such": "Il n'existe aucune machine nommée {asked}.",
  "told.machine.running.one": "{machine} tourne, {lines} ligne modifiée.",
  "told.machine.running.other": "{machine} tourne, {lines} lignes modifiées.",
  "told.machine.was-already-set": "{machine} était déjà réglée.",
  "told.file.not-readable": "La configuration n'a pas pu être lue : {detail}",
  "told.token.not-given": "Interrompu faute de jeton.",
  "told.rollback.could-not-write": "{machine} {why}, et la configuration précédente n'a pas pu être réécrite : {detail}. La machine est joignable en SSH.",
  "told.rollback.emulator-will-not-end": "{machine} {why}, la configuration précédente est de retour dans le fichier, mais l'émulateur n'a pas voulu s'arrêter. Cela demande un coup d'œil en SSH.",
  "told.rollback.back-as-before": "{machine} {why}. La configuration précédente est de retour dans le fichier et la machine tourne comme avant.",
  "told.rollback.nothing-runs": "{machine} {why}, et rien ne tourne non plus avec la configuration précédente. Cela demande un coup d'œil en SSH.",
};
