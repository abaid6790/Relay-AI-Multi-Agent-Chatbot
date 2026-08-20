# Relay — Multi-Provider AI Chat & Image Generator

**Relay** is a self-hosted, AI-powered chat application built with **Python and Flask** that connects to multiple AI providers through a single interface.

It supports **Groq, Google Gemini, OpenRouter, and Hugging Face**, with automatic provider fallback, streaming responses, image generation, conversation history, personas, vision input, document Q&A, and AI tool calling.

The project was developed as a practical exploration of **AI APIs, LLM integration, prompt engineering, API fallback systems, and AI-assisted software development**.

---

## 🚀 Features

### 🤖 Multi-Provider AI Chat

Relay supports multiple AI providers:

* **Groq**
* **Google Gemini**
* **OpenRouter**
* **Hugging Face**

If one provider is unavailable, rate-limited, or fails, Relay can automatically move to the next available provider.

```text
Groq
  ↓
Gemini
  ↓
OpenRouter
```

This makes the application more reliable than depending on a single AI provider.

---

### ⚡ Streaming AI Responses

AI responses can be streamed in real time so users see the response as it is generated instead of waiting for the complete response.

---

### 🖼️ AI Image Generation

Relay can generate images from text prompts.

The primary image-generation provider is:

* Pollinations.ai

Hugging Face is available as a backup provider.

---

### 💬 Multiple Conversations

Users can manage multiple conversations from the sidebar.

Supported actions include:

* Create new conversations
* Rename conversations
* Delete conversations
* Automatically generate conversation titles
* Continue previous conversations
* Store complete conversation history

Conversation data is persisted using **SQLite**.

---

### 🎭 Per-Conversation Personas

Each conversation can have its own system prompt/persona.

For example:

```text
Python Expert
Coding Tutor
Research Assistant
Creative Writer
General Assistant
```

This allows the behavior of the AI to be customized for different conversations.

---

### 👁️ Vision Input

Users can attach an image and ask the AI questions about it.

Vision requests are routed through Gemini.

Example use cases:

* Image explanation
* Object identification
* Screenshot analysis
* Visual question answering

---

### 📄 Document Q&A

Users can attach `.txt` or `.md` documents and ask questions about their content.

The document content is provided to the AI as context, allowing users to perform lightweight document-based question answering without requiring a vector database.

---

### 🛠️ AI Tool Calling

Relay supports AI tool calling for:

* Calculator
* Clock
* Weather

The AI can determine when a tool is useful and use the appropriate function before generating its final response.

Tool calling currently uses Groq and OpenRouter.

---

### ✏️ Regenerate & Edit

Users can:

* Regenerate the latest AI response
* Edit their previous message
* Resend an edited message

---

### 📝 Markdown & Code Support

AI responses support:

* Markdown
* Code blocks
* Syntax highlighting
* Copy-to-clipboard buttons

This makes programming and technical conversations easier to read.

---

### 🌙 Light & Dark Mode

The interface includes both:

* Light theme
* Dark theme

---

### 📤 Conversation Export

Conversations can be exported to Markdown for saving or sharing.

---

### 📊 Usage Tracking

Relay tracks API usage through:

```text
/api/usage
```

This provides information about provider usage and helps monitor free-tier API consumption.

---

### 🛡️ Rate Limiting

API routes are protected using rate limiting to prevent accidental excessive API usage.

This helps prevent a bug or repeated request from unnecessarily consuming an API provider's quota.

---

### 🧪 Testing

The project includes:

* Pytest test suite
* Mocked provider tests
* Real API key validation script

The automated tests do not require real API calls.

---

# 🧰 Technologies Used

### Backend

* Python
* Flask
* SQLite
* Flask-Limiter

### AI & APIs

* Google Gemini API
* Groq API
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

* Pytest
* Mock API calls

---

# 🏗️ Project Structure

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
├── Procfile
├── LICENSE
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

### Main components

| File                   | Purpose                               |
| ---------------------- | ------------------------------------- |
| `app.py`               | Flask application and API routes      |
| `providers.py`         | AI provider integrations              |
| `tools.py`             | Calculator, clock, and weather tools  |
| `db.py`                | SQLite conversation and usage storage |
| `test_keys.py`         | Checks configured API keys            |
| `templates/index.html` | Main application interface            |
| `static/css/style.css` | Application styling                   |
| `static/js/app.js`     | Frontend functionality                |
| `tests/test_app.py`    | Automated tests                       |

---

# 🔄 How Relay Works

## Chat Request

```text
User
 ↓
Flask Backend
 ↓
AI Provider
 ↓
Groq
 ↓
Gemini
 ↓
OpenRouter
 ↓
AI Response
 ↓
Streaming to User
```

If a provider fails, Relay automatically attempts the next available provider.

---

## Image Generation

```text
User Prompt
     ↓
Flask Backend
     ↓
Pollinations.ai
     ↓
Generated Image
```

Hugging Face can be used as a backup provider.

---

## Vision

```text
User
 ↓
Image + Question
 ↓
Flask Backend
 ↓
Gemini
 ↓
Vision Analysis
 ↓
Response
```

---

## Document Q&A

```text
Document
   ↓
Text Extraction
   ↓
User Question
   ↓
Document Context
   ↓
AI Provider
   ↓
Answer
```

---

# 🔑 API Configuration

Create a `.env` file based on `.env.example`.

Example:

```env
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
HF_API_KEY=your_huggingface_api_key
```

API keys are stored server-side and are **never exposed to the frontend**.

> **Important:** Never commit your `.env` file or real API keys to GitHub.

---

# 🔗 API Providers

You can obtain API keys from the official provider websites:

* [Groq](https://console.groq.com/keys)
* [Google AI Studio / Gemini](https://aistudio.google.com/apikey)
* [OpenRouter](https://openrouter.ai/keys)
* [Hugging Face](https://huggingface.co/settings/tokens)

Relay is designed to work with available free-tier resources where supported, but provider limits and availability can change.

---

# ⚙️ Installation

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd relay
```

## 2. Create a virtual environment

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv

source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Then add your API keys.

## 5. Test API keys

```bash
python test_keys.py
```

---

# ▶️ Run the Application

Start the Flask server:

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

---

# 🧪 Testing

## Automated Tests

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run:

```bash
pytest
```

The provider calls are mocked, so the test suite does not consume API credits.

---

## API Key Testing

To test your configured providers:

```bash
python test_keys.py
```

This checks whether the configured API keys can communicate with their respective providers.

---

# 🧠 AI Tools Used During Development

This project also demonstrates how modern AI tools can assist with software development.

### ChatGPT

Used for:

* Understanding API integration concepts
* Debugging Python and Flask issues
* Improving application architecture
* Generating and refining code
* Troubleshooting errors
* Improving documentation
* Brainstorming features and improvements

### Google Gemini

Used for:

* AI-powered conversation
* Vision-based image analysis
* Testing multimodal AI capabilities

### Groq

Used for:

* Fast AI responses
* Primary/alternative conversational model provider
* Tool-calling functionality

### OpenRouter

Used for:

* Accessing different AI models through a unified API
* Provider fallback
* Experimenting with different models

### Hugging Face

Used for:

* Additional AI model/API support
* Image-generation fallback

This project helped demonstrate that AI tools can be used not only as end-user applications but also as **development assistants for coding, debugging, research, testing, and productivity**.

---

# 📚 What I Learned

Through this project, I gained practical experience with:

* Integrating multiple AI APIs
* Working with LLM APIs
* Handling API failures and fallback providers
* Streaming AI responses
* Prompt engineering
* Vision models
* AI tool calling
* Document-based question answering
* Managing API keys securely
* Flask backend development
* REST API design
* SQLite database persistence
* Frontend/backend integration
* Error handling
* Rate limiting
* Automated testing
* Environment variables
* Git and GitHub
* AI-assisted software development

---

# ⚠️ Known Limitations

### Vision and Tool Calling

Vision and tool calling cannot currently be combined in the same request.

When an image is attached, vision takes priority.

### Tool Calling Providers

Tool calling currently uses:

* Groq
* OpenRouter

Gemini is not currently included in the tool-calling route.

### Uploaded Images

Uploaded images are not permanently stored in SQLite.

Vision applies only to the request in which the image was attached.

### Document Q&A

Currently supported:

```text
.txt
.md
```

PDF documents are not currently supported by this lightweight document Q&A implementation.

### User Accounts

Relay currently does not have a traditional authentication system.

Conversations are associated with a browser through a locally stored identifier.

For a public multi-user deployment, authentication should be added.

### AI Model Availability

AI providers periodically change, rename, or retire models.

If a provider returns a model-related error, update the configured model ID to a currently supported model.

---

# 🚀 Future Improvements

Possible future improvements include:

* [ ] User authentication
* [ ] Search across conversations
* [ ] Conversation folders
* [ ] Pin conversations
* [ ] Conversation branching
* [ ] PDF document support
* [ ] RAG with vector database
* [ ] Voice input
* [ ] Voice output
* [ ] Model selection per conversation
* [ ] Advanced usage dashboard
* [ ] Multi-user support
* [ ] Telegram integration
* [ ] Discord integration
* [ ] Mobile-friendly improvements

---

# 🌐 Deployment

Relay can be deployed to cloud platforms that support Python/Flask applications.

For example:

* Render
* Railway
* PythonAnywhere

For deployment, configure the required API keys as environment variables in the hosting platform instead of uploading the `.env` file.

Example start command:

```bash
gunicorn app:app
```

---

# 🔐 Security

API keys should always be stored in environment variables.

The following files should **never** be committed:

```text
.env
venv/
*.db
__pycache__/
```

Make sure `.gitignore` is configured before pushing the project to GitHub.

If an API key is accidentally exposed publicly, revoke it immediately and generate a new one.

---

# 🎓 Module 5 — AI Tools & Mini Project

This project is being used as my **Module 5 AI Tools & Mini Project**.

### Assignment Requirements

* Explore AI tools
* Understand how AI can assist with coding and productivity
* Build an AI-powered application
* Document the learning experience
* Publish the project on GitHub
* Share the learning journey on LinkedIn

### Project Outcome

Relay demonstrates how multiple AI services can be combined into one practical application while using AI tools throughout the development process for:

**Coding → Debugging → Research → Testing → Documentation → Productivity**

---

# 📸 Screenshots

Screenshots of the application are added in the screenshot folder.

---

# 📄 License

This project is licensed under the **MIT License**.

See [LICENSE](LICENSE) for details.

---

# 🤝 Contributing

Contributions, suggestions, and improvements are welcome.

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## ⭐ Project

If you find this project useful or interesting, consider giving the repository a ⭐ on GitHub.
