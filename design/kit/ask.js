/* --- nx-ask ------------------------------------------------------------- */

/**
 * The panel that asks before anything changes.
 *
 * NeXTSTEP's attention panel comes up in the upper part of the screen with the
 * icon of whatever is about to happen, a sentence saying what it is, and the
 * safe answer on the left. This is that, and it is a component rather than
 * markup in the page because more than one thing needs to ask: stopping the
 * emulator does, and changing the machine does.
 *
 * Its title bar is empty, which is what tells an attention panel from an
 * ordinary one. The panel is named inside itself, beside the icon, after
 * whatever brought it up, so the first line a caller gives is that name.
 *
 * It answers with a promise rather than a callback, so the caller reads as one
 * sequence: ask, then act on the answer.
 */
class NxAsk extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    /* Two blocks with a groove between them, which is how the chapter's own
       figure of an attention panel is built: the application icon and the
       panel's name above the line, and what the panel has to say below it. */
    this.innerHTML = `
      <div class="panel">
        <div class="titlebar"></div>
        <div class="naming">
          <i class="art icon raised"></i>
          <div class="name"></div>
        </div>
        <div class="pane">
          <div class="lines"></div>
          <input class="entry" type="text" spellcheck="false" hidden>
          <div class="buttons" style="padding-right:0">
            <button data-answer="no"></button>
            <button data-answer="yes"></button>
          </div>
        </div>
      </div>`;

    this.settle = null;
    for (const button of this.querySelectorAll("button")) {
      button.addEventListener("click", () => this.close(button.dataset.answer === "yes"));
    }

    /* Escape is the safe answer, which is the one a panel like this must have:
       somebody who wants out of a question should not have to aim at a button. */
    this.keys = (event) => {
      if (event.key === "Escape") this.close(false);
      const entry = this.querySelector(".entry");
      if (event.key === "Enter" && !entry.hidden) this.close(true);
    };
  }

  /**
   * Puts the question and waits for an answer.
   * @param {object} question
   * @param {string} question.name - What the panel calls itself, after the
   *   command that brought it up. It stands beside the icon above the groove,
   *   because an attention panel's title bar is empty.
   * @param {(string|Node)[]} question.text - One paragraph per entry, below
   *   the groove.
   * @param {string} [question.icon] - Which picture, by the name showArt knows.
   * @param {string} question.confirm - The wording on the acting button. The
   *   kit holds no words of its own, in any language, so both buttons are
   *   named by whoever asks.
   * @param {string} question.cancel - The wording on the safe one.
   * @param {boolean} [question.field] - Show a line to type into.
   * @param {boolean} [question.secret] - Draw that line as a password field, so
   *   what is typed into it is not read over the typist's shoulder.
   * @returns {Promise<boolean>} True where the acting button was pressed.
   */
  ask({ name, text, icon, confirm, cancel, field = false, secret = false }) {
    this.querySelector(".name").textContent = name;
    this.querySelector(".lines").replaceChildren(
      ...text.map((line) => {
        /* A line is a sentence, or an element where the caller had to build
           it: a copyright carrying a link is still one line, and the kit has
           no business knowing which word in it leads where. */
        if (line instanceof Node) return line;
        const paragraph = document.createElement("p");
        paragraph.textContent = line;
        return paragraph;
      }));
    if (icon) showArt(this.querySelector(".icon"), icon);

    const acting = this.querySelector('[data-answer="yes"]');
    acting.textContent = confirm;

    /* A panel that only says something has one button, and the safe answer is
       the same as the acting one. Left standing and empty it would be a second
       button offering nothing, which is worse than none. */
    const safe = this.querySelector('[data-answer="no"]');
    safe.hidden = !cancel;
    safe.textContent = cancel ?? "";

    const entry = this.querySelector(".entry");
    entry.hidden = !field;
    entry.type = secret ? "password" : "text";
    entry.value = "";

    /* The Return-key symbol says Return presses this button, so it goes on
       only where Return does. A panel carrying a line to type into commits it
       that way. One that only asks is answered by clicking, which is what the
       chapter asks for wherever the answer costs something. */
    acting.classList.toggle("returns", field);

    this.toggleAttribute("data-open", true);
    addEventListener("keydown", this.keys);
    (field ? entry : (cancel ? safe : acting)).focus();

    return new Promise((settle) => { this.settle = settle; });
  }

  /**
   * Says something and waits for it to be read.
   * @param {object} panel
   * @param {string} panel.name - What the panel calls itself.
   * @param {(string|Node)[]} panel.text - One paragraph per entry, as a
   *   sentence or as an element where the caller had to build the line
   *   itself.
   * @param {string} [panel.icon] - Which picture, by the name showArt knows.
   * @param {string} panel.confirm - The wording on the one button. The kit
   *   holds no words of its own, in any language.
   * @returns {Promise<boolean>} Always true, so the caller can wait for it to
   *   be dismissed without reading the answer.
   *
   * The whole of it is ask with no safe button, because a panel that only says
   * something has one answer and offering a second would be a button that does
   * what the first does.
   */
  tell({ name, text, icon, confirm }) {
    return this.ask({ name, text, icon, confirm, cancel: null });
  }

  /**
   * Puts a question that needs something typed.
   * @param {object} question - As ask, and the field is shown.
   * @returns {Promise<string|null>} What was typed, or null where the panel was
   *   dismissed. Empty counts as dismissed, because a blank answer is not one.
   */
  async askFor(question) {
    const answered = await this.ask({ ...question, field: true });
    if (!answered) return null;
    const typed = this.querySelector(".entry").value.trim();
    return typed || null;
  }

  /**
   * Closes the panel and settles whoever was waiting.
   * @param {boolean} answer
   */
  close(answer) {
    this.toggleAttribute("data-open", false);
    removeEventListener("keydown", this.keys);
    this.settle?.(answer);
    this.settle = null;
  }
}

