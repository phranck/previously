/* What checks the interface, which is the half of this repository flake8
 * cannot see.
 *
 * On the rules that catch mistakes rather than the ones that argue about
 * style: a name used and never declared, a name declared and never used, a
 * case that falls through. What the code looks like is settled by the code
 * around it and by review.
 *
 * `no-undef` is the one that matters most since the interface became modules.
 * A name that used to be there because everything shared one scope is now a
 * name that has to be imported, and nothing else says when one was missed:
 * esbuild bundles a free variable without a word, and the page fails at the
 * moment somebody presses the thing that needs it.
 */

export default [
  {
    files: ["interface/**/*.js"],
    ignores: ["interface/nextstep.js", "interface/vendor/**"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        // What a browser brings.
        document: "readonly",
        window: "readonly",
        navigator: "readonly",
        location: "readonly",
        localStorage: "readonly",
        fetch: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        requestAnimationFrame: "readonly",
        addEventListener: "readonly",
        removeEventListener: "readonly",
        matchMedia: "readonly",
        customElements: "readonly",
        getComputedStyle: "readonly",
        innerWidth: "readonly",
        innerHeight: "readonly",
        devicePixelRatio: "readonly",
        CustomEvent: "readonly",
        Event: "readonly",
        Node: "readonly",
        HTMLElement: "readonly",
        Image: "readonly",
        Intl: "readonly",
        URL: "readonly",
        WebSocket: "readonly",
        AbortController: "readonly",
        ResizeObserver: "readonly",
        MutationObserver: "readonly",
        performance: "readonly",
        console: "readonly",
        crypto: "readonly",
        URLSearchParams: "readonly",
        AbortSignal: "readonly",
        TextEncoder: "readonly",
        TextDecoder: "readonly",
        // The one library this interface takes, which arrives as a global
        // because that is how its own file is written.
        Terminal: "readonly",
        FitAddon: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      // An imported name cannot be assigned to, so a module that keeps a
      // value has to be the one that changes it. This is what says so at the
      // moment the import is written rather than when the page is built.
      "no-import-assign": "error",
      "no-unused-vars": ["error", { args: "none" }],
      "no-fallthrough": "error",
      "no-dupe-keys": "error",
      "no-dupe-args": "error",
      "no-const-assign": "error",
      "no-self-compare": "error",
      "no-unreachable": "error",
      "require-atomic-updates": "off",
    },
  },
];
