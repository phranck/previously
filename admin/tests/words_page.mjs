/* Just enough of a page to run `words.js` outside a browser.
 *
 * The one thing of a browser that module and the catalogs touch while they
 * load is localStorage, where the chosen language is kept. With nothing chosen
 * they speak English, which is the catalog the tests read.
 *
 * An answer of the service arrives on stdin as JSON, and the sentence `say`
 * makes of it is written to stdout. Where the JSON names a `call` instead, the
 * export of that name is called with the values in `with`, and what it returns
 * is written out.
 */

globalThis.localStorage = { getItem: () => null, setItem() {} };

const here = new URL("../interface/app/words.js", import.meta.url);
const words = await import(here.href);

const sent = [];
for await (const chunk of process.stdin) sent.push(chunk);
const given = JSON.parse(Buffer.concat(sent).toString("utf-8"));
console.log(given.call ? words[given.call](...given.with) : words.say(given));
