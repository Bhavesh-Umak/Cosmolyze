"""
cv_analyzer.py — Cosmolyze Computer Vision Facial & Skin Feature Extractor
Uses OpenCV and NumPy to extract objective clinical skin metrics from face images.
"""

import base64
import io
import numpy as np
from PIL import Image

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def decode_base64_image(image_base64: str) -> np.ndarray:
    """Decode a base64 data URI to an OpenCV BGR numpy array."""
    if ',' in image_base64:
        image_base64 = image_base64.split(',', 1)[1]
    
    image_bytes = base64.b64decode(image_base64)
    pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    rgb_arr = np.array(pil_img)
    # Convert RGB to BGR for OpenCV
    bgr_arr = rgb_arr[:, :, ::-1].copy()
    return bgr_arr


def analyze_skin_features(image_base64: str) -> dict:
    """
    Extracts clinical skin biomarkers using Computer Vision:
    - Erythema Index (Skin Redness detection for acne / rosacea / inflammation)
    - Texture Roughness Index (Laplacian variance for open pores / bumpy texture)
    - Melanin / Hyperpigmentation Contrast
    - Overall Luminosity & Uniformity
    """
    if not OPENCV_AVAILABLE:
        return {
            "cv_enabled": False,
            "erythema_index": 0.35,
            "texture_roughness": "Moderate",
            "skin_luminosity": 72.0,
            "uniformity_score": 80.0,
        }

    try:
        img_bgr = decode_base64_image(image_base64)
        h, w, _ = img_bgr.shape

        # Convert to HSV and LAB color spaces
        img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 1. Erythema / Redness Index (a* channel in LAB color space measures Red-Green)
        l_channel, a_channel, b_channel = cv2.split(img_lab)
        mean_redness = float(np.mean(a_channel))
        # Normalized redness score (typically a* is 128 for neutral, >145 indicates redness/inflammation)
        erythema_score = round(max(0.0, min(100.0, (mean_redness - 120.0) * 2.5)), 2)

        # 2. Texture & Pore Roughness (Laplacian variance)
        laplacian_var = float(cv2.Laplacian(img_gray, cv2.CV_64F).var())
        if laplacian_var > 450:
            texture_label = "Rough / High Pore Prominence"
        elif laplacian_var > 200:
            texture_label = "Moderate / Visible Texture"
        else:
            texture_label = "Smooth / Refined"

        # 3. Luminosity (L* channel in LAB)
        mean_lum = float(np.mean(l_channel)) / 255.0 * 100.0

        # 4. Uniformity (standard deviation of gray values)
        std_gray = float(np.std(img_gray))
        uniformity = round(max(0.0, min(100.0, 100.0 - (std_gray * 0.8))), 2)

        return {
            "cv_enabled": True,
            "resolution": f"{w}x{h}",
            "erythema_index": erythema_score,
            "erythema_status": "Elevated Redness / Irritation" if erythema_score > 35 else "Normal Tone",
            "texture_roughness_score": round(laplacian_var, 2),
            "texture_roughness": texture_label,
            "skin_luminosity": round(mean_lum, 2),
            "uniformity_score": uniformity,
        }
    except Exception as e:
        return {
            "cv_enabled": False,
            "error": str(e),
            "erythema_index": 25.0,
            "texture_roughness": "Normal",
        }
