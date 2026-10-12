/* What came of asking the service to do something, read off its answer.
 *
 * `tell` hands over whatever body a POST answered with: what the route
 * answers, a refusal carrying `error` and nothing else, or the page's own
 * answer where nobody gave the password. Which of the three it was decides
 * what the page may do with it, so that is decided here, once.
 */

/**
 * Whether an answer carries the machine's status, as every answer to a change
 * of the machine does beside what came of it.
 * @param {any} answer - What `tell` handed over, or null on no contact.
 * @returns {boolean}
 *
 * A refusal carries none, and drawn as one it reads as a machine that has
 * stopped and whose file cannot be read.
 */
function isAStatus(answer) {
  return typeof answer?.running === "boolean";
}

/**
 * Whether the service took the request.
 * @param {any} answer - What `tell` handed over, or null on no contact.
 * @returns {boolean} True only where the answer says so. A refusal carries no
 *   `ok` at all, and the page's own answer for a dismissed password panel
 *   carries false.
 */
function wasTaken(answer) {
  return answer?.ok === true;
}

export {
  isAStatus,
  wasTaken,
};
