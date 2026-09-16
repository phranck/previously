/* --- nx-ask ------------------------------------------------------------- */

/**
 * The panel that asks before anything changes.
 *
 * NeXTSTEP put an attention panel in the middle of the screen over a dimmed
 * desk, with the icon of whatever is about to happen, a sentence saying what
 * it is, and the safe answer on the left. This is that, and it is a component
 * rather than markup in the page because more than one thing needs to ask:
 * stopping the emulator does, and changing the machine will.
 *
 * It answers with a promise rather than a callback, so the caller reads as one
 * sequence: ask, then act on the answer.
 */
class NxAsk extends HTMLElement {
  connectedCallback() {
    if (this.ready) return;
    this.ready = true;

    this.innerHTML = `
      <div class="panel">
        <div class="titlebar"><div class="title"></div></div>
        <div class="pane">
          <div class="panel-body">
            <i class="art icon"></i>
            <div class="words">
              <div class="lines"></div>
              <input class="entry" type="text" spellcheck="false" hidden>
            </div>
          </div>
          <div class="buttons" style="padding-right:0">
            <button data-answer="no"></button>
            <button data-answer="yes" class="default"></button>
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
   * @param {string} question.title - The panel's own title bar.
   * @param {string[]} question.text - One paragraph per entry.
   * @param {string} [question.icon] - Which picture, by the name showArt knows.
   * @param {string} question.confirm - The wording on the acting button. The
   *   kit holds no words of its own, in any language, so both buttons are
   *   named by whoever asks.
   * @param {string} question.cancel - The wording on the safe one.
   * @param {boolean} [question.field] - Show a line to type into.
   * @returns {Promise<boolean>} True where the acting button was pressed.
   */
  ask({ title, text, icon, confirm, cancel, field = false }) {
    this.querySelector(".title").textContent = title;
    this.querySelector(".lines").replaceChildren(
      ...text.map((line) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = line;
        return paragraph;
      }));
    if (icon) showArt(this.querySelector(".icon"), icon);
    this.querySelector('[data-answer="yes"]').textContent = confirm;
    this.querySelector('[data-answer="no"]').textContent = cancel;

    const entry = this.querySelector(".entry");
    entry.hidden = !field;
    entry.value = "";

    this.toggleAttribute("data-open", true);
    addEventListener("keydown", this.keys);
    (field ? entry : this.querySelector('[data-answer="no"]')).focus();

    return new Promise((settle) => { this.settle = settle; });
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

