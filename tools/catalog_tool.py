"""
Catalog Tool - Garment Catalog Management System
Users can only select garments from the catalog (no uploads allowed)
"""

import logging
from pathlib import Path
from typing import Optional, List
from PIL import Image
import io

logger = logging.getLogger(__name__)

# Catalog directory path
CATALOG_DIR = Path(__file__).parent.parent / "catalog"


def list_catalog_clothes() -> str:
    """
    Display all garments available in the catalog.
    
    Returns:
        List of garments with their numbers
    """
    try:
        # Find all image files in catalog folder
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
            image_files.extend(CATALOG_DIR.glob(ext))
        
        image_files = sorted(image_files, key=lambda x: x.name)
        
        if not image_files:
            return "❌ No garments found in catalog\n\nPlease add garment images to the catalog/ folder"
        
        result = f"👗 **Garment Catalog** (Total: {len(image_files)} items)\n\n"
        result += "📋 **Available Garments**:\n\n"
        
        for i, img_file in enumerate(image_files, 1):
            file_size = img_file.stat().st_size / 1024  # KB
            result += f"{i}. **{img_file.name}** ({file_size:.1f} KB)\n"
        
        result += f"\n💡 **How to Use**: Use `select_catalog_cloth` with a number or filename to select a garment\n"
        result += f"📝 **Example**: select_catalog_cloth(1) or select_catalog_cloth('1.jpg')"
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing catalog clothes: {e}", exc_info=True)
        return f"❌ Error occurred: {str(e)}"


def select_catalog_cloth(identifier: str) -> str:
    """
    Select a garment from the catalog by number or filename.
    
    Args:
        identifier: Number (e.g., "1", "5") or filename (e.g., "1.jpg")
    
    Returns:
        Confirmation message with selected garment
    """
    try:
        # Find all image files in catalog folder
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
            image_files.extend(CATALOG_DIR.glob(ext))
        
        image_files = sorted(image_files, key=lambda x: x.name)
        
        if not image_files:
            return "❌ No garments found in catalog"
        
        selected_file = None
        
        # Try to find by number
        if identifier.isdigit():
            index = int(identifier) - 1
            if 0 <= index < len(image_files):
                selected_file = image_files[index]
        
        # Try to find by filename
        if not selected_file:
            for img_file in image_files:
                if img_file.name.lower() == identifier.lower():
                    selected_file = img_file
                    break
        
        if not selected_file:
            available = ", ".join([f"{i}. {f.name}" for i, f in enumerate(image_files, 1)])
            return f"❌ Garment '{identifier}' not found\n\n📋 Available garments:\n{available}\n\n💡 Use `list_catalog_clothes` to see the full list"
        
        # Check image properties
        try:
            with Image.open(selected_file) as img:
                width, height = img.size
                aspect_ratio = width / height
                file_size = selected_file.stat().st_size / 1024  # KB
        except Exception as e:
            logger.error(f"Error reading image: {e}")
            return f"❌ Cannot read image file '{selected_file.name}': {str(e)}"
        
        result = f"✅ **Garment Selected from Catalog**\n\n"
        result += f"📦 **Details**:\n"
        result += f"- File: {selected_file.name}\n"
        result += f"- File Size: {file_size:.1f} KB\n"
        result += f"- Image Size: {width} x {height} pixels\n"
        result += f"- Aspect Ratio: {aspect_ratio:.2f}:1\n"
        result += f"- Location: {str(selected_file)}\n\n"
        result += f"✨ Ready for Virtual Try-On!\n"
        result += f"💡 When using `virtual_tryon`, specify the garment file as: **catalog/{selected_file.name}**\n"
        result += f"📝 Example: virtual_tryon(person='reference_image_v1.png', garment='catalog/{selected_file.name}')"
        
        return result
        
    except Exception as e:
        logger.error(f"Error selecting catalog cloth: {e}", exc_info=True)
        return f"❌ Error occurred: {str(e)}"
