# Previewing the guide locally

The guide is published by GitHub Pages from the committed `guide/` folder (see `.github/workflows/pages.yml`). To preview it with the same gems GitHub Pages uses (`github-pages`, Jekyll 3.10), run these from the repository root. Gems install into `tools/pages/vendor/bundle`, which is gitignored.

```bash
BUNDLE_GEMFILE=tools/pages/Gemfile bundle config set --local path vendor/bundle
```

```bash
BUNDLE_GEMFILE=tools/pages/Gemfile bundle install
```

```bash
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 BUNDLE_GEMFILE=tools/pages/Gemfile bundle exec jekyll serve --source guide --destination _site --port 4000
```

Then open http://localhost:4000/ca-retention-guide/ (the site path matches the published URL). The UTF-8 locale is required: without it, the theme's Sass compiler fails on non-ASCII characters.

Re-run `uv run python -m src.render` after changing data or templates; the running server picks up the new files.
