# Catalogic hero study

- [Redesigned hero](https://av.github.io/catalogic-hero/)
- [Before/after comparison](https://av.github.io/catalogic-hero/catalogic-hero-compare.html)

These are the two original self-contained HTML pages, published without design or copy changes. `docs/index.html` is a byte-identical alias of the hero so the root URL opens it directly. The comparison links to the original named hero file in the same directory.

## Hosting

GitHub Pages serves `/docs` on `main`, with `.nojekyll`. All styles, JavaScript, fonts and images are embedded. There is no application server, custom domain, renewal, secret, expiring share link or scheduled job. No build dependency is needed to keep the published files available.

Public repositories can use GitHub Pages on GitHub Free. Standard GitHub-hosted Actions runners are also free for public repositories: [Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

## Verification

`python scripts/audit_source.py` checks both original file hashes, inline assets, absence of private-host references and common credential patterns.

The manually triggered verification workflow opens the actual public URLs in fresh, logged-out Chromium contexts on a standard GitHub-hosted Ubuntu runner. It verifies public server addresses, absence of tailnet interfaces/routes, all images and fonts, desktop/mobile rendering and comparison controls. Only requests to the public Pages host are allowed. Screenshots and the request/network report are saved to `proof/`.

The workflow is not scheduled. Hosting continues independently of future verification runs or artifact retention. Permanent screenshot and network evidence is committed in [proof/](proof/README.md).
