# 🛡️ PrivateDesk

> **The 100% Private, On-Device AI Terminal Assistant for Any Document.**  
> Turn your PDFs and PowerPoint presentations into an instant, searchable knowledge base right in your terminal.  
> Zero cloud calls. No corporate data leaks. Zero API costs. Built for macOS with local Qwen 2.5.

---

## ⚡ What is PrivateDesk?

Whether you are an **IT support technician**, a **software engineer debugging production**, a **student cramming 20 lecture slide decks**, or a **lawyer reviewing compliance policies**, digging through massive documents is painful.

Uploading confidential internal files to cloud AI tools like ChatGPT or Gemini risks breaching corporate policies and data regulations (FIPPA, PIPEDA, HIPAA, GDPR).

**PrivateDesk gives you a personal, Claude Code-style AI co-pilot that runs 100% locally on your Mac:**
* **100% Offline & Air-Gapped:** Powered by [Ollama](https://ollama.com) running **Qwen 2.5** directly on Apple Silicon Metal GPU. Zero bytes leave your machine.
* **Persistent Knowledge Vault:** Drag and drop your PDFs or PowerPoint decks (`.pptx`) once. Documents remain cached locally across all terminal tabs until you clear them.
* **Mac Clipboard Superpower:** Pipe copied Jira tickets, customer emails, or terminal error logs directly into the bot using `pbpaste | privatedesk`.
* **Zero Hallucinations & Exact Citations:** Answers are strictly grounded in your uploaded documents, complete with slide- and page-level citations.

---

## 🚀 1-Line Installation

### macOS (Terminal)
```bash
curl -fsSL https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/install.sh | bash
```

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/prabhsharan1/PrivateDesk/main/install.ps1 | iex
```

*(Or clone the repository manually):*
```bash
git clone https://github.com/prabhsharan1/PrivateDesk.git
cd PrivateDesk
# macOS: ./install.sh  |  Windows: .\install.ps1
```

### What the installer does:
1. Verifies Python 3.10+ and sets up an isolated environment at `~/.privatedesk/venv`.
2. Installs lightweight document parsers (`pypdf`, `python-pptx`, `requests`).
3. Verifies [Ollama](https://ollama.com) and pulls the compact `qwen2.5:1.5b` model (~986 MB).
4. Creates the global `privatedesk` command and configures your system PATH.

---

## 💡 Real-World Use Cases & Examples

PrivateDesk adapts to any role and any document set:

### 1. 🖥️ IT Helpdesks & Service Desks (Onboarding & Triage)
> **Documents to ingest:** `VPN_Setup_Guide.pdf`, `Hardware_Loan_Policy.pptx`, `Account_Security_SOP.pdf`

```text
$ privatedesk "What is the policy if an employee loses access to their 2FA device?"

Thinking...
──────────────────────────────────────────────────────────────
2FA Recovery Procedure:
1. Verify the employee's identity via government ID or employee badge number.
2. Issue a temporary 24-hour bypass code through the Identity Admin Console.
3. Require the employee to enroll their replacement hardware token or phone before next shift.

📚 Source Citations:
  • Account_Security_SOP.pptx (Slide 8)
  • Hardware_Loan_Policy.pptx (Slide 4)
──────────────────────────────────────────────────────────────
```

---

### 2. 🛠️ Software Engineering & DevOps (Incident Response & Runbooks)
> **Documents to ingest:** `Production_Architecture_ADR.pdf`, `Kubernetes_Runbook.pdf`, `Disaster_Recovery_SOP.pdf`

**Pipe live server error logs directly into your runbooks:**
```bash
kubectl logs pod/auth-service-7f89b | privatedesk "Match this log against our Disaster Recovery runbook and suggest the fix"
```

```text
Thinking...
──────────────────────────────────────────────────────────────
Identified Error: Database connection pool exhaustion (Error 1040).

Resolution steps from Kubernetes_Runbook.pdf:
1. Run `kubectl scale deployment auth-service --replicas=2` to relieve immediate connection contention.
2. Check PostgreSQL max_connections in vault secret `prod-db-config`.
3. Restart PgBouncer pod: `kubectl rollout restart deployment pgbouncer`.

📚 Source Citations:
  • Kubernetes_Runbook.pdf (Page 24)
  • Production_Architecture_ADR.pdf (Page 7)
──────────────────────────────────────────────────────────────
```

---

### 3. 🎓 University Students & Researchers (Exam Cramming & Research Papers)
> **Documents to ingest:** `CS101_Lecture_Slides_1-20.pptx`, `Course_Syllabus.pdf`, `Research_Paper.pdf`

```text
$ privatedesk

> What is the penalty for late assignment submission in the syllabus?
──────────────────────────────────────────────────────────────
Late Submission Policy:
• Submissions up to 24 hours late receive a flat 15% deduction.
• Submissions between 24 and 48 hours late receive a 30% deduction.
• Submissions beyond 48 hours receive a score of 0 unless accompanied by an approved medical note.

📚 Source Citations:
  • Course_Syllabus.pdf (Page 3)
──────────────────────────────────────────────────────────────

> Explain how virtual memory paging handles page faults in week 4 slides
...
```

---

### 4. 💼 Legal, HR & Corporate Operations (Employee Handbooks & Policies)
> **Documents to ingest:** `Employee_Handbook_2026.pdf`, `Travel_Expense_Policy.pdf`, `Parental_Leave.pdf`

**Copy an employee question (`Cmd + C`), then pipe clipboard:**
```bash
pbpaste | privatedesk "Draft a polite response adhering to Company X travel guidelines"
```

```text
Thinking...
──────────────────────────────────────────────────────────────
Draft Response:
"Hi John, according to Section 4.2 of our Company Travel & Expense Policy, domestic meal reimbursements are capped at $75 per day excluding alcohol. Since your receipt includes $32 in alcoholic beverages, only the remaining $58 eligible meal expense can be approved."

📚 Source Citations:
  • Travel_Expense_Policy.pdf (Page 9)
──────────────────────────────────────────────────────────────
```

---

### 5. 🏥 Healthcare, Clinical & Regulated Fields (100% Air-Gapped Compliance)
> **Documents to ingest:** `ICU_Clinical_Protocols.pdf`, `Shift_Handover_Guidelines.pdf`, `Drug_Dosage_Matrix.pdf`

In regulated environments where patient data or hospital procedures **cannot touch the internet** due to HIPAA, PIPEDA, or hospital IT policies, PrivateDesk runs entirely on the physical machine.

```text
$ privatedesk "What is the standard protocol for suspected heparin-induced thrombocytopenia?"

Thinking...
──────────────────────────────────────────────────────────────
Protocol for Suspected HIT:
1. Immediately discontinue all forms of heparin (including flushes).
2. Obtain a 4Ts score to determine pre-test probability.
3. If 4Ts score is >= 4, initiate alternative non-heparin anticoagulation (e.g., Argatroban or Fondaparinux).
4. Send blood sample for anti-PF4/heparin enzyme immunoassay (EIA).

📚 Source Citations:
  • ICU_Clinical_Protocols.pdf (Page 42)
──────────────────────────────────────────────────────────────
```

---

## 💻 How to Use PrivateDesk

### Mode 1: Interactive REPL (Claude Code Style)
Launch the interactive assistant from any terminal window:

```bash
privatedesk
```

```text
╭──────────────────────────────────────────────────────────────╮
│  PrivateDesk CLI v2.0.0 — 100% Offline AI Assistant (Qwen 2.5)   │
│  Commands: /upload <file>, /docs, /clear, /help, /exit           │
╰──────────────────────────────────────────────────────────────╯
[Vault: 2 document(s) loaded • 32 indexed chunks]

> /upload [drag & drop any PDF or PPTX from Finder]
✔ Successfully indexed: Team_Playbook.pdf (18 pages, 22 chunks)

> How do we provision new developer accounts?
...
```

---

### Mode 2: One-Shot Terminal Query
Ask quick questions directly without entering interactive mode:

```bash
privatedesk "What are the core SLAs for Priority 1 issues?"
```

---

### Mode 3: Clipboard Piping (`pbpaste` / `Get-Clipboard`)
Copy any error message, ticket, or customer email on your screen (`Cmd + C` on Mac, `Ctrl + C` on Windows), then pipe it straight into PrivateDesk:

**macOS (Terminal):**
```bash
pbpaste | privatedesk
pbpaste | privatedesk "Summarize this email and draft a 3-bullet resolution"
```

**Windows (PowerShell):**
```powershell
Get-Clipboard | privatedesk
Get-Clipboard | privatedesk "Summarize this email and draft a 3-bullet resolution"
```

---

### Mode 4: Batch Upload Files from Command Line
Index all your team documents in one go:

```bash
privatedesk --upload ~/Documents/SOPs/*.pdf ~/Desktop/Slides/*.pptx
```

---

## 📁 Finder Drag-and-Drop File Upload

In macOS Terminal, you can **drag and drop any PDF or PPTX file directly from Finder into the terminal window**. PrivateDesk automatically unescapes backslashes, spaces, and brackets:

```text
> /upload [drag & drop 'Company_Onboarding.pptx' from Finder]
✔ Successfully indexed: Company_Onboarding.pptx (16 slides, 16 chunks)
```

---

## 📖 Command & Options Reference

### Interactive REPL Commands
| Command | Description |
| :--- | :--- |
| **`/upload <path>`** or **`/add`** | Index one or more `.pdf` or `.pptx` documents (supports Finder drag-and-drop). |
| **`/docs`** or **`/list`** | View all currently loaded documents, slide/page counts, and total chunks. |
| **`/clear`** | Purge all loaded documents from memory and persistent cache (`~/.privatedesk/store.json`). |
| **`/help`** | Display command reference and usage shortcuts. |
| **`/exit`** or **`exit`** | Exit PrivateDesk (or press `Ctrl + D`). |

### Command-Line Flags
| Flag | Description |
| :--- | :--- |
| **`privatedesk "<query>"`** | One-shot query mode. Prints response to stdout and exits. |
| **`privatedesk --upload <files...>`** | Batch upload and index documents from command line. |
| **`privatedesk --docs`** | Display list of indexed documents in the vault. |
| **`privatedesk --clear`** | Wipe all indexed documents from cache. |
| **`privatedesk --help`** | Display help and flag reference. |
| **`privatedesk --version`** | Display current CLI version. |

---

## 🔒 Security & Privacy Guarantees

* **Zero Network Calls:** Runs entirely on `localhost`. Disconnect your Mac from Wi-Fi or Ethernet—PrivateDesk continues to work identically.
* **No Telemetry or Logging:** Prompts and documents are never sent to external servers or logged in the cloud.
* **Static Model Weights:** The local Qwen 2.5 model is strictly read-only. It cannot and does not retain, memorize, or train on your private documents.
* **Persistent Cache Isolation:** Stored locally in `~/.privatedesk/store.json` with user-only permissions.
* **Instant Data Wipe:** Run `privatedesk --clear` at any time to purge all indexed chunks between shifts.

---

## 💻 Hardware Compatibility (Mac)

| Mac Model | Processor | Memory | Model | Speed |
| :--- | :--- | :--- | :--- | :--- |
| **Apple Silicon (M1/M2/M3/M4)** | arm64 (Metal GPU) | **8 GB** | **Qwen 2.5 1.5B** | ⚡ ~80–100 tok/s |
| **Apple Silicon (Pro/Max)** | arm64 (Metal GPU) | **16 GB+** | **Qwen 2.5 3B** | 🚀 ~60–80 tok/s |
| **Intel Mac (2017–2020)** | x86_64 (CPU) | **8 GB – 16 GB** | **Qwen 2.5 0.5B / 1.5B** | ⏱️ ~15–25 tok/s |

---

## 🧪 Automated Test Suite

To run the automated verification suite (parsing, unescaping, persistence, retrieval, and inference):

```bash
~/.privatedesk/venv/bin/python test_suite.py
```

---

## 📄 License
MIT License. Open-source and free for all students, co-ops, engineers, and researchers.
