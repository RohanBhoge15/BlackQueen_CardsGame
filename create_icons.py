"""
Generate PNG icons for PWA from SVG
Run this once to create all icon sizes
Requires: pip install pillow cairosvg
"""

import os

# Create icons directory
icons_dir = os.path.join(os.path.dirname(__file__), 'client', 'static', 'icons')
os.makedirs(icons_dir, exist_ok=True)

# SVG icon content
SVG_ICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="80" fill="#1a1a2e"/>
  <text x="256" y="200" font-size="120" text-anchor="middle" fill="#e74c3c">&#9829;</text>
  <text x="256" y="320" font-size="120" text-anchor="middle" fill="#2c3e50">&#9824;</text>
  <text x="256" y="440" font-size="60" text-anchor="middle" fill="white" font-family="Arial" font-weight="bold">TRUMP</text>
</svg>'''

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

def create_icons_with_pillow():
    """Create simple icons using Pillow (no external dependencies)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed. Run: pip install pillow")
        return False

    for size in SIZES:
        # Create image with dark background
        img = Image.new('RGBA', (size, size), (26, 26, 46, 255))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle background
        padding = size // 10
        draw.rounded_rectangle(
            [padding, padding, size - padding, size - padding],
            radius=size // 8,
            fill=(26, 26, 46, 255)
        )

        # Draw card suits
        center_x = size // 2

        # Heart (red)
        heart_y = size // 3
        heart_size = size // 4
        draw.text(
            (center_x, heart_y),
            "♥",
            fill=(231, 76, 60, 255),
            anchor="mm"
        )

        # Spade (dark)
        spade_y = size * 2 // 3
        draw.text(
            (center_x, spade_y),
            "♠",
            fill=(44, 62, 80, 255),
            anchor="mm"
        )

        # Save
        filepath = os.path.join(icons_dir, f'icon-{size}.png')
        img.save(filepath, 'PNG')
        print(f"Created: {filepath}")

    return True

def create_simple_icons():
    """Create very simple colored square icons as fallback"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed. Creating placeholder files.")
        for size in SIZES:
            filepath = os.path.join(icons_dir, f'icon-{size}.png')
            # Create a minimal valid PNG
            with open(filepath, 'wb') as f:
                # Minimal 1x1 red PNG
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
            print(f"Created placeholder: {filepath}")
        return True

    for size in SIZES:
        # Create image
        img = Image.new('RGBA', (size, size), (26, 26, 46, 255))
        draw = ImageDraw.Draw(img)

        # Draw a simple card design
        margin = size // 8

        # White card background
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=size // 10,
            fill=(255, 255, 255, 255)
        )

        # Red heart shape (simplified)
        cx, cy = size // 2, size // 2
        r = size // 5

        # Draw heart using circles and triangle
        draw.ellipse([cx - r, cy - r, cx, cy + r//2], fill=(231, 76, 60, 255))
        draw.ellipse([cx, cy - r, cx + r, cy + r//2], fill=(231, 76, 60, 255))
        draw.polygon([
            (cx - r, cy),
            (cx + r, cy),
            (cx, cy + r + r//2)
        ], fill=(231, 76, 60, 255))

        # Save
        filepath = os.path.join(icons_dir, f'icon-{size}.png')
        img.save(filepath, 'PNG')
        print(f"Created: {filepath}")

    return True

if __name__ == '__main__':
    print("Creating PWA icons...")
    if not create_simple_icons():
        print("\nFailed to create icons.")
    else:
        print("\nIcons created successfully!")
        print(f"Location: {icons_dir}")
