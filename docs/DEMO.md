# Demo walkthrough

Use only the fictional files in `docs/samples/`. Start the app as described in the README and confirm the lower-left connection label says **AI ready**. This requires a real Groq API key.

1. Show the empty overview and import all three sample files.
2. In the inbox, select the garden note and press **Analyze with open-weight AI**. Show the source text, the exact evidence quote, category, title, and suggested path. Explain that the model is proposing, not moving.
3. Edit the title or category. Show that saving a correction requires fresh approval.
4. Approve and file it. Show the archive path and activity event. Download the original.
5. Analyze and file a second sample. Search the archive and export the CSV manifest.
6. Undo one move and show that it returns to the inbox, with its previous approval cleared.

If a model response fails evidence verification or a rate limit occurs, show the error and retry later; do not present a mocked response as a live model result. For a shorter recording, skip bulk actions but show them in the UI.
