# Virtual Try-On AI Agent

An intelligent multi-agent AI system built with Google ADK for virtual clothing try-on. Upload a person image, select from our catalog, and let AI show you how the outfit would look!

## 🎯 Features

### Core Features
- ✅ **Virtual Try-On**: Select catalog garments and see realistic try-on results
- ✅ **Catalog System**: Browse 10 curated fashion garments (no uploads needed)
- ✅ **Auto-Start Mode**: New image upload automatically begins workflow
- ✅ **Continuous Workflow**: Unlimited try-ons with automatic versioning
- ✅ **Rate Limiting**: Smart cooldown (5s) prevents excessive API calls
- ✅ **Result Comparison**: Compare multiple try-on versions side-by-side
- ✅ **Image Validation**: Automatic person image validation
- ✅ **9:16 Aspect Ratio**: Optimized for portrait/mobile viewing
- ✅ **Session Management**: Track all uploads and try-on results

### v3.1.0 - Interactive Multi-Agent Architecture ⭐ CURRENT!
- 🎯 **Interactive Coordinator**: User-driven workflow with LLM intelligence
- 🖼️ **Image Manager Agent**: Handles person image uploads with auto-start (3 tools)
- 👔 **Catalog Manager Agent**: Shows catalog and manages selection (2 tools)
- ✨ **Try-On Specialist Agent**: Executes virtual try-on operations (5 tools)
- 📊 **Clean Organization**: 10 tools distributed across 3 specialized sub-agents
- � **Fast Workflow**: Auto-start mode for continuous try-ons
- 💬 **User Control**: Interactive with natural conversation flow

## 🏗️ Architecture

### Interactive Multi-Agent System (v3.1.0)

```
COORDINATOR AGENT (LlmAgent - Interactive)
    │
    ├─→ Image Manager Agent (3 tools) - AUTO-START
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

**Why Interactive?**
- ✅ User controls pace at each phase
- ✅ Auto-start on new image upload
- ✅ Natural conversation flow
- ✅ Flexible and maintainable
- ✅ Support for continuous operations

## 🔄 Workflow

### Auto-Start Workflow (v3.1.0)

1. **Upload Person Image** → AUTO-START
   - Image saved automatically (reference_image_v1.png)
   - System immediately shows catalog
   
2. **View Catalog** → AUTOMATIC
   - 10 garments displayed
   - User selects by number
   
3. **Select Garment** → INTERACTIVE
   - User chooses garment
   - Confirmation displayed
   
4. **Execute Try-On** → AUTOMATIC
   - Virtual try-on processed
   - Result saved (tryon_result_v1.png)
   
5. **View Result** → WAIT
   - User reviews result
   - Can compare with previous versions
   
6. **Continue?** → INTERACTIVE
   - Upload new person (→ auto-start)
   - Try different garment (same person)
   - Compare results
   - Finish

### Continuous Workflow
- Upload multiple person images (v1, v2, v3...)
- Each upload auto-starts new workflow
- All results preserved for comparison
- No manual cleanup needed

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

Start the Interactive Multi-Agent system:

```bash
adk run agent:runner
```

Expected output:
```
🎯 Virtual Try-On Agent System (v3.1.0) - Ready!
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

## 📖 Usage Guide

### Basic Workflow

1. **Start Agent**: Run `adk run agent:runner`
2. **Upload Image**: Attach person photo (9:16 ratio preferred)
3. **Auto-Start**: System automatically shows catalog
4. **Select Garment**: Choose by number (1-10)
5. **View Result**: See virtual try-on result
6. **Continue**: Upload new person or try different garment

### Step 1: Upload Person Image (AUTO-START)

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
```
## 🛠️ Available Tools

### Image Manager Agent (3 tools)
1. **list_reference_images** - List all uploaded person images
2. **clear_reference_images** - Clear all uploaded images
3. **load_artifacts_tool** - Load previous artifacts

### Catalog Manager Agent (2 tools)

1. **list_catalog_clothes** - Display all 10 catalog garments
2. **select_catalog_cloth** - Select garment by ID (1-10)

### Try-On Specialist Agent (5 tools)

1. **virtual_tryon** - Execute virtual try-on with selected garment
2. **list_tryon_results** - Show all try-on results
3. **compare_tryon_results** - Compare multiple versions
4. **get_comparison_summary** - Get AI analysis of comparisons
5. **get_rate_limit_status** - Check cooldown status

## 📁 File Structure

```
adk-design-agent/
├── agent.py                     # ⭐ Interactive Multi-Agent System (v3.1.0)
├── prompts.py                   # All agent instructions
├── prompt.py.old                # Legacy single agent (backup)
├── tools/
│   ├── tryon_tool.py           # Virtual try-on tools (10 tools)
│   └── rate_limiter.py         # Rate limiting utilities
├── catalog/                     # 10 fashion garments
├── reference_images/            # Uploaded person images (auto-versioned)
├── tryon_results/               # Generated results (auto-versioned)
├── deep_think_loop.py          # Deep thinking utilities
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Project configuration
├── run.bat / run.sh            # Quick start scripts
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
RATE_LIMIT_COOLDOWN=5.0         # Cooldown seconds (default: 5.0)
```

### Rate Limiting Configuration

Environment variable in `.env`:

```bash
RATE_LIMIT_COOLDOWN=5.0  # Cooldown between try-ons (default: 5s)
```

Or edit `tools/rate_limiter.py` for custom logic.

### Catalog Configuration

Add/modify garments in `tools/tryon_tool.py`:

```python
CATALOG_CLOTHES = [
    {"id": 1, "name": "Your Garment", "description": "Description"},
    # ... add up to 10 garments
]
```

Place garment images in `catalog/` folder.

## 🐛 Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY environment variable not set"**
   - Ensure your `.env` file contains the API key
   - Verify the key has image generation permissions
   - Check the key is loaded: `echo $GEMINI_API_KEY` (Linux/Mac) or `echo $env:GEMINI_API_KEY` (PowerShell)

2. **"Rate limit exceeded"**
   - Wait 5 seconds between try-ons (default cooldown)
   - Check status: "What's the rate limit status?"
   - The cooldown resets automatically

3. **"Invalid garment selection"**
   - Use garment ID from 1-10 only
   - Run "Show me the catalog" to see available garments
   - Cannot upload custom garments (catalog-only mode)

4. **"Person image validation failed"**
   - Ensure image is 9:16 aspect ratio (portrait)
   - Upload clear portrait photos
   - File must be JPG or PNG format

5. **"Cannot import module"**
   - Check you're in the project directory
   - Verify all files exist: `agent.py`, `prompts.py`, `tools/`
   - Run: `python -c "from agent import root_agent; print('OK')"`

### Debug Mode

Enable detailed logging:

```bash
# Windows PowerShell
$env:PYTHONPATH="."; python -c "import logging; logging.basicConfig(level='DEBUG'); from agent import root_agent"

# Linux/Mac
export PYTHONPATH=.; python -c "import logging; logging.basicConfig(level=logging.DEBUG); from agent import root_agent"
```

Or in your Python code:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

## 📚 Documentation

logging.basicConfig(level=logging.DEBUG)
```

## 📚 Documentation

- **[Google ADK Docs](https://google.github.io/adk-docs/)** - Official ADK documentation
- **[Gemini API](https://ai.google.dev/gemini-api/docs)** - Gemini model documentation
- **[Image Generation](https://ai.google.dev/gemini-api/docs/imagen)** - Imagen 3 documentation

## 🚀 Advanced Usage

### Adding New Agents

To extend the Interactive system:

```python
# In agent.py

# 1. Import new instruction from prompts.py
from prompts import (
    IMAGE_MANAGER_INSTRUCTION,
    CATALOG_MANAGER_INSTRUCTION,
    TRYON_SPECIALIST_INSTRUCTION,
    INTERACTIVE_COORDINATOR_INSTRUCTION,
    STYLE_ADVISOR_INSTRUCTION  # Add new instruction
)

# 2. Create new agent
style_advisor_agent = LlmAgent(
    name="style_advisor_agent",
    model="gemini-2.5-flash",
    instruction=STYLE_ADVISOR_INSTRUCTION,
    tools=[recommend_style, analyze_preferences],
    before_model_callback=process_reference_images_callback
)

# 3. Add to coordinator's sub_agents
root_agent = LlmAgent(
    name="virtual_tryon_coordinator",
    sub_agents=[
        image_manager_agent,
        catalog_manager_agent,
        tryon_specialist_agent,
        style_advisor_agent  # Add here
    ]
)
```

### Custom Workflows

Modify agent instructions in `prompts.py`:

```python
CUSTOM_WORKFLOW_INSTRUCTION = """
You are the Custom Workflow Agent for the Virtual Try-On system.

Your responsibilities:
1. Step 1: [Your custom step]
2. Step 2: [Your custom step]
3. Step 3: [Your custom step]

Available tools:
- [list your tools]

Important:
- Always validate inputs
- Provide clear feedback
- Handle errors gracefully
"""
```

### Performance Tuning

```python
# Adjust model for speed/quality
LlmAgent(
    model="gemini-2.5-flash",       # ⭐ Best balance (recommended)
    # model="gemini-2.0-flash-exp", # Fast, experimental features
    # model="gemini-2.5-pro",       # Slower, highest quality
)
```

### Custom Rate Limiting

Edit `tools/rate_limiter.py` or set environment variable:

```bash
# In .env
RATE_LIMIT_COOLDOWN=10.0  # 10 seconds cooldown
```

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Test thoroughly**:
   ```bash
   # Test your changes
   adk run agent:runner
   # Upload test image and verify workflow
   ```
5. **Commit**: `git commit -m "Add amazing feature"`
6. **Push**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Guidelines

- Follow existing code style and structure
- Add docstrings to new functions
- Update `prompts.py` for instruction changes
- Test interactive workflow thoroughly
- Update README.md for new features
- Maintain backward compatibility

## 📄 License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## 💬 Support

For issues and questions:

- Check the [troubleshooting section](#-troubleshooting) above
- Review [ADK documentation](https://google.github.io/adk-docs/)
- Open an issue in the repository
- Check existing issues for solutions

## 🎯 Version History

### v3.1.0 (Latest) - Interactive Multi-Agent with AUTO-START
- ✅ **AUTO-START MODE**: New image upload triggers automatic workflow
- ✅ Interactive coordinator with 3 specialist agents
- ✅ User-controlled workflow pacing (except auto-start)
- ✅ Continuous workflow support
- ✅ 10 garments in catalog (expanded from 7)
- ✅ Consolidated prompts in single file (`prompts.py`)
- ✅ Clean logging output
- ✅ Enhanced documentation

### v3.0.0 - LoopAgent Architecture
- ✅ Automatic workflow with LoopAgent
- ✅ Sequential chaining with output_key
- ✅ Fully automated pipeline

### v2.0.0 - SequentialAgent Implementation
- ✅ SequentialAgent with automatic chaining
- ✅ Output key-based data flow
- ✅ Improved tool organization

### v1.7.0 - Sequential Multi-Agent Architecture
- ✅ Added Sequential Multi-Agent system (4 agents)
- ✅ Better tool organization (3+2+5 distribution)
- ✅ Comprehensive documentation

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
- ✅ Single agent architecture
- ✅ Image upload handling
- ✅ Result management

---

**Built with ❤️ using Google ADK and Gemini AI**

**⭐ Recommended:** Use Sequential Multi-Agent architecture for production!
