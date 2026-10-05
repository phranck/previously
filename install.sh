#!/usr/bin/env bash
#
# Turns a freshly imaged Raspberry Pi OS Lite (64 bit, Trixie) into a machine
# that runs NeXTSTEP under the Previous emulator, and leaves it running.
#
#   curl -fsSL https://previous.li/install.sh | bash
#
# And afterwards, to put the newest admin tool on a machine that already has
# one, which is the one part of this that changes often enough to be worth
# replacing by itself:
#
#   curl -fsSL https://previous.li/install.sh | bash -s -- --update-admin
#
# It installs the admin tool and asks the tool's privileged helper for the
# rest, which is the job the Installer window runs from a browser: the
# emulator, the system's disk, the configuration, the console, the quiet boot,
# the sound, and finally the machine itself. So every step exists once, in
# admin/previously/setup.py, and this shows them as they happen.
#
# Written to run straight off the network, so it carries everything it needs
# and reads no file beside itself. Two details make that safe.
#
# All the work sits in functions and nothing runs until `main` is called on
# the last line, so a download cut short executes nothing at all.
#
# And nothing in here reads from stdin, which is where the script itself
# arrives when it is piped in. A program that did would swallow the rest of
# the script. That is why apt runs with DEBIAN_FRONTEND set: a package asking
# a configuration question would otherwise reach for stdin. `apt_get` below is
# what sets it, and it sets it on the sudo rather than in this shell, because
# sudo runs with env_reset and drops whatever this shell exports. sudo itself
# is not a concern, because it reads the password from the terminal device
# rather than from stdin unless told otherwise with -S.
#
# Interrupted while the tool is being installed, it takes the tool off again.
# Once the helper has the job, the Pi carries on by itself: an interruption
# stops the watching and nothing else, and the Installer window shows the rest.

set -euo pipefail

# Where this script is, so it can find the files that ship beside it. Resolved
# rather than taken from $0, because the script is meant to be runnable from
# anywhere and through a symlink.
#
# Run through a pipe there is no file to resolve, which is how the line on the
# Previously page runs it: BASH_SOURCE is unset, and under `set -u` reading it
# ends the script before its first line of work. The fallback is the current
# directory, where nothing will be found, and everything that looks beside the
# script is written to take that as an answer.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd -P || pwd -P)"
readonly SCRIPT_DIR

# Every apt call in this script, so the frontend is stated once and reaches
# the command that needs it.
#
# Exporting it into this shell does nothing: sudo runs with `Defaults
# env_reset`, so it builds a fresh environment and whatever this shell set is
# gone by the time apt-get starts. Measured on a Pi: `export
# DEBIAN_FRONTEND=noninteractive; sudo printenv DEBIAN_FRONTEND` prints nothing.
# Given to the sudo it survives, because sudo puts an assignment in front of
# the command into the environment it builds.
apt_get() {
  sudo DEBIAN_FRONTEND=noninteractive apt-get "$@"
}

# The admin tool, for a run that has no checkout beside it. The name carries no
# version, so this address is the latest release whatever that is, and the
# version is in the package where dpkg can report it.
readonly PACKAGE_FILE="previously_all.deb"
readonly PACKAGE_URL="https://github.com/phranck/previously/releases/latest/download/${PACKAGE_FILE}"

# The system a fresh machine gets, by the identifier the helper looks it up
# under in admin/previously/systems.py.
readonly SYSTEM="nextstep-3.3"

# Where the emulator runs, and therefore where it writes what it is asked to
# write. The console below changes into it.
readonly WORK_DIR="${HOME}/.cache/previously"

# ~/.profile and not ~/.bash_profile. Bash reads only the first of the login
# files that exists, and on Raspberry Pi OS that is ~/.profile, which pulls in
# ~/.bashrc. Creating ~/.bash_profile would switch both off, including for SSH
# sessions, which are the way back into a machine whose screen is taken.
readonly PROFILE="${HOME}/.profile"

# The admin tool's own runtime directory, which its unit makes on a tmpfs. The
# request for the helper goes in here, under the name previously-setup.path
# watches for.
readonly RUNTIME_DIR="/run/previously"
readonly REQUEST="${RUNTIME_DIR}/setup"

# Where the helper says what it is doing. Root's own directory, which this
# only reads.
readonly PROGRESS="/run/previously-setup/progress.json"

# Who the tool runs as, which its package wrote down on install. The request
# goes into that user's runtime directory, so this has to run as them too.
readonly OWNER_FILE="/etc/systemd/system/previously.service.d/owner.conf"

# The admin tool holds the emulator down by creating this file, and the
# console's autostart below waits on it. On a tmpfs, so a board that has just
# started runs its emulator whoever switched it off before the last shutdown.
readonly HOLD_FILE="${RUNTIME_DIR}/hold"

# Where the console writes down an emulator that ended badly, one line each,
# which the Raspberry Pi window reads. On the same tmpfs, so the file is gone
# at every boot and what is in it is what happened since this board came up.
readonly CRASHES_FILE="${RUNTIME_DIR}/crashes"

readonly AUTOSTART_MARKER="# >>> nextstep-rpi >>>"
readonly AUTOSTART_END="# <<< nextstep-rpi <<<"

# How long the helper may take to answer a request before this gives up on
# it. The path unit fires within a second; this is for a machine where it
# never does.
readonly ANSWER_SECONDS=60

# ---------------------------------------------------------------------------
# What the screen shows
#
# Only this script's own lines reach the terminal. What apt and dpkg print goes
# to a log file, which a failure names. Color and the spinner are for a
# terminal; piped into a file the same run writes plain lines, one per step.
# NO_COLOR is honored, as https://no-color.org asks.
# ---------------------------------------------------------------------------

# Made by main, so a download cut short leaves no file behind.
LOG=""

if [[ -t 1 ]]; then TERMINAL=true; else TERMINAL=false; fi
if [[ "$TERMINAL" == true && -z "${NO_COLOR:-}" ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
  CYAN=$'\033[36m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; CYAN=""; RESET=""
fi
readonly TERMINAL BOLD DIM RED GREEN CYAN RESET

readonly SPINNER=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
SPUN=0

# Clears the line the spinner is on, where there is one.
clear_line() {
  [[ "$TERMINAL" == true ]] && printf '\r\033[K'
  return 0
}

# One turn of the spinner beside what is happening now. Plain output has no
# line to redraw, so it writes nothing and the finished line says it all.
spin() {
  [[ "$TERMINAL" == true ]] || return 0
  printf '\r\033[K  %s%s%s %s' "$CYAN" "${SPINNER[SPUN % ${#SPINNER[@]}]}" "$RESET" "$1"
  SPUN=$((SPUN + 1))
}

done_line()    { clear_line; printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
already_line() { clear_line; printf '  %s✓ %s  already in place%s\n' "$DIM" "$1" "$RESET"; }
failed_line()  { clear_line; printf '  %s✗%s %s\n' "$RED" "$RESET" "$1"; }
detail()       { printf '    %s%s%s\n' "$DIM" "$1" "$RESET"; }

abort() {
  failed_line "$1"
  [[ -s "$LOG" ]] && detail "What the tools said is in ${LOG}"
  exit 1
}

banner() {
  printf '\n  %sPreviously%s\n' "$BOLD" "$RESET"
  printf '  %sYour fastest way to get NeXTSTEP on your Raspberry Pi up and running.%s\n\n' "$DIM" "$RESET"
}

# Runs a command with its output in the log and the spinner beside it.
#
# $1 is what to show whilst it runs, and the rest is the command. Answers with
# the command's own status.
quietly() {
  local label="$1"
  shift
  "$@" >>"$LOG" 2>&1 &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    spin "$label"
    sleep 0.1
  done
  wait "$pid"
}

# ---------------------------------------------------------------------------
# Undo record
#
# Two parallel arrays rather than one of "description|command", because a
# command holding the separator would be cut in half. Commands are assembled
# with printf %q so that a path with spaces survives being stored as text and
# evaluated later.
# ---------------------------------------------------------------------------

declare -a UNDO_WHAT=()
declare -a UNDO_HOW=()
COMPLETED=false

# Set once the helper has the job. From there on the Pi carries on by itself,
# so leaving early stops the watching and takes nothing away.
HANDED_OVER=false

undo() {
  UNDO_WHAT+=("$1")
  UNDO_HOW+=("$2")
}

rollback() {
  [[ ${#UNDO_HOW[@]} -gt 0 ]] || return 0
  printf '\n  %sPutting back what this run changed%s\n' "$BOLD" "$RESET"
  # Backwards, so each step is reversed in a world that still looks the way it
  # did when that step ran.
  local index
  for (( index = ${#UNDO_HOW[@]} - 1; index >= 0; index-- )); do
    detail "${UNDO_WHAT[index]}"
    eval "${UNDO_HOW[index]}" > /dev/null 2>&1 || \
      printf '    %sfailed, do this by hand:%s %s\n' "$RED" "$RESET" "${UNDO_HOW[index]}" >&2
  done
}

on_exit() {
  local code=$?
  [[ "$COMPLETED" == true ]] && return 0
  clear_line

  if [[ "$HANDED_OVER" == true ]]; then
    printf '\n'
    detail "The Pi carries on by itself. The Installer window at $(admin_address) shows how far it is."
    exit "$code"
  fi

  if [[ $code -eq 130 ]]; then
    printf '\n  %sInterrupted%s\n' "$BOLD" "$RESET"
  fi
  rollback
  exit "$code"
}

on_interrupt() {
  # Leave through the exit handler with the conventional code for SIGINT
  # rather than doing the work twice.
  exit 130
}

# Called from an undo entry. A function rather than an inline `sed -i`, because
# in-place editing is spelled differently on different systems and an undo step
# that fails silently is worse than no undo step at all.
remove_autostart_block() {
  local file="$1" scratch
  [[ -f "$file" ]] || return 0
  scratch="$(mktemp)"
  sed "/${AUTOSTART_MARKER}/,/${AUTOSTART_END}/d" "$file" > "$scratch"
  mv -f "$scratch" "$file"
}

trap on_exit EXIT
trap on_interrupt INT TERM

# The one thing somebody needs once this has finished. The name rather than the
# address, because a Pi answers to <hostname>.local on the network it is on
# and its address may not last.
admin_address() {
  printf 'http://%s.local:8810' "$(hostname)"
}

# ---------------------------------------------------------------------------
# Refuse to run anywhere the Previous package would not fit.
# ---------------------------------------------------------------------------

check_host() {
  [[ $EUID -ne 0 ]] || abort "Run this as your normal user, not as root. It uses sudo where it needs to."

  local architecture
  architecture="$(dpkg --print-architecture)"
  [[ "$architecture" == "arm64" ]] || abort "This needs arm64, found ${architecture}. Use the 64 bit image of Raspberry Pi OS."

  local codename
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
  [[ "$codename" == "trixie" ]] || abort "This needs Raspberry Pi OS based on Debian trixie, found '${codename:-unknown}'. Older releases carry no SDL3."

  done_line "Raspberry Pi OS, arm64, ${codename}"
}

# Asks for the sudo password once, on a line of its own, before any spinner
# could draw over the prompt. A user the Imager created needs none.
check_sudo() {
  sudo -n true 2>/dev/null && return 0
  printf '  %sThe next steps need sudo.%s\n' "$DIM" "$RESET"
  sudo -v || abort "sudo did not let this run."
}

# ---------------------------------------------------------------------------
# The admin tool. It arrives as a package with the service, its configuration
# and the units that act for it as root, so there is one place the tool comes
# from and one command that takes it away again.
#
# Two ways in, because this script arrives two ways. Run out of a checkout it
# builds the package from what is already beside it, which always matches that
# checkout. Run from the web there is nothing beside it and it takes the
# package from the latest release.
# ---------------------------------------------------------------------------

# Where fetch_admin_package left the package. A variable rather than something
# printed, because the callers also print as they go and a function that
# answers through stdout could only do one or the other.
ADMIN_PACKAGE=""

# The version dpkg has, or nothing at all where the tool is absent.
admin_version() {
  dpkg-query -W -f='${Version}' previously 2>/dev/null || true
}

admin_is_installed() {
  dpkg-query -W -f='${Status}' previously 2>/dev/null | grep -q "ok installed"
}

fetch_admin_package() {
  local packaging="${SCRIPT_DIR}/admin/packaging"
  if [[ -f "${packaging}/build.py" ]]; then
    ADMIN_PACKAGE="$(python3 "${packaging}/build.py" 2>>"$LOG" | awk '{print $2}')" \
      || abort "Could not build the admin package."
  else
    ADMIN_PACKAGE="$(mktemp -d)/${PACKAGE_FILE}"
    quietly "Fetching the admin tool" curl -fsSL -o "$ADMIN_PACKAGE" "$PACKAGE_URL" \
      || abort "Could not fetch ${PACKAGE_URL}."
    undo "remove the downloaded package" "rm -f $(printf '%q' "$ADMIN_PACKAGE")"
  fi
}

install_admin() {
  if admin_is_installed; then
    already_line "The admin tool $(admin_version)"
    return
  fi

  fetch_admin_package

  # apt rather than dpkg, so the dependencies it declares are resolved. The
  # package enables and starts the service and the units that act for it.
  quietly "Installing the admin tool" apt_get update -qq \
    || abort "apt could not read its package lists."
  quietly "Installing the admin tool" apt_get install -y -qq "$ADMIN_PACKAGE" \
    || abort "Could not install the admin tool."
  undo "remove the admin tool" "apt_get purge -y -qq previously"

  done_line "The admin tool $(admin_version)"
}

# The admin tool on its own, for a machine that already has everything else.
#
# Nothing here is written to the undo record. A run that fails half way leaves
# the tool that was already installed, and rolling that back would take away a
# working one to answer for a replacement that never happened.
update_admin() {
  local before
  before="$(admin_version)"
  [[ -n "$before" ]] || abort "The admin tool is not installed. Run this without --update-admin."

  fetch_admin_package

  # A package carries the release and the commit it was built from, so two
  # builds are two versions and apt can order them. --reinstall is for putting
  # the same build in place again, which is what a rebuild of one commit is,
  # and --allow-downgrades is for going back to a release from a checkout that
  # ran ahead of it.
  quietly "Updating the admin tool" \
    apt_get install -y -qq --reinstall --allow-downgrades "$ADMIN_PACKAGE" \
    || abort "Could not install the admin tool."

  local after
  after="$(admin_version)"
  if [[ "$before" == "$after" ]]; then
    done_line "The admin tool ${after}, put in place again"
  else
    done_line "The admin tool ${before} replaced by ${after}"
  fi
}

# ---------------------------------------------------------------------------
# The rest of the machine, through the helper.
#
# The request is the one the Installer window sends: a job, a system and no
# machine, which the helper reads as the one a fresh machine gets. It is
# written under another name and moved into place, because the path unit fires
# the moment the name appears and a file half written is a request half read.
# ---------------------------------------------------------------------------

# The steps of the install job, in the order the helper takes them. A step
# that finds its work done is over in a few milliseconds, which is quicker than
# this looks, so the record often names a later step than the last one shown,
# and every step in between is closed from this list.
readonly INSTALL_STEPS=(host tools archive emulator system configuration autologin quiet autostart sound start)

# Where a step stands in that list, or -1.
step_index() {
  local index
  for index in "${!INSTALL_STEPS[@]}"; do
    if [[ "${INSTALL_STEPS[index]}" == "$1" ]]; then
      echo "$index"
      return
    fi
  done
  echo -1
}

# What each step of the install job is called, in the words the Installer
# window uses for it. tests/test_install.py holds these to the English
# catalogue and to the steps the job takes.
step_label() {
  case "$1" in
    host) echo "Checking the machine" ;;
    tools) echo "The compositor and the tools" ;;
    archive) echo "The archive Previous comes from" ;;
    emulator) echo "The Previous emulator" ;;
    system) echo "The system's disk" ;;
    configuration) echo "The emulator's configuration" ;;
    autologin) echo "Logging in on the console" ;;
    quiet) echo "Silencing the startup" ;;
    autostart) echo "Starting on the first console" ;;
    sound) echo "Sound to a speaker" ;;
    start) echo "Starting the machine" ;;
    *) echo "$1" ;;
  esac
}

# What a long step is doing inside itself, in the same words. {done} and {of}
# are filled with sizes.
doing_label() {
  case "$1" in
    fetching) echo "Fetching {done} of {of}." ;;
    unpacking) echo "Unpacking {done} of {of}." ;;
    copying) echo "Copying {done} of {of}." ;;
    checking) echo "Checking what arrived." ;;
    installing) echo "Putting it in place." ;;
    *) echo "" ;;
  esac
}

# The helper's record, as one line of fields: when this run
# started, whether it has finished and how, which step it is on, what that
# step is doing and how far, which steps changed something, and why it failed.
# Python because the record is JSON, and python3 is on every Raspberry Pi OS.
# Parted by the unit separator rather than a tab, because read collapses a run
# of tabs into one and an empty field would shift every field after it.
read_progress() {
  python3 -c '
import json, sys

def size(count):
    count = float(count or 0)
    for unit in ("bytes", "KB", "MB", "GB"):
        if count < 1000 or unit == "GB":
            return ("%d %s" if unit in ("bytes", "KB", "MB") else "%.1f %s") % (count, unit)
        count /= 1000

try:
    with open(sys.argv[1], encoding="utf-8") as file:
        record = json.load(file)
except (OSError, ValueError):
    sys.exit(1)
part = record.get("part") or {}
failed = record.get("failed") or {}
print("\x1f".join(str(field) for field in (
    record.get("started_at") or 0,
    "" if record.get("finished_at") is None else "finished",
    record.get("ok"),
    record.get("step") or "",
    part.get("doing") or "",
    size(part.get("done")),
    size(part.get("of")),
    ",".join(record.get("changed") or []),
    failed.get("reason") or "",
    ",".join(record.get("undone") or []),
)))
' "$PROGRESS"
}

# The line beside the spinner for one step: its name, and what it is doing
# inside itself where it says.
running_label() {
  local step="$1" doing="$2" done_size="$3" of_size="$4" words
  words="$(doing_label "$doing")"
  words="${words//\{done\}/$done_size}"
  words="${words//\{of\}/$of_size}"
  if [[ -n "$words" ]]; then
    printf '%s  %s%s%s' "$(step_label "$step")" "$DIM" "$words" "$RESET"
  else
    step_label "$step"
  fi
}

# Closes the line of a step that has ended.
finish_step() {
  local step="$1" changed="$2"
  if [[ ",${changed}," == *",${step},"* ]]; then
    done_line "$(step_label "$step")"
  else
    already_line "$(step_label "$step")"
  fi
}

# The index of the first step whose line is not closed yet.
OPEN_STEP=0

# Whether the last step started the emulator, rather than finding it running.
STARTED=false

# Closes every step before the one at $1, which the helper has passed.
close_steps_before() {
  local until="$1" changed="$2"
  while (( OPEN_STEP < until )); do
    finish_step "${INSTALL_STEPS[OPEN_STEP]}" "$changed"
    OPEN_STEP=$((OPEN_STEP + 1))
  done
}

set_up_the_machine() {
  local owner
  owner="$(sed -n 's/^User=//p' "$OWNER_FILE" 2>/dev/null || true)"
  if [[ -n "$owner" && "$owner" != "$(id -un)" ]]; then
    # The tool stays: it is installed for the right person, and this run was
    # only started by the wrong one.
    COMPLETED=true
    abort "The admin tool runs as ${owner}. Log in as ${owner} and run this again."
  fi

  [[ -d "$RUNTIME_DIR" ]] || abort "The admin tool is not running, so there is nobody to ask for the rest."

  local asked_at
  asked_at="$(date +%s)"
  printf '{"do": "install", "system": "%s", "machine": null, "backup": null}' "$SYSTEM" \
    > "${REQUEST}.writing"
  mv -f "${REQUEST}.writing" "$REQUEST"
  HANDED_OVER=true

  local line started finished ok step doing done_size of_size changed reason undone
  local waited=0 index
  while true; do
    line="$(read_progress 2>/dev/null || true)"
    IFS=$'\x1f' read -r started finished ok step doing done_size of_size changed reason undone <<< "$line"

    # A record from before this request is the last run, not this one.
    if [[ -z "$line" || "${started%.*}" -lt "$asked_at" ]]; then
      waited=$((waited + 1))
      if (( waited >= ANSWER_SECONDS * 10 )); then
        # The tool stays: it is installed and answering, and its Installer
        # window can ask again. So nothing is put back on the way out.
        COMPLETED=true
        abort "The helper never answered. journalctl -u previously-setup says why."
      fi
      spin "Asking the Pi for the rest"
      sleep 0.1
      continue
    fi

    index="$(step_index "$step")"
    (( index < 0 )) || close_steps_before "$index" "$changed"

    if [[ -n "$finished" ]]; then
      if [[ "$ok" == "True" ]]; then
        close_steps_before "${#INSTALL_STEPS[@]}" "$changed"
        [[ ",${changed}," == *",start,"* ]] && STARTED=true
        return 0
      fi
      failed_line "$(step_label "${step:-host}")"
      detail "It stopped here: ${reason:-no reason given}."
      [[ -n "$undone" ]] && detail "Put back: ${undone//,/, }."
      detail "The Installer window at $(admin_address) says it in words and can try again."
      COMPLETED=true
      exit 1
    fi

    spin "$(running_label "$step" "$doing" "$done_size" "$of_size")"
    sleep 0.1
  done
}

# ---------------------------------------------------------------------------
# The console, under --update-admin. A full run has the helper write it; a
# machine whose tool is replaced has its console brought up to what this
# version writes, because it is what starts the emulator and what writes down
# a crash, and a tool that has moved on with a console that has not is the
# state this exists to prevent.
# ---------------------------------------------------------------------------

# What the autostart says, as one piece. Written out here rather than straight
# into the file, because a block that is already there has to be compared with
# it: it is generated, so a machine set up before this version carries whatever
# that version wrote, and the change that matters most is the one nobody would
# notice, which is the line that writes down a crash.
autostart_block() {
  cat <<EOF
${AUTOSTART_MARKER}
# Hand the first console to Previous. XDG_VTNR carries the number of the text
# console and is set only where one is actually behind the login, so an SSH
# session falls through and stays the way in once the screen is taken.
#
# The wait is how the admin tool stops and starts the emulator without any
# privileges at all: it creates ${HOLD_FILE} to hold it down and removes the
# file to let it come back. Waiting rather than exiting matters twice. It keeps
# the console from falling through to a shell prompt while the emulator is
# held, and it avoids the race that stopping through systemd would have, since
# this unit restarts itself the moment a session ends and would bring a fresh
# emulator up underneath whatever stopped the last one.
#
# The file is on a tmpfs, so a board that has just booted never finds one and
# always starts its emulator.
#
# The directory it runs in is where it writes a screen grab, and the admin tool
# reads those and removes them. Its own rather than the home directory, so the
# tool needs write access to that one directory and to nothing else of yours.
#
# An emulator that ends badly says so in one line, which the Raspberry Pi window
# reads. It goes in the runtime directory because that is a tmpfs: the file is
# gone at every boot, so whatever is in it happened since this board came up and
# nothing has to work out when. The exit runs the session down exactly as exec
# did, so the console never falls through to a prompt.
if [ "\$XDG_VTNR" = 1 ] && [ -z "\$WAYLAND_DISPLAY" ]; then
  clear
  while [ -f ${HOLD_FILE} ]; do sleep 2; done
  mkdir -p ${WORK_DIR}
  cd ${WORK_DIR}
  cage -- /usr/bin/previous
  status=\$?
  if [ "\$status" -ne 0 ] && [ -d ${RUNTIME_DIR} ]; then
    printf "%s %s\\n" "\$(date +%s)" "\$status" >> ${CRASHES_FILE}
  fi
  exit "\$status"
fi
${AUTOSTART_END}
EOF
}

# What the file says now, between the markers, or nothing where there is none.
autostart_in_profile() {
  [[ -f "$PROFILE" ]] || return 0
  sed -n "/${AUTOSTART_MARKER}/,/${AUTOSTART_END}/p" "$PROFILE"
}

# Brings a console that is there up to what this version writes. A machine
# that has never had a console is not given one: --update-admin exists to
# replace the admin tool and touch nothing else.
refresh_autostart() {
  local wanted there
  wanted="$(autostart_block)"
  there="$(autostart_in_profile)"

  if [[ -z "$there" ]]; then
    already_line "No console here, and --update-admin adds none"
    return
  fi
  if [[ "$there" == "$wanted" ]]; then
    already_line "The console"
    return
  fi

  # The whole file is kept, rather than the block alone, so the undo puts back
  # what was there instead of taking the console away altogether.
  local was
  was="$(mktemp)"
  cp "$PROFILE" "$was"
  remove_autostart_block "$PROFILE"
  printf '\n%s\n' "$wanted" >> "$PROFILE"
  undo "put ${PROFILE} back as it was" \
       "mv -f $(printf '%q' "$was") $(printf '%q' "$PROFILE")"
  done_line "The console, brought up to this version"
}

usage() {
  cat <<'EOF'
Usage: install.sh [--update-admin]

With no arguments it sets a Raspberry Pi up from nothing and starts NeXTSTEP,
and skips every step it finds already done.

  --update-admin   Replace the admin tool with the newest one. Built from the
                   checkout this script sits in, or taken from the latest
                   release where there is no checkout. The console that starts
                   the emulator comes with it, where this machine has one and
                   it no longer says what this version writes. A machine that
                   has none is given none.
EOF
}

main() {
  case "${1:-}" in
    --update-admin)
      LOG="$(mktemp -t previously-install.XXXXXX)"
      banner
      check_host
      check_sudo
      update_admin
      refresh_autostart
      COMPLETED=true
      rm -f "$LOG"
      return
      ;;
    --help | -h)
      usage
      COMPLETED=true
      return
      ;;
    "") ;;
    *) abort "Unknown option: ${1}. Try --help." ;;
  esac

  LOG="$(mktemp -t previously-install.XXXXXX)"
  banner
  check_host
  check_sudo
  install_admin
  set_up_the_machine

  COMPLETED=true
  rm -f "$LOG"
  if [[ "$STARTED" == true ]]; then
    printf '\n  %sNeXTSTEP is starting on the Pi'"'"'s screen.%s\n' "$BOLD" "$RESET"
  else
    printf '\n  %sNeXTSTEP is running on the Pi'"'"'s screen.%s\n' "$BOLD" "$RESET"
  fi
  printf '  The admin tool is at %s%s%s\n' "$CYAN" "$(admin_address)" "$RESET"
  detail "The first browser to open it chooses the password."
  detail "NeXTSTEP account: me, no password."
  printf '\n'
}

main "$@"
