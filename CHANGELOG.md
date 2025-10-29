# Changelog

All notable changes to the Virtual Try-On AI Agent project will be documented in this file.

## [1.1.0] - 2025-10-29

### Added
- ✨ **Image Validation**: Automatic aspect ratio validation (9:16) with warnings
- 🗑️ **Clear Images Tool**: New `clear_reference_images` function to delete uploaded images
- 📊 **Enhanced Logging**: Added file logging with timestamps and better formatting
- 📝 **Environment Template**: Added `.env.example` for easier setup
- 🛡️ **Error Messages**: Improved error messages with actionable suggestions

### Improved
- 🔧 **Code Organization**: Better function documentation and type hints
- 📚 **Prompts**: Updated agent instructions to include new tools
- 🎨 **User Experience**: More informative feedback messages

### Security
- 🔒 **Log Files**: Added `*.log` to `.gitignore` to prevent sensitive data leaks

## [1.0.0] - Initial Release

### Features
- Virtual try-on with Gemini 2.5 Flash
- Reference image management
- Deep think loop for quality refinement
- Artifact versioning system
- Session state management
