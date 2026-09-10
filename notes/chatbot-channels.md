# Chatbot channel tests (2026-09-10)

## DeepSeek (chat.deepseek.com) — LOGIN REQUIRED
- Landing page forces sign-in (email/phone + password, Google/Apple). No guest chat box.
- Ruled OUT for no-login copy-paste research. Revisit only if user authorizes login.

## Kimi (Moonshot) — pending scout result.

## Kimi (kimi.com) — LOGIN REQUIRED
- Homepage shows chat box, but submitting triggers login modal: WeChat QR or phone (+86) only. No guest mode.
- Ruled OUT for no-login copy-paste research.

## duck.ai (DuckDuckGo AI Chat) — scout dispatched, pending.

## duck.ai (DuckDuckGo AI Chat) — WORKS ANONYMOUSLY ✅
- No login, no captcha, no usage-limit screen. Model pre-set "GPT-5.6 Luna", used web search ("Searching the web" indicator), ~60s for a full deep answer.
- Saved verbatim OFI answer → batches/SB1/duckai-answers.md. Quality high; model self-flagged estimates vs documented facts.
- Candidate for SB1–SB5 batch questions (3 per batch from question bank).

## duck.ai (DuckDuckGo AI Chat) — WORKS ANONYMOUSLY (no login)
- Verified 2026-09-10. GPT-5.6 Luna, web-search assisted, self-flags estimates vs documented facts.
- Treat batches/<BATCH>/duckai-answers.md EXACTLY like grok/cursor-answers.md: fold in when present, never block, note "pending" in source logs when absent.
- SB1: batches/SB1/duckai-answers.md contains verbatim OFI deep-dive → folded into S001.
