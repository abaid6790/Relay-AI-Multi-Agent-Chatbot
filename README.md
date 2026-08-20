# Relay — Multi-Provider AI Chat & Image Generator

Relay is a self-hosted AI chatbot built with Flask that connects multiple AI providers through a single interface.

It supports **Groq, Google Gemini, OpenRouter, and Hugging Face**, with automatic provider fallback to keep conversations available when a provider is unavailable or rate-limited. It also includes AI image generation, conversation management, vision input, document Q&A, tool calling, streaming responses, and persistent chat history.

## Features

* **Multi-provider AI chat** — Groq, Gemini, and OpenRouter with automatic fallback
* **Streaming responses** — AI responses appear in real time
* **AI image generation** — Pollinations.ai with Hugging Face as a backup provider
* **Multiple conversations** — Create, rename, delete, and switch between conversations
* **Persistent chat history** — Conversations and messages are stored using SQLite
* **Conversation personas** — Set a custom system prompt for individual conversations
* **Vision support** — Upload an image and ask questions about it using Gemini
* **Document Q&A** — Ask questions about `.txt` and `.md` files
* **Tool calling** — Supports calculator, clock, and weather tools
* **Message regeneration** — Regenerate the latest AI response
* **Message editing** — Edit and resend your previous message
* **Markdown support** — Render formatted text and syntax-highlighted code
* **Code copying** — Easily copy generated code from responses
* **Light and dark themes** — Switch between interface themes
* **Conversation export** — Export conversations as Markdown
* **Usage tracking** — Monitor provider usage through the API
* **Rate limiting** — Helps prevent excessive API requests
* **Provider fallback status** — Shows when the application switches between providers
* **Automated testing** — Includes a pytest test suite with mocked provider calls

---

## AI Providers

Relay integrates multiple AI providers so the application is not dependent on a single API.

| Provider            | Purpose                                 |
| ------------------- | --------------------------------------- |
| **Groq**            | Fast AI chat responses                  |
| **Google Gemini**   | Chat and vision capabilities            |
| **OpenRouter**      | Access to multiple AI models            |
| **Hugging Face**    | Additional AI/image generation provider |
| **Pollinations.ai** | Image generation                        |

The application automatically falls back to another configured provider when possible.

---

## Tech Stack

### Backend

* Python
* Flask
* SQLite
* Flask-Limiter

### AI & APIs

* Groq API
* Google Gemini API
* OpenRouter API
* Hugging Face API
* Pollinations.ai

### Frontend

* HTML5
* CSS3
* JavaScript
* Markdown rendering
* Syntax highlighting

### Testing

* pytest

---

## Project Structure

```text
relay/
│
├── app.py
├── providers.py
├── tools.py
├── db.py
├── test_keys.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   │
│   └── js/
│       └── app.js
│
└── tests/
    └── test_app.py
```

### Main Components

**`app.py`**
Contains the Flask application and API routes.

**`providers.py`**
Handles communication with Groq, Gemini, OpenRouter, Pollinations, and Hugging Face.

**`tools.py`**
Contains the calculator, clock, and weather tools.

**`db.py`**
Manages SQLite storage for conversations, messages, and usage information.

**`static/js/app.js`**
Handles frontend interactions and communication with the Flask backend.

**`tests/test_app.py`**
Contains automated tests with mocked API calls.

**`test_keys.py`**
Checks whether configured API keys can successfully connect to their providers.

---

## How the AI Chat Works

When a user sends a message, Relay attempts to use the configured providers in the fallback chain:

```text
User Message
     │
     ▼
   Groq
     │
     ├── Success ──► Response
     │
     └── Failure
          │
          ▼
       Gemini
          │
          ├── Success ──► Response
          │
          └── Failure
               │
               ▼
           OpenRouter
               │
               ▼
            Response
```

This allows the application to continue working when a provider is temporarily unavailable or rate-limited.

---

## Image Generation

Image requests use the following provider flow:

```text
Image Request
      │
      ▼
Pollinations.ai
      │
      └── Failure
            │
            ▼
      Hugging Face
```

The generated image is returned to the application without requiring the frontend to have direct access to API credentials.

---

## Conversation Management

Relay supports multiple independent conversations.

Users can:

* Create new conversations
* Rename conversations
* Delete conversations
* Switch between conversations
* Set individual conversation personas
* Regenerate responses
* Edit and resend messages
* Export conversations as Markdown

Conversation data is stored locally using SQLite.

---

## Vision Support

Users can attach an image and ask questions about it.

The image is sent to a vision-capable provider, currently routed through Gemini.

Example:

```text
User:
[Uploads image]

"What objects are visible in this image?"
```

The model analyzes the image and generates a response.

---

## Document Q&A

Relay supports lightweight document-based question answering for:

* `.txt`
* `.md`

The uploaded document content is included as context when generating the response.

Example:

```text
Upload:
project_notes.txt

Question:
"What are the main features mentioned in this document?"
```

No vector database is required for this lightweight implementation.

---

## Tool Calling

The chatbot can use several built-in tools when supported by the selected provider.

### Available Tools

* Calculator
* Clock
* Weather

Example:

```text
User:
"What is 245 × 37?"

AI:
Uses the calculator tool
        ↓
Returns the calculated result
```

Tool calling currently uses Groq and OpenRouter.

---

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd relay
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file based on `.env.example`.

```bash
cp .env.example .env
```

On Windows, you can simply create a `.env` file manually.

Add the API keys you want to use:

```env
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
HF_API_KEY=your_huggingface_api_key
```

You do not need to configure every provider. Missing API keys are skipped by the application.

---

## API Keys

API keys can be obtained from the official provider dashboards:

* [Groq API Keys](https://console.groq.com/keys)
* [Google AI Studio](https://aistudio.google.com/apikey)
* [OpenRouter API Keys](https://openrouter.ai/keys)
* [Hugging Face Tokens](https://huggingface.co/settings/tokens)

**Never commit your `.env` file or expose API keys publicly.**

---

## Test API Keys

Before running the application, you can check your configured API keys:

```bash
python test_keys.py
```

This tests the configured providers and helps identify invalid or missing credentials.

---

## Run the Application

Start the Flask application:

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

---

## Testing

Relay includes automated tests using mocked provider calls.

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest
```

The tests do not require real API keys and do not make paid API requests.

---

## Security

API credentials are kept on the server and loaded from environment variables.

The frontend does not directly receive provider API keys.

Make sure your `.gitignore` contains:

```gitignore
.env
venv/
__pycache__/
*.pyc
*.db
```

Never upload real API keys to GitHub.

If a key is accidentally exposed, revoke it immediately from the provider dashboard and generate a new one.

---

## Known Limitations

* Vision and tool calling cannot be used simultaneously in the same message.
* Tool calling currently uses Groq and OpenRouter.
* Uploaded images are not permanently stored.
* Document Q&A currently supports `.txt` and `.md` files.
* PDF documents are not currently supported.
* There are no user accounts; conversations are associated with the browser.
* AI model IDs may need to be updated when providers retire or rename models.
* Provider availability and API limits depend on the respective services.

---

## Future Improvements

Potential future improvements include:

* Conversation search
* Conversation folders and projects
* Pinning important conversations
* Model selection per conversation
* Usage dashboard
* User authentication
* Multi-user support
* Telegram/Discord integration
* Voice input
* Voice output
* PDF document support
* More AI providers
* Persistent uploaded documents

---

## What I Learned

Building Relay provided practical experience with:

* Integrating multiple AI APIs
* Designing provider fallback systems
* Working with Flask REST APIs
* Streaming AI responses
* Managing API credentials securely
* Building AI-powered frontend interfaces
* Working with SQLite databases
* Implementing conversation history
* Handling file uploads
* Implementing vision-based AI interactions
* Implementing tool calling
* API rate limiting
* Automated testing and mocking
* Structuring a multi-provider AI application

---

## License

This project is licensed under the MIT License.

See [LICENSE](LICENSE) for more information.

---

## Contributing

Contributions, suggestions, and improvements are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
