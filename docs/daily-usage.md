# Daily Usage

This guide explains how to use the app after it has already been set up.

## Start the App

```bash
source venv/bin/activate
streamlit run streamlit_app.py
```

On Windows, activate with:

```powershell
venv\Scripts\Activate.ps1
```

Expected result: Streamlit prints a local browser address.

## Ask a Question

Use the chat box at the bottom of the page.

Good questions are specific:

```text
What are the most common attack vectors against energy-sector OT systems?
```

```text
Recommend an action plan for insecure remote access at an electric utility.
```

```text
Draft policy language for patch management in energy delivery systems.
```

## Read the Answer

The app may show:

- `Answer`: short summary.
- `Key Points`: important findings.
- `Attack Vectors`: attack methods, likely targets, and mitigation focus.
- `Risk Categories`: grouped risks for OT, IT, and cyber-physical systems.
- `Policy Recommendations`: recommended actions.
- `Draft Policy Language`: sample wording.
- `Sources`: documents used as evidence.

## Use the Sidebar

The sidebar includes:

- `New analysis`: starts a new chat.
- `History`: switches between previous chats in the current browser session.
- `Retrieved evidence chunks`: controls how many document chunks are retrieved.
- `Debug mode`: shows raw diagnostic JSON.

Tip: raise `Retrieved evidence chunks` if answers seem too narrow.

## Save an Answer

The app does not include a built-in export button.

Practical options:

1. Select the answer text and copy it.
2. Save browser screenshots.
3. Run the command-line query and redirect output to a file:

```bash
python -m scripts.04_query_bot --q "Your question here" > answer.json
```

What this does: writes the terminal output into `answer.json`.

## Limitations

- Answers are only as good as the available document chunks.
- Some source PDFs may extract imperfectly.
- Live web search requires SerpAPI and internet access.
- There is no user account system.
- Chat history is stored in Streamlit session state, not in a long-term database.
