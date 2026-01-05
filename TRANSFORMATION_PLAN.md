# Alpaca → NanoGPT Transformation Plan

## Project Goals Summary

Transform Alpaca from an Ollama-focused local LLM app into a NanoGPT-exclusive cloud AI client with:
- ✅ Single NanoGPT instance only
- ✅ Simplified onboarding (API key → model selection → chat)
- ✅ Web search with depth selection (standard/deep) and pricing display
- ✅ Automatic YouTube transcript fetching
- ✅ Image generation support with model capability indicators
- ✅ Account balance display in settings
- ✅ All models shown by default with subscription filter toggle
- ✅ Context memory toggle in chat UI

## Key NanoGPT API Details

### API Base URL
- **Base URL**: `https://nano-gpt.com/api/v1`
- **Chat**: `/api/v1/chat/completions` (OpenAI-compatible)
- **Models**: `/api/v1/models` (with `?detailed=true` for pricing)
- **Web Search**: `/api/web` (separate endpoint)
- **Web Scraping**: `/api/scrape-urls`
- **YouTube**: `/api/youtube-transcribe`
- **Balance**: `/api/v1/check-balance` (POST)

### Authentication
- Header: `Authorization: Bearer {API_KEY}` OR `x-api-key: {API_KEY}`

### Web Search Pricing
- Standard: $0.006 per search
- Deep: $0.06 per search

### YouTube Transcripts
- $0.01 per transcript
- Automatic via chat completions (`youtube_transcripts: true`)

## Implementation Phases

### PHASE 1: CODE REMOVAL & CLEANUP
1. Delete `src/ollama_models.py`
2. Delete `src/widgets/instances/ollama_instances.py`
3. Remove all OpenAI provider classes except BaseInstance
4. Remove WebBrowser activity files
5. Clean up welcome screen
6. Update window.py
7. Simplify instance management
8. Update preferences

### PHASE 2: NANOGPT INSTANCE IMPLEMENTATION
1. Create NanoGPT class extending BaseInstance
2. Implement model fetching with details
3. Implement web search via `/api/web`
4. Implement balance checking
5. Add YouTube transcript auto-fetching
6. Add context memory support
7. Add image generation

### PHASE 3: SIMPLIFIED ONBOARDING
1. Create setup.py with wizard flow
2. Create setup.blp blueprint
3. Update window initialization

### PHASE 4: SETTINGS INTERFACE
1. Create NanoGPT preferences page
2. Add API key entry with balance display
3. Add model settings with subscription filter
4. Add web search configuration
5. Add generation parameters
6. Add advanced features (YouTube, memory)

### PHASE 5: CHAT UI UPDATES
1. Add context memory toggle to toolbar
2. Add web search depth selector
3. Update model selector with capability indicators

### PHASE 6: TOOL UPDATES
1. Update WebSearch tool for NanoGPT
2. Add YouTube transcript tool
3. Add web scraping tool
4. Update image generation tool

### PHASE 7: IMAGE GENERATION
1. Add ImageGeneration tool class
2. Integrate with chat interface
3. Display generated images

### PHASE 8: DATABASE MIGRATION
1. Create migration script
2. Handle Ollama instance cleanup
3. Preserve user chat data

### PHASE 9: DOCUMENTATION
1. Update AGENTS.md
2. Update README.md
3. Update metainfo.xml

### PHASE 10: TESTING
1. Setup flow testing
2. Chat functionality testing
3. Settings testing
4. Tool testing
5. Build testing

## Quick Reference

### NanoGPT API Endpoints

```
POST https://nano-gpt.com/api/v1/chat/completions
GET https://nano-gpt.com/api/v1/models?detailed=true
POST https://nano-gpt.com/api/web
POST https://nano-gpt.com/api/scrape-urls
POST https://nano-gpt.com/api/youtube-transcribe
POST https://nano-gpt.com/api/v1/check-balance
```

### Model Suffixes
- `:online` - Web search enabled
- `:memory` - Context memory (30 days)
- `:memory-{days}` - Custom memory retention (1-365)
- `:online:memory` - Both web search and memory

### Instance Properties
```python
{
    'api': 'YOUR_API_KEY',
    'default_model': 'gpt-4o-mini',
    'temperature': 0.7,
    'max_tokens': 4096,
    'web_search_enabled': False,
    'web_search_depth': 'standard',  # 'standard' or 'deep'
    'auto_youtube_transcripts': True,
    'context_memory_enabled': False,
    'context_memory_days': 30,
    'system_prompt': ''
}
```

## Files to Modify/Create

### Created (New Files)
- `src/widgets/setup.py` (onboarding wizard)
- `src/ui/setup.blp` (onboarding UI)

### Deleted (Complete Removal)
- `src/ollama_models.py`
- `src/widgets/instances/ollama_instances.py`
- `src/widgets/activities/web_browser.py`
- `src/ui/widgets/activities/web_browser.blp`
- `src/widgets/welcome.py`
- `src/ui/welcome.blp`

### Modified
- `src/widgets/instances/openai_instances.py`
- `src/widgets/instances/__init__.py`
- `src/window.py`
- `src/widgets/preferences.py`
- `src/ui/preferences.blp`
- `src/widgets/chat.py`
- `src/ui/widgets/chat/chat.blp`
- `src/widgets/tools/tools.py`
- `src/sql_manager.py`
- `src/main.py`
- `AGENTS.md`
- `README.md`
- `data/com.jeffser.Alpaca.metainfo.xml.in`

## Testing Checklist

### Setup Flow
- [ ] Setup dialog appears on first run
- [ ] Invalid API key shows error
- [ ] Valid API key shows balance
- [ ] Models fetch and display
- [ ] Setup completes successfully

### Chat
- [ ] Messages generate correctly
- [ ] Web search toggle works
- [ ] Web search depth selection works
- [ ] Context memory toggle works
- [ ] YouTube transcripts auto-fetch

### Settings
- [ ] API key can be changed
- [ ] Balance displays correctly
- [ ] Model selection works
- [ ] Subscription filter works
- [ ] All parameters save correctly

### Tools
- [ ] Web search returns results
- [ ] YouTube transcripts work
- [ ] Web scraping extracts content
- [ ] Image generation creates images

### Build
- [ ] Meson build succeeds
- [ ] Flatpak build succeeds
- [ ] No import errors
- [ ] No runtime crashes

## Timeline

- **Week 1**: Foundation (Removal + NanoGPT Instance)
- **Week 2**: UI & Onboarding (Settings + Setup)
- **Week 3**: Features & Tools (Chat + Tools)
- **Week 4**: Polish & Deploy (Migration + Documentation)

## Success Criteria

✅ User completes setup in < 2 minutes
✅ All Ollama code removed
✅ Chat with NanoGPT works
✅ Web search (standard/deep) functional
✅ YouTube transcripts automatic
✅ Image generation works
✅ Balance display in settings
✅ Model filter works
✅ Context memory toggle works
✅ App builds without errors
✅ No crashes during normal usage
✅ Documentation fully updated

---

*Plan generated: January 2026*
*Project: Alpaca → NanoGPT Transformation*