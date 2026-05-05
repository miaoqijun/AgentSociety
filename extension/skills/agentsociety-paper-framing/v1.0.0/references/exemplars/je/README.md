# JE PDF Markdown + Assets

This package contains separated markdown text and cropped figure assets for the five JE PDFs.

## Scope

For each paper, the markdown keeps the main body content useful for downstream model reading:

- Abstract
- Introduction / background / framework
- Results / analysis
- Discussion / implications

The following were intentionally omitted where present:

- Methods / Materials and Methods
- References
- Acknowledgements, author contributions, competing interests
- Reporting summaries, data/code availability sections
- Extended Data, appendices and supplementary material

For Nature/Nature Human Behaviour articles, only main-text figures were retained. Extended Data figures were not retained.  
For the preprint-style word-embedding paper, the main figures placed at the back of the PDF were retained; appendices and appendix figures were omitted.

## Structure

- `JE_1.md` ... `JE_5.md`: cleaned markdown text with relative links to figures.
- `assets/JE_x/figure_XX.png`: cropped main figure assets.
- `manifest.json`: machine-readable inventory.
- `asset_contact_sheet.jpg`: quick preview of all figure assets.

Text was extracted from the embedded PDF text layer. Figure assets were cropped from rendered PDF pages.
