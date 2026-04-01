# Future Ideas

1. **Realtime streaming transcription** — text appears as you speak (whisper.cpp streaming mode)
2. **AI post-processing** — LLM fixes punctuation/grammar, formats output, or executes voice commands
3. **Voice commands for macOS** — "open Chrome", "play next song", with a prefix to distinguish from dictation
4. **Per-app context** — adapt behavior based on active application (Slack, Terminal, Notes)
5. **Speaker diarization** — identify who is speaking in meetings (whisper.cpp + pyannote)
6. **Real-time translation** — speak in BG → paste in EN and vice versa
7. **Searchable history with timestamps** — SQLite database, full-text search, filter by date/language
8. **Context-aware custom dictionary** — dynamic initial prompt with names, technical terms, slang
9. **Web App version** — FastAPI backend + HTML/JS frontend with MediaRecorder API, PWA for iPhone, HTTPS required
