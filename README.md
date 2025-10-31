# Virtual Try-On AI Agent

An intelligent AI agent built with Google ADK for virtual clothing try-on. Upload a person image, select from our catalog, and let AI show you how the outfit would look!

## 🎯 Features

### Core Features
- ✅ **Virtual Try-On**: Select catalog garments and see realistic try-on results
- ✅ **Catalog System**: Browse 7 curated fashion garments (no uploads needed)
- ✅ **Rate Limiting**: Smart cooldown (5s) prevents excessive API calls
- ✅ **Result Comparison**: Compare multiple try-on versions side-by-side
- ✅ **Image Validation**: Automatic person image validation
- ✅ **9:16 Aspect Ratio**: Optimized for portrait/mobile viewing
- ✅ **Session Management**: Track all uploads and try-on results

### v1.7.0 - Sequential Multi-Agent Architecture ⭐ NEW!
- 🎯 **Coordinator Agent**: Orchestrates the entire workflow
- 🖼️ **Image Manager Agent**: Handles person image uploads (3 tools)
- 👔 **Catalog Manager Agent**: Shows catalog and manages selection (2 tools)
- ✨ **Try-On Specialist Agent**: Executes virtual try-on operations (5 tools)
- 📊 **Better Organization**: 10 tools distributed across 4 specialized agents
- 🔧 **Easy Maintenance**: Clear separation of responsibilities

## 🏗️ Architecture

### Sequential Multi-Agent System (Recommended)

```
COORDINATOR AGENT (Orchestrator)
    │
    ├─→ Image Manager Agent (3 tools)
    │   ├─ list_reference_images
    │   ├─ clear_reference_images
    │   └─ load_artifacts_tool
    │
    ├─→ Catalog Manager Agent (2 tools)
    │   ├─ list_catalog_clothes
    │   └─ select_catalog_cloth
    │
    └─→ Try-On Specialist Agent (5 tools)
        ├─ virtual_tryon
        ├─ list_tryon_results
        ├─ compare_tryon_results
        ├─ get_comparison_summary
        └─ get_rate_limit_status
```

**Why Sequential?**
- ✅ Clear workflow: Upload → Select → Try-On
- ✅ Easy to maintain and extend
- ✅ Better debugging and testing
- ✅ Professional architecture

**Legacy Single Agent** still available in `agent.py` for backwards compatibility.

## Prerequisites

- Python 3.10+
- Google ADK (`pip install google-adk`)
- Gemini API key with image generation access

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd adk-design-agent
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   GOOGLE_API_KEY=your_gemini_api_key_here
   GOOGLE_GENAI_USE_VERTEXAI=false
   ```

4. **Verify installation**:
   ```bash
   python -c "import google.adk; print('ADK installed successfully')"
   ```

## Running the Agent

### Quick Start ⭐ Recommended

Start the Sequential Multi-Agent system:

```bash
adk run agent:runner
```

Or use the quick start script:

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

### Web UI Mode

Start the ADK web interface:

```bash
adk web
```

Then navigate to: `http://127.0.0.1:8000/dev-ui?app=agent`

Or use the web UI script:

**Windows:**
```bash
run_web.bat
```

**Linux/Mac:**
```bash
chmod +x run_web.sh
./run_web.sh
```

### Compare Architectures

Analyze the architecture:

```bash
python compare_architecture.py all
```

## 📖 Usage Guide

### Step 1: Upload Person Image (Image Manager)

```
User: "Hi, I want to try on some clothes"
Agent: "Hello! Welcome to our Virtual Try-On service! 👔✨
        
        Let's start by uploading a person image.
        Please provide a 9:16 portrait photo."

User: [Uploads person image]
Agent: "✅ Person image validated and saved!
        Ready to browse our catalog!"
```

### Step 2: Browse Catalog (Catalog Manager)

```
User: "Show me the catalog"
Agent: "Here are our available garments:

        1. 👕 Classic White T-Shirt - Versatile everyday essential
        2. 👔 Navy Business Suit - Professional formal wear
        3. 🧥 Denim Jacket - Casual cool style
        4. 👗 Floral Summer Dress - Bright and cheerful
        5. 🎽 Athletic Sports Jersey - Active lifestyle
        6. 🧥 Leather Biker Jacket - Edgy street style
        7. 🎩 Vintage Cardigan - Cozy classic comfort
        
        Which garment would you like to try? (1-7)"
```

### Step 3: Virtual Try-On (Try-On Specialist)

```
User: "I want to try garment #2"
Agent: "✅ Navy Business Suit selected!
        
        Checking rate limit... ✅ Ready!
        Creating your virtual try-on... 🎨"
        
Agent: "✨ Virtual Try-On Complete!
        
        📸 Result: tryon_result_v1.png
        
        How does it look? Would you like to:
        • Try another garment
        • Compare with other results
        • Get a comparison summary"
```

### Step 4: Compare Results (Try-On Specialist)

```
User: "Compare my try-on results"
Agent: [Shows all try-on versions]
       "Here are all your try-ons:
        
        v1: Navy Business Suit
        v2: Denim Jacket
        v3: Leather Biker Jacket
        
        Which looks best to you?"

User: "Show me a comparison summary"
Agent: [Calls get_comparison_summary]
       "📊 Comparison Summary:
        
        ✅ Best Match: Denim Jacket (v2)
        • Natural fit
        • Great color coordination
        • Most versatile style"
```## 🛠️ Available Tools

### Image Manager Agent (3 tools)
1. **list_reference_images** - List all uploaded person images
2. **clear_reference_images** - Clear all uploaded images
3. **load_artifacts_tool** - Load previous artifacts

### Catalog Manager Agent (2 tools)
1. **list_catalog_clothes** - Display all 7 catalog garments
2. **select_catalog_cloth** - Select garment by ID (1-7)

### Try-On Specialist Agent (5 tools)
1. **virtual_tryon** - Execute virtual try-on with selected garment
2. **list_tryon_results** - Show all try-on results
3. **compare_tryon_results** - Compare multiple versions
4. **get_comparison_summary** - Get AI analysis of comparisons
5. **get_rate_limit_status** - Check cooldown status

## 📁 File Structure

```
adk-design-agent/
├── sequential_agent.py          # ⭐ Sequential Multi-Agent (Recommended)
├── sequential_prompts.py        # Agent instructions
├── agent.py                     # Legacy single agent
├── prompt.py                    # Legacy instructions
├── tools/
│   ├── tryon_tool.py           # Virtual try-on tools (10 tools)
│   └── post_creator_tool.py    # Legacy tool
├── compare_architecture.py      # Architecture comparison tool
├── ARCHITECTURE.md             # Architecture documentation
├── AGENT_CONFIG.md             # Configuration guide
├── SEQUENTIAL_SUMMARY.md       # Implementation summary
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional
GOOGLE_GENAI_USE_VERTEXAI=false
```

### Rate Limiting Configuration

Edit `tools/tryon_tool.py`:

```python
RATE_LIMIT_SECONDS = 5  # Cooldown between try-ons (default: 5s)
```

### Catalog Configuration

Add/modify garments in `tools/tryon_tool.py`:

```python
CATALOG_CLOTHES = [
    {"id": 1, "name": "Your Garment", "description": "Description"},
    # ... add more
]
```

## 🐛 Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY environment variable not set"**
   - Ensure your `.env` file contains the API key
   - Verify the key has image generation permissions
   - Check the key is loaded: `echo $GEMINI_API_KEY` (Linux/Mac) or `echo %GEMINI_API_KEY%` (Windows)

2. **"Rate limit exceeded"**
   - Wait 5 seconds between try-ons
   - Check status: `"What's the rate limit status?"`
   - The cooldown resets automatically

3. **"Invalid garment selection"**
   - Use garment ID from 1-7 only
   - Run `"Show me the catalog"` to see available garments
   - Cannot upload custom garments (catalog-only mode)

4. **"Person image validation failed"**
   - Ensure image is 9:16 aspect ratio
   - Upload clear portrait photos
   - File must be JPG or PNG format

5. **"Cannot import sequential_agent"**
   - Check you're in the project directory
   - Verify all files exist: `sequential_agent.py`, `sequential_prompts.py`, `tools/`
   - Run: `python -c "from sequential_agent import runner; print('OK')"`

### Debug Mode

Enable detailed logging:

```bash
# Windows PowerShell
$env:PYTHONPATH="."; python -c "import logging; logging.basicConfig(level='DEBUG'); from sequential_agent import runner"

# Linux/Mac
export PYTHONPATH=.; python -c "import logging; logging.basicConfig(level=logging.DEBUG); from sequential_agent import runner"
```

### Testing Tools

```bash
# Test Sequential Agent
python compare_architecture.py sequential

# Test Single Agent  
python compare_architecture.py single

# Compare Both
python compare_architecture.py all
```

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture comparison (Single vs Sequential)
- **[AGENT_CONFIG.md](AGENT_CONFIG.md)** - Configuration and deployment guide
- **[SEQUENTIAL_SUMMARY.md](SEQUENTIAL_SUMMARY.md)** - Implementation summary and benefits
- **[Google ADK Docs](https://google.github.io/adk-docs/)** - Official ADK documentation

## 🚀 Advanced Usage

### Adding New Agents

To extend the Sequential system:

```python
# In sequential_agent.py

# 1. Create new agent
style_advisor = LlmAgent(
    name="style_advisor_agent",
    model="gemini-2.0-flash-exp",
    instruction=STYLE_ADVISOR_INSTRUCTION,
    tools=[recommend_style, analyze_preferences]
)

# 2. Add to coordinator's sub_agents
root_agent = LlmAgent(
    name="coordinator_agent",
    sub_agents=[
        image_manager_agent,
        catalog_manager_agent,
        tryon_specialist_agent,
        style_advisor  # Add here
    ]
)
```

### Custom Workflows

Modify agent instructions in `sequential_prompts.py`:

```python
CUSTOM_WORKFLOW_INSTRUCTION = """
You are the Custom Workflow Agent.

Your workflow:
1. Step 1: [Your custom step]
2. Step 2: [Your custom step]
3. Step 3: [Your custom step]

Available tools: [list your tools]
"""
```

### Performance Tuning

```python
# Adjust model for speed/quality
LlmAgent(
    model="gemini-2.0-flash-exp",  # Fast, good quality
    # model="gemini-1.5-pro",      # Slower, best quality
    # model="gemini-1.5-flash",    # Fastest, good quality
)
```

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Test thoroughly**:
   ```bash
   # Test your changes
   python compare_architecture.py all
   adk run sequential_agent:runner
   ```
5. **Commit**: `git commit -m "Add amazing feature"`
6. **Push**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Guidelines

- Follow existing code style
- Add docstrings to new functions
- Update documentation
- Test both architectures if changing tools
- Keep backward compatibility with single agent

## 📄 License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## 💬 Support

For issues and questions:

- Check the [troubleshooting section](#-troubleshooting) above
- Review [ADK documentation](https://google.github.io/adk-docs/)
- Open an issue in the repository
- Check existing issues for solutions

## 🎯 Version History

### v1.7.0 (Latest) - Sequential Multi-Agent Architecture
- ✅ Added Sequential Multi-Agent system (4 agents)
- ✅ Better tool organization (3+2+5 distribution)
- ✅ Comprehensive documentation (ARCHITECTURE.md, AGENT_CONFIG.md)
- ✅ Architecture comparison tool

### v1.6.0 - Regular Mode Only
- ✅ Removed Deep Think mode
- ✅ Simplified to regular agent only
- ✅ Code cleanup (removed unused imports)

### v1.5.0 - Catalog System
- ✅ Added catalog with 7 garments
- ✅ Catalog-only mode (no garment uploads)
- ✅ English-only output

### v1.4.0 - Comparison Features
- ✅ Compare multiple try-on results
- ✅ AI-powered comparison summary
- ✅ Side-by-side result viewing

### v1.3.0 - Rate Limiting
- ✅ 5-second cooldown between try-ons
- ✅ Rate limit status tool
- ✅ Prevents excessive API calls

### v1.2.0 - Image Validation
- ✅ Person image validation
- ✅ Clear reference images tool
- ✅ List reference images tool

### v1.1.0 - Core Features
- ✅ Virtual try-on tool
- ✅ List try-on results
- ✅ Load previous artifacts

### v1.0.0 - Initial Release
- ✅ Basic virtual try-on agent
- ✅ Image upload handling
- ✅ Result management

---

**Built with ❤️ using Google ADK and Gemini AI**

**⭐ Recommended:** Use Sequential Multi-Agent architecture for production!
