---
title: "Stillroom: a document inbox that proposes, waits, and lets you undo"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

## What I Built

I built **Stillroom** for the small pile of documents that never gets filed because naming, sorting, and checking each one is tedious. Upload a PDF or text file and Stillroom extracts its text, proposes a useful name, a category, a date, tags, and a destination. Its proposal comes with an exact quote from the document. I can correct the proposal, approve it, and then move the file. I can undo that move later.

The point is to make the repetitive part fast while preserving the part I should decide myself. Nothing is moved automatically, and the source file is visible beside the proposed classification.

## Demo

**Add a deployed link or a short video demo here before publishing.** The official rules require one of those formats. The script in `docs/DEMO.md` walks through import, evidence review, correction, approval, archive, collision handling, search, export, and undo. Use the fictional files in `docs/samples/`.

In my local end-to-end run on October 22, the model classified the fictional community garden note under **Projects**, proposed the title **Community Garden Fall Planting Prep**, cited the exact sentence **“This is an internal project note, not a receipt.”**, and extracted **October 22, 2026** from the source. The API refused to file it before approval, then moved it after approval, and finally restored it to the inbox with Undo.

## Code

**Add the public repository link here before publishing.** Include a link to the README and setup instructions. The project is MIT licensed.

## How I Built It

The Vue 3 interface talks to a FastAPI server running on the same local origin. Python extracts PDF or UTF-8 text locally. The server sends up to 30,000 characters of extracted text to Groq's hosted `openai/gpt-oss-120b` model, requesting strict JSON output. It then checks that the evidence quote really occurs in the source. If a proposed date cannot be tied to an exact source phrase and parsed into the same date, Stillroom drops that date.

SQLite stores document metadata and an activity trail. Original files are staged in a local inbox. An explicit approval is required before a file move. Archive paths use a sanitized title and fixed category; filename collisions get numbered suffixes. Undo moves the original back and clears the prior approval. SHA-256 detects duplicate uploads.

I used tests to cover the workflow, including approval enforcement, corrections, undo, duplicate uploads, collisions, bad files, quote validation, cross-origin write protection, and safe CSV export. The frontend has an overview, inbox, archive, activity trail, bulk actions, search, and a side-by-side source review.

## Why Does Open Innovation Matter?

The classification step is built around an open-weight model, so the model choice is inspectable and replaceable. Groq is the current inference host because it offers the model through an API; the interface between extraction, structured proposal, validation, and review is explicit. This makes it possible to move inference to another host or local runtime later without redesigning the archive workflow.

That portability matters for a personal document tool. The current build **does send extracted text to Groq when Analyze is pressed**, so I do not claim it is offline or that document text never leaves the machine. The originals, SQLite database, and archive stay local. A future local inference adapter could remove the hosted text transfer while preserving the review flow.

Open AI is useful here because the messy part is semantic: a filename rarely says whether a file is a receipt, project note, or reading material. Rules alone would make users do the sorting again. The model proposes; deterministic code checks the quote and controls the file move.

## What I Learned

The biggest design choice was to keep model output away from filesystem operations. The AI suggests metadata, while the server validates evidence and the person approves the move. This makes wrong classifications correctable and file operations auditable. It also made the failure cases concrete: scanned PDFs need OCR, date extraction must be conservative, and a process crash between a filesystem move and database commit may require manual recovery.

<!-- Add a real usage observation or measured time saving here if you collect one. Do not invent a benchmark. -->
