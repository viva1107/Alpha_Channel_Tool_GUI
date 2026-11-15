from PIL import Image
import sys
import os

def extract_alpha(input_path, output_rgb_path, output_alpha_path):
    """Extract alpha channel and save RGB with full opacity"""
    img = Image.open(input_path)
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Split into channels
    r, g, b, a = img.split()
    
    # Save alpha channel as grayscale image
    a.save(output_alpha_path)
    print(f"Alpha channel saved to: {output_alpha_path}")
    
    # Create new image with RGB and full opacity
    rgb_opaque = Image.merge('RGBA', (r, g, b, Image.new('L', img.size, 255)))
    rgb_opaque.save(output_rgb_path)
    print(f"RGB image (fully opaque) saved to: {output_rgb_path}")

def restore_alpha(edited_rgb_path, alpha_path, output_path):
    """Restore alpha channel to edited RGB image"""
    rgb_img = Image.open(edited_rgb_path)
    alpha_img = Image.open(alpha_path)
    
    # Convert to RGBA if needed
    if rgb_img.mode != 'RGBA':
        rgb_img = rgb_img.convert('RGBA')
    
    # Convert alpha to L mode if needed
    if alpha_img.mode != 'L':
        alpha_img = alpha_img.convert('L')
    
    # Ensure alpha is same size as RGB
    if alpha_img.size != rgb_img.size:
        print("Warning: Alpha and RGB sizes don't match. Resizing alpha to match RGB.")
        alpha_img = alpha_img.resize(rgb_img.size, Image.LANCZOS)
    
    # Split RGB and replace alpha
    r, g, b, _ = rgb_img.split()
    result = Image.merge('RGBA', (r, g, b, alpha_img))
    
    result.save(output_path)
    print(f"Final image with restored alpha saved to: {output_path}")

def main():
    if len(sys.argv) < 2:
        print("PNG Alpha Channel Tool")
        print("\nUsage:")
        print("  Extract alpha:")
        print("    python script.py extract input.png")
        print("    Creates: input_rgb.png and input_alpha.png")
        print("\n  Restore alpha:")
        print("    python script.py restore edited_rgb.png alpha.png output.png")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'extract':
        if len(sys.argv) < 3:
            print("Error: Please provide input file path")
            return
        
        input_path = sys.argv[2]
        base_name = os.path.splitext(input_path)[0]
        output_rgb = f"{base_name}_rgb.png"
        output_alpha = f"{base_name}_alpha.png"
        
        extract_alpha(input_path, output_rgb, output_alpha)
        
    elif command == 'restore':
        if len(sys.argv) < 5:
            print("Error: Please provide RGB file, alpha file, and output path")
            return
        
        rgb_path = sys.argv[2]
        alpha_path = sys.argv[3]
        output_path = sys.argv[4]
        
        restore_alpha(rgb_path, alpha_path, output_path)
        
    else:
        print(f"Unknown command: {command}")
        print("Use 'extract' or 'restore'")

if __name__ == "__main__":
    main()
