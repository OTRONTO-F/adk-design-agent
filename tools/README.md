# Tools Directory

This directory contains all the specialized tools for the Virtual Try-On Agent System (v3.1.0).

## 📦 Overview

The tools are organized into 3 main categories:
1. **Virtual Try-On Tools** (tryon_tool.py) - 8 tools
2. **Catalog Management Tools** (catalog_tool.py) - 2 tools  
3. **Rate Limiting Utilities** (rate_limiter.py) - Utility class

**Total: 10 tools across 3 specialized agents**

---

## 📁 File Structure

```
tools/
├── tryon_tool.py         # Virtual try-on operations (8 tools)
├── catalog_tool.py       # Catalog management (2 tools)
├── rate_limiter.py       # Rate limiting utilities
├── __init__.py           # Package initializer
└── README.md             # This file
```

---

## 🛠️ Tool Categories

### 1. Image Manager Agent Tools (3 tools)

**Location**: `tryon_tool.py`

#### `list_reference_images()`
**Purpose**: List all uploaded person images with version tracking

**Returns**:
```
📸 Reference Images (Total: 3)

1. reference_image_v1.png (1.2 MB) - ✅ Valid
2. reference_image_v2.png (1.5 MB) - ✅ Valid  
3. reference_image_v3.png (1.3 MB) - ✅ Valid

💡 Latest: reference_image_v3.png
```

**Used for**: Viewing upload history, tracking versions

---

#### `clear_reference_images()`
**Purpose**: Delete all uploaded person images (requires confirmation)

**Returns**:
```
⚠️ WARNING: This will delete ALL reference images!

Are you sure? Type 'yes' to confirm.
```

**Used for**: Cleanup, starting fresh workflow

---

#### `validate_reference_image(image_data, filename)`
**Purpose**: Validate person image (9:16 aspect ratio preferred)

**Parameters**:
- `image_data`: Binary image data
- `filename`: Image filename

**Returns**:
```
✅ Image aspect ratio: 1080x1920 (ratio: 0.56)
✅ Image saved as reference_image_v1.png
```

**Used for**: Auto-validation during upload

---

### 2. Catalog Manager Agent Tools (2 tools)

**Location**: `catalog_tool.py`

#### `list_catalog_clothes()`
**Purpose**: Display all available garments in catalog

**Returns**:
```
👗 Garment Catalog (Total: 10 items)

📋 Available Garments:

1. 1.jpg (245.3 KB)
2. 2.jpg (312.8 KB)
3. 3.jpg (198.5 KB)
... (10 total)

💡 How to Use: Use select_catalog_cloth with a number or filename
```

**Used for**: Showing available options to user

---

#### `select_catalog_cloth(selection)`
**Purpose**: Select a garment by number or filename

**Parameters**:
- `selection`: Number (1-10) or filename (e.g., "1.jpg")

**Returns**:
```
✅ Selected: 1.jpg (245.3 KB)
📁 Path: catalog/1.jpg

📝 Example: virtual_tryon(person='reference_image_v1.png', garment='catalog/1.jpg')
```

**Used for**: Garment selection before try-on

---

### 3. Try-On Specialist Agent Tools (5 tools)

**Location**: `tryon_tool.py`

#### `virtual_tryon(person_image_filename, garment_image_filename)`
**Purpose**: Execute virtual try-on with selected garment

**Parameters**:
- `person_image_filename`: Person image (e.g., "reference_image_v1.png")
- `garment_image_filename`: Garment image (e.g., "catalog/1.jpg")

**Returns**:
```
✨ Virtual Try-On Complete!

📸 Result saved: tryon_result_v1.png
👤 Person: reference_image_v1.png
👔 Garment: catalog/1.jpg

⏱️ Processing time: 2.5 seconds
```

**Rate Limited**: 5 seconds cooldown between calls

**Used for**: Main try-on operation

---

#### `list_tryon_results()`
**Purpose**: Show all generated try-on results with versions

**Returns**:
```
🎨 Try-On Results (Total: 3)

1. tryon_result_v1.png (2.1 MB)
   👤 Person: reference_image_v1.png
   👔 Garment: catalog/1.jpg
   
2. tryon_result_v2.png (2.3 MB)
   👤 Person: reference_image_v1.png
   👔 Garment: catalog/2.jpg
   
3. tryon_result_v3.png (2.0 MB)
   👤 Person: reference_image_v2.png
   👔 Garment: catalog/3.jpg
```

**Used for**: Viewing history, result management

---

#### `compare_tryon_results(result_filenames)`
**Purpose**: Compare multiple try-on results side-by-side

**Parameters**:
- `result_filenames`: List of result filenames (e.g., `['tryon_result_v1.png', 'tryon_result_v2.png']`)

**Returns**:
```
📊 Comparison View

Version 1: tryon_result_v1.png
👔 Garment: catalog/1.jpg

Version 2: tryon_result_v2.png  
👔 Garment: catalog/2.jpg

💡 Tip: Use get_comparison_summary for AI analysis
```

**Used for**: Side-by-side result comparison

---

#### `get_comparison_summary(result_filenames)`
**Purpose**: Get AI-powered analysis and recommendations for comparisons

**Parameters**:
- `result_filenames`: List of result filenames to analyze

**Returns**:
```
🤖 AI Comparison Summary

✅ Best Match: tryon_result_v2.png
   • Natural fit and draping
   • Great color coordination
   • Most versatile style

📊 Analysis:
   v1: Professional look, formal style
   v2: ⭐ Best overall balance
   v3: Casual and comfortable

💡 Recommendation: Version 2 works best for versatile wear
```

**Used for**: AI-assisted decision making

---

#### `get_rate_limit_status()`
**Purpose**: Check rate limit cooldown status

**Returns**:
```
✅ Rate Limit Status: Ready

⏱️ Cooldown: 5.0 seconds
🔄 Last try-on: 10 seconds ago
✅ Status: Ready for next try-on
```

**Or when on cooldown**:
```
⏳ Rate Limit Status: On Cooldown

⏱️ Cooldown: 5.0 seconds
🔄 Last try-on: 2 seconds ago
⏰ Wait time: 3 more seconds
```

**Used for**: Checking if ready for next try-on

---

## 🔧 Utility Components

### Rate Limiter

**Location**: `rate_limiter.py`

**Purpose**: Prevent excessive API calls with configurable cooldown

**Configuration**:
```python
# In .env file
RATE_LIMIT_COOLDOWN=5.0  # seconds

# Or use default
rate_limiter = get_rate_limiter(5.0)
```

**Features**:
- ✅ Configurable cooldown period
- ✅ Thread-safe implementation
- ✅ Automatic reset after cooldown
- ✅ Status checking

**Usage**:
```python
from tools.rate_limiter import get_rate_limiter

rate_limiter = get_rate_limiter(5.0)

# Check if ready
if rate_limiter.can_proceed():
    result = virtual_tryon(...)
else:
    wait_time = rate_limiter.time_until_ready()
    print(f"⏳ Please wait {wait_time:.1f} seconds")
```

---

## 📊 Tool Distribution by Agent

| Agent | Tools | Purpose |
|-------|-------|---------|
| **Image Manager** | 3 tools | Person image management |
| **Catalog Manager** | 2 tools | Garment selection |
| **Try-On Specialist** | 5 tools | Try-on execution & results |
| **Total** | **10 tools** | Complete workflow |

---

## 🔄 Typical Workflow

```
1. User uploads image
   └─→ validate_reference_image (auto)
   └─→ list_reference_images (show history)

2. Show catalog
   └─→ list_catalog_clothes
   
3. User selects garment
   └─→ select_catalog_cloth
   
4. Check rate limit
   └─→ get_rate_limit_status
   
5. Execute try-on
   └─→ virtual_tryon
   
6. View results
   └─→ list_tryon_results
   
7. Compare (optional)
   └─→ compare_tryon_results
   └─→ get_comparison_summary
```

---

## 🎯 Tool Design Principles

### 1. **Single Responsibility**
Each tool does one thing well:
- ✅ `list_*` tools only list
- ✅ `select_*` tools only select
- ✅ `virtual_tryon` only processes

### 2. **Clear Naming**
Tool names are self-documenting:
- ✅ Verb-first: `list_`, `select_`, `get_`, `compare_`
- ✅ Descriptive: Clear what they do

### 3. **User-Friendly Output**
All tools return formatted, emoji-rich text:
- ✅ Clear headers with emojis
- ✅ Structured information
- ✅ Helpful tips and examples

### 4. **Error Handling**
Comprehensive error messages:
- ✅ Validation errors
- ✅ Rate limit errors
- ✅ File not found errors
- ✅ API errors

### 5. **Versioning**
Automatic version management:
- ✅ `reference_image_v1, v2, v3...`
- ✅ `tryon_result_v1, v2, v3...`
- ✅ No overwrites, all preserved

---

## 🔒 Rate Limiting

**Default**: 5 seconds cooldown between try-ons

**Why?**
- ⚠️ Prevents excessive API calls
- 💰 Cost control
- 🚀 Server load management

**Configuration**:
```bash
# In .env file
RATE_LIMIT_COOLDOWN=5.0  # Change to any value
```

**Bypass** (for development only):
```python
# Not recommended for production
RATE_LIMIT_COOLDOWN=0.1  # Very short cooldown
```

---

## 📈 Tool Performance

| Tool | Avg Time | Rate Limited |
|------|----------|--------------|
| list_reference_images | ~0.1s | No |
| clear_reference_images | ~0.2s | No |
| list_catalog_clothes | ~0.1s | No |
| select_catalog_cloth | ~0.05s | No |
| virtual_tryon | ~2-5s | **Yes** |
| list_tryon_results | ~0.2s | No |
| compare_tryon_results | ~0.3s | No |
| get_comparison_summary | ~1-2s | No |
| get_rate_limit_status | ~0.01s | No |

---

## 🧪 Testing Tools

### Quick Test Commands

```bash
# Test imports
python -c "from tools.tryon_tool import *; print('✅ Tryon tools OK')"
python -c "from tools.catalog_tool import *; print('✅ Catalog tools OK')"
python -c "from tools.rate_limiter import *; print('✅ Rate limiter OK')"

# Test rate limiter
python -c "from tools.rate_limiter import get_rate_limiter; rl = get_rate_limiter(5.0); print(f'Can proceed: {rl.can_proceed()}')"

# Test catalog listing
python -c "from tools.catalog_tool import list_catalog_clothes; print(list_catalog_clothes())"
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Rate limit exceeded"
**Solution**: Wait for cooldown period (default 5s)
```python
status = get_rate_limit_status()
# Shows exact wait time remaining
```

### Issue 2: "Image not found"
**Solution**: Check filename spelling and version number
```python
images = list_reference_images()
# Shows all available images
```

### Issue 3: "Invalid garment selection"
**Solution**: Use number 1-10 or exact filename
```python
catalog = list_catalog_clothes()
# Shows available garments with numbers
```

### Issue 4: "Aspect ratio warning"
**Solution**: Upload portrait images (9:16 preferred)
- ✅ Good: 1080x1920, 720x1280
- ⚠️ Acceptable: Close to 9:16 ratio
- ❌ Poor: Landscape or square

---

## 🔧 Extending Tools

### Adding New Tools

1. **Create tool function** in appropriate file:
```python
# In tryon_tool.py
def new_tool_name(tool_context: ToolContext, param: str) -> str:
    """
    Tool description for AI.
    
    Args:
        param: Parameter description
        
    Returns:
        Formatted result string
    """
    # Implementation
    return "✅ Result"
```

2. **Add to agent** in `agent.py`:
```python
from tools.tryon_tool import new_tool_name

specialist_agent = LlmAgent(
    tools=[
        existing_tool,
        new_tool_name  # Add here
    ]
)
```

3. **Update documentation**:
- Update this README
- Update main README.md
- Add examples

---

## 📝 Tool Development Guidelines

### Best Practices

1. **Always use ToolContext**:
```python
def my_tool(tool_context: ToolContext, ...):
    # Access state
    state = tool_context.state
    
    # Load artifacts
    artifact = await tool_context.load_artifact(filename)
```

2. **Return formatted strings**:
```python
return f"""
✅ Success!

📊 Details:
   • Item 1
   • Item 2

💡 Tip: Helpful suggestion
"""
```

3. **Handle errors gracefully**:
```python
try:
    result = process(...)
    return f"✅ Success: {result}"
except Exception as e:
    logger.error(f"Error: {e}")
    return f"❌ Error occurred: {str(e)}"
```

4. **Use emojis consistently**:
- ✅ Success
- ❌ Error
- ⚠️ Warning
- 💡 Tip
- 📸 Image
- 👔 Garment
- 👤 Person
- ⏱️ Time
- 🎨 Result

5. **Validate inputs**:
```python
if not filename:
    return "❌ Error: Filename required"
    
if not filename.endswith(('.jpg', '.png')):
    return "❌ Error: Only JPG/PNG supported"
```

---

## 📚 Additional Resources

- **Main Documentation**: `../README.md`
- **Agent Configuration**: `../agent.py`
- **Agent Instructions**: `../prompts.py`
- **Google ADK Docs**: https://google.github.io/adk-docs/

---

## 🎯 Version History

### v3.1.0 (Current)
- ✅ 10 tools across 3 agents
- ✅ Rate limiting with cooldown
- ✅ Auto-versioning system
- ✅ Comprehensive error handling
- ✅ User-friendly output

### Future Enhancements
- 🔮 Multi-language support
- 🔮 Progress indicators
- 🔮 Advanced editing tools
- 🔮 Batch processing

---

**Last Updated**: October 31, 2025  
**Version**: 3.1.0  
**Maintainer**: Virtual Try-On Agent Team
