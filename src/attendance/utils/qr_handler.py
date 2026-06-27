import io
from PIL import Image
import toga

ZBAR_AVAILABLE = None # Lazy check

import qrcode

def generate_qr_image(data: str) -> toga.Image:
    """Generates a QR code and returns it as a Toga Image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert PIL Image to bytes for Toga
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return toga.Image(byte_arr.getvalue())

def decode_qr_from_file(file_path: str) -> str:
    """Decodes a QR code from a file path and returns the data string."""
    try:
        try:
            from pyzbar.pyzbar import decode
        except (ImportError, Exception):
            # macOS path hints for both Intel (/usr/local) and Apple Silicon (/opt/homebrew)
            import ctypes.util
            import os
            paths = ["/opt/homebrew/lib/libzbar.dylib", "/usr/local/lib/libzbar.dylib"]
            found_path = None
            for p in paths:
                if os.path.exists(p):
                    found_path = p
                    break
            
            if found_path:
                def custom_find(name):
                    if name == "zbar": return found_path
                    return None
                ctypes.util.find_library = custom_find
            from pyzbar.pyzbar import decode
    except (ImportError, Exception) as e:
        print(f"[ERROR] pyzbar/zbar not available: {e}")
        return None

    try:
        # Pre-process the image to grayscale to improve recognition reliability
        img = Image.open(file_path).convert('L')
        decoded = decode(img)
        if decoded:
            return decoded[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"[DEBUG] QR Decoding error: {e}")
        return None
