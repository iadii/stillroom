---
title: "Stillroom: a document inbox that does the sorting and waits for you"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

## What I Built

My downloads folder does not need another clever filename. It needs someone to read the file, decide what it is, and put it somewhere I can find it later. I kept putting off those little decisions, so I built **Stillroom**.

Stillroom is a local document inbox. I can drop in a PDF, TXT, Markdown, or CSV file. An open-weight model proposes a category, useful title, document date, summary, tags, and archive path. It must also copy a quote from the file to explain the choice. I see the original text next to the proposal, can correct it, and must approve the move. If I change my mind, Undo brings the original back.

The deliberate pause is the point: the repetitive reading and naming is automated, while the consequential file move stays under my control. It also supports batch analysis and filing once proposals have been approved.

## Demo

**[Watch or download the 25-second real browser walkthrough](https://raw.githubusercontent.com/iadii/stillroom/main/docs/demo/stillroom-demo.webm).** It shows upload, a live Groq classification, the source quote, a title correction, approval, archive, activity history, and Undo. The document is a fictional community garden note, and the recording ran against an isolated temporary database.

[Full proposal screenshot](https://raw.githubusercontent.com/iadii/stillroom/main/docs/demo/proposal.png) · [Activity trail screenshot](https://raw.githubusercontent.com/iadii/stillroom/main/docs/demo/activity.png)

In the recorded run, the model put the note under **Projects**, proposed **Community Garden Fall Planting Prep**, and cited the exact line **“This is an internal project note, not a receipt.”** It extracted the date from **“October 22, 2026.”** I changed the title to **Autumn garden workday**, approved it, filed it, and undid the move. The app recorded all six events. The proposal was genuine model output; no canned response was substituted.

## Code

**[Stillroom source and setup instructions](https://github.com/iadii/stillroom)** · MIT licensed. The project was started during this challenge window, with the first local commit on October 22, 2026.

## How I Built It

Vue 3 provides the inbox, proposal review, archive search, bulk actions, and activity trail. FastAPI extracts text locally and sends up to 30,000 characters to Groq's hosted `openai/gpt-oss-120b` model using strict JSON schema output. Python checks that the model's evidence quote appears in the extracted text. A proposed date is dropped unless its source phrase is present and parses to the same calendar date.

SQLite holds metadata and the event log; originals are staged locally. The model never chooses a filesystem path directly. The server builds one from a fixed category and sanitized title. Identical uploads are rejected by SHA-256, collisions receive numbered names, and the archive move requires explicit human approval. Editing clears an earlier approval; Undo restores the file to the inbox and clears approval again.

That separation helped me test the awkward cases: a model with no valid quote, an ambiguous date, a duplicate upload, two files with the same proposed name, an attempted move before approval, and a reversed move. The backend has automated workflow tests, and GitHub Actions is configured to run those plus frontend formatting and production build checks.

## Why Does Open Innovation Matter?

The model is [GPT-OSS 120B, an open-weight model](https://openai.com/index/introducing-gpt-oss/). The weights can be inspected and run through other infrastructure; I chose Groq for hosted inference during this build. That gives the document workflow an exit path from this particular provider. The semantic step—deciding whether a note is a receipt, project, or reading material—is where the model matters. Rules alone would push the sorting work back onto the user.

This version **is not offline**. Pressing Analyze sends extracted text to Groq. The originals, SQLite database, and archive remain local. A local inference adapter could later remove that network transfer, but I do not claim it exists today. Open weights matter here because model hosting is a choice, while evidence checks and human approval stay part of the application regardless of host.

## The Lazy Payoff

Stillroom turns several blank decisions into one reviewable proposal: what the file is, what to call it, which date matters, what tags fit, and where it should live. I have not measured a manual-versus-Stillroom time saving, so I won't invent one. The recorded workflow demonstrates the narrower claim: one real document goes from an unnamed pile to a verifiable, reversible archive decision without manual filename or folder construction.

There are limits. Scanned PDFs need OCR first, text analysis is capped, and this local single-user build should not be exposed as a public service without authentication. I would rather show those edges than imply the model is always right.
