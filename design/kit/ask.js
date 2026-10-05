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
          <div class="heading">
            <div class="name"></div>
            <p class="subtitle" hidden></p>
          </div>
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
    this.returns = true;
    for (const button of this.querySelectorAll("button")) {
      button.addEventListener("click", () => this.close(button.dataset.answer === "yes"));
    }

    /* Escape is the safe answer, which is the one a panel like this must have:
       somebody who wants out of a question should not have to aim at a button.

       Return presses the acting button, and only that one: "No button except
       for the default button should be operable by the Return key." Where the
       panel said its default is dangerous, Return presses nothing at all and
       the answer has to be clicked. */
    this.keys = (event) => {
      if (event.key === "Escape") this.close(false);
      if (event.key === "Enter" && this.returns) this.close(true);
    };

    /* The mark says Return will press the button, so it has to stop saying so
       the moment Return would not. In a browser that is the document losing
       focus, which is this desk's version of the panel not being the key
       window. */
    this.focusChanged = () => this.markTheReturnKey();
  }

  /**
   * Puts the question and waits for an answer.
   * @param {object} question
   * @param {string} question.name - What the panel calls itself, after the
   *   command that brought it up. It stands beside the icon above the groove,
   *   because an attention panel's title bar is empty.
   * @param {string} [question.subtitle] - A line under the name, above the
   *   groove, in the panel's ordinary type. Left out, the name stands alone.
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
   * @param {boolean} [question.dangerous] - Whether the acting button costs
   *   something that does not come back. Such a button takes no Return and
   *   carries no Return-key symbol, so it has to be clicked. The chapter puts
   *   it the other way round, in "The default button in an attention panel
   *   should normally be operable by pressing the Return key... However, if
   *   the button has dangerous side effects, it's acceptable to require that
   *   the user press the button", so normal here is that Return presses.
   * @returns {Promise<boolean>} True where the acting button was pressed.
   */
  ask({ name, subtitle, text, icon, confirm, cancel, field = false,
        secret = false, dangerous = false }) {
    this.querySelector(".name").textContent = name;
    const under = this.querySelector(".subtitle");
    under.hidden = !subtitle;
    under.textContent = subtitle ?? "";
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

    this.returns = !dangerous;
    this.markTheReturnKey();

    this.toggleAttribute("data-open", true);
    addEventListener("keydown", this.keys);
    addEventListener("focus", this.focusChanged);
    addEventListener("blur", this.focusChanged);
    (field ? entry : (cancel ? safe : acting)).focus();

    return new Promise((settle) => { this.settle = settle; });
  }

  /** Puts the Return-key symbol on the acting button, or takes it off. */
  markTheReturnKey() {
    this.querySelector('[data-answer="yes"]')
      .classList.toggle("returns", this.returns && document.hasFocus());
  }

  /**
   * Says something and waits for it to be read.
   * @param {object} panel
   * @param {string} panel.name - What the panel calls itself.
   * @param {string} [panel.subtitle] - A line under the name, as ask takes it.
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
  tell({ name, subtitle, text, icon, confirm }) {
    return this.ask({ name, subtitle, text, icon, confirm, cancel: null });
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
    removeEventListener("focus", this.focusChanged);
    removeEventListener("blur", this.focusChanged);
    this.settle?.(answer);
    this.settle = null;
  }
}

