/* The covers of software entries, cut the way the mockup of #752 settled:
   the front of a spread, and inside it the frame the cover is printed in.

   The page cuts them rather than the Pi, because a browser decodes a JPEG and
   Python's standard library does not. The Pi hands out archive.org's thumbnail
   as it is, and each cover is cut once per page and kept for every place that
   shows it. */

/** How much wider than tall a picture is at least to be a spread: the back
 *  on the left and the front on the right. A single booklet is about square
 *  and an opened one about twice as wide. */
const SPREAD = 1.6;

/** The lightness under which a pixel counts as dark, out of 255. */
const DARK = 70;

/** The share of dark pixels at which a line counts as an edge of the frame. */
const LINE = 0.8;

/** What each cover became once cut, by its address, or null where it could
 *  not be cut. @type {Map<string, string | null>} */
const ready = new Map();

/** The covers being cut. @type {Set<string>} */
const cutting = new Set();

/**
 * Where to cut a cover.
 * @param {Uint8Array} lightness - Every pixel's lightness from 0 to 255, row
 *   by row.
 * @param {number} width
 * @param {number} height
 * @returns {{left: number, top: number, width: number, height: number}} The
 *   part to keep.
 *
 * A spread keeps its right half. Then each side is searched from the edge
 * inwards, within the outer quarter, for the first line whose pixels are at
 * least LINE dark, and whatever lies outside it goes. A side with no such line
 * stays where it is, so a cover without a frame is kept as it is, and a dark
 * line further in is part of the picture rather than its frame.
 */
function frameIn(lightness, width, height) {
  const from = width >= height * SPREAD ? Math.floor(width / 2) : 0;
  const across = width - from;
  const dark = (/** @type {number} */ x, /** @type {number} */ y) => lightness[y * width + x] < DARK;
  const column = (/** @type {number} */ x) => {
    let count = 0;
    for (let y = 0; y < height; y += 1) count += dark(x, y) ? 1 : 0;
    return count / height >= LINE;
  };
  const row = (/** @type {number} */ y) => {
    let count = 0;
    for (let x = from; x < width; x += 1) count += dark(x, y) ? 1 : 0;
    return count / across >= LINE;
  };
  const first = (/** @type {number[]} */ steps, /** @type {(at: number) => boolean} */ isEdge,
                 /** @type {number} */ otherwise) => steps.find(isEdge) ?? otherwise;
  const reach = (/** @type {number} */ size) => Math.floor(size / 4);
  const run = (/** @type {number} */ start, /** @type {number} */ step, /** @type {number} */ count) =>
    Array.from({ length: count + 1 }, (_, at) => start + step * at);

  const left = first(run(from, 1, reach(across)), column, from);
  const right = first(run(width - 1, -1, reach(across)), column, width - 1);
  const top = first(run(0, 1, reach(height)), row, 0);
  const bottom = first(run(height - 1, -1, reach(height)), row, height - 1);
  return { left, top, width: right - left + 1, height: bottom - top + 1 };
}

/**
 * Cuts one cover.
 * @param {string} address - Where the picture is.
 * @returns {Promise<string | null>} The cut cover as a data address, or null
 *   where the picture could not be read.
 */
async function cut(address) {
  try {
    const image = new Image();
    image.src = address;
    await image.decode();
    const width = image.naturalWidth;
    const height = image.naturalHeight;
    const whole = document.createElement("canvas");
    whole.width = width;
    whole.height = height;
    const context = whole.getContext("2d");
    if (!context || !width || !height) return null;
    context.drawImage(image, 0, 0);

    const pixels = context.getImageData(0, 0, width, height).data;
    const lightness = new Uint8Array(width * height);
    for (let at = 0; at < lightness.length; at += 1) {
      lightness[at] = 0.299 * pixels[at * 4] + 0.587 * pixels[at * 4 + 1] + 0.114 * pixels[at * 4 + 2];
    }
    const box = frameIn(lightness, width, height);

    const kept = document.createElement("canvas");
    kept.width = box.width;
    kept.height = box.height;
    kept.getContext("2d")?.drawImage(whole, box.left, box.top, box.width, box.height,
                                     0, 0, box.width, box.height);
    return kept.toDataURL("image/png");
  } catch {
    return null;
  }
}

/**
 * A cover as it is shown, where it has been cut already.
 * @param {string} address - Where the picture is.
 * @param {() => void} redraw - What draws the place again once the cover is
 *   cut, which happens once per address and page.
 * @returns {string | null} The cut cover, or null while it is being cut or
 *   where it could not be.
 */
function coverNow(address, redraw) {
  if (ready.has(address)) return ready.get(address) ?? null;
  if (!cutting.has(address)) {
    cutting.add(address);
    cut(address).then((done) => {
      ready.set(address, done);
      redraw();
    });
  }
  return null;
}

/**
 * Puts a cover on an element, or an icon where there is no cover yet.
 * @param {HTMLElement} element - What shows it.
 * @param {string | null | undefined} address - Where the cover is, or nothing.
 * @param {string} icon - The icon shown without one, by the name the kit
 *   knows it by.
 * @param {() => void} redraw - What draws the place again once the cover is
 *   cut.
 */
function wearCover(element, address, icon, redraw) {
  const picture = address ? coverNow(address, redraw) : null;
  element.style.backgroundImage = picture ? `url(${JSON.stringify(picture)})` : `var(--${icon})`;
  element.classList.toggle("picture", Boolean(picture));
}

export { coverNow, frameIn, wearCover };
