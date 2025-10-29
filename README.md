# Virtual Try-On AI Agent

An intelligent AI agent built with Google ADK for virtual clothing try-on. Upload a person image and a garment image, and let AI show you how the outfit would look!

## Features

- **Virtual Try-On**: Upload person and garment images to see realistic try-on results
- **9:16 Aspect Ratio**: Optimized for portrait/mobile viewing
- **Realistic Results**: Powered by Gemini's advanced image generation
- **Session Management**: Track all uploaded images and try-on results
- **Easy Image Management**: Automatic versioning and organization

## Architecture

The agent consists of specialized components:

- **Virtual Try-On Agent**: Handles user interactions and image processing
- **Image Upload Handler**: Automatically saves uploaded images
- **Try-On Generator**: Creates realistic virtual try-on results
- **Artifact Manager**: Organizes all images and results

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

### Development UI (Recommended)

Start the ADK development server:

```bash
adk web
```

Then navigate to `http://127.0.0.1:8000/dev-ui?app=adk-design-agent` in your browser.

## Usage Examples

### Basic Virtual Try-On

```
User: "Hi, I want to try on some clothes"
Agent: "Great! Please upload two images:
        1. A person image (9:16 aspect ratio)
        2. A garment/clothing image (9:16 aspect ratio)"

User: [Uploads person image]
Agent: "✅ Person image received and saved as reference_image_v1.png"

User: [Uploads garment image]  
Agent: "✅ Garment image received and saved as reference_image_v2.png
        
        Ready to proceed with virtual try-on?"

User: "Yes, show me how it looks!"
Agent: [Calls virtual_tryon tool]
       "✅ Virtual Try-On Successful!
        
        Result saved as: tryon_result_v1.png
        The outfit looks great! Would you like to try another garment?"
```

### Try Multiple Garments

```
User: "Let me try another shirt"
User: [Uploads new garment image]
Agent: "✅ New garment saved! Shall I create a new try-on?"
User: "Yes"
Agent: [Creates new try-on with person_image_v1 and new garment]
```

Autonomous quality assurance with multiple iterations:

```
User: "Deep think create a professional product launch announcement"
Agent: [Enters autonomous loop]
       1. Generates initial content
       2. Reviews for quality and adherence
       3. Refines based on feedback
       4. Repeats until professional standard
       5. Presents final result
```

### With Reference Images

Upload inspiration images for style guidance:

```
User: [Uploads reference image] "Create a social media post in this style"
Agent: [Automatically saves reference as reference_image_v1.png]
       [Uses reference for style and composition guidance]
```

## Key Commands

- **Regular Generation**: `"Create a [description]"`
- **Deep Think Mode**: `"Deep think create a [description]"`
- **With Reference**: Upload image + `"Create something in this style"`
- **List Assets**: `"Show me all my assets"`
- **List References**: `"What reference images do I have?"`
- **Load Previous**: `"Show me [asset_name_v2.png]"`

## File Structure

```
social_media_agent/
├── agent.py                 # Main agent configuration
├── deep_think_loop.py       # Deep think mode implementation
├── tools/
│   └── post_creator_tool.py # Image generation and editing tools
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Configuration

The agent can be customized by modifying:

- **Max iterations**: Change `max_iterations=5` in `deep_think_loop.py`
- **Models**: Update model names in agent configurations
- **Instructions**: Modify agent instructions for different behaviors
- **Tools**: Add or remove tools from the agent's toolkit

## Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY environment variable not set"**
   - Ensure your `.env` file contains the API key
   - Verify the key has image generation permissions

2. **"Artifact service is not initialized"**
   - The agent uses `InMemoryArtifactService` by default
   - For production, consider using `GcsArtifactService`

3. **"Deep think mode not activating"**
   - Ensure you include "deep think" in your prompt
   - Check that `sub_agents=[deep_think_loop]` is configured

### Debug Mode

Enable detailed logging:

```bash
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from social_media_agent.agent import runner
# Your agent interaction code here
"
```

## Advanced Usage

### Custom Asset Names

Provide meaningful names for better organization:

```python
# In your prompts, specify asset names
"Create a holiday_promotion poster"
# Results in: holiday_promotion_v1.png, holiday_promotion_v2.png, etc.
```

### Reference Image Management

```python
# List all reference images
"What reference images do I have?"

# Use specific reference
"Create a design using reference_image_v2.png as inspiration"

# Use latest uploaded reference
"Create something based on the latest reference image"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review ADK documentation: https://google.github.io/adk-docs/
- Open an issue in the repository
